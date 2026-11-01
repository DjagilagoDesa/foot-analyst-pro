import unittest,tempfile,json,time
from datetime import datetime,timezone,timedelta
from unittest.mock import patch
from flask import Flask
import accounts,tracking

class Tracking(unittest.TestCase):
 def setUp(self):
  self.file=tempfile.NamedTemporaryFile();self.app=Flask(__name__);self.app.testing=True
  self.app.config.update(ACCOUNT_DATABASE_URL='sqlite:///'+self.file.name,ACCOUNT_PUBLIC_ORIGIN='https://foot-analyst-pro.onrender.com')
  self.info={'header':{'competitions':[{'date':(datetime.now(timezone.utc)+timedelta(days=1)).isoformat(),'status':{'type':{'state':'pre','completed':False,'name':'STATUS_SCHEDULED'},'period':0},'competitors':[{'homeAway':'home','score':'2','team':{'id':'1'}},{'homeAway':'away','score':'1','team':{'id':'2'}}]}]}}
  tracking.init_app(self.app,lambda *a,**k:self.info,'espn',['fra.1'])
  self.app.register_error_handler(accounts.AccountError,lambda e:(tracking.jsonify(message=e.message),e.code))
  self.patch=patch.object(tracking,'current_user',return_value={'id':'u'});self.patch.start()
  with self.app.app_context(),accounts.database() as db:
   for sql in accounts.SCHEMA:db.execute(sql)
   for uid in ['u','other']:db.execute('INSERT INTO account_users VALUES(?,?,?,?,?,?,?,?)',(uid,uid+'@example.org','n','pw','r',1,3,0))
   result={'event_id':'123','league':'fra.1','home_id':'1','away_id':'2','home_name':'Alpha','away_name':'Beta','prediction':{'markets':{'home':70,'btts':60,'over_2_5':55}}}
   db.execute('INSERT INTO account_analyses VALUES(?,?,?,?,?,?,?,?)',('a','u','key','Alpha-Beta','complete',0,1,json.dumps(result)))
  self.client=self.app.test_client()
 def tearDown(self):self.patch.stop();self.file.close()
 def post(self,market='home',aid='a'):return self.client.post('/api/tracking/record',json={'analysis_id':aid,'market':market},headers={'X-App-Request':'1'})
 def finish(self,period=2):
  c=self.info['header']['competitions'][0];c['date']=(datetime.now(timezone.utc)-timedelta(hours=3)).isoformat();c['status']={'type':{'state':'post','completed':True,'name':'STATUS_FULL_TIME'},'period':period}
  with self.app.app_context(),accounts.database() as db:db.execute('UPDATE account_predictions SET starts_at=?',(int(time.time())-5,))
 def test_record_duplicate_and_settle(self):
  self.assertEqual(self.post().status_code,200);self.post();self.post('btts')
  self.finish();d=self.client.get('/api/tracking/performance').json
  self.assertEqual((d['won'],d['lost'],d['success_pct']),(2,0,100));self.assertEqual(d['total'],2)
 def test_losses_and_percentage(self):
  self.post();self.post('btts');self.info['header']['competitions'][0]['competitors'][0]['score']='0';self.info['header']['competitions'][0]['competitors'][1]['score']='0';self.finish()
  d=self.client.get('/api/tracking/performance').json;self.assertEqual((d['won'],d['lost'],d['success_pct']),(0,2,0))
 def test_extra_time_excluded(self):
  self.post();self.finish(4);d=self.client.get('/api/tracking/performance').json;self.assertEqual(d['void'],1);self.assertIsNone(d['success_pct'])
 def test_ownership(self):
  with patch.object(tracking,'current_user',return_value={'id':'other'}):self.assertEqual(self.post().status_code,404)
 def test_no_retroactive(self):
  self.finish();self.assertEqual(self.post().status_code,409)
 def test_wrong_fixture(self):
  self.info['header']['competitions'][0]['competitors'][0]['team']['id']='9';self.assertEqual(self.post().status_code,400)
 def test_pending_not_percentage(self):
  self.post();d=self.client.get('/api/tracking/performance').json;self.assertEqual(d['pending'],1);self.assertIsNone(d['success_pct'])
 def test_markets(self):
  self.assertTrue(tracking.resolve('home_or_draw',0,0));self.assertFalse(tracking.resolve('over_2_5',1,1));self.assertTrue(tracking.resolve('over_1_5',1,1))
if __name__=='__main__':unittest.main()
