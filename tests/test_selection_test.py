import copy
import unittest
from datetime import datetime,timedelta,timezone
from selection_test import decision,report,VERSION

NOW=datetime(2026,11,3,10,tzinfo=timezone.utc)

def sample(market='home_or_draw'):
    histories={side:[dict(id=side+str(i),date=(NOW-timedelta(days=3*i+1)).isoformat(),
                         home_id=str(n),away_id='99',home_goals=2,away_goals=1) for i in range(10)]
               for side,n in [('home',1),('away',2)]}
    return dict(match=dict(id='10',league='fra.1',date=(NOW+timedelta(hours=4)).isoformat(),home=dict(id='1'),away=dict(id='2')),
                market=market,probability=78,status='pending',published_at=NOW.isoformat(),
                expected_goals=dict(home=1.5,away=1.0),
                selection_basis=dict(captured_at=NOW.isoformat(),source_errors=dict(home=[],away=[]),history=histories))

class SelectionTest(unittest.TestCase):
    def test_clean_inputs_and_no_mutation(self):
        p=sample(); before=copy.deepcopy(p)
        self.assertTrue(decision(p,NOW)['accepted'])
        self.assertEqual(p,before)

    def test_balance_applies_to_directional_markets_only(self):
        for market in ['home','away','home_or_draw','away_or_draw','over_1_5','btts']:
            p=sample(market);p['expected_goals']=dict(home=1.5,away=1.4)
            self.assertEqual(decision(p,NOW)['accepted'],market in ['over_1_5','btts'])
        p=sample();p['expected_goals']=dict(home=1.35,away=1.0)
        self.assertTrue(decision(p,NOW)['accepted'])

    def test_incomplete_old_stale_duplicate_and_foreign_inputs(self):
        for mode in ['missing','partial','short','old','stale','duplicate','foreign','negative','future','late']:
            p=sample();b=p['selection_basis'];g=b['history']['home']
            if mode=='missing':p.pop('selection_basis')
            if mode=='partial':b['source_errors']['home']=['timeout']
            if mode=='short':g.pop()
            if mode=='old':g[0]['date']=(NOW-timedelta(days=181)).isoformat()
            if mode=='stale':
                for i,game in enumerate(g):game['date']=(NOW-timedelta(days=46+i)).isoformat()
            if mode=='duplicate':g[1]['id']=g[0]['id']
            if mode=='foreign':g[0]['home_id']='88'
            if mode=='negative':g[0]['home_goals']=-1
            if mode=='future':g[0]['date']=(NOW+timedelta(days=1)).isoformat()
            if mode=='late':p['match']['date']=NOW.isoformat()
            self.assertFalse(decision(p,NOW)['accepted'],mode)

    def test_same_cohort_separate_denominators_no_retroactive_decisions(self):
        kept=sample();kept['selection_test']=decision(kept,NOW);kept['status']='won'
        rejected=sample();rejected['match']['id']='11';rejected['expected_goals']=dict(home=1.1,away=1)
        rejected['selection_test']=decision(rejected,NOW);rejected['status']='lost'
        old=sample();old['match']['id']='12';old['status']='won'
        now=NOW+timedelta(days=1)
        result=report([kept,rejected,old,copy.deepcopy(kept)],now)
        self.assertEqual((result['registered'],result['retained'],result['rejected']),(2,1,1))
        self.assertEqual(result['baseline']['overall']['success_pct'],50)
        self.assertEqual(result['candidate']['overall']['success_pct'],100)
        self.assertEqual(result['retained_pct'],50)
        self.assertEqual(result['candidate']['overall']['evidence'],'insufficient')
        self.assertEqual(result['excluded'],dict(not_recorded_prospectively=1,duplicate=1))

    def test_fixed_window_future_decision_and_empty_start(self):
        p=sample();p['selection_test']=decision(p,NOW)
        self.assertEqual(report([p],NOW-timedelta(seconds=1))['registered'],0)
        self.assertEqual(report([],NOW)['status'],'waiting_for_new_choices')
        late=copy.deepcopy(p);late['match']['id']='20'
        late['selection_test']['recorded_at']=(NOW+timedelta(days=91)).isoformat()
        late['match']['date']=(NOW+timedelta(days=92)).isoformat()
        r=report([p,late],NOW+timedelta(days=93))
        self.assertEqual(r['registered'],1)
        self.assertEqual(r['status'],'window_complete')
        self.assertEqual(r['baseline']['overall']['count'],0)
        self.assertEqual(r['policy'],'prospective_subset_only_no_automatic_activation')

class SelectionEndpoint(unittest.TestCase):
    def test_read_only_report_keeps_official_picks_unchanged(self):
        import json,tempfile
        from flask import Flask
        from accounts import database,DAILY_OPINION_SCHEMA
        from daily_opinion import init_app,today
        with tempfile.TemporaryDirectory() as folder:
            app=Flask(__name__)
            app.config.update(TESTING=True,ACCOUNT_DATABASE_URL='sqlite:///'+folder+'/test.sqlite')
            init_app(app,None)
            p=sample();p['selection_test']=decision(p,NOW)
            payload=json.dumps({'picks':[p]})
            with app.app_context(),database() as db:
                db.execute(DAILY_OPINION_SCHEMA)
                db.execute('INSERT INTO daily_opinion_boards(day,payload) VALUES(?,?)',(today(),payload))
            response=app.test_client().get('/api/daily-opinion/selection-test')
            self.assertEqual(response.status_code,200)
            self.assertEqual(response.headers['Cache-Control'],'no-store')
            self.assertEqual(response.json['experiment'],VERSION)
            with app.app_context(),database() as db:
                self.assertEqual(db.execute('SELECT payload FROM daily_opinion_boards').fetchone()['payload'],payload)

if __name__=='__main__':unittest.main()
