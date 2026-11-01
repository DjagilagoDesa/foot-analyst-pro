"""Transparent prediction journal. Local SQLite is ephemeral on default Render instances.
Configure FAP_TRACKING_DB to a persistent mounted volume for durable history.
No synthetic historical success rate.
"""
import os,sqlite3,datetime,math
DB=os.environ.get('FAP_TRACKING_DB','/tmp/fap_predictions_v43.sqlite3')
def connect():
    c=sqlite3.connect(DB,timeout=15)
    c.execute('PRAGMA busy_timeout=15000')
    c.execute("""CREATE TABLE IF NOT EXISTS predictions (fixture_id TEXT NOT NULL, league TEXT NOT NULL, kickoff TEXT NOT NULL, match_name TEXT NOT NULL, market TEXT NOT NULL, probability REAL NOT NULL, captured_at TEXT NOT NULL, status TEXT NOT NULL DEFAULT 'pending', outcome INTEGER, PRIMARY KEY(fixture_id,market))""")
    return c
def record(tickets):
    now=datetime.datetime.now(datetime.timezone.utc).isoformat()
    with connect() as c:
        for ticket in tickets:
            if ticket.get('status')!='ok':continue
            for leg in ticket['legs']:
                try:
                    kickoff=datetime.datetime.fromisoformat(leg['kickoff'].replace('Z','+00:00'))
                    if kickoff<=datetime.datetime.now(datetime.timezone.utc):continue
                    c.execute('INSERT OR IGNORE INTO predictions (fixture_id,league,kickoff,match_name,market,probability,captured_at) VALUES (?,?,?,?,?,?,?)',(str(leg['fixture_id']),str(leg['league']),leg['kickoff'],leg['match'],leg['market_key'],leg['probability_pct']/100,now))
                except (ValueError,TypeError,KeyError):continue

def evaluate(market,h,a):
    return int({'home':h>a,'away':a>h,'home_or_draw':h>=a,'away_or_draw':a>=h,'over_1_5':h+a>=2,'over_2_5':h+a>=3,'btts':h>0 and a>0}[market])
def settle(fetch,espn):
    now=datetime.datetime.now(datetime.timezone.utc)
    with connect() as c:
        rows=c.execute('SELECT fixture_id,league,kickoff,market FROM predictions WHERE status=?',('pending',)).fetchall()
        groups={}
        for fid,lg,kickoff,market in rows:
            try: dt=datetime.datetime.fromisoformat(kickoff.replace('Z','+00:00'))
            except ValueError:continue
            if dt>=now or (now-dt).days>12:continue
            groups.setdefault((lg,dt.strftime('%Y%m%d')),set()).add(fid)
        for (lg,day),ids in list(groups.items())[:20]:
            try: events=fetch(f'{espn}/{lg}/scoreboard',{'dates':day,'limit':200},ttl=300).get('events') or []
            except Exception:continue
            for e in events:
                fid=str(e.get('id',''))
                if fid not in ids:continue
                comp=(e.get('competitions') or [{}])[0]
                status=(e.get('status') or comp.get('status') or {}).get('type') or {}
                if not status.get('completed'):continue
                teams=comp.get('competitors') or []
                try:
                    def score(team):
                        s=team['score'];return int(float(s.get('value',s.get('displayValue')) if isinstance(s,dict) else s))
                    h=score(next(t for t in teams if t.get('homeAway')=='home'))
                    a=score(next(t for t in teams if t.get('homeAway')=='away'))
                    for _,_,_,market in [r for r in rows if r[0]==fid and r[1]==lg]:
                        c.execute('UPDATE predictions SET status=?,outcome=? WHERE fixture_id=? AND market=? AND status=?',('settled',evaluate(market,h,a),fid,market,'pending'))
                except (ValueError,TypeError,KeyError,StopIteration):continue

def metrics():
    with connect() as c:
        total,pending=c.execute('SELECT COUNT(*),SUM(CASE WHEN status=? THEN 1 ELSE 0 END) FROM predictions',('pending',)).fetchone()
        rows=c.execute('SELECT market,probability,outcome FROM predictions WHERE status=?',('settled',)).fetchall()
    n=len(rows)
    by_market={}
    for market,p,y in rows:
        d=by_market.setdefault(market,{'settled':0,'wins':0,'sum_probability':0.,'sum_brier':0.})
        d['settled']+=1;d['wins']+=y;d['sum_probability']+=p;d['sum_brier']+=(p-y)**2
    for d in by_market.values():
        d['win_rate_pct']=round(100*d['wins']/d['settled'],1)
        d['mean_forecast_pct']=round(100*d.pop('sum_probability')/d['settled'],1)
        d['brier_score']=round(d.pop('sum_brier')/d['settled'],4)
    return {'status':'measured' if n else 'awaiting_settled_predictions','predictions_recorded':total,'pending':pending or 0,'settled':n,'wins':sum(y for _,_,y in rows),'observed_success_pct':round(100*sum(y for _,_,y in rows)/n,1) if n else None,'brier_score':round(sum((p-y)**2 for _,p,y in rows)/n,4) if n else None,'by_market':by_market,'storage':'configured_path' if 'FAP_TRACKING_DB' in os.environ else 'ephemeral_render_filesystem','caution':'Mesure des sélections enregistrées uniquement, pas de tous les paris possibles. Les résultats ne garantissent aucune performance future.'}
