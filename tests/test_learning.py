import copy
import unittest
from datetime import datetime, timezone
from learning import build, penalties, scorer_report, scorer_factor
from daily_opinion import choose
from test_daily_opinion import result, NOW, DAY

AS_OF=datetime(2026,11,1,9,tzinfo=timezone.utc)

def pick(i, won=False):
    return dict(match=dict(id=str(i),league='fra.1',date='2026-10-31T18:00:00Z'),
                published_at='2026-10-31T12:00:00Z',settled_at='2026-10-31T20:00:00Z',
                market='home_or_draw',probability=80,model_version='poisson-10-v1',
                status='won' if won else 'lost',home_score=2 if won else 0,away_score=1)

class FeedbackTests(unittest.TestCase):
    def test_single_defeat_and_small_samples_never_tune(self):
        for n in (1,29):
            report=build([pick(i) for i in range(n)],AS_OF)
            self.assertEqual(report['status'],'collecting')
            self.assertTrue(all(r['penalty']==0 for r in report['rules']))

    def test_repeated_overconfidence_changes_future_ranking_not_probabilities(self):
        report=build([pick(i) for i in range(40)],AS_OF)
        self.assertEqual(report['status'],'active')
        p=penalties(report,'fra.1','poisson-10-v1',{'home_or_draw':80,'over_1_5':79})
        self.assertEqual(p,{'home_or_draw':10,'over_1_5':0})
        r=result(100,{'home_or_draw':80,'over_1_5':79})
        original=copy.deepcopy(r)
        old=choose([r],[],NOW,DAY)
        new=choose([r],[],NOW,DAY,report)
        self.assertEqual(old[0]['market'],'home_or_draw')
        self.assertEqual(new[0]['market'],'over_1_5')
        self.assertEqual(new[0]['probability'],79)
        self.assertEqual(choose([r],old,NOW,DAY,report),old)
        self.assertEqual(r,original)

    def test_model_confidence_and_markets_are_separate(self):
        report=build([pick(i) for i in range(40)],AS_OF)
        self.assertEqual(penalties(report,'fra.1','different',{'home_or_draw':80})['home_or_draw'],0)
        self.assertEqual(penalties(report,'fra.1','poisson-10-v1',{'home_or_draw':70})['home_or_draw'],0)

    def test_success_does_not_inflate_probabilities(self):
        report=build([pick(i,True) for i in range(40)],AS_OF)
        self.assertTrue(all(r['penalty']==0 for r in report['rules']))

    def test_unverified_late_future_void_and_inconsistent_outcomes_excluded(self):
        rows=[]
        for field,value in [('published_at','2026-10-31T18:00:00Z'),('settled_at',None),
                            ('settled_at','2026-11-02T18:00:00Z'),('home_score',True),
                            ('status','void'),('probability',float('nan')),('home_score',4)]:
            row=pick(len(rows));row[field]=value;rows.append(row)
        report=build(rows,AS_OF)
        self.assertEqual(report['eligible'],0)
        self.assertEqual(report['rules'],[])

    def test_duplicates_do_not_trigger_training_and_window_expires(self):
        report=build([pick(1)]*50,AS_OF)
        self.assertEqual(report['eligible'],1)
        self.assertEqual(report['status'],'collecting')
        self.assertEqual(build([pick(1)],datetime(2027,6,1,tzinfo=timezone.utc))['eligible'],0)

    def test_scorer_adjustment_requires_comparable_verified_player_results(self):
        rows=[]
        for i in range(80):
            p=pick(i);won=i>=40
            p.update(player=dict(id=str(i),competition_category='men'),model_version='scorer-v1',
                     availability='reported_starter' if won else 'unconfirmed',
                     status='won' if won else 'lost',goals_scored=1 if won else 0)
            rows.append(p)
        report=scorer_report(rows,AS_OF)
        factor=scorer_factor({'scorer':report},rows[0])
        self.assertGreaterEqual(factor,.8)
        self.assertLess(factor,1)
        self.assertEqual(scorer_factor({'scorer':report},dict(rows[0],model_version='different')),1)
        self.assertEqual(scorer_report([rows[0]]*60,AS_OF)['rules'][0]['count'],1)
        rows[0]['published_at']=rows[0]['match']['date']
        self.assertEqual(scorer_report([rows[0]],AS_OF)['eligible'],0)

class StoredFeedbackTests(unittest.TestCase):
    def setUp(self):
        import tempfile
        from flask import Flask
        from accounts import database, SCHEMA
        self.temp=tempfile.NamedTemporaryFile()
        self.app=Flask(__name__);self.app.testing=True
        self.app.config['ACCOUNT_DATABASE_URL']='sqlite:///'+self.temp.name
        self.context=self.app.app_context();self.context.push()
        with database() as db:
            for sql in SCHEMA:db.execute(sql)
            for uid in ('owner','other'):
                db.execute('INSERT INTO account_users VALUES(?,?,?,?,?,?,?,?)',(uid,uid+'@example.com','User','pw','r',1,0,0))
    def tearDown(self):
        self.context.pop();self.temp.close()
    def test_training_reads_only_own_frozen_analysis_and_observed_results(self):
        import json
        from accounts import database
        from learning import current
        dates=[int(datetime.fromisoformat(d.replace('Z','+00:00')).timestamp()) for d in ('2026-10-31T12:00:00Z','2026-10-31T18:00:00Z','2026-10-31T20:00:00Z')]
        published,kickoff,settled=dates
        result=dict(event_id='1',league='fra.1',home_id='1',away_id='2',model='personal-v1',prediction=dict(markets=dict(home_or_draw=80)))
        with database() as db:
            for uid in ('owner','other'):
                db.execute('INSERT INTO account_analyses VALUES(?,?,?,?,?,?,?,?)',(uid,uid,uid,'A-B','complete',published-1,published-1,json.dumps(result)))
                db.execute('INSERT INTO account_predictions VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)',(uid,'1','fra.1','home_or_draw',80,'A-B','1','2',kickoff,published,'lost',0,1,settled))
        self.assertEqual(current(AS_OF,user_id='owner')['eligible'],1)
        self.assertEqual(current(AS_OF)['eligible'],0)
        with database() as db:db.execute("UPDATE account_analyses SET created_at=? WHERE user_id='owner'",(kickoff+1,))
        self.assertEqual(current(AS_OF,user_id='owner')['eligible'],0)
