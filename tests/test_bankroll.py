"""Real money ledger boundaries, idempotency and private account isolation."""
from test_ticket_archive import TicketArchive
from unittest.mock import patch
import accounts,tracking

class Bankroll(TicketArchive):
 def request(self,path,data):return self.client.post('/api/bankroll'+path,json=data,headers={'X-App-Request':'1'})
 def setup_budget(self):
  self.prepare();self.tid=self.make().json['id']
  return self.request('',{'initial':'100','risk_bps':100})
 def test_budget_stake_return_and_idempotency(self):
  d=self.setup_budget().json;self.assertEqual(d['suggested_cents'],100)
  data={'ticket_id':self.tid,'stake':'1'}
  d=self.request('/bets',data).json;self.assertEqual((d['available_cents'],d['pending_cents']),(9900,100))
  self.assertEqual(self.request('/bets',data).json['available_cents'],9900)
  d=self.request('/settle',{'ticket_id':self.tid,'payout':'2.50'}).json
  self.assertEqual((d['available_cents'],d['profit_cents'],d['pending_cents']),(10150,150,0))
  self.assertEqual(self.request('/settle',{'ticket_id':self.tid,'payout':'999'}).json['available_cents'],10150)
 def test_invalid_amounts_cap_and_initial_preserved(self):
  self.setup_budget()
  for n in ('NaN','Infinity','-1','0','0.001','1.01',True):
   self.assertEqual(self.request('/bets',{'ticket_id':self.tid,'stake':n}).status_code,400,n)
  self.assertEqual(self.request('/bets',{'ticket_id':self.tid,'stake':'1'}).status_code,200)
  self.assertEqual(self.request('',{'initial':200,'risk_bps':100}).status_code,400)
  self.assertEqual(self.request('',{'initial':100,'risk_bps':200}).status_code,200)
 def test_private_and_csrf(self):
  self.setup_budget()
  self.assertEqual(self.client.post('/api/bankroll',json={'initial':100}).status_code,403)
  with patch.object(tracking,'current_user',return_value={'id':'other'}):
   self.assertFalse(self.client.get('/api/bankroll').json['configured'])
   self.request('',{'initial':100})
   self.assertEqual(self.request('/bets',{'ticket_id':self.tid,'stake':'1'}).status_code,400)
 def test_loss_and_zero_budget(self):
  self.setup_budget();self.request('/bets',{'ticket_id':self.tid,'stake':'1'})
  d=self.request('/settle',{'ticket_id':self.tid,'payout':0}).json
  self.assertEqual((d['available_cents'],d['profit_cents']),(9900,-100))
 def test_started_ticket_cannot_be_added(self):
  self.setup_budget()
  with self.app.app_context(),accounts.database() as db:db.execute('UPDATE account_predictions SET starts_at=1')
  self.assertEqual(self.request('/bets',{'ticket_id':self.tid,'stake':'1'}).status_code,400)
 def test_daily_cap_shared_by_all_tickets(self):
  self.setup_budget()
  with self.app.app_context(),accounts.database() as db:
   for i in range(5):
    tid='cap'+str(i);db.execute('INSERT INTO account_tickets VALUES(?,?,?,?,?)',(tid,'u',tid,tid,1))
    db.execute('INSERT INTO account_bankroll_bets VALUES(?,?,?,?,?)',('u',tid,100,500,__import__('time').time()))
  self.assertEqual(self.client.get('/api/bankroll').json['suggested_cents'],0)
  self.assertEqual(self.request('/bets',{'ticket_id':self.tid,'stake':'0.01'}).status_code,400)

 def test_risk_up_to_ten_percent_and_daily_limit(self):
  self.setup_budget()
  for percent in range(1,11):
   r=self.request('',{'initial':100,'risk_bps':percent*100})
   self.assertEqual(r.status_code,200)
   self.assertEqual(r.json['suggested_cents'],percent*100)
   self.assertEqual(r.json['daily_remaining_cents'],max(5,percent)*100)
  self.assertEqual(self.request('',{'initial':100,'risk_bps':1100}).status_code,400)
  self.assertEqual(self.request('/bets',{'ticket_id':self.tid,'stake':'10.01'}).status_code,400)
  d=self.request('/bets',{'ticket_id':self.tid,'stake':'10'}).json
  self.assertEqual((d['available_cents'],d['pending_cents'],d['daily_remaining_cents']),(9000,1000,0))
