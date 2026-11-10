import copy,json,unittest
from datetime import datetime,timedelta,timezone
from unittest.mock import patch
import daily_scorer as scorer
from accounts import database
import test_daily_opinion as dailytests

NOW=dailytests.NOW;DAY=dailytests.DAY


def payload():
 m=dailytests.result(1)['match'];home=m['home']['id'];away=m['away']['id']
 def team(tid,pid,name,goals):
  return dict(team={'id':tid},leaders=[dict(name='goalsLeaders',leaders=[dict(athlete=dict(id=pid,displayName=name,status={'type':'active'}),statistics=[dict(name='totalGoals',value=goals),dict(name='appearances',value=9)])])])
 def games(tid,other):
  return dict(team={'id':tid},events=[dict(id=tid+'past'+str(i),gameDate=(NOW-timedelta(days=i+1)).isoformat(),homeTeamId=tid,awayTeamId=other,homeTeamScore='2',awayTeamScore='1',gameResult='W') for i in range(5)])
 def roster(tid,pid):return dict(team={'id':tid},roster=[dict(athlete=dict(id=pid,displayName='Player '+pid),starter=True,active=True)])
 data=dict(header=dict(season=dict(name='Test season'),competitions=[dict(id=m['id'],date=m['date'],status=dict(type=dict(state='pre',completed=False,name='STATUS_SCHEDULED'),period=0),competitors=[dict(homeAway='home',team={'id':home}),dict(homeAway='away',team={'id':away})])]),leaders=[team(home,'11','Alpha scorer',4),team(away,'22','Beta scorer',2)],lastFiveGames=[games(home,away),games(away,home)],rosters=[roster(home,'11'),roster(away,'22')])
 return m,data


class ScorerModel(unittest.TestCase):
 def setUp(self):self.match,self.data=payload()
 def choices(self):return scorer.candidates(self.data,self.match,NOW)
 def pick(self):return self.choices()[0]
 def final(self,goals=1,apps=1,period=2):
  c=self.data['header']['competitions'][0];c['status']=dict(type=dict(state='post',completed=True,name='STATUS_FULL_TIME'),period=period)
  self.data['rosters'][0]['roster'][0]['stats']=[dict(name='totalGoals',value=goals),dict(name='appearances',value=apps),dict(name='ownGoals',value=0)]
 def settle(self,pick):
  from types import SimpleNamespace
  scorer.settle(SimpleNamespace(ESPN='source',fetch=lambda *a,**k:self.data),pick,NOW+timedelta(hours=5))
 def test_observed_stats_match_context_and_no_fake_probability(self):
  pick=self.pick();self.assertEqual(pick['player']['id'],'11');self.assertEqual(pick['basis']['goals'],4)
  self.assertIn('4 buts en 9 apparitions',pick['rationale']);self.assertIn(self.match['away']['name'],pick['rationale']);self.assertNotIn('probability',pick)
 def test_missing_invalid_and_small_statistics_not_selected(self):
  for value in (None,True,'bad',float('nan'),float('inf'),-2):
   m,data=payload();data['leaders'][0]['leaders'][0]['leaders'][0]['statistics'][0]['value']=value
   self.assertEqual([p['player']['id'] for p in scorer.candidates(data,m,NOW)],['22'])
  self.data['leaders'][0]['leaders'][0]['leaders'][0]['statistics'][1]['value']=2
  self.assertEqual([p['player']['id'] for p in self.choices()],['22'])
 def test_injury_bench_and_missing_roster_excluded(self):
  for mode in ('bench','not_listed','injury','inactive'):
   m,data=payload()
   if mode=='bench':data['rosters'][0]['roster'][0]['starter']=False
   if mode=='not_listed':data['rosters'][0]['roster'][0]['athlete']['id']='999'
   if mode=='injury':data['injuries']=[dict(team={'id':m['home']['id']},injuries=[dict(athlete={'id':'11'},status='Out')])]
   if mode=='inactive':data['leaders'][0]['leaders'][0]['leaders'][0]['athlete']['status']['type']='inactive'
   self.assertNotIn('11',[p['player']['id'] for p in scorer.candidates(data,m,NOW)],mode)
 def test_unknown_lineup_is_not_called_confirmed(self):
  self.data['rosters']=[];pick=self.pick();self.assertEqual(pick['availability'],'unconfirmed');self.assertIn('reste à confirmer',pick['rationale'])
 def test_wrong_event_team_kickoff_or_started_cannot_publish(self):
  for mode in ('id','team','date','started'):
   m,data=payload();c=data['header']['competitions'][0]
   if mode=='id':c['id']='999'
   if mode=='team':c['competitors'][0]['team']['id']='999'
   if mode=='date':c['date']=(NOW+timedelta(days=1)).isoformat()
   if mode=='started':c['status']['type']['state']='in'
   try:rows=scorer.candidates(data,m,NOW)
   except ValueError:rows=[]
   self.assertEqual(rows,[],mode)
 def test_future_or_missing_team_form_is_not_invented(self):
  self.data['lastFiveGames'][0]['events'][0]['gameDate']=(NOW+timedelta(days=1)).isoformat()
  self.assertEqual(len(self.pick()['basis']['team_form']),4)
  self.data['lastFiveGames']=[];self.assertEqual(self.choices(),[])
 def test_goals_win_no_goals_lose_and_own_goals_do_not_win(self):
  for goals,outcome in [(1,'won'),(0,'lost')]:
   self.match,self.data=payload();pick=self.pick();self.final(goals);self.data['rosters'][0]['roster'][0]['stats'].append(dict(name='ownGoals',value=1))
   self.settle(pick);self.assertEqual(pick['status'],outcome)
 def test_did_not_play_void_and_missing_stats_remain_pending(self):
  pick=self.pick();self.final(0,0);self.settle(pick);self.assertEqual(pick['status'],'void')
  self.match,self.data=payload();pick=self.pick();self.final();self.data['rosters'][0]['roster'][0]['stats']=[]
  self.settle(pick);self.assertEqual(pick['status'],'pending')
 def test_extra_time_and_rescheduled_void(self):
  pick=self.pick();self.final(2,1,4);self.settle(pick);self.assertEqual(pick['status'],'void')
  self.match,self.data=payload();pick=self.pick();self.data['header']['competitions'][0]['date']=(NOW+timedelta(days=1)).isoformat();self.settle(pick);self.assertEqual(pick['status'],'void')
 def test_matching_identity_required_before_settlement(self):
  pick=self.pick();self.final();self.data['header']['competitions'][0]['id']='999'
  with self.assertRaises(ValueError):self.settle(pick)
  self.assertEqual(pick['status'],'pending')


class DomesticScorerEvidence(unittest.TestCase):
 def setup_source(self,female=True):
  from types import SimpleNamespace
  match,data=payload();match['league']='uefa.wchampions' if female else 'eng.trophy'
  # A short cup campaign is insufficient by itself.
  for block in data['leaders']:
   for lead in block['leaders'][0]['leaders']:lead['statistics'][1]['value']=2
  team=match['home']['id'];code='esp.w.1' if female else 'eng.3'
  athlete=dict(id='11',displayName='Test scorer',gender='FEMALE' if female else 'MALE',status={'type':'active'},
    defaultTeam={'id':team},statistics={'splits':{'categories':[{'stats':[dict(name='totalGoals',value=4),dict(name='appearances',value=9)]}]}})
  roster=dict(team={'id':team},season={'year':NOW.year},athletes=[athlete])
  info=dict(team=dict(id=team,defaultLeague=dict(slug=code,name='Domestic league')))
  server=SimpleNamespace(ESPN='source',LEAGUES=['uefa.wchampions','esp.w.1','eng.trophy','eng.3'],
    fetch=lambda url,**kwargs:roster if url.endswith('/roster') else info)
  return match,data,server,roster,info
 def test_women_and_men_use_the_same_domestic_statistics_checks(self):
  for female in (True,False):
   match,data,server,source,info=self.setup_source(female)
   self.assertEqual(scorer.candidates(data,match,NOW),[])
   enriched,errors=scorer.domestic_evidence(server,data,match,[match['home']['id']],NOW)
   picks=scorer.candidates(enriched,match,NOW)
   self.assertEqual(errors,0);self.assertEqual(len(picks),1)
   self.assertEqual(picks[0]['player']['competition_category'],'women' if female else 'men')
   self.assertEqual(picks[0]['basis']['appearances'],9)
   self.assertIn('Domestic league',picks[0]['rationale'])
   self.assertEqual(data['leaders'][0]['leaders'][0]['leaders'][0]['statistics'][1]['value'],2)
 def test_wrong_team_season_category_and_player_membership_are_rejected(self):
  for mode in ('team','season','league','athlete_gender','athlete_team'):
   match,data,server,source,info=self.setup_source()
   if mode=='team':source['team']['id']='999'
   if mode=='season':source['season']['year']=NOW.year-2
   if mode=='league':info['team']['defaultLeague']['slug']='eng.3'
   if mode=='athlete_gender':source['athletes'][0]['gender']='MALE'
   if mode=='athlete_team':source['athletes'][0]['defaultTeam']['id']='999'
   enriched,_=scorer.domestic_evidence(server,data,match,[match['home']['id']],NOW)
   self.assertEqual(scorer.candidates(enriched,match,NOW),[],mode)
 def test_domestic_stats_never_override_match_availability(self):
  match,data,server,source,info=self.setup_source()
  data['rosters'][0]['roster'][0]['starter']=False
  enriched,_=scorer.domestic_evidence(server,data,match,[match['home']['id']],NOW)
  self.assertEqual(scorer.candidates(enriched,match,NOW),[])


class ScorerPersistence(unittest.TestCase):
 setUp=dailytests.PersistenceTests.setUp
 tearDown=dailytests.PersistenceTests.tearDown
 def refresh(self,now=NOW):
  match,data=payload();self.server.fetch.return_value=data
  with patch.object(self.service,'fixtures',return_value=([match],0)),patch.object(self.service,'analyze',return_value=dailytests.result(1)),patch.object(self.service,'settle_previous'):
   self.service.refresh(now)
 def test_one_scorer_frozen_and_separate_performance(self):
  self.refresh();first=self.service.read(DAY)[0];self.assertEqual(first['scorer']['player']['id'],'11');self.assertEqual(first['scorer']['published_at'],NOW.isoformat())
  with patch('daily_scorer.select',side_effect=AssertionError('Already selected')):self.refresh(NOW+timedelta(minutes=20))
  second=self.service.read(DAY)[0];self.assertEqual(first['scorer'],second['scorer']);self.assertEqual(self.service.performance(DAY)['pending'],1);self.assertEqual(self.service.scorer_performance(DAY)['pending'],1)
  second['scorer']['status']='won';second['scorers'][0]['status']='won'
  with database() as db:db.execute('UPDATE daily_opinion_boards SET payload=? WHERE day=?',(json.dumps(second),DAY))
  self.assertIsNone(self.service.performance(DAY)['success_pct']);self.assertEqual(self.service.scorer_performance(DAY)['success_pct'],100)
 def test_existing_board_enriched_immediately_without_changing_six_picks(self):
  picks=dailytests.choose(dailytests.results(),[],NOW,DAY)
  with database() as db:db.execute('INSERT INTO daily_opinion_boards(day,payload,checked_at) VALUES(?,?,?)',(DAY,json.dumps(dict(picks=picks)),int(NOW.timestamp())))
  self.refresh();board=self.service.read(DAY)[0];self.assertEqual(board['picks'],picks);self.assertIsNotNone(board['scorer'])
 def test_no_retroactive_choice_after_network_delay(self):
  match,data=payload();candidate=scorer.candidates(data,match,NOW)[0]
  with patch('daily_scorer.select',return_value=([candidate],{})),patch.object(self.service,'fixtures',return_value=([match],0)),patch.object(self.service,'analyze',return_value=None),patch.object(self.service,'settle_previous'):
   self.service.refresh(NOW+timedelta(hours=4))
  self.assertIsNone(self.service.read(DAY)[0]['scorer'])
 def test_endpoint_and_day_reset(self):
  self.refresh()
  with patch('daily_opinion.today',return_value=DAY):response=self.app.test_client().get('/api/daily-opinion')
  self.assertEqual(response.json['scorer']['player']['id'],'11');self.assertEqual(response.json['scorer_performance']['scope'],'daily_scorer_only')
  self.assertEqual(self.service.read('2026-11-02')[0],{})
 def test_old_scorer_only_board_settles_even_without_six_picks(self):
  self.refresh();board=self.service.read(DAY)[0];board['picks']=[]
  with database() as db:db.execute('UPDATE daily_opinion_boards SET payload=? WHERE day=?',(json.dumps(board),DAY))
  def settle(board,recover_odds=True):board['scorer']['status']='won'
  with patch.object(self.service,'settle',side_effect=settle):self.service.settle_previous('2026-11-20')
  self.assertEqual(self.service.read(DAY)[0]['scorer']['status'],'won')

 def test_history_pagination_and_independent_rate(self):
  self.refresh();board=self.service.read(DAY)[0]
  statuses=['won','lost','void','pending','won','lost','won']
  with database() as db:
   db.execute('DELETE FROM daily_opinion_boards')
   for i,status in enumerate(statuses):
    board['scorer']['status']=status;board['scorers'][0]['status']=status
    db.execute('INSERT INTO daily_opinion_boards(day,payload,checked_at) VALUES(?,?,?)',
      (f'2026-10-{20+i}',json.dumps(board),0))
  with patch('daily_opinion.today',return_value=DAY):
   client=self.app.test_client();first=client.get('/api/daily-opinion/scorer-history').json
   second=client.get('/api/daily-opinion/scorer-history?page=2').json
   self.assertEqual(client.get('/api/daily-opinion/scorer-history?page=bad').status_code,400)
  self.assertEqual(len(first['items']),5);self.assertTrue(first['has_more'])
  self.assertEqual(len(second['items']),2);self.assertFalse(second['has_more'])
  self.assertEqual(first['items'][0]['day'],'2026-10-26')
  self.assertEqual(first['performance']['success_pct'],60)
  self.assertEqual(first['performance']['scope'],'daily_scorer_only')

 def test_three_distinct_frozen_scorers_and_legacy_migration(self):
  import copy
  self.refresh();old=self.service.read(DAY)[0]
  legacy=copy.deepcopy(old);legacy.pop('scorers')
  with database() as db:db.execute('UPDATE daily_opinion_boards SET payload=?,checked_at=0 WHERE day=?',(json.dumps(legacy),DAY))
  pool=[]
  for pid,event in [('11','1'),('22','2'),('33','2'),('44','3'),('55','4')]:
   p=copy.deepcopy(old['scorer']);p['player']['id']=pid;p['match']['id']=event;pool.append(p)
  with patch('daily_scorer.select',return_value=(pool,{})):self.refresh(NOW+timedelta(minutes=20))
  board=self.service.read(DAY)[0]
  self.assertEqual(len(board['scorers']),3)
  self.assertEqual(board['scorers'][0],old['scorer'])
  self.assertEqual(len({p['player']['id'] for p in board['scorers']}),3)
  self.assertEqual(len({p['match']['id'] for p in board['scorers']}),3)
  for p,status in zip(board['scorers'],['won','lost','void']):p['status']=status
  with database() as db:db.execute('UPDATE daily_opinion_boards SET payload=? WHERE day=?',(json.dumps(board),DAY))
  perf=self.service.scorer_performance(DAY);self.assertEqual(perf['success_pct'],50)
  self.assertEqual(len(self.service.scorer_history(DAY)['items']),3)
  with patch('daily_scorer.select',side_effect=AssertionError('Already three')):self.refresh(NOW+timedelta(minutes=40))


class RecentPlayerEvidence(unittest.TestCase):
 def test_short_usage_reduces_ranking_and_missing_minutes_are_not_invented(self):
  match,data=payload();original=scorer.candidates(data,match,NOW)[0]
  def rows(minutes,goals=0):
   return [dict(event_id=str(i),appearances=1,goals=goals,starter=False,minutes=minutes,shots_on_target=1,penalty_goals=None) for i in range(3)]
  short=copy.deepcopy(original);full=copy.deepcopy(original)
  scorer.apply_recent(short,rows(20),NOW)
  scorer.apply_recent(full,rows(90),NOW)
  self.assertLess(short['ranking'],full['ranking'])
  self.assertIn('20 minutes',short['rationale'])
  missing=copy.deepcopy(original);scorer.apply_recent(missing,rows(None),NOW)
  self.assertIn('minutes non documentées',missing['rationale'])
  self.assertEqual(missing['basis']['penalty_role'],'unconfirmed')
  self.assertNotIn('probability',missing)
 def test_recent_goals_change_ranking_but_tiny_samples_do_not(self):
  match,data=payload();original=scorer.candidates(data,match,NOW)[0]
  def records(goals):return [dict(appearances=1,goals=goals,starter=True,minutes=None,shots_on_target=None,penalty_goals=None) for _ in range(3)]
  hot=copy.deepcopy(original);cold=copy.deepcopy(original)
  scorer.apply_recent(hot,records(1),NOW);scorer.apply_recent(cold,records(0),NOW)
  self.assertGreater(hot['ranking'],cold['ranking'])
  small=copy.deepcopy(original);scorer.apply_recent(small,records(3)[:1],NOW)
  self.assertEqual(small['ranking'],original['ranking'])
 def test_historical_identity_and_completed_state_required(self):
  match,data=payload();pid='11';tid=match['home']['id'];game=dict(id=match['id'],home_id=tid,away_id=match['away']['id'])
  c=data['header']['competitions'][0];c['date']=(NOW-timedelta(days=1)).isoformat();c['status']=dict(type=dict(state='post',completed=True,name='STATUS_FULL_TIME'),period=2)
  data['rosters'][0]['roster'][0]['stats']=[dict(name='appearances',value=1),dict(name='totalGoals',value=1),dict(name='minutesPlayed',value=75)]
  row=scorer.recent_player_match(data,game,tid,pid,NOW);self.assertEqual(row['minutes'],75)
  for mode in ('wrong_id','future','live','extra_time'):
   altered=copy.deepcopy(data);comp=altered['header']['competitions'][0]
   if mode=='wrong_id':comp['id']='999'
   if mode=='future':comp['date']=(NOW+timedelta(days=1)).isoformat()
   if mode=='live':comp['status']['type']['state']='in'
   if mode=='extra_time':comp['status']['period']=4
   self.assertIsNone(scorer.recent_player_match(altered,game,tid,pid,NOW),mode)
