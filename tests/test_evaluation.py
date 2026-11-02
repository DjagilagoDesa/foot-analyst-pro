import copy
import unittest
from evaluation import evaluate


def pick(event, probability, status):
    return dict(match=dict(id=str(event), league='fra.1', date='2026-11-02T20:00:00Z'),
                published_at='2026-11-02T12:00:00Z', market='btts', probability=probability,
                status=status, model_version='test-v1')


class Evaluation(unittest.TestCase):
    def test_calibration_and_brier(self):
        report = evaluate([pick(1, 80, 'won'), pick(2, 80, 'lost')])
        self.assertEqual(report['overall']['brier'], .34)
        self.assertEqual(report['overall']['calibration_gap_pp'], -30)
        self.assertEqual(report['overall']['evidence'], 'insufficient')
        self.assertEqual(report['breakdown']['confidence']['80']['count'], 2)
        self.assertIsNone(report['roi'])

    def test_retroactive_invalid_unsettled_and_duplicate_excluded(self):
        valid = pick(1, 80, 'won')
        late = pick(2, 90, 'won'); late['published_at'] = late['match']['date']
        naive = pick(3, 80, 'won'); naive['published_at'] = '2026-11-02T12:00:00'
        samples = [valid, copy.deepcopy(valid), late, naive, pick(4, float('nan'), 'won'),
                   pick(5, True, 'won'), pick(6, 101, 'won'), pick(7, 90, 'pending'), pick(8, 90, 'void')]
        report = evaluate(samples)
        self.assertEqual(report['overall']['count'], 1)
        self.assertEqual(report['excluded'], dict(duplicate=1, invalid_snapshot=5, pending=1, void=1))

    def test_empty_and_legacy(self):
        self.assertIsNone(evaluate([])['overall']['brier'])
        old = pick(1, 70, 'lost'); del old['model_version']
        self.assertEqual(evaluate([old])['breakdown']['model']['legacy-unversioned']['count'], 1)

if __name__ == '__main__':
    unittest.main()
