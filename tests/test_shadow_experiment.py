import copy
import json
import os
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import Mock, patch
from flask import Flask
import app as server
from accounts import database
from opponent_benchmark import State
from shadow_experiment import ShadowExperiment, predict_pair, replay, init_app, VERSION

NOW=datetime(2026,11,3,9,tzinfo=timezone.utc)


def sample():
    rows=[]
    for n in range(10):
        date=NOW-timedelta(days=3*n+2)
        rows.append(dict(id=str(n),league='fra.1',home_id='1',away_id='2',home='Paris',away='Lyon',
                         date=date.isoformat(),available_at=(date+timedelta(hours=3)).isoformat(),
                         home_goals=2,away_goals=1,regulation_only=True))
    return rows


def fixture():
    return dict(id='999',league='fra.1',date=(NOW+timedelta(hours=3)).isoformat(),state='pre',completed=False,
                home=dict(id='1',name='Paris'),away=dict(id='2',name='Lyon'))


def info(match=None):
    m=match or fixture()
    return dict(home_id='1',away_id='2',date=datetime.fromisoformat(m['date']),state='pre',completed=False,
                name='STATUS_SCHEDULED',period=0,home=dict(score='2'),away=dict(score='1'))


class ShadowTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.app=Flask(__name__)
        self.app.config.update(TESTING=True,ACCOUNT_DATABASE_URL=os.environ.get('TEST_DATABASE_URL','sqlite:///'+self.temp.name+'/shadow.sqlite'))
        self.context=self.app.app_context();self.context.push()
        self.api=SimpleNamespace(history=Mock(return_value=(sample(),[])),summary=server.summary,
                                 probabilities=server.probabilities,ESPN='https://example.invalid',fetch=Mock())
        self.state=replay(sample(),NOW)
        init_app(self.app,self.api)
        self.service=ShadowExperiment(self.app,self.api,clock=lambda:NOW);self.service.initialize()
        with database() as db:
            for table in ('shadow_pairs','shadow_results','shadow_attempts','shadow_control'):db.execute('DELETE FROM '+table)
        self.service.initialize()

    def tearDown(self):
        self.context.pop();self.temp.cleanup()

    def pair(self):
        pair,reason=predict_pair(self.api,self.state,fixture())
        self.assertIsNone(reason)
        return pair

    def record(self,pair=None):
        with patch('shadow_experiment.fixture_info',return_value=info()):
            return self.service.record(pair or self.pair())

    def test_baseline_is_daily_engine_on_exact_same_history_and_private_scope(self):
        pair=self.pair()
        self.assertEqual(pair['baseline'],server.probabilities(server.summary(sample(),'1'),server.summary(sample(),'2')))
        self.assertEqual(len(pair['histories']['home']),10)
        self.assertEqual(self.record(pair),'recorded')
        report=self.app.test_client().get('/api/shadow-experiment')
        self.assertEqual(report.status_code,200)
        self.assertEqual(report.json['registered'],1)
        self.assertEqual(report.json['comparison']['test']['btts']['count'],0)
        self.assertNotIn('histories',report.json)
        self.assertNotIn('candidate',report.json)
        self.assertEqual(report.headers['Cache-Control'],'no-store')

    def test_evaluation_window_fixed_at_first_snapshot(self):
        self.record();r=self.service.report()
        self.assertEqual(r['evaluation_window']['start'],NOW.isoformat())
        self.assertEqual(r['evaluation_window']['end'],(NOW+timedelta(days=90)).isoformat())
        self.assertEqual(r['evaluation_window']['days'],90)
        self.service.clock=lambda:NOW+timedelta(days=91)
        self.assertEqual(self.service.report()['evaluation_window'],r['evaluation_window'])
        late=self.pair();late['match']['id']='1001';late['match']['date']=(NOW+timedelta(days=91,hours=3)).isoformat()
        with database() as db:
            db.execute("UPDATE shadow_pairs SET status='complete',home_score=2,away_score=1")
            db.execute('''INSERT INTO shadow_pairs(experiment,league,event_id,day,recorded_at,starts_at,payload,status,home_score,away_score)
                VALUES(?,?,?,?,?,?,?,?,?,?)''',(VERSION,'fra.1','1001','2027-02-02',self.service.clock().isoformat(),
                late['match']['date'],json.dumps(late),'complete',2,1))
        result=self.service.report()
        self.assertEqual(result['registered'],2)
        self.assertEqual(result['comparison']['test']['btts']['count'],1)

    def test_first_snapshot_immutable_across_workers(self):
        pair=self.pair();self.record(pair)
        changed=copy.deepcopy(pair);changed['candidate']['markets']['btts']=99
        self.assertEqual(self.record(changed),'already_recorded')
        with database() as db:
            row=db.execute('SELECT payload FROM shadow_pairs WHERE event_id=?',('999',)).fetchone()
        self.assertEqual(json.loads(row['payload']),pair)

    def test_clock_rechecked_after_network_and_while_holding_transaction(self):
        pair=self.pair();self.service.clock=lambda:NOW+timedelta(hours=3)
        self.assertEqual(self.record(pair),'not_prematch')
        self.service.clock=lambda:NOW+timedelta(hours=3,seconds=-30)
        self.assertEqual(self.record(pair),'too_late')
        self.assertEqual(self.service.report()['registered'],0)

    def test_changed_teams_kickoff_and_live_source_rejected(self):
        for changes,reason in [(dict(home_id='3'),'teams_mismatch'),
                               (dict(date=NOW+timedelta(hours=4)),'kickoff_changed'),
                               (dict(state='in'),'not_prematch'),
                               (dict(name='STATUS_POSTPONED'),'not_prematch')]:
            source=info();source.update(changes)
            with patch('shadow_experiment.fixture_info',return_value=source):
                self.assertEqual(self.service.record(self.pair()),reason)

    def test_partial_unmatched_and_disconnected_inputs_not_filled(self):
        self.api.history.return_value=(sample(),['timeout'])
        self.assertEqual(predict_pair(self.api,self.state,fixture())[1],'partial_history')
        self.api.history.return_value=(sample()[:3],[])
        self.assertEqual(predict_pair(self.api,self.state,fixture())[1],'insufficient_history')
        altered=sample();altered[0]['home_goals']=9;self.api.history.return_value=(altered,[])
        self.assertEqual(predict_pair(self.api,self.state,fixture())[1],'unmatched_history')
        self.api.history.return_value=(sample(),[])
        self.assertEqual(predict_pair(self.api,State(),fixture())[1],'disconnected_ratings')

    def test_result_not_available_cannot_enter_kickoff_ratings(self):
        delayed=sample()
        for row in delayed:row['available_at']=(NOW+timedelta(days=1)).isoformat()
        self.assertFalse(replay(delayed,NOW).histories)
        earlier=replay(sample(),NOW)
        future=sample();future[0]['home_goals']=10
        future[0]['available_at']=(NOW+timedelta(days=1)).isoformat()
        # The unobserved result never enters the histories used for prediction.
        self.assertEqual(len(replay(future,NOW).histories['1']),9)
        self.assertEqual(len(earlier.histories['1']),10)

    def test_settlement_only_after_verified_regulation_result_and_no_rewrite(self):
        pair=self.pair();self.record(pair);self.service.clock=lambda:NOW+timedelta(hours=5)
        source=info();source.update(state='post',completed=True,period=2)
        with patch('shadow_experiment.fixture_info',return_value=source):self.service.settle()
        report=self.service.report()
        self.assertEqual(report['counts'],{'complete':1})
        self.assertEqual(report['comparison']['test']['btts']['count'],1)
        self.assertEqual(report['comparison']['test']['btts']['observed_pct'],100)
        source['home']['score']='0'
        with patch('shadow_experiment.fixture_info',return_value=source):self.service.settle()
        with database() as db:
            row=db.execute('SELECT payload,home_score FROM shadow_pairs').fetchone()
        self.assertEqual(json.loads(row['payload']),pair)
        self.assertEqual(row['home_score'],2)

    def test_extra_time_unknown_period_and_changed_date_are_void(self):
        for changes in (dict(period=4),dict(period=None),dict(date=NOW+timedelta(hours=4))):
            with database() as db:db.execute('DELETE FROM shadow_pairs')
            self.service.clock=lambda:NOW;self.record();self.service.clock=lambda:NOW+timedelta(hours=5)
            source=info();source.update(state='post',completed=True,period=2);source.update(changes)
            with patch('shadow_experiment.fixture_info',return_value=source):self.service.settle()
            self.assertEqual(self.service.report()['counts'],{'void':1})
            self.assertEqual(self.service.report()['comparison']['test']['btts']['count'],0)

    def test_expired_lease_refuses_prediction(self):
        pair=self.pair()
        with patch('shadow_experiment.fixture_info',return_value=info()):
            self.assertEqual(self.service.record(pair,token='old-worker'),'expired_lease')
        self.assertEqual(self.service.report()['registered'],0)

    def test_source_outage_keeps_pair_pending_and_recoverable(self):
        self.record();self.service.clock=lambda:NOW+timedelta(hours=5)
        with patch('shadow_experiment.fixture_info',side_effect=ValueError('offline')):
            self.service.settle()
        self.assertEqual(self.service.report()['counts'],{'pending':1})
        source=info();source.update(state='post',completed=True,period=2)
        with patch('shadow_experiment.fixture_info',return_value=source):self.service.settle()
        self.assertEqual(self.service.report()['counts'],{'complete':1})

    def test_attempt_rotation_and_persistent_coverage(self):
        other=fixture();other['id']='1000'
        with patch.object(self.service,'observe',return_value=([fixture(),other],0)), \
             patch.object(self.service,'state',return_value=self.state), \
             patch('shadow_experiment.predict_pair',return_value=(None,'partial_history')):
            self.service.refresh()
        report=self.service.report()
        self.assertEqual(report['registered'],0)
        self.assertEqual(report['coverage'],[dict(reason='partial_history',fixtures=2,attempts=2)])
        self.assertNotIn('payload',report)

    def test_live_observations_keep_first_observed_at_across_restarts(self):
        event={'competitions':[{'status':{'period':2}}]}
        self.api._fixture=Mock(return_value=None)
        row=sample()[0]
        self.api.parse_events=Mock(return_value=[row])
        self.api.fetch.return_value={'events':[event]}
        self.service.observe('2026-11-03')
        self.service.clock=lambda:NOW+timedelta(hours=2)
        self.service.observe('2026-11-03')
        with database() as db:
            saved=db.execute('SELECT available_at,payload FROM shadow_results').fetchall()
        self.assertEqual(len(saved),1)
        self.assertEqual(saved[0]['available_at'],NOW.isoformat())
        self.assertFalse(json.loads(saved[0]['payload'])['availability_assumed'])

    def test_lease_and_failure_do_not_touch_official_or_personal_tables(self):
        with database() as db:
            db.execute('UPDATE shadow_control SET lease_until=?',(int(NOW.timestamp())+300,))
        with patch.object(self.service,'observe') as observe:self.service.refresh()
        observe.assert_not_called()
        with database() as db:db.execute('UPDATE shadow_control SET lease_until=0')
        with patch.object(self.service,'observe',side_effect=RuntimeError('offline')):self.service.refresh()
        report=self.service.report()
        self.assertEqual(report['last_cycle']['error'],'RuntimeError')
        self.assertEqual(report['registered'],0)

if __name__=='__main__':unittest.main()
