import unittest
from app import probabilities
from tracking import resolve

class MarketOutcomes(unittest.TestCase):
    def test_complements(self):
        stats={'goals_for_avg':1.5,'goals_against_avg':1}
        markets=probabilities(stats,stats)['markets']
        for under,over in [('under_1_5','over_1_5'),('under_2_5','over_2_5'),('btts_no','btts')]:
            self.assertAlmostEqual(markets[under]+markets[over],100,delta=.2)
    def test_under_thresholds_and_btts_no(self):
        self.assertTrue(resolve('under_2_5',1,1))
        self.assertFalse(resolve('under_2_5',2,1))
        self.assertTrue(resolve('under_1_5',1,0))
        self.assertFalse(resolve('under_1_5',1,1))
        self.assertTrue(resolve('btts_no',0,3))
        self.assertFalse(resolve('btts_no',1,3))
