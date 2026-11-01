import unittest
from analysis_report import report

class ReportTests(unittest.TestCase):
    def test_report_uses_real_metrics_and_balanced_scenarios(self):
        team=dict(wins=7,draws=3,losses=2,matches=12,goals_for_avg=1.7,goals_against_avg=1.1)
        data=dict(status='ok',home_name='Paris',away_name='Lyon',home=team,away=team,prediction=dict(expected_goals={'home':1.8,'away':1.3},markets={'home':48,'draw':28,'away':24,'over_1_5':70,'over_2_5':45,'btts':50}))
        result=report(data)
        self.assertIn('Paris',result['verdict'])
        self.assertEqual(len(result['sections']),5)
        self.assertIn('7 victoires',result['sections'][0]['text'])
        self.assertIn('Lyon',result['sections'][1]['title'])
        self.assertIn('ne sont pas intégrés',result['sections'][-1]['text'])
    def test_no_report_without_successful_data(self):
        self.assertIsNone(report({'status':'insufficient_data'}))
