import os, math, time, threading, unicodedata
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from collections import defaultdict
import requests
from flask import Flask, jsonify, request, send_from_directory
from flask_cors import CORS

app = Flask(__name__)
CORS(app, resources={r'/api/*': {'origins': '*'}})
SESSION = requests.Session()
SESSION.headers.update({'User-Agent': 'FootAnalystPro/22 (football statistics)'})
CACHE = {}
LOCK = threading.Lock()
ESPN = 'https://site.api.espn.com/apis/site/v2/sports/soccer'
LEAGUES = ['eng.1','esp.1','ita.1','ger.1','fra.1','bra.1','por.1','ned.1','usa.1','arg.1','mex.1','uefa.champions','uefa.europa']

def fetch(url, params=None, ttl=900):
    key = (url, tuple(sorted((params or {}).items())))
    with LOCK:
        item = CACHE.get(key)
        if item and time.time()-item[0] < ttl: return item[1]
    r = SESSION.get(url, params=params, timeout=(3, 5))
    r.raise_for_status()
    data = r.json()
    with LOCK:
        if len(CACHE)>600: CACHE.clear()
        CACHE[key] = (time.time(), data)
    return data

def parse_events(data, team_id=None):
    out=[]
    for e in data.get('events') or []:
        comp=(e.get('competitions') or [{}])[0]
        teams=comp.get('competitors') or []
        if len(teams)!=2: continue
        state=(comp.get('status') or e.get('status') or {}).get('type') or {}
        if not state.get('completed'): continue
        try:
            if datetime.fromisoformat(e['date'].replace('Z','+00:00')) > datetime.now(timezone.utc): continue
        except (KeyError, ValueError, TypeError): continue
        try:
            home=next(t for t in teams if t.get('homeAway')=='home')
            away=next(t for t in teams if t.get('homeAway')=='away')
            def score(t):
                s=t.get('score')
                if isinstance(s,dict): s=s.get('value',s.get('displayValue'))
                return int(float(s))
            h,a=score(home),score(away)
            hid=str(home.get('team',{}).get('id',''))
            aid=str(away.get('team',{}).get('id',''))
            if team_id and str(team_id) not in (hid,aid): continue
            out.append({'id':str(e.get('id')),'date':e.get('date'),'home_id':hid,'away_id':aid,'home':home.get('team',{}).get('displayName'),'away':away.get('team',{}).get('displayName'),'home_goals':h,'away_goals':a})
        except (ValueError,TypeError,StopIteration): continue
    return out

def history(league,team_id,limit=12):
    # ESPN team schedule: completed fixtures across current and previous seasons.
    now=datetime.now(timezone.utc)
    collected={}
    errors=[]
    with ThreadPoolExecutor(max_workers=3) as pool:
        jobs={pool.submit(fetch,f'{ESPN}/{league}/teams/{team_id}/schedule',{'season':season},1800):season
              for season in (now.year,now.year-1,now.year-2)}
        for job in as_completed(jobs):
            try:
                for match in parse_events(job.result(),team_id):
                    if match['id']: collected[match['id']]=match
            except (requests.RequestException,ValueError) as exc:
                errors.append(f'{jobs[job]}: {type(exc).__name__}')
    matches=sorted(collected.values(),key=lambda m:m.get('date') or '',reverse=True)
    return matches[:limit],errors

def summary(matches,team_id):
    goals_for=[]; goals_against=[]; wins=draws=losses=0
    for m in matches:
        is_home=m['home_id']==str(team_id)
        gf=m['home_goals'] if is_home else m['away_goals']
        ga=m['away_goals'] if is_home else m['home_goals']
        goals_for.append(gf); goals_against.append(ga)
        wins+=gf>ga; draws+=gf==ga; losses+=gf<ga
    n=len(matches)
    return {'matches':n,'wins':wins,'draws':draws,'losses':losses,'goals_for_avg':round(sum(goals_for)/n,2) if n else None,'goals_against_avg':round(sum(goals_against)/n,2) if n else None}

def poisson(k, lam): return math.exp(-lam)*lam**k/math.factorial(k)

def probabilities(home,away):
    # Transparent, simple independent Poisson baseline; not an AI or calibrated betting model.
    lh=max(.25,min(4.0,(home['goals_for_avg']+away['goals_against_avg'])/2*1.07))
    la=max(.25,min(4.0,(away['goals_for_avg']+home['goals_against_avg'])/2*.93))
    outcomes=defaultdict(float)
    for i in range(12):
        for j in range(12):
            p=poisson(i,lh)*poisson(j,la)
            outcomes['home' if i>j else 'draw' if i==j else 'away']+=p
            if i+j>=2: outcomes['over_1_5']+=p
            if i+j>=3: outcomes['over_2_5']+=p
            if i>0 and j>0: outcomes['btts']+=p
    outcomes['home_or_draw']=outcomes['home']+outcomes['draw']
    outcomes['away_or_draw']=outcomes['away']+outcomes['draw']
    return {'expected_goals':{'home':round(lh,2),'away':round(la,2)},'markets':{k:round(v*100,1) for k,v in outcomes.items()}}

@app.get('/')
def frontend():
    return send_from_directory('.', 'index.html')

@app.get('/match-analysis.js')
def frontend_analysis():
    return send_from_directory('.', 'match-analysis.js', mimetype='application/javascript')

@app.get('/manifest.webmanifest')
def frontend_manifest():
    return send_from_directory('.', 'manifest.webmanifest')

@app.get('/icon.svg')
def frontend_icon():
    return send_from_directory('.', 'icon.svg')

@app.get('/api/health')
def healthcheck(): return jsonify({'status':'ok','version':'46','sources':['ESPN (unofficial)'],'note':'Coverage varies by league; no guaranteed predictions'})

@app.get('/api/leagues')
def leagues(): return jsonify({'leagues':LEAGUES})

@app.get('/api/teams')
def teams():
    league=request.args.get('league','fra.1')
    if league not in LEAGUES: return jsonify({'error':'unsupported_league'}),400
    try:
        data=fetch(f'{ESPN}/{league}/teams',ttl=3600)
        entries=[]
        for block in data.get('sports',[]):
            for l in block.get('leagues',[]):
                for entry in l.get('teams',[]):
                    t=entry.get('team',{})
                    entries.append({'id':t.get('id'),'name':t.get('displayName'),'badge':(t.get('logos') or [{}])[0].get('href')})
        return jsonify({'league':league,'teams':entries})
    except (requests.RequestException,ValueError) as e: return jsonify({'error':'source_unavailable','detail':type(e).__name__}),502


def _normalize_team_name(value):
    return ''.join(c for c in unicodedata.normalize('NFKD', str(value or '').casefold()) if not unicodedata.combining(c))

@app.get('/api/search-teams')
def search_teams():
    q=_normalize_team_name(request.args.get('q','').strip())
    if not q: return jsonify({'teams': []})
    if len(q)>80: return jsonify({'error':'query_too_long'}),400
    def one_league(league):
        data=fetch(f'{ESPN}/{league}/teams',ttl=3600)
        output=[]
        for sport in data.get('sports',[]):
            for group in sport.get('leagues',[]):
                for entry in group.get('teams',[]):
                    team=entry.get('team',{})
                    name=team.get('displayName') or team.get('name') or ''
                    aliases=[name,team.get('shortDisplayName'),team.get('abbreviation'),team.get('location')]
                    if any(q in _normalize_team_name(a) for a in aliases if a):
                        logos=team.get('logos') or []
                        output.append({'id':team.get('id'),'name':name,'badge':logos[0].get('href') if logos else None,'league':league})
        return output
    found=[];errors=0
    with ThreadPoolExecutor(max_workers=len(LEAGUES)) as pool:
        futures=[pool.submit(one_league,lg) for lg in LEAGUES]
        for f in as_completed(futures):
            try: found.extend(f.result())
            except (requests.RequestException,ValueError,KeyError): errors+=1
    seen=set();teams=[]
    for team in sorted(found,key=lambda t:(not _normalize_team_name(t['name']).startswith(q),len(t['name']),t['name'])):
        key=(team['league'],str(team['id']))
        if key in seen:continue
        seen.add(key);teams.append(team)
    if errors==len(LEAGUES):return jsonify({'error':'sources_unavailable'}),502
    return jsonify({'teams':teams[:25],'partial':errors>0,'leagues_checked':len(LEAGUES)})

@app.get('/api/next-match')
def next_match():
    league=request.args.get('league','')
    team=request.args.get('team_id','')
    if league not in LEAGUES or not team.isdigit():
        return jsonify({'error':'invalid_team'}),400
    now=datetime.now(timezone.utc)
    candidates=[]; failures=[]
    for season in (now.year,now.year+1):
        try:
            data=fetch(f'{ESPN}/{league}/teams/{team}/schedule',{'season':season},ttl=600)
            for e in data.get('events') or []:
                try:
                    date=datetime.fromisoformat(e['date'].replace('Z','+00:00'))
                    if date < now or date > now.replace(year=now.year+1): continue
                    comp=(e.get('competitions') or [{}])[0]
                    competitors=comp.get('competitors') or []
                    if len(competitors)!=2: continue
                    home=next(c for c in competitors if c.get('homeAway')=='home')
                    away=next(c for c in competitors if c.get('homeAway')=='away')
                    ht=home.get('team') or {};at=away.get('team') or {}
                    if str(team) not in (str(ht.get('id')),str(at.get('id'))):continue
                    candidates.append({'idEvent':str(e.get('id','')),'dateEvent':date.strftime('%Y-%m-%d'),'strTime':date.strftime('%H:%M:%S'),'strHomeTeam':ht.get('displayName'),'strAwayTeam':at.get('displayName'),'strLeague':league,'strHomeTeamBadge':ht.get('logo'),'strAwayTeamBadge':at.get('logo'),'_homeId':str(ht.get('id','')),'_awayId':str(at.get('id','')),'_leagueId':league,'source':'ESPN'})
                except (KeyError,ValueError,StopIteration,TypeError):continue
        except (requests.RequestException,ValueError) as exc:failures.append(type(exc).__name__)
    if candidates:return jsonify({'events':[min(candidates,key=lambda x:(x['dateEvent'],x['strTime']))],'source':'ESPN'})
    if len(failures)==2:return jsonify({'error':'upstream_unavailable','details':failures}),502
    return jsonify({'events':[],'source':'ESPN','note':'No confirmed upcoming fixture in covered schedule'})

@app.get('/api/analyze')
def analyze():
    league=request.args.get('league','')
    home=request.args.get('home_id','')
    away=request.args.get('away_id','')
    if league not in LEAGUES or not home.isdigit() or not away.isdigit() or home==away:
        return jsonify({'error':'provide valid league, home_id, away_id'}),400
    with ThreadPoolExecutor(max_workers=2) as pool:
        hf=pool.submit(history,league,home)
        af=pool.submit(history,league,away)
        hm,he=hf.result()
        am,ae=af.result()
    hs,as_=summary(hm,home),summary(am,away)
    result={'league':league,'home_id':home,'away_id':away,'home':hs,'away':as_,'source':'ESPN unofficial API','data_quality':{'home_games':len(hm),'away_games':len(am),'source_errors':{'home':he,'away':ae}},'generated_at':datetime.now(timezone.utc).isoformat(),'disclaimer':'Statistical estimates are not certainties. Odds, injuries, lineups and xG are not included.'}
    if len(hm)<5 or len(am)<5:
        result.update({'status':'insufficient_data','message':'Fewer than five completed matches found per team; no probabilities or betting ticket generated.'})
    else:
        result.update({'status':'ok','model':'simple_poisson_baseline','prediction':probabilities(hs,as_)})
    return jsonify(result)

@app.get('/api/ticket')
def ticket():
    # Never fabricate odds. Input: league,home_id,away_id. One match at a time initially.
    with app.test_request_context('/api/analyze',query_string=request.args):
        response=analyze()
    if isinstance(response,tuple): return response
    data=response.get_json()
    if data.get('status')!='ok': return jsonify({'status':'no_selection','analysis':data})
    markets=data['prediction']['markets']
    choices=[{'market':k,'estimated_probability':v} for k,v in markets.items() if k in ('over_1_5','over_2_5','btts','home_or_draw','away_or_draw')]
    choices.sort(key=lambda c:c['estimated_probability'],reverse=True)
    return jsonify({'status':'ok','suggestions':choices[:3],'analysis':data,'warning':'No real bookmaker odds; not a verified value bet. Probabilities are model estimates, not guarantees.'})


# V29: unified server-side fixture feed to avoid browser CORS failures.
from datetime import timedelta

def _badge(t):
    logos=t.get('logos') or []
    return t.get('logo') or (logos[0].get('href') if logos else '')

def _fixture(e, league):
    comp=(e.get('competitions') or [{}])[0]
    competitors=comp.get('competitors') or []
    if len(competitors)!=2:return None
    h=next((c for c in competitors if c.get('homeAway')=='home'),None)
    a=next((c for c in competitors if c.get('homeAway')=='away'),None)
    if not h or not a:return None
    ht=h.get('team') or {};at=a.get('team') or {}
    status=comp.get('status') or e.get('status') or {}
    state=status.get('type') or {}
    def score(value):
        if isinstance(value,dict): value=value.get('displayValue',value.get('value'))
        return str(value) if value is not None else None
    return {'id':str(e.get('id','')),'league':league,'date':e.get('date'),
      'home':{'id':str(ht.get('id','')),'name':ht.get('displayName') or ht.get('name') or 'Domicile','badge':_badge(ht)},
      'away':{'id':str(at.get('id','')),'name':at.get('displayName') or at.get('name') or 'Extérieur','badge':_badge(at)},
      'state':state.get('state','pre'),'completed':bool(state.get('completed')),
      'home_score':score(h.get('score')),'away_score':score(a.get('score')),
      'status_name':state.get('name',''),'status_detail':state.get('shortDetail') or state.get('detail',''),
      'clock':status.get('displayClock',''),'period':status.get('period')}

@app.get('/api/fixtures')
def fixtures():
    day=request.args.get('date',datetime.now(timezone.utc).date().isoformat())
    try:
        d=datetime.strptime(day,'%Y-%m-%d').date()
    except ValueError:return jsonify({'error':'invalid_date'}),400
    if abs((d-datetime.now(timezone.utc).date()).days)>90:return jsonify({'error':'date_out_of_range'}),400
    selected=request.args.get('league','all')
    if selected!='all' and selected not in LEAGUES:return jsonify({'error':'invalid_league'}),400
    leagues_to_check=LEAGUES if selected=='all' else [selected]
    def load(lg):
        data=fetch(f'{ESPN}/{lg}/scoreboard',{'dates':d.strftime('%Y%m%d'),'limit':200},ttl=20 if abs((d-datetime.now(timezone.utc).date()).days)<=1 else 1800)
        return [x for e in data.get('events') or [] if (x:=_fixture(e,lg))]
    found=[];failed=[]
    with ThreadPoolExecutor(max_workers=len(leagues_to_check)) as pool:
        futures={pool.submit(load,lg):lg for lg in leagues_to_check}
        for future in as_completed(futures):
            try:found.extend(future.result())
            except (requests.RequestException,ValueError,KeyError):failed.append(futures[future])
    if len(failed)==len(leagues_to_check):return jsonify({'error':'upstream_unavailable','message':'Sources sportives temporairement indisponibles'}),503
    found.sort(key=lambda x:x.get('date') or '')
    return jsonify({'events':found,'partial':bool(failed),'failed_leagues':failed,'source':'ESPN unofficial','date':day,'updated_at':datetime.now(timezone.utc).isoformat()})

@app.get('/api/team-next')
def team_next():
    lg=request.args.get('league','');team=request.args.get('team_id','')
    if lg not in LEAGUES or not team.isdigit():return jsonify({'error':'invalid_team'}),400
    now=datetime.now(timezone.utc)
    candidates=[];failed=0
    def season_data(season):
        try:
            return fetch(f'{ESPN}/{lg}/teams/{team}/schedule',{'season':season},ttl=900)
        except (requests.RequestException,ValueError):return None
    with ThreadPoolExecutor(max_workers=3) as pool:
        schedules=list(pool.map(season_data,(now.year-1,now.year,now.year+1)))
    for data in schedules:
        if data is None:
            failed+=1
            continue
        try:
            for e in data.get('events') or []:
                try:date=datetime.fromisoformat(e['date'].replace('Z','+00:00'))
                except (ValueError,KeyError,TypeError):continue
                if date < now-timedelta(hours=4) or date > now+timedelta(days=90):continue
                f=_fixture(e,lg)
                if f and team in (f['home']['id'],f['away']['id']) and not f['completed']:candidates.append(f)
        except (requests.RequestException,ValueError):failed+=1
    if candidates:return jsonify({'event':min(candidates,key=lambda x:x['date']),'source':'ESPN unofficial'})
    if failed==3:return jsonify({'error':'upstream_unavailable'}),503
    return jsonify({'event':None,'message':'Aucun prochain match confirmé dans les 90 jours couverts'})

@app.get('/stadium.jpg')
def stadium_asset():
    return send_from_directory('.', 'stadium.jpg', mimetype='image/jpeg')

@app.get('/premium-cover.jpg')
def premium_cover_asset():
    return send_from_directory('.', 'premium-cover.jpg', mimetype='image/jpeg')


# V36: independent analysis endpoint; statistics must be supplied, never invented.
from engine import analyse as analyse_independent
@app.post('/api/analyse-statistique')
def analyse_statistique():
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        return jsonify({'error':'invalid_json'}),400
    result=analyse_independent(data)
    return jsonify(result), (400 if 'error' in result else 200)

@app.get("/stade_premium.png")
def stade_premium_v37():
    return send_from_directory(".", "stade_premium.png", mimetype="image/png")


if __name__=='__main__':
    app.run(host='0.0.0.0',port=int(os.environ.get('PORT','10000')))
