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
        with patch.object(server,'history',return_value=([],[])), server.app.test_request_context('/api/analyze',method='POST',json={'league':'fra.1','home_id':'1','away_id':'2'}):
            data=server.analyze().get_json()
        self.assertEqual(data['status'],'insufficient_data')
        self.assertNotIn('prediction',data)

    def test_live_and_final_scores_are_preserved(self):
        live=event(completed=False)
        live['competitions'][0]['status']={'type':{'state':'in','completed':False,'name':'STATUS_IN_PROGRESS','shortDetail':"67'"},'displayClock':"67'",'period':2}
        live['competitions'][0]['competitors'][0]['score']={'displayValue':'3','value':3}
        result=server._fixture(live,'fra.1')
        self.assertEqual(result['state'],'in')
        self.assertEqual(result['home_score'],'3')
        self.assertEqual(result['away_score'],'1')
        self.assertEqual(result['clock'],"67'")
        final=event()
        final['status']['type'].update(state='post',name='STATUS_FULL_TIME',shortDetail='FT')
        result=server._fixture(final,'fra.1')
        self.assertTrue(result['completed'])
        self.assertEqual(result['state'],'post')
        self.assertEqual(result['home_score'],'2')

    def test_fixture_feed_includes_every_status_and_short_cache(self):
        today=datetime.now(timezone.utc).date().isoformat()
        live=event(completed=False)
        live['status']['type'].update(state='in',name='STATUS_IN_PROGRESS')
        final=event()
        final['status']['type'].update(state='post')
        with patch.object(server,'fetch',return_value={'events':[live,final,event(completed=False,future=True)]}) as fetch:
            response=self.client.get('/api/fixtures?league=fra.1&date='+today)
        self.assertEqual(response.status_code,200)
        self.assertEqual(len(response.json['events']),3)
        self.assertEqual(fetch.call_args.kwargs['ttl'],20)
        self.assertIn('updated_at',response.json)

    def test_input_validation_and_asset_routes(self):
        self.assertEqual(self.client.get('/api/analyze?league=fra.1&home_id=1&away_id=1').status_code,405)
        self.assertEqual(self.client.get('/api/fixtures?date=invalid').status_code,400)
        self.assertEqual(self.client.post('/api/analyse-statistique',json=[]).status_code,403)
        with self.client.get('/stade_premium.png') as response:
            self.assertEqual(response.status_code,200)
        self.assertEqual(self.client.get('/api/health').json['version'],'48')

if __name__=='__main__': unittest.main()
