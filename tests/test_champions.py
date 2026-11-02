import unittest
from datetime import datetime, timezone, timedelta
from unittest.mock import patch
import app as server
from test_backend import event

class ChampionsTests(unittest.TestCase):
    def test_european_history_excludes_old_and_extra_time(self):
        current = event(); current['id'] = 'recent'
        old = event(); old['id'] = 'old'; old['date'] = (datetime.now(timezone.utc)-timedelta(days=541)).isoformat()
        extra = event(); extra['id'] = 'extra'; extra['competitions'][0]['status'] = {'type':{'completed':True,'name':'STATUS_FINAL_AET'},'period':4}
        with patch.object(server, 'fetch', return_value={'events':[current,old,extra]}):
            champions, errors = server.history('uefa.champions', '1')
            domestic, _ = server.history('fra.1', '1')
        self.assertEqual([m['id'] for m in champions], ['recent'])
        self.assertEqual(len(domestic), 3)
        self.assertFalse(errors)

    def test_ucl_insufficient_data_explains_evidence_window(self):
        with patch.object(server,'history',return_value=([],[])), patch.object(server,'head_to_head',return_value={'matches':[]}), patch('champions_context.collect',return_value={'teams':{}}), server.app.test_request_context('/api/analyze',method='POST',json={'league':'uefa.champions','home_id':'1','away_id':'2'}):
            data = server.analyze().get_json()
        self.assertEqual(data['status'], 'insufficient_data')
        self.assertIn('3 par équipe', data['message'])
        self.assertEqual(data['analysis_basis']['window_days'],540)
        self.assertNotIn('prediction', data)
        self.assertFalse(data['competition_profile']['opponent_strength_adjusted'])

if __name__ == '__main__': unittest.main()
