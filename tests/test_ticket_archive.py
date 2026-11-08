"""Combined tickets retain their own grouping without changing selection statistics."""
import json,time
from unittest.mock import patch
from test_tracking import Tracking
import accounts,tracking

class TicketArchive(Tracking):
 def setUp(self):
  super().setUp()
  with self.app.app_context(),accounts.database() as db:
   r=json.loads(db.execute("SELECT result FROM account_analyses WHERE id='a'").fetchone()['result']);r['event_id']='456'
   db.execute('INSERT INTO account_analyses VALUES(?,?,?,?,?,?,?,?)',('b','u','key2','Gamma-Delta','complete',0,1,json.dumps(r)))
 def make(self,title='Mon ticket',picks=None):
  return self.client.post('/api/tracking/tickets',json={'title':title,'selections':picks or [{'analysis_id':'a','market':'home'},{'analysis_id':'b','market':'btts'}]},headers={'X-App-Request':'1'})
 def prepare(self):
  self.assertEqual(self.post().status_code,200);self.assertEqual(self.post('btts','b').status_code,200)
 def archive(self,status='pending',offset=0):return self.client.get('/api/tracking/tickets',query_string={'status':status,'offset':offset}).json
 def test_persistent_and_idempotent(self):
  self.prepare();a=self.make();self.assertEqual(a.status_code,200)
  self.assertEqual(a.json['id'],self.make().json['id'])
  self.assertEqual(len(self.archive()['tickets']),1);ticket=self.archive()['tickets'][0]
  self.assertEqual(len(ticket['selections']),2);self.assertEqual(ticket['status'],'pending')
  self.assertEqual(self.client.get('/api/tracking/performance').json['total'],2)
 def test_account_isolation(self):
  self.prepare();self.make()
  with patch.object(tracking,'current_user',return_value={'id':'other'}):
   self.assertEqual(self.archive()['tickets'],[]);self.assertEqual(self.make().status_code,404)
 def test_pending_then_won_with_void(self):
  self.prepare();self.make()
  with self.app.app_context(),accounts.database() as db:db.execute("UPDATE account_predictions SET status='won' WHERE event_id='123'")
  self.assertEqual(self.archive()['tickets'][0]['status'],'pending')
  with self.app.app_context(),accounts.database() as db:db.execute("UPDATE account_predictions SET status='void' WHERE event_id='456'")
  self.assertEqual(self.archive()['tickets'],[]);self.assertEqual(self.archive('past')['tickets'][0]['status'],'won')
 def test_lost_closes_early(self):
  self.prepare();self.make()
  with self.app.app_context(),accounts.database() as db:db.execute("UPDATE account_predictions SET status='lost' WHERE event_id='123'")
  self.assertEqual(self.archive()['tickets'],[]);self.assertEqual(self.archive('past')['tickets'][0]['status'],'lost')
 def test_all_void(self):
  self.prepare();self.make()
  with self.app.app_context(),accounts.database() as db:db.execute("UPDATE account_predictions SET status='void'")
  self.assertEqual(self.archive('past')['tickets'][0]['status'],'void')
 def test_untracked_or_started_rejected_atomically(self):
  self.post();self.assertEqual(self.make().status_code,409);self.assertEqual(self.archive()['tickets'],[])
  self.post('btts','b')
  with self.app.app_context(),accounts.database() as db:db.execute('UPDATE account_predictions SET starts_at=?',(int(time.time())-1,))
  self.assertEqual(self.make().status_code,409);self.assertEqual(self.archive()['tickets'],[])
 def test_duplicate_match_invalid_input_and_csrf(self):
  self.prepare()
  self.assertEqual(self.make(picks=[{'analysis_id':'a','market':'home'}]*2).status_code,400)
  self.assertEqual(self.make(title='x'*101).status_code,400)
  self.assertEqual(self.client.post('/api/tracking/tickets',json={}).status_code,403)
  self.assertEqual(self.client.get('/api/tracking/tickets?offset=bad').status_code,400)
 def test_pagination_no_missing_tickets(self):
  self.prepare()
  with self.app.app_context(),accounts.database() as db:
   for i in range(7):
    db.execute('INSERT INTO account_tickets VALUES(?,?,?,?,?)',(str(i),'u',str(i),'Ticket '+str(i),i))
    for n,(event,market) in enumerate([('123','home'),('456','btts')]):db.execute('INSERT INTO account_ticket_legs VALUES(?,?,?,?)',(str(i),n,event,market))
  first=self.archive();second=self.archive(offset=first['next_offset'])
  self.assertEqual(len(first['tickets']),5);self.assertEqual(len(second['tickets']),2)
  self.assertEqual(len({t['id'] for t in first['tickets']+second['tickets']}),7)
  self.assertIsNone(second['next_offset'])
 def test_account_deletion_cascades(self):
  self.prepare();self.make()
  with self.app.app_context(),accounts.database() as db:
   db.execute("DELETE FROM account_users WHERE id='u'")
   self.assertEqual(db.execute('SELECT count(*) n FROM account_tickets').fetchone()['n'],0)
   self.assertEqual(db.execute('SELECT count(*) n FROM account_ticket_legs').fetchone()['n'],0)
