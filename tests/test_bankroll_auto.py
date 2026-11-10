import copy,json
from unittest.mock import patch
from test_tracking import Tracking
import accounts,tracking

class AutoBankroll(Tracking):
 def setUp(self):
  super().setUp()
  self.client.post('/api/bankroll',json={'initial':100,'risk_bps':100},headers={'X-App-Request':'1'})
 def add(self,legs=None,key='manual-1',stake='1'):
  return self.client.post('/api/bankroll/manual',json={'request_key':key,'title':'Mon combiné','stake':stake,'selections':legs or [self.leg()]},headers={'X-App-Request':'1'})
 def leg(self,event='123',market='home',odds='2.5'):
  return dict(event_id=event,league='fra.1',home_id='1',away_id='2',market=market,odds=odds)
 def state(self):return self.client.get('/api/bankroll').json
 def test_single_win_auto_and_repeat_read(self):
  self.assertEqual(self.add().status_code,200)
  self.assertEqual(self.state()['pending_cents'],100)
  self.finish();d=self.state()
  self.assertEqual((d['available_cents'],d['profit_cents'],d['pending_cents']),(10150,150,0))
  self.assertTrue(d['bets'][0]['automatic']);self.assertEqual(self.state()['available_cents'],10150)
 def test_combined_odds_and_loss(self):
  self.add([self.leg(odds='2'),self.leg('456','btts','3')],stake='1.01')
  self.finish();d=self.state();self.assertEqual(d['bets'][0]['payout_cents'],606)
  self.assertEqual(d['profit_cents'],505)
 def test_loss_zero_return(self):
  self.add([self.leg(market='away')]);self.finish();d=self.state()
  self.assertEqual((d['available_cents'],d['profit_cents']),(9900,-100))
 def test_void_leg_reduces_combined_odds(self):
  self.add([self.leg(odds='2'),self.leg('456','btts','3')])
  self.finish();cancelled=copy.deepcopy(self.info)
  cancelled['header']['competitions'][0]['status']['type']['name']='STATUS_CANCELED'
  import bankroll
  final=tracking.fixture_info(self.info);void=tracking.fixture_info(cancelled)
  with self.app.app_context():bankroll.refresh_results('u',lambda league,event,ttl: void if event=='456' else final,tracking.resolve,tracking.score)
  self.assertEqual(self.state()['bets'][0]['payout_cents'],200)
 def test_invalid_sources_keep_budget_pending(self):
  self.add();self.finish()
  with patch.object(tracking,'fixture_info',side_effect=ValueError('unavailable')):d=self.state()
  self.assertEqual(d['pending_cents'],100);self.assertEqual(d['source_errors'],1)
 def test_postponed_or_extra_time_does_not_guess(self):
  self.add();self.finish(4)
  self.assertEqual(self.state()['pending_cents'],100)
  c=self.info['header']['competitions'][0];c['status']['period']=2;c['status']['type']['name']='STATUS_POSTPONED'
  self.assertEqual(self.state()['pending_cents'],100)
 def test_duplicate_invalid_odds_and_isolation(self):
  self.add();self.add();self.assertEqual(len(self.state()['bets']),1)
  for odds in ['NaN','Infinity','-1','1','1.001']:
   self.assertEqual(self.add([self.leg(odds=odds)],key='invalid').status_code,400)
  self.assertEqual(self.add([self.leg(),self.leg()],key='duplicate').status_code,400)
  wrong=self.leg();wrong['home_id']='99'
  self.assertEqual(self.add([wrong],key='wrong').status_code,400)
  with patch.object(tracking,'current_user',return_value={'id':'other'}):self.assertFalse(self.state()['configured'])
 def test_actual_played_stake_can_exceed_advice(self):
  d=self.add(stake='20').json
  self.assertEqual(d['available_cents'],8000);self.assertEqual(d['suggested_cents'],0)
 def test_cancelled_refunded_and_cent_rounding(self):
  self.add(stake='1.01',legs=[self.leg(odds='1.5')]);self.finish()
  self.assertEqual(self.state()['bets'][0]['payout_cents'],152)
 def test_unauthorized_write(self):
  self.assertEqual(self.client.post('/api/bankroll/manual',json={}).status_code,403)
 def test_team_metadata_and_existing_ticket_backfill_preserve_payout(self):
  competitors=self.info['header']['competitions'][0]['competitors']
  competitors[0]['team'].update(displayName='Plymouth Parkway',logo='https://example.org/plymouth.png')
  competitors[1]['team'].update(displayName='Berkhamsted',logos=[{'href':'https://example.org/berkhamsted.png'}])
  self.add();leg=self.state()['bets'][0]['selections'][0]
  self.assertEqual(leg['home_name'],'Plymouth Parkway');self.assertEqual(leg['away_badge'],'https://example.org/berkhamsted.png')
  self.finish();before=self.state();self.assertEqual(before['bets'][0]['payout_cents'],250)
  with self.app.app_context(),accounts.database() as db:
   row=db.execute('SELECT id,selections FROM account_bankroll_manual').fetchone();legs=json.loads(row['selections'])
   for key in ['home_name','away_name','home_badge','away_badge','date']:legs[0].pop(key,None)
   db.execute('UPDATE account_bankroll_manual SET selections=? WHERE id=?',(json.dumps(legs),row['id']))
  after=self.state();leg=after['bets'][0]['selections'][0]
  self.assertEqual(leg['home_name'],'Plymouth Parkway');self.assertEqual(leg['home_badge'],'https://example.org/plymouth.png')
  self.assertEqual((after['available_cents'],after['bets'][0]['payout_cents']),(before['available_cents'],250))

 def scorer_leg(self):
  self.info['header']['id']='123'
  self.info['rosters']=[dict(team={'id':'1'},roster=[dict(athlete={'id':'11','displayName':'Verified scorer'})])]
  return dict(self.leg(market='anytime_scorer'),player=dict(id='11',team_id='1',name='Untrusted name'))
 def test_scorer_identity_and_win_auto_settle(self):
  self.assertEqual(self.add([self.scorer_leg()]).status_code,200)
  self.assertEqual(self.state()['bets'][0]['selections'][0]['player']['name'],'Verified scorer')
  self.finish();self.info['rosters'][0]['roster'][0]['stats']=[dict(name='appearances',value=1),dict(name='totalGoals',value=1)]
  d=self.state();self.assertEqual(d['bets'][0]['payout_cents'],250)
  self.assertEqual(d['available_cents'],10150)
  self.assertEqual(self.state()['available_cents'],10150)
 def test_scorer_missing_stats_never_uses_team_score(self):
  self.add([self.scorer_leg()]);self.finish()
  self.assertIsNone(self.state()['bets'][0]['payout_cents'])
  self.info['rosters'][0]['roster'][0]['stats']=[dict(name='appearances',value=1),dict(name='totalGoals',value=0),dict(name='ownGoals',value=1)]
  self.assertEqual(self.state()['bets'][0]['payout_cents'],0)
 def test_scorer_did_not_play_is_refunded(self):
  self.add([self.scorer_leg()]);self.finish()
  self.info['rosters'][0]['roster'][0]['stats']=[dict(name='appearances',value=0)]
  self.assertEqual(self.state()['bets'][0]['payout_cents'],100)
  self.assertEqual(self.state()['available_cents'],10000)
 def test_scorer_wrong_player_or_team_cannot_debit(self):
  for field,value in [('id','999'),('team_id','2')]:
   leg=self.scorer_leg();leg['player'][field]=value
   self.assertEqual(self.add([leg]).status_code,400)
  self.assertEqual(self.state()['available_cents'],10000)
