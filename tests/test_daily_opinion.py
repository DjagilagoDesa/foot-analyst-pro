import copy
import json
import os
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import Mock, patch

from flask import Flask
from accounts import database
from daily_opinion import DailyOpinion, choose, init_app, today, upcoming


NOW = datetime(2026, 11, 1, 9, tzinfo=timezone.utc)
DAY = '2026-11-01'


def result(i, markets=None):
    stats = dict(matches=10, wins=6, draws=2, losses=2, goals_for_avg=2, goals_against_avg=1)
    return dict(match=dict(id=str(i), date=(NOW + timedelta(hours=3)).isoformat(), league='fra.1',
                          state='pre', completed=False, status_name='STATUS_SCHEDULED',
                          home=dict(id=str(i * 2), name='Club '+str(i), badge=''),
                          away=dict(id=str(i * 2 + 1), name='Adversaire '+str(i), badge='')),
                home=stats, away=stats, prediction=dict(markets=markets or {'home_or_draw': 80, 'home': 65, 'away': 20},
                expected_goals=dict(home=2, away=1)))


def results():
    return ([result(i) for i in range(1, 4)]
            + [result(i, {'home': 68, 'away': 20}) for i in (4, 5)]
            + [result(6, {'home': 60, 'away': 35})])


class SelectionTests(unittest.TestCase):
    def test_six_unique_games_and_teams_in_three_bands(self):
        picks = choose(results(), [], NOW, DAY)
        self.assertEqual([sum(p['group'] == g for p in picks) for g in ('prudent', 'challenge', 'surprise')], [3, 2, 1])
        self.assertEqual(len({p['match']['id'] for p in picks}), 6)
        self.assertEqual(len({p['match'][s]['id'] for p in picks for s in ('home', 'away')}), 12)
        surprise = next(p for p in picks if p['group'] == 'surprise')
        self.assertEqual(surprise['market'], 'away')
        self.assertEqual(surprise['probability'], 35)

    def test_no_fabrication_or_relaxation_when_insufficient(self):
        self.assertEqual(choose([result(1, {'home': 98, 'away': 1})], [], NOW, DAY), [])
        picks = choose([result(1)], [], NOW, DAY)
        self.assertEqual(len(picks), 1)

    def test_no_live_cancelled_past_or_wrong_day_predictions(self):
        for changes in [dict(state='in'), dict(completed=True), dict(date=NOW.isoformat()),
                        dict(date=(NOW + timedelta(days=1)).isoformat()), dict(status_name='STATUS_POSTPONED')]:
            r = result(1)
            r['match'].update(changes)
            self.assertFalse(upcoming(r['match'], NOW, DAY))
            self.assertEqual(choose([r], [], NOW, DAY), [])

    def test_published_choices_are_immutable_and_never_retroactively_replaced(self):
        picks = choose(results(), [], NOW, DAY)
        original = copy.deepcopy(picks)
        changed = results()
        changed[0]['prediction']['markets']['home_or_draw'] = 95
        after = choose(changed, picks, NOW + timedelta(hours=8), DAY)
        self.assertEqual(after, original)
        self.assertEqual(picks, original)

    def test_paris_midnight_and_dst(self):
        self.assertEqual(today(datetime(2026, 11, 1, 23, 5, tzinfo=timezone.utc)), '2026-11-02')
        self.assertEqual(today(datetime(2026, 7, 1, 22, 5, tzinfo=timezone.utc)), '2026-07-02')


class PersistenceTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.app = Flask(__name__)
        self.app.config.update(TESTING=True, ACCOUNT_DATABASE_URL=os.environ.get('TEST_DATABASE_URL', 'sqlite:///'+self.temp.name+'/daily.sqlite'))
        self.context = self.app.app_context()
        self.context.push()
        self.server = SimpleNamespace(LEAGUES=['fra.1'], ESPN='https://example.invalid', fetch=Mock())
        init_app(self.app, self.server)
        self.service = self.app.extensions['daily_opinion']
        self.service.read(DAY)
        with database() as db:
            db.execute('DELETE FROM daily_opinion_boards')

    def tearDown(self):
        self.context.pop()
        self.temp.cleanup()

    def refresh(self):
        with patch.object(self.service, 'fixtures', return_value=([r['match'] for r in results()], 0)), \
             patch.object(self.service, 'analyze', side_effect=lambda m: next(r for r in results() if r['match']['id'] == m['id'])), \
             patch.object(self.service, 'settle'), patch.object(self.service, 'settle_previous'):
            self.service.refresh(NOW)

    def test_persistence_across_workers_and_no_quota_consumption(self):
        self.refresh()
        other = DailyOpinion(self.app, self.server)
        board, checked = other.read(DAY)
        self.assertEqual(len(board['picks']), 6)
        self.assertEqual(checked, int(NOW.timestamp()))
        with patch.object(other, 'fixtures') as fixtures:
            other.refresh(NOW)
        fixtures.assert_not_called()

    def test_daily_reset_does_not_reuse_previous_day(self):
        self.refresh()
        new, _ = self.service.read('2026-11-02')
        self.assertEqual(new, {})

    def test_database_lease_prevents_duplicate_generation(self):
        with database() as db:
            db.execute('INSERT INTO daily_opinion_boards(day,payload,lease_until) VALUES(?,?,?)', (DAY, '{}', int(NOW.timestamp()) + 300))
        with patch.object(self.service, 'fixtures') as fixtures:
            self.service.refresh(NOW)
        fixtures.assert_not_called()

    def test_source_failure_preserves_existing_board(self):
        self.refresh()
        before = self.service.read(DAY)
        with patch.object(self.service, 'fixtures', side_effect=RuntimeError('offline')):
            with self.assertRaises(RuntimeError):
                self.service.refresh(NOW + timedelta(hours=1))
        self.assertEqual(self.service.read(DAY), before)

    def test_endpoint_returns_no_previous_day_or_user_information(self):
        self.refresh()
        with patch('daily_opinion.today', return_value=DAY):
            response = self.app.test_client().get('/api/daily-opinion')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json['status'], 'ready')
        self.assertEqual([len(g['picks']) for g in response.json['groups']], [3, 2, 1])
        self.assertNotIn('user', response.json)
        self.assertEqual(response.headers['Cache-Control'], 'no-store')

    def test_final_score_and_extra_time_handling(self):
        board = dict(picks=choose([result(1)], [], NOW, DAY))
        p = board['picks'][0]
        info = dict(home_id=p['match']['home']['id'], away_id=p['match']['away']['id'],
                    name='STATUS_FULL_TIME', completed=True, state='post', period=2,
                    home=dict(score='2'), away=dict(score='1'))
        with patch('daily_opinion.fixture_info', return_value=info):
            self.service.settle(board)
        self.assertEqual(p['status'], 'won')
        p['status'] = 'pending'
        info['period'] = 4
        with patch('daily_opinion.fixture_info', return_value=info):
            self.service.settle(board)
        self.assertEqual(p['status'], 'void')

    def test_french_day_queries_both_utc_dates(self):
        self.server._fixture = lambda event, league: event
        self.server.fetch.return_value = {'events': []}
        self.service.fixtures(DAY)
        dates = {call.args[1]['dates'] for call in self.server.fetch.call_args_list}
        self.assertEqual(dates, {'20261031', '20261101'})

    def test_public_performance_excludes_pending_and_void(self):
        self.refresh()
        board, _ = self.service.read(DAY)
        for pick, status in zip(board['picks'], ['won', 'lost', 'pending', 'void', 'won', 'pending']):
            pick['status'] = status
        with database() as db:
            db.execute('UPDATE daily_opinion_boards SET payload=? WHERE day=?', (json.dumps(board), DAY))
        performance = self.service.performance(DAY)
        self.assertEqual(performance['won'], 2)
        self.assertEqual(performance['lost'], 1)
        self.assertEqual(performance['success_pct'], 66.7)
