import copy
import json
import unittest
from datetime import datetime,timedelta,timezone
from unittest.mock import patch
import app as server
import accounts
import test_accounts as helpers

class PersonnelAccountTests(unittest.TestCase):
    setUp=helpers.AccountTests.setUp
    tearDown=helpers.AccountTests.tearDown
    post=helpers.AccountTests.post
    register=helpers.AccountTests.register

    def context(self,minutes=10,name='Joueur initial'):
        now=datetime.now(timezone.utc)
        return dict(version=2,fixture_verified=True,status='partial',observed_at=(now-timedelta(minutes=minutes)).isoformat(),
                    kickoff=(now+timedelta(days=1)).isoformat(),teams={'1':dict(starters=[dict(id='10',name=name)],availability=[])})

    def initial(self):
        self.register()
        now=datetime.now(timezone.utc)
        def history(league,team,**kwargs):
            return [dict(id=team+str(i),date=(now-timedelta(days=i+2)).isoformat(),home_id=team,away_id='999',home='Club '+team,away='Autre',home_goals=2,away_goals=1) for i in range(10)],[]
        first=self.context()
        with patch.object(server,'history',side_effect=history),patch.object(server,'head_to_head',return_value={'matches':[]}),patch('match_availability.collect',return_value=first) as collected:
            response=self.post('/api/analyze',dict(league='fra.1',home_id='1',away_id='2',event_id='123'))
        self.assertEqual(response.status_code,200,response.json)
        self.assertEqual(collected.call_args.args[1],'fra.1')
        self.assertEqual(response.json['personnel_context'],first)
        return response.json

    def test_domestic_analysis_refresh_is_free_and_archives_previous_state(self):
        initial=self.initial();analysis=initial['tracking_id'];before=copy.deepcopy(initial)
        updated=self.context(minutes=0,name='Nouveau titulaire')
        with patch('match_availability.collect',return_value=updated) as source:
            response=self.post('/api/account/analysis/'+analysis+'/personnel',{})
            again=self.post('/api/account/analysis/'+analysis+'/personnel',{})
        self.assertEqual(response.status_code,200,response.json)
        self.assertEqual(response.json['status'],'updated')
        self.assertEqual(again.json['status'],'not_modified')
        self.assertEqual(source.call_count,1)
        self.assertEqual(response.json['personnel_snapshots'][0],before['personnel_context'])
        self.assertEqual(len(response.json['personnel_snapshots']),2)
        saved=self.client.get('/api/account/history').json['analyses'][0]['result']
        self.assertEqual(saved['prediction'],before['prediction'])
        self.assertEqual(saved['generated_at'],before['generated_at'])
        self.assertEqual(self.client.get('/api/account').json['user']['trial_remaining'],2)
        export=self.client.get('/api/account/export').json
        self.assertEqual(len(export['analyses'][0]['result']['personnel_snapshots']),2)
        self.assertEqual(response.headers['Cache-Control'],'no-store')

    def test_owner_csrf_and_archived_result_guards(self):
        initial=self.initial();path='/api/account/analysis/'+initial['tracking_id']+'/personnel'
        self.assertEqual(server.app.test_client().post(path,json={},headers=self.headers).status_code,401)
        wrong={**self.headers,'X-CSRF-Token':'bad'}
        self.assertEqual(self.post(path,{},headers=wrong).status_code,403)
        self.assertEqual(self.post('/api/account/analysis/not-owned/personnel',{}).status_code,404)
        other=server.app.test_client()
        signup=self.post('/api/account/register',dict(email='other@example.com',nickname='Autre',password=self.pw,accept_privacy=True),client=other)
        other_headers={**self.headers,'X-CSRF-Token':signup.json['csrf_token']}
        self.assertEqual(self.post(path,{},client=other,headers=other_headers).status_code,404)
        with server.app.app_context(),accounts.database() as db:
            old=copy.deepcopy(initial);old['personnel_context']['kickoff']='2020-01-01T12:00:00Z'
            db.execute('UPDATE account_analyses SET result=? WHERE id=?',(json.dumps(old),initial['tracking_id']))
        with patch('match_availability.collect') as source:
            response=self.post(path,{})
        source.assert_not_called()
        self.assertEqual(response.json['status'],'not_modified')
        saved=self.client.get('/api/account/history').json['analyses'][0]['result']
        self.assertEqual(saved,old)

    def test_source_failure_preserves_original_and_no_new_trial(self):
        initial=self.initial()
        with patch('match_availability.collect',return_value={'fixture_verified':False,'reason':'source_unavailable'}):
            response=self.post('/api/account/analysis/'+initial['tracking_id']+'/personnel',{})
        self.assertEqual(response.json['status'],'not_modified')
        self.assertEqual(response.json['personnel_context'],initial['personnel_context'])
        self.assertEqual(self.client.get('/api/account').json['user']['trial_remaining'],2)

    def test_slow_refresh_cannot_overwrite_newer_saved_context(self):
        initial=self.initial();aid=initial['tracking_id'];newer=self.context(minutes=-1,name='État conservé')
        def refresh(server,cached):
            saved=copy.deepcopy(initial);saved['personnel_context']=newer
            with accounts.database() as db:
                db.execute('UPDATE account_analyses SET result=? WHERE id=?',(json.dumps(saved),aid))
            cached['personnel_context']=self.context(minutes=0,name='Réponse lente')
            return True
        with patch('match_availability.refresh_cached',side_effect=refresh):
            response=self.post('/api/account/analysis/'+aid+'/personnel',{})
        self.assertEqual(response.json['personnel_context'],newer)

if __name__=='__main__':unittest.main()
