import copy
import unittest
from datetime import datetime, timedelta, timezone
from app import probabilities, summary
from opponent_benchmark import State, run, validate

START = datetime(2025,1,1,tzinfo=timezone.utc)


def dataset():
    games=[]
    # Synthetic connected league; only verifies the evaluation machinery.
    pairs=[('1','2'),('3','4'),('1','3'),('2','4'),('1','4'),('2','3')]
    for i in range(60):
        home,away=pairs[i%len(pairs)];kickoff=START+timedelta(days=2*i)
        games.append(dict(id=str(i),league='fra.1',home_id=home,away_id=away,home='Club '+home,away='Club '+away,
            date=kickoff.isoformat(),available_at=(kickoff+timedelta(hours=24)).isoformat(),
            home_goals=i%4,away_goals=(i+1)%3,regulation_only=True))
    return games


def benchmark(games):
    return run(games,(START+timedelta(days=40)).isoformat(),(START+timedelta(days=80)).isoformat(),probabilities,summary)


class OpponentBenchmarkTests(unittest.TestCase):
    def test_future_scores_cannot_change_earlier_predictions(self):
        original=dataset();changed=copy.deepcopy(original)
        for game in changed[40:]:game['home_goals']=9;game['away_goals']=0
        before=benchmark(original)['predictions'];after=benchmark(changed)['predictions']
        self.assertGreater(len(before),10)
        earlier=lambda rows:[{k:r[k] for k in ('id','baseline','candidate','ratings','samples')} for r in rows if int(r['id'])<40]
        self.assertEqual(earlier(before),earlier(after))

    def test_unavailable_results_are_not_used_even_when_kickoff_is_old(self):
        games=dataset()
        for row in games:row['available_at']='2027-01-01T00:00:00Z'
        report=benchmark(games)
        self.assertEqual(report['scored_fixtures'],0)
        self.assertGreater(sum(report['skipped'].values()),0)

    def test_paired_scoring_separate_splits_and_no_promotion(self):
        report=benchmark(dataset())
        self.assertGreater(report['validation']['count'],0)
        self.assertGreater(report['test']['count'],0)
        self.assertEqual(report['decision'],'experimental_only_no_automatic_promotion')
        self.assertEqual(report['test']['evidence'],'insufficient')
        self.assertEqual(report['test']['count'],report['by_competition']['fra.1']['count'])
        self.assertTrue(all(row['split']=='test' for row in report['predictions'] if row['date']>=report['test_from']))

    def test_conflicting_duplicate_and_invalid_regulation_rejected(self):
        games=dataset();duplicate=dict(games[0],home_goals=7)
        with self.assertRaises(ValueError):validate(games+[duplicate])
        games[0]['regulation_only']=False
        with self.assertRaises(ValueError):validate(games)

    def test_rating_rewards_an_upset_more_and_keeps_kickoff_snapshot(self):
        game=dataset()[0]
        weak=State();weak.ratings['2']=1300;weak.add(game)
        strong=State();strong.ratings['2']=1700
        won=dict(game,home_goals=2,away_goals=0,rating_home_before=1500,rating_away_before=1700)
        strong.add(won)
        normal=State();normal.ratings['2']=1300;normal.add(dict(won,rating_away_before=1300))
        self.assertGreater(strong.ratings['1']-1500,normal.ratings['1']-1500)
        self.assertEqual(strong.histories['1'][0]['opponent_rating'],1700)

    def test_disconnected_competitions_are_not_a_cross_league_ranking(self):
        state=State()
        for i in range(4):
            g=dataset()[i]
            state.add(dict(g,home_id='1',away_id='2'))
            state.add(dict(g,home_id='3',away_id='4',id='x'+str(i)))
        prediction,reason=state.predict('1','3','fra.1',START+timedelta(days=50),probabilities,summary)
        self.assertIsNone(prediction)
        self.assertEqual(reason,'disconnected_opponent_graph')

if __name__=='__main__':unittest.main()
