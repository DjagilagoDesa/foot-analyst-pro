import copy
import unittest
from datetime import datetime,timedelta,timezone
from types import SimpleNamespace
from venue_test import build,freeze,report,VERSION
from app import summary,probabilities

NOW=datetime(2026,11,3,10,tzinfo=timezone.utc)
SERVER=SimpleNamespace(summary=summary,probabilities=probabilities)

def result():
    history={}
    for side,team in [('home','1'),('away','2')]:
        rows=[]
        for i in range(10):
            ground=side if i<5 else ('away' if side=='home' else 'home')
            rows.append(dict(id=side+str(i),date=(NOW-timedelta(days=i*4+2)).isoformat(),
                             home_id=team if ground=='home' else '99',away_id=team if ground=='away' else '99',
                             home_goals=3 if ground=='home' else 0,away_goals=1))
        history[side]=rows
    return dict(match=dict(id='10',league='fra.1',date=(NOW+timedelta(hours=4)).isoformat(),home=dict(id='1'),away=dict(id='2')),
                history=history,source_errors=dict(home=[],away=[]))


def pick(n=1,status='won',candidate=60):
    r=result();r['venue_test']=dict(status='ready',prediction=dict(markets={'btts':candidate}))
    return dict(match=dict(r['match'],id=str(n)),published_at=NOW.isoformat(),status=status,
                market='btts',probability=80,venue_test=freeze(r,NOW))

class VenueTests(unittest.TestCase):
    def test_correct_home_and_away_subsets_and_same_scoring(self):
        r=result();before=copy.deepcopy(r);v=build(SERVER,r,NOW)
        self.assertEqual(v['status'],'ready');self.assertEqual(v['samples'],dict(home=5,away=5))
        home=[g for g in r['history']['home'] if g['home_id']=='1']
        away=[g for g in r['history']['away'] if g['away_id']=='2']
        self.assertEqual(v['prediction'],probabilities(summary(home,'1'),summary(away,'2')))
        self.assertEqual(r,before)

    def test_insufficient_old_partial_duplicate_and_future_inputs(self):
        for mode in ['short','venue','old','partial','duplicate','future','score','foreign']:
            r=result();g=r['history']['home']
            if mode=='short':g.pop()
            if mode=='venue':
                for game in g[:3]:game['home_id']='99';game['away_id']='1'
            if mode=='old':g[0]['date']=(NOW-timedelta(days=181)).isoformat()
            if mode=='partial':r['source_errors']['home']=['timeout']
            if mode=='duplicate':g[1]['id']=g[0]['id']
            if mode=='future':g[0]['date']=(NOW+timedelta(days=1)).isoformat()
            if mode=='score':g[0]['home_goals']=True
            if mode=='foreign':g[0]['home_id']='88'
            self.assertEqual(build(SERVER,r,NOW)['status'],'unavailable',mode)

    def test_freeze_and_missing_variant_do_not_reconstruct_old_choices(self):
        r=result();r['venue_test']=dict(status='ready',prediction=dict(markets={'btts':60}))
        saved=freeze(r,NOW);r['venue_test']['prediction']['markets']['btts']=99
        self.assertEqual(saved['prediction']['markets']['btts'],60)
        self.assertEqual(freeze({},NOW)['reason'],'not_calculated')
        self.assertEqual(report([{'status':'won'}],NOW)['registered'],0)

    def test_paired_brier_and_equal_result_rates(self):
        rows=[pick(1,'won',60),pick(2,'lost',60),pick(3,'pending',60)]
        missing=pick(4);missing['venue_test']=dict(version=VERSION,recorded_at=NOW.isoformat(),status='unavailable',reason='insufficient_venue_history')
        rows.append(missing)
        r=report(rows,NOW+timedelta(days=1))
        self.assertEqual((r['registered'],r['paired'],r['coverage_pct']),(4,3,75))
        self.assertEqual(r['baseline']['overall']['success_pct'],50)
        self.assertEqual(r['candidate']['overall']['success_pct'],50)
        self.assertEqual(r['baseline']['overall']['count'],r['candidate']['overall']['count'])
        self.assertEqual(r['brier_difference'],-.08)
        self.assertEqual(r['unavailable'],{'insufficient_venue_history':1})
        self.assertEqual(r['candidate']['overall']['evidence'],'insufficient')

    def test_passive_failure_never_discards_the_official_prediction(self):
        from flask import Flask
        from unittest.mock import Mock,patch
        from daily_opinion import DailyOpinion
        r=result()
        api=SimpleNamespace(summary=summary,probabilities=probabilities,
                            history=Mock(side_effect=[(r['history']['home'],[]),(r['history']['away'],[])]))
        with patch('daily_opinion.build_venue',side_effect=RuntimeError('test failure')):
            analysis=DailyOpinion(Flask(__name__),api).analyze(r['match'])
        self.assertIn('prediction',analysis)
        self.assertEqual(analysis['venue_test']['reason'],'calculation_error')

    def test_duplicates_late_future_and_fixed_window(self):
        p=pick();late=pick(2);late['venue_test']['recorded_at']=late['match']['date']
        far=pick(3);far['published_at']=(NOW+timedelta(days=91)).isoformat()
        far['venue_test']['recorded_at']=far['published_at'];far['match']['date']=(NOW+timedelta(days=92)).isoformat()
        r=report([p,copy.deepcopy(p),late,far],NOW+timedelta(days=93))
        self.assertEqual(r['registered'],1);self.assertEqual(r['status'],'window_complete')
        self.assertEqual(r['excluded'],dict(duplicate=1,invalid_snapshot=1))
        self.assertEqual(report([p],NOW-timedelta(seconds=1))['registered'],0)
        self.assertEqual(report([],NOW)['status'],'waiting_for_new_choices')

if __name__=='__main__':unittest.main()
