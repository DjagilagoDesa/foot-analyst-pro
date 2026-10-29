import os, math, time, threading
from datetime import datetime, timezone
from collections import defaultdict
import requests
from flask import Flask, jsonify, request
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
    r = SESSION.get(url, params=params, timeout=12)
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
    for season in (now.year,now.year-1,now.year-2):
        try:
            data=fetch(f'{ESPN}/{league}/teams/{team_id}/schedule',{'season':season},ttl=1800)
            for match in parse_events(data,team_id):
                if match['id']: collected[match['id']]=match
        except (requests.RequestException,ValueError) as exc:
            errors.append(f'{season}: {type(exc).__name__}')
        if len(collected)>=limit: break
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
def root(): return jsonify({'service':'FOOT ANALYST PRO V22','status':'ok','docs':'/api/health'})

@app.get('/api/health')
def healthcheck(): return jsonify({'status':'ok','version':'22','sources':['ESPN (unofficial)'],'note':'Coverage varies by league; no guaranteed predictions'})

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

@app.get('/api/analyze')
def analyze():
    league=request.args.get('league','')
    home=request.args.get('home_id','')
    away=request.args.get('away_id','')
    if league not in LEAGUES or not home.isdigit() or not away.isdigit() or home==away:
        return jsonify({'error':'provide valid league, home_id, away_id'}),400
    hm,he=history(league,home)
    am,ae=history(league,away)
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

if __name__=='__main__':
    app.run(host='0.0.0.0',port=int(os.environ.get('PORT','10000')))
