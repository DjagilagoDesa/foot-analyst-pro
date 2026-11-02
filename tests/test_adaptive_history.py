import unittest
from datetime import datetime, timedelta, timezone
from unittest.mock import patch
import app as server
from adaptive_history import combine

NOW = datetime.now(timezone.utc)


def game(event, team='1', days=2):
    return dict(id=str(event),date=(NOW-timedelta(days=days)).isoformat(),home_id=team,away_id='99',
                home='Club '+team,away='Other',home_goals=2,away_goals=1)


class AdaptiveHistoryTests(unittest.TestCase):
    def test_deduplication_validation_and_twenty_most_recent(self):
        games=[game(i,days=i+1) for i in range(25)]
        invalid=[game('future',days=-1),game('old',days=541),game('foreign',team='9')]
        rows,basis=combine('1',[('uefa.champions',games[:4]),('tur.1',games+invalid)],now=NOW)
        self.assertEqual(len(rows),20)
        self.assertEqual(len({r['id'] for r in rows}),20)
        self.assertEqual(rows[0]['id'],'0')
        self.assertEqual(basis['competitions'],{'uefa.champions':4,'tur.1':16})
        self.assertTrue(basis['mixed_competitions'])

    def test_ucl_research_uses_domestic_results_independently_per_team(self):
        def history(league,team,**kwargs):
            if league=='uefa.champions':return [game('e'+team+str(i),team,days=i+2) for i in range(4 if team=='1' else 3)],[]
            return [],[]
        context={'teams':{'1':{'league':'tur.1','model_games':[game('d'+str(i),'1',days=i+10) for i in range(10)]},
                          '2':{'league':'ger.1','model_games':[game('b'+str(i),'2',days=i+10) for i in range(5)]}}}
        with patch.object(server,'history',side_effect=history), patch.object(server,'head_to_head',return_value={'matches':[]}), patch('champions_context.collect',return_value=context), patch('match_availability.collect',return_value={'status':'unavailable'}), server.app.test_request_context('/api/analyze',method='POST',json={'league':'uefa.champions','home_id':'1','away_id':'2'}):
            data=server.analyze().json
        self.assertEqual(data['status'],'ok')
        self.assertEqual((data['home']['matches'],data['away']['matches']),(14,8))
        self.assertEqual(data['analysis_basis']['home']['competitions'],{'uefa.champions':4,'tur.1':10})
        section=next(s for s in data['report']['sections'] if s['title'].startswith('Base des calculs'))
        self.assertIn('ÉCHANTILLON LIMITÉ',section['text'])
        self.assertIn('tur.1 : 10',section['text'])
        europe=next(s for s in data['report']['sections'] if s['title'].startswith('Ligue des champions'))
        self.assertIn('Club 1',europe['text'])
        self.assertTrue(all(0<=p<=100 for p in data['prediction']['markets'].values()))

    def test_partial_histories_can_be_analysed_but_empty_team_cannot(self):
        def history(league,team,**kwargs):return [game(team+str(i),team,days=i+2) for i in range(3 if team=='1' else 5)],[]
        with patch.object(server,'history',side_effect=history),patch.object(server,'head_to_head',return_value={'matches':[]}),server.app.test_request_context('/api/analyze',method='POST',json={'league':'fra.1','home_id':'1','away_id':'2'}):
            data=server.analyze().json
        self.assertEqual(data['status'],'ok')
        self.assertEqual(data['analysis_basis']['home']['evidence'],'very_limited')
        with patch.object(server,'history',return_value=([],[])),patch.object(server,'head_to_head',return_value={'matches':[]}),server.app.test_request_context('/api/analyze',method='POST',json={'league':'fra.1','home_id':'1','away_id':'2'}):
            data=server.analyze().json
        self.assertEqual(data['status'],'insufficient_data')
        self.assertNotIn('prediction',data)

if __name__=='__main__':unittest.main()
