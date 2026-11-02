import os
import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor
from unittest.mock import patch
from flask import jsonify
import app as server
import accounts

class AccountTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.previous={k:server.app.config.get(k) for k in ('TESTING','ACCOUNT_DATABASE_URL','ACCOUNT_SECURE_COOKIE')}
        server.app.config.update(TESTING=True,ACCOUNT_DATABASE_URL=os.environ.get('TEST_DATABASE_URL','sqlite:///'+self.temp.name+'/accounts.sqlite'),ACCOUNT_SECURE_COOKIE=False)
        accounts.init_schema(server.app)
        with server.app.app_context(),accounts.database() as db:
            for table in ('account_sessions','account_analyses','account_users','account_rate_limits'):
                db.execute('DELETE FROM '+table)
        self.client=server.app.test_client()
        self.headers={'X-App-Request':'1','Origin':'https://foot-analyst-pro.onrender.com'}
        self.pw='Test-password-2026!'

    def tearDown(self):
        server.app.config.update(self.previous)
        self.temp.cleanup()

    def post(self,path,data,client=None,headers=None):
        return (client or self.client).post(path,json=data,headers=headers or self.headers)

    def register(self,email='jordan@example.com'):
        r=self.post('/api/account/register',dict(email=email,nickname='Jordan',password=self.pw,accept_privacy=True))
        self.assertEqual(r.status_code,201,r.json)
        self.headers['X-CSRF-Token']=r.json['csrf_token']
        return r.json

    def manual(self,home='A'):
        return dict(home=home,away='B',home_scored_avg=1.5,home_conceded_avg=1,away_scored_avg=1,away_conceded_avg=1.2,sample_matches_per_team=10)

    def test_register_login_persistence_and_no_password_exposure(self):
        data=self.register()
        self.assertEqual(data['user']['trial_remaining'],3)
        self.assertNotIn('password_hash',data['user'])
        token=self.client.get_cookie(accounts.COOKIE).value
        with server.app.app_context(),accounts.database() as db:
            row=db.execute('SELECT * FROM account_users').fetchone()
            self.assertNotEqual(row['password_hash'],self.pw)
            session=db.execute('SELECT * FROM account_sessions').fetchone()
            self.assertNotEqual(session['token_hash'],token)
        # A second client logs into the same DB: state is independent of phone storage.
        other=server.app.test_client()
        response=self.post('/api/account/login',dict(email='JORDAN@example.com',password=self.pw),other)
        self.assertEqual(response.status_code,200)
        self.assertEqual(response.json['user']['id'],data['user']['id'])
        self.assertEqual(self.client.get('/api/account').json['csrf_token'],self.client.get('/api/account').json['csrf_token'])

    def test_origin_csrf_and_unauthenticated_requests(self):
        self.assertEqual(self.post('/api/account/login',{},headers={'X-App-Request':'1','Origin':'https://evil.example'}).status_code,403)
        self.assertEqual(self.post('/api/analyse-statistique',self.manual()).status_code,401)
        self.register()
        bad={**self.headers,'X-CSRF-Token':'wrong'}
        self.assertEqual(self.post('/api/account/profile',{'nickname':'Bad'},headers=bad).status_code,403)
        self.assertEqual(self.client.get('/api/analyze').status_code,405)
        self.assertEqual(self.client.get('/api/ticket').status_code,410)

    def test_three_trials_cache_and_private_history(self):
        self.register()
        for name in ('A','C','D'):
            response=self.post('/api/analyse-statistique',self.manual(name))
            self.assertEqual(response.status_code,200,response.json)
        self.assertEqual(self.client.get('/api/account').json['user']['trial_remaining'],0)
        locked=self.post('/api/analyse-statistique',self.manual('E'))
        self.assertEqual(locked.status_code,200)
        self.assertEqual(locked.json['status'],'locked')
        self.assertNotIn('probabilities',locked.json)
        self.assertNotIn('report',locked.json)
        self.assertEqual(self.post('/api/analyse-statistique',self.manual('A')).status_code,200)
        self.assertEqual(len(self.client.get('/api/account/history').json['analyses']),3)
        self.assertEqual(server.app.test_client().get('/api/account/history').status_code,401)
        export=self.client.get('/api/account/export').json
        self.assertEqual(len(export['analyses']),3)
        self.assertNotIn('password_hash',export['profile'])
        with server.app.app_context(),accounts.database() as db:
            self.assertEqual(db.execute('SELECT trial_used FROM account_users').fetchone()['trial_used'],3)

    def test_cached_champions_context_does_not_charge_or_change_predictions(self):
        import json
        from test_champions_context import game
        self.register()
        inputs = dict(league='uefa.champions',home_id='1',away_id='2',event_id='123')
        context = dict(version=1,fixture_verified=True,observed_at='2026-11-02T12:00:00Z',teams={})
        with patch.object(server,'history',side_effect=lambda league,team,**kw:([game(i,i+2,home=team) for i in range(10)],[])), patch.object(server,'head_to_head',return_value={'matches':[]}), patch('champions_context.collect',return_value=context):
            initial=self.post('/api/analyze',inputs)
        self.assertEqual(initial.status_code,200,initial.json)
        prediction=initial.json['prediction']
        with server.app.app_context(),accounts.database() as db:
            row=db.execute('SELECT id,result FROM account_analyses').fetchone()
            saved=json.loads(row['result']);saved.pop('domestic_context')
            saved['report']['sections']=[s for s in saved['report']['sections'] if not s['title'].startswith('Forme nationale')]
            db.execute('UPDATE account_analyses SET result=? WHERE id=?',(json.dumps(saved),row['id']))
        with patch('champions_context.collect',return_value=context):
            enriched=self.post('/api/analyze',inputs)
        self.assertEqual(enriched.json['prediction'],prediction)
        self.assertEqual(enriched.json['domestic_context'],context)
        self.assertEqual(self.client.get('/api/account').json['user']['trial_remaining'],2)
        self.assertEqual(sum(s['title'].startswith('Forme nationale') for s in enriched.json['report']['sections']),1)

    def test_failed_and_insufficient_analyses_are_refunded(self):
        self.register()
        invalid=self.manual();invalid['home_scored_avg']=-1
        self.assertEqual(self.post('/api/analyse-statistique',invalid).status_code,400)
        with patch.object(server,'history',return_value=([],[])), patch.object(server,'head_to_head',return_value={'matches':[]}):
            r=self.post('/api/analyze',dict(league='fra.1',home_id='1',away_id='2',event_id='123'))
        self.assertEqual(r.json['status'],'insufficient_data')
        self.assertEqual(self.client.get('/api/account').json['user']['trial_remaining'],3)
        self.assertEqual(self.client.get('/api/account/history').json['analyses'],[])

    def test_recovery_is_single_use_and_invalidates_sessions(self):
        data=self.register()
        old_token=self.client.get_cookie(accounts.COOKIE).value
        r=self.post('/api/account/recover',dict(email=data['user']['email'],recovery_code=data['recovery_code'],password='A-new-password-2026!'))
        self.assertEqual(r.status_code,200)
        self.assertNotEqual(r.json['recovery_code'],data['recovery_code'])
        old_client=server.app.test_client();old_client.set_cookie(accounts.COOKIE,old_token)
        self.assertIsNone(old_client.get('/api/account').json['user'])
        r=self.post('/api/account/recover',dict(email=data['user']['email'],recovery_code=data['recovery_code'],password='Another-password-2026!'))
        self.assertEqual(r.status_code,401)

    def test_change_password_profile_logout_delete(self):
        data=self.register()
        self.assertEqual(self.post('/api/account/profile',dict(nickname='Nouveau pseudo')).json['user']['nickname'],'Nouveau pseudo')
        changed=self.post('/api/account/password',dict(current_password=self.pw,password='New-long-password-2026!'))
        self.assertEqual(changed.status_code,200)
        self.headers['X-CSRF-Token']=changed.json['csrf_token']
        self.assertEqual(self.post('/api/account/delete',dict(password='wrong',confirmation='SUPPRIMER')).status_code,400)
        self.assertEqual(self.post('/api/account/logout',{}).status_code,200)
        self.assertIsNone(self.client.get('/api/account').json['user'])
        login=self.post('/api/account/login',dict(email=data['user']['email'],password='New-long-password-2026!'))
        self.headers['X-CSRF-Token']=login.json['csrf_token']
        self.assertEqual(self.post('/api/account/delete',dict(password='New-long-password-2026!',confirmation='SUPPRIMER')).status_code,200)
        with server.app.app_context(),accounts.database() as db:
            for table in ('account_users','account_sessions','account_analyses'):
                self.assertEqual(db.execute('SELECT COUNT(*) AS n FROM '+table).fetchone()['n'],0)

    def test_rate_limit_and_no_storage_mode(self):
        for _ in range(21):
            r=self.post('/api/account/login',dict(email='none@example.com',password=self.pw))
        self.assertEqual(r.status_code,429)
        server.app.config['ACCOUNT_DATABASE_URL']=''
        self.assertFalse(self.client.get('/api/account').json['available'])
        self.assertEqual(self.post('/api/account/register',dict(email='a@example.com',nickname='Name',password=self.pw,accept_privacy=True)).status_code,503)

    def test_concurrent_reservations_cannot_exceed_three(self):
        data=self.register();uid=data['user']['id']
        def reserve(i):
            with server.app.app_context():
                try:accounts.reserve_analysis({'id':uid},str(i),'Match '+str(i));return 'ok'
                except accounts.AccountError as e:return e.kind
        with ThreadPoolExecutor(max_workers=5) as pool:
            results=list(pool.map(reserve,range(5)))
        self.assertEqual(results.count('ok'),3)
        self.assertEqual(results.count('trial_exhausted'),2)
        with server.app.app_context(),accounts.database() as db:
            self.assertEqual(db.execute('SELECT trial_used FROM account_users').fetchone()['trial_used'],3)

if __name__=='__main__':unittest.main()

