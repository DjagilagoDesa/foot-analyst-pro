import copy,json,unittest
from datetime import timedelta
from unittest.mock import patch
from scorer_odds import extract,event_url,parse_page,ScorerOdds,same_team,INDEX
from accounts import database
import test_daily_opinion as dailytests

NOW=dailytests.NOW;DAY=dailytests.DAY
URL='https://www.unibet.fr/paris-football/espagne/laliga/123/atl-madrid-vs-fc-barcelone'


def fixture():
 m=dict(id='42',date=(NOW+timedelta(hours=2)).isoformat(),home={'name':'Atlético Madrid'},away={'name':'Barcelona'})
 p=dict(status='pending',match=m,player={'id':'11','name':'Raphinha'})
 selection=dict(id=99,description='Raphinha',price='1,75',hidden=False,suspended=False,eventId=123,marketId=8,marketDesc='Buteur - 90 Mins')
 market=dict(id=8,description='Buteur',period='90 Mins',outcomes=[selection])
 event=dict(id=123,sportCode='FOOT',eventKind='MAIN',parsedStart=m['date'],opponentA={'label':'Atl. Madrid'},opponentB={'label':'FC Barcelone'},groupedMarkets=[{'markets':[market]}])
 index=[dict(**{'@type':'SportsEvent'},sport='Football',startDate=m['date'],homeTeam={'name':'Atl. Madrid'},awayTeam={'name':'FC Barcelone'},url=URL)]
 return p,event,index


class ScorerQuotes(unittest.TestCase):
 def test_exact_anytime_market_and_identity(self):
  p,e,index=fixture();self.assertEqual(event_url(index,p['match']),URL)
  index[0]['startDate']=(NOW+timedelta(hours=3)).replace(tzinfo=None).isoformat();self.assertEqual(event_url(index,p['match']),URL)
  q=extract([e],p,URL,NOW,NOW);self.assertEqual(q['price'],1.75);self.assertEqual(q['player_id'],'11');self.assertEqual(q['event_id'],'42');self.assertEqual(q['bookmaker'],'Unibet')
 def test_first_last_assist_substitute_boost_and_other_period_not_used(self):
  for label in ('1er Buteur','Dernier buteur','Buteur ou passeur','Buteur (remplaçant inclus)','Buteur boosté'):
   p,e,_=fixture();e['groupedMarkets'][0]['markets'][0]['description']=label
   self.assertIsNone(extract([e],p,URL,NOW,NOW))
  p,e,_=fixture();e['groupedMarkets'][0]['markets'][0]['period']='1ère mi-temps';self.assertIsNone(extract([e],p,URL,NOW,NOW))
 def test_hidden_suspended_stale_future_and_started_not_quoted(self):
  for field in ('hidden','suspended'):
   p,e,_=fixture();e['groupedMarkets'][0]['markets'][0]['outcomes'][0][field]=True;self.assertIsNone(extract([e],p,URL,NOW,NOW))
  for observed,current in [(NOW-timedelta(minutes=3),NOW),(NOW+timedelta(seconds=1),NOW),(NOW,NOW+timedelta(hours=3))]:
   p,e,_=fixture();self.assertIsNone(extract([e],p,URL,observed,current))
 def test_same_name_wrong_match_team_date_or_player_is_rejected(self):
  for mode in ('event','date','team','player'):
   p,e,_=fixture()
   if mode=='event':e['id']=999
   if mode=='date':e['parsedStart']=(NOW+timedelta(days=1)).isoformat()
   if mode=='team':e['opponentA']['label']='Real Madrid'
   if mode=='player':e['groupedMarkets'][0]['markets'][0]['outcomes'][0]['description']='Other Player'
   self.assertIsNone(extract([e],p,URL,NOW,NOW),mode)
  self.assertFalse(same_team('Barcelona','FC Barcelone F'))
 def test_invalid_price_and_ambiguous_duplicate_rejected(self):
  for value in (None,True,0,1,'bad','NaN','Infinity'):
   p,e,_=fixture();e['groupedMarkets'][0]['markets'][0]['outcomes'][0]['price']=value;self.assertIsNone(extract([e],p,URL,NOW,NOW))
  p,e,_=fixture();e['groupedMarkets'][0]['markets']*=2;self.assertIsNone(extract([e],p,URL,NOW,NOW))
 def test_only_official_event_url_exact_time_and_order(self):
  for mode in ('host','time','order'):
   p,e,index=fixture()
   if mode=='host':index[0]['url']=URL.replace('www.unibet.fr','attacker.example')
   if mode=='time':index[0]['startDate']=(NOW+timedelta(days=1)).isoformat()
   if mode=='order':index[0]['homeTeam'],index[0]['awayTeam']=index[0]['awayTeam'],index[0]['homeTeam']
   self.assertIsNone(event_url(index,p['match']))
 def test_cache_keeps_observation_timestamp_without_session_page_state(self):
  p,e,index=fixture();clock=[NOW];calls=[]
  def download(url):
   calls.append(url)
   return '<script id="sport-main-jsonLd" type="application/ld+json">'+json.dumps(index)+'</script>' if url==INDEX else '<script id="serverApp-state" type="application/json">'+json.dumps({'EventsDetail':{'events':[e]},'HsToken':{'value':'not-retained'}})+'</script>'
  provider=ScorerOdds(download,clock=lambda:clock[0]);q=provider.quote(p);self.assertEqual(q['price'],1.75)
  clock[0]+=timedelta(seconds=30);self.assertEqual(provider.quote(p)['observed_at'],q['observed_at']);self.assertEqual(len(calls),2)
  self.assertNotIn('not-retained',repr(provider.cache))
  clock[0]+=timedelta(minutes=3);self.assertNotEqual(provider.quote(p)['observed_at'],q['observed_at']);self.assertEqual(len(calls),4)
 def test_download_failure_is_empty_and_cached(self):
  p,_,_=fixture();calls=[]
  def failed(url):calls.append(url);raise RuntimeError('offline')
  provider=ScorerOdds(failed,clock=lambda:NOW);self.assertIsNone(provider.quote(p));self.assertIsNone(provider.quote(p));self.assertEqual(len(calls),1)


class QuotePersistence(unittest.TestCase):
 setUp=dailytests.PersistenceTests.setUp
 tearDown=dailytests.PersistenceTests.tearDown
 def seed(self,lease=0):
  p,e,_=fixture();raw=json.dumps({'picks':[],'scorer':p},ensure_ascii=False)
  with database() as db:db.execute('INSERT INTO daily_opinion_boards(day,payload,lease_until) VALUES(?,?,?)',(DAY,raw,lease))
  return extract([e],p,URL,NOW,NOW)
 def request(self,q):
  with patch('daily_opinion.today',return_value=DAY),patch('daily_opinion.datetime') as clock,patch.object(self.service.scorer_odds,'quote',return_value=q):
   clock.now.return_value=NOW
   return self.app.test_client().get('/api/daily-opinion/scorer-odds')
 def test_quote_is_archived_without_mutating_selection(self):
  q=self.seed();before=copy.deepcopy(self.service.read(DAY)[0]['scorer']);r=self.request(q);self.assertEqual(r.status_code,200);after=self.service.read(DAY)[0]['scorer']
  self.assertEqual(after.pop('odds'),q);self.assertEqual(after,before);self.assertEqual(r.headers['Cache-Control'],'no-store')
 def test_generation_lease_prevents_overwrite(self):
  q=self.seed(int(NOW.timestamp())+300);self.request(q);self.assertNotIn('odds',self.service.read(DAY)[0]['scorer'])
 def test_missing_price_is_never_replaced_by_team_odds(self):
  self.seed();r=self.request(None);self.assertIsNone(r.json['odds']);self.assertNotIn('odds',self.service.read(DAY)[0]['scorer'])
