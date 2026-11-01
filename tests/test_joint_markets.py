import unittest
from app import probabilities
from tracking import resolve

class JointMarkets(unittest.TestCase):
    def test_joint_is_subset_and_not_independent_product(self):
        t={'goals_for_avg':1.5,'goals_against_avg':1.2}
        p=probabilities(t,t)['markets']
        for side in ['home_or_draw','away_or_draw']:
            for goal in ['btts','btts_no','over_1_5','over_2_5','under_1_5','under_2_5']:
                self.assertLessEqual(p[side+'_and_'+goal],min(p[side],p[goal])+.11)
        self.assertGreater(abs(p['home_or_draw_and_btts']-p['home_or_draw']*p['btts']/100),.1)
    def test_both_conditions_must_win(self):
        self.assertTrue(resolve('home_or_draw_and_btts',1,1))
        self.assertFalse(resolve('home_or_draw_and_btts',0,0))
        self.assertFalse(resolve('home_or_draw_and_btts',1,2))
        self.assertTrue(resolve('home_or_draw_and_over_2_5',3,0))
        self.assertFalse(resolve('home_or_draw_and_over_2_5',1,1))
