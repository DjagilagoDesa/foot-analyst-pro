import copy
import unittest
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import Mock
from champions_context import collect
from analysis_report import report
import app

NOW = datetime(2026, 11, 2, 12, tzinfo=timezone.utc)


def game(i, days, home='1', away='3'):
    return dict(id=str(i), date=(NOW-timedelta(days=days)).isoformat(), home_id=home, away_id=away,
                home='Club '+home, away='Club '+away, home_goals=2, away_goals=1)


class ContextTests(unittest.TestCase):
    def source(self, fail=False, mismatch=False):
        def fetch(url, params=None, **kwargs):
            if url.endswith('/summary'):
                return {'header':{'competitions':[{'date':(NOW+timedelta(days=2)).isoformat(),
                    'status':{'type':{'state':'pre','name':'STATUS_SCHEDULED'}},
                    'competitors':[{'homeAway':'home','team':{'id':'9' if mismatch else '1'}},
                                   {'homeAway':'away','team':{'id':'2'}}]}]}}
            league = url.split('/')[-2]
            if fail and league == 'eng.1': raise TimeoutError()
            ids = ['1'] if league == 'fra.1' else ['2'] if league == 'esp.1' else []
            return {'sports':[{'leagues':[{'teams':[{'team':{'id':x}} for x in ids]}]}]}
        def history(league, team, **kwargs):
            if league == 'uefa.champions':
                return [game('e'+team, 1, home=team)], []
            return [game(i, i+2, home=team) for i in range(6)] + [game('future',-1,home=team),game('old',181,home=team)], []
        return SimpleNamespace(fetch=Mock(side_effect=fetch), history=Mock(side_effect=history), ESPN='https://source', summary=app.summary)

    def test_verified_fixture_form_and_latest_european_rest(self):
        source = self.source()
        context = collect(source,'1','2','123',now=NOW)
        self.assertTrue(context['fixture_verified'])
        self.assertEqual(context['teams']['1']['league'],'fra.1')
        self.assertEqual(context['teams']['1']['sample'],5)
        self.assertEqual(context['teams']['1']['rest_hours'],72)
        self.assertTrue(any(call.kwargs.get('regulation_only') is False for call in source.history.call_args_list))
        self.assertEqual(context['teams']['2']['record']['wins'],5)

    def test_wrong_fixture_and_partial_rosters_never_invent_rest(self):
        context=collect(self.source(fail=True,mismatch=True),'1','2','123',now=NOW)
        self.assertFalse(context['fixture_verified'])
        self.assertIsNone(context['teams']['1']['rest_hours'])
        self.assertEqual(context['failed_leagues'],['eng.1'])

    def test_missing_league_and_source_failure_are_explicit(self):
        source=self.source();source.fetch=Mock(return_value={})
        context=collect(source,'1','2',now=NOW)
        self.assertEqual(context['teams']['1']['status'],'unavailable')
        source=self.source();source.history=Mock(side_effect=TimeoutError())
        context=collect(source,'1','2',now=NOW)
        self.assertEqual(context['teams']['1']['reason'],'source_error')

    def test_report_keeps_probabilities_and_separates_domestic_from_europe(self):
        context=collect(self.source(),'1','2','123',now=NOW)
        team=dict(matches=10,wins=6,draws=2,losses=2,goals_for_avg=1.5,goals_against_avg=1)
        data=dict(status='ok',league='uefa.champions',home_id='1',away_id='2',home_name='Paris',away_name='Madrid',
                  home=team,away=team,domestic_context=context,
                  prediction=dict(expected_goals={'home':1.5,'away':1.2},markets={'home':45,'draw':30,'away':25}))
        before=copy.deepcopy(data)
        result=report(data)
        section=next(s for s in result['sections'] if s['title'].startswith('Forme nationale'))
        self.assertIn('72 heures',section['text'])
        self.assertIn('15 point(s) sur 15',section['text'])
        self.assertIn('ne modifient pas les probabilités',section['text'])
        self.assertEqual(data,before)

if __name__ == '__main__': unittest.main()
