import unittest
from unittest.mock import patch
from datetime import datetime, timedelta, timezone
import requests
import app as server


def event(home='1', away='2', completed=True, future=False):
    date=datetime.now(timezone.utc)+timedelta(days=2 if future else -2)
    return {'id':'123','date':date.isoformat(), 'status':{'type':{'completed':completed}}, 'competitions':[{'competitors':[
        {'homeAway':'home','score':'2','team':{'id':home,'displayName':'Équipe A'}},
        {'homeAway':'away','score':'1','team':{'id':away,'displayName':'Équipe B'}}]}]}

class BackendTests(unittest.TestCase):
    def setUp(self): self.client=server.app.test_client()

    def test_one_letter_accent_search_and_partial_failure(self):
        data={'sports':[{'leagues':[{'teams':[{'team':{'id':'1','displayName':'Évian','logos':[]}}]}]}]}
        def fetch(url, *args, **kwargs):
            if '/eng.1/' in url: raise requests.Timeout()
            return data
        with patch.object(server,'fetch',side_effect=fetch):
            response=self.client.get('/api/search-teams?q=e')
        self.assertEqual(response.status_code,200)
        self.assertTrue(response.json['partial'])
        self.assertEqual(response.json['teams'][0]['name'],'Évian')

    def test_source_failure_is_not_empty_success(self):
        with patch.object(server,'fetch',side_effect=requests.Timeout()):
            self.assertEqual(self.client.get('/api/search-teams?q=a').status_code,502)
            self.assertEqual(self.client.get('/api/team-next?league=fra.1&team_id=1').status_code,503)

    def test_next_match_shape_and_deduplicated_history(self):
        with patch.object(server,'fetch',return_value={'events':[event(completed=False,future=True)]}):
            response=self.client.get('/api/team-next?league=fra.1&team_id=1')
            self.assertEqual(response.status_code,200)
            self.assertEqual(response.json['event']['home']['id'],'1')
        with patch.object(server,'fetch',return_value={'events':[event(),event(),event(future=True)]}):
            matches,errors=server.history('fra.1','1')
            self.assertEqual(len(matches),1)
            self.assertEqual(errors,[])

    def test_low_sample_never_generates_probabilities(self):
        with patch.object(server,'history',return_value=([],[])):
            data=self.client.get('/api/analyze?league=fra.1&home_id=1&away_id=2').json
        self.assertEqual(data['status'],'insufficient_data')
        self.assertNotIn('prediction',data)

    def test_input_validation_and_asset_routes(self):
        self.assertEqual(self.client.get('/api/analyze?league=fra.1&home_id=1&away_id=1').status_code,400)
        self.assertEqual(self.client.get('/api/fixtures?date=invalid').status_code,400)
        self.assertEqual(self.client.post('/api/analyse-statistique',json=[]).status_code,400)
        with self.client.get('/stade_premium.png') as response:
            self.assertEqual(response.status_code,200)
        self.assertEqual(self.client.get('/api/health').json['version'],'45')

if __name__=='__main__': unittest.main()
