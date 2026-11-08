"""Observed Unibet anytime-scorer prices from its public football pages.

Match identity, kickoff, exact player name and the 90-minute anytime market are
verified. No first-scorer, assists, boosted or inferred price is substituted.
"""
import json
import math
import re
import threading
import unicodedata
from datetime import datetime, timezone
from html.parser import HTMLParser
from urllib.parse import urlparse
from zoneinfo import ZoneInfo

ORIGIN='https://www.unibet.fr'
INDEX=ORIGIN+'/paris-football'
MAX_AGE=120


def instant(value):
    date=datetime.fromisoformat(value.replace('Z','+00:00'))
    return date.replace(tzinfo=ZoneInfo('Europe/Paris')) if date.tzinfo is None else date


def normalize(value):
    return re.sub('[^a-z0-9]','',unicodedata.normalize('NFKD',str(value)).encode('ascii','ignore').decode().lower())


# Explicit club-name translations; no fuzzy surname or youth/women-team matching.
ALIASES=[('Barcelona','FC Barcelone','FC Barcelona'),('Atlético Madrid','Atl. Madrid','Atletico de Madrid'),
 ('Paris Saint-Germain','Paris SG','PSG'),('Bayern Munich','Bayern München'),('Juventus','Juventus Turin'),
 ('Internazionale','Inter Milan'),('AC Milan','Milan AC'),('AS Roma','AS Rome'),('Napoli','Naples'),
 ('Sevilla','FC Séville'),('Real Betis','Betis Séville'),('Real Sociedad','Real Sociedad San Sebastian'),
 ('Borussia Dortmund','Dortmund'),('Bayer Leverkusen','Leverkusen'),('Sporting CP','Sporting Portugal'),
 ('Benfica','Benfica Lisbonne'),('FC Porto','Porto'),('Lyon','Lyon OL'),('Marseille','Marseille OM')]


def same_team(a,b):
    a,b=normalize(a),normalize(b)
    return bool(a and b and (a==b or any({a,b} <= {normalize(n) for n in group} for group in ALIASES)))


class Scripts(HTMLParser):
    def __init__(self):super().__init__();self.nodes={};self.key=None;self.chunks=[]
    def handle_starttag(self,tag,attrs):
        if tag=='script':
            self.key=dict(attrs).get('id');self.chunks=[]
    def handle_data(self,data):
        if self.key:self.chunks.append(data)
    def handle_endtag(self,tag):
        if tag=='script' and self.key:
            if self.key in ('sport-main-jsonLd','serverApp-state'):self.nodes[self.key]=''.join(self.chunks)
            self.key=None;self.chunks=[]


def parse_page(text,kind):
    if not isinstance(text,str) or len(text)>6000000:raise ValueError('invalid_page')
    parser=Scripts();parser.feed(text)
    # Retain only sports data; do not keep session or account-related page state.
    if kind=='index':return json.loads(parser.nodes.get('sport-main-jsonLd','[]'))
    state=json.loads(parser.nodes.get('serverApp-state','{}'))
    return (state.get('EventsDetail') or {}).get('events') or []


def safe_url(value):
    p=urlparse(value)
    return p.scheme=='https' and p.netloc=='www.unibet.fr' and bool(re.fullmatch(r'/paris-football/[^/]+/[^/]+/\d+/[a-z0-9-]+/?',p.path)) and not p.query and not p.fragment


def event_url(events,match):
    found=[]
    for event in events if isinstance(events,list) else []:
        try:
            if event.get('@type')!='SportsEvent' or event.get('sport')!='Football':continue
            if not same_team(event['homeTeam']['name'],match['home']['name']) or not same_team(event['awayTeam']['name'],match['away']['name']):continue
            if instant(event['startDate'])!=instant(match['date']):continue
            if safe_url(event['url']):found.append(event['url'])
        except (KeyError,ValueError,TypeError,AttributeError):continue
    return next(iter(set(found))) if len(set(found))==1 else None


def extract(events,pick,url,observed,now):
    if not safe_url(url) or not 0<=(now-observed).total_seconds()<=MAX_AGE:return None
    match=pick['match'];kickoff=instant(match['date'])
    if pick.get('status')!='pending' or kickoff<=now or observed>=kickoff:return None
    candidates=[]
    expected_id=urlparse(url).path.rstrip('/').split('/')[-2]
    for event in events if isinstance(events,list) else []:
        try:
            if str(event['id'])!=expected_id or event.get('sportCode')!='FOOT' or event.get('eventKind')!='MAIN':continue
            if instant(event['parsedStart'])!=kickoff:continue
            if not same_team(event['opponentA']['label'],match['home']['name']) or not same_team(event['opponentB']['label'],match['away']['name']):continue
            for group in event.get('groupedMarkets') or []:
                for market in group.get('markets') or []:
                    if market.get('description')!='Buteur' or market.get('period')!='90 Mins' or market.get('suspended') is True or market.get('hidden') is True:continue
                    for outcome in market.get('outcomes') or []:
                        if normalize(outcome.get('description'))!=normalize(pick['player']['name']):continue
                        if outcome.get('hidden') is not False or outcome.get('suspended') is not False:continue
                        if str(outcome.get('eventId'))!=expected_id or outcome.get('marketId')!=market.get('id') or outcome.get('marketDesc')!='Buteur - 90 Mins':continue
                        raw=outcome.get('price')
                        if isinstance(raw,bool):continue
                        try:price=float(str(raw).replace(',','.'))
                        except (ValueError,TypeError):continue
                        if not math.isfinite(price) or not 1<price<=10000:continue
                        candidates.append(dict(price=price,bookmaker='Unibet',market='anytime_scorer',
                            event_id=str(match['id']),player_id=pick['player']['id'],provider_event_id=expected_id,
                            market_id=str(market['id']),outcome_id=str(outcome['id']),
                            observed_at=observed.isoformat(),expires_at=datetime.fromtimestamp(min(observed.timestamp()+MAX_AGE,kickoff.timestamp()),timezone.utc).isoformat(),
                            source_url=url,kind='prematch_quote'))
        except (KeyError,ValueError,TypeError,AttributeError):continue
    # Multiple ambiguous markets/players are not guessed.
    return candidates[0] if len(candidates)==1 else None


class ScorerOdds:
    def __init__(self,download,clock=None):
        self.download=download;self.cache={};self.lock=threading.Lock()
        self.clock=clock or (lambda:datetime.now(timezone.utc))
    def page(self,url,kind,now):
        with self.lock:
            old=self.cache.get(url)
            if old and 0<=(now-old[0]).total_seconds()<MAX_AGE:return old
            try:
                text=self.download(url)
                data=parse_page(text,kind)
                observed=self.clock()
                result=(observed,data)
            except Exception:
                # Cache failures briefly too, avoiding repeated requests from every client.
                result=(self.clock(),[])
            if len(self.cache)>=32:self.cache.clear()
            self.cache[url]=result
            return result
    def quote(self,pick):
        now=self.clock()
        if not pick or pick.get('status')!='pending' or instant(pick['match']['date'])<=now:return None
        _,events=self.page(INDEX,'index',now)
        url=event_url(events,pick['match'])
        if not url:return None
        observed,events=self.page(url,'event',now)
        current=self.clock()
        return extract(events,pick,url,observed,current)
