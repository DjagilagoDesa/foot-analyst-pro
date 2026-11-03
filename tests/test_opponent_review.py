import copy
import unittest
from datetime import datetime, timedelta, timezone
from opponent_review import review, paired_interval, extended_review, MARKETS


def rows():
    start = datetime(2026, 1, 1, tzinfo=timezone.utc)
    return [dict(id=str(i), league='fra.1', date=(start+timedelta(weeks=i)).isoformat(),
                 score=[2, 1], split='test',
                 baseline={'markets': dict.fromkeys(MARKETS, 50)},
                 candidate={'markets': dict.fromkeys(MARKETS, 80)}) for i in range(9)]


class ReviewTests(unittest.TestCase):
    def test_paired_market_scores_and_no_promotion(self):
        result = extended_review({'predictions': rows()})
        self.assertEqual(result['test']['btts']['baseline']['brier'], .25)
        self.assertEqual(result['test']['btts']['candidate']['brier'], .04)
        self.assertEqual(result['test']['btts']['delta_candidate_minus_baseline'], -.21)
        self.assertEqual(result['test']['btts_no']['delta_candidate_minus_baseline'], .39)
        self.assertEqual(result['test']['home_or_draw']['count'], 9)
        self.assertEqual(result['decision'], 'experimental_only_no_automatic_promotion')
        self.assertEqual(result['test'], result['by_competition']['fra.1'])
        self.assertIsNone(result['validation']['btts']['baseline']['brier'])

    def test_week_clusters_and_reproducible_interval(self):
        data = [(r['date'], -.2) for r in rows()]
        self.assertEqual(paired_interval(data)['interval_95'], [-.2, -.2])
        self.assertEqual(paired_interval(data), paired_interval(data))
        # Many matches in one week are not many independent blocks.
        self.assertIsNone(paired_interval([data[0]] * 200)['interval_95'])

    def test_duplicate_and_nonfinite_prediction_rejected(self):
        data = rows()
        with self.assertRaises(ValueError): review(data+[data[0]])
        invalid = copy.deepcopy(data)
        invalid[0]['candidate']['markets']['btts'] = float('nan')
        with self.assertRaises(ValueError): review(invalid)

if __name__ == '__main__': unittest.main()
