"""Private persistent pre-match selections; scores verified from the sports source."""
import json
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
import requests
from flask import Blueprint, jsonify, request
from accounts import database, current_user, write_guard, body, rate_limit, AccountError

MARKETS={'home','away','draw','home_or_draw','away_or_draw','over_1_5','over_2_5','under_1_5','under_2_5','btts','btts_no'}

MARKETS.update(side+'_and_'+goal for side in ('home_or_draw','away_or_draw') for goal in ('btts','btts_no','over_1_5','over_2_5','under_1_5','under_2_5'))

def resolve(market,home,away):
    outcomes={'home':home>away,'away':away>home,'draw':home==away,
            'home_or_draw':home>=away,'away_or_draw':away>=home,
            'over_1_5':home+away>=2,'over_2_5':home+away>=3,'under_1_5':home+away<2,'under_2_5':home+away<3,'btts_no':home==0 or away==0,'btts':home>0 and away>0}
    return all(outcomes[part] for part in market.split('_and_'))


def fixture_info(data):
    header=data.get('header') or {}
    comp=(header.get('competitions') or [None])[0]
    if not isinstance(comp,dict):raise ValueError('missing_competition')
    teams=comp.get('competitors') or []
    home=next(c for c in teams if c.get('homeAway')=='home')
    away=next(c for c in teams if c.get('homeAway')=='away')
    status=comp.get('status') or {}
    kind=status.get('type') or {}
    date=datetime.fromisoformat(comp['date'].replace('Z','+00:00'))
    if date.tzinfo is None:raise ValueError('missing_timezone')
    return {'home_id':str(home['team']['id']),'away_id':str(away['team']['id']),
            'date':date,'home':home,'away':away,'state':kind.get('state'),
            'completed':bool(kind.get('completed')),'name':kind.get('name','').upper(),
            'period':status.get('period')}


def score(value):
    if isinstance(value,dict):value=value.get('value',value.get('displayValue'))
    n=int(str(value))
    if n<0:raise ValueError('negative_score')
    return n


def init_app(app, fetch, base, leagues):
    bp=Blueprint('tracking',__name__)
    def source(league,event,ttl):
        return fixture_info(fetch(f'{base}/{league}/summary',{'event':event},ttl=ttl))

    @bp.post('/api/tracking/record')
    def record():
        write_guard();user=current_user(csrf=True);rate_limit('tracking-write',60,900,user['id'])
        data=body();analysis_id=str(data.get('analysis_id',''));market=data.get('market')
        if market not in MARKETS or not analysis_id:raise AccountError('Sélection non valide.')
        with database() as db:
            row=db.execute("SELECT result,created_at FROM account_analyses WHERE id=? AND user_id=? AND status='complete'",(analysis_id,user['id'])).fetchone()
        if not row:raise AccountError('Analyse enregistrée introuvable.',404)
        result=json.loads(row['result']);event=str(result.get('event_id',''));league=result.get('league')
        probability=(result.get('prediction') or {}).get('markets',{}).get(market)
        complements={'under_1_5':'over_1_5','under_2_5':'over_2_5','btts_no':'btts'}
        if probability is None and market in complements:
            opposite=(result.get('prediction') or {}).get('markets',{}).get(complements[market])
            if isinstance(opposite,(int,float)):probability=round(100-opposite,1)
        if league not in leagues or not event.isdigit() or not isinstance(probability,(int,float)):
            raise AccountError('Cette analyse ne contient pas de rencontre vérifiable.',400)
        with database() as db:
            existing=db.execute('SELECT status FROM account_predictions WHERE user_id=? AND event_id=? AND market=?',(user['id'],event,market)).fetchone()
        if existing:return jsonify(status='recorded')
        try:info=source(league,event,30)
        except (requests.RequestException,ValueError,KeyError,TypeError,StopIteration):
            raise AccountError('Impossible de vérifier la rencontre : sélection non enregistrée.',503)
        now=int(time.time())
        if (info['home_id']!=str(result['home_id']) or info['away_id']!=str(result['away_id'])):
            raise AccountError('La rencontre ne correspond pas à l’analyse.',400)
        if info['state']!='pre' or info['date'].timestamp()<=now or info['completed']:
            raise AccountError('Le match a commencé : aucune prédiction rétroactive ajoutée.',409)
        if any(x in info['name'] for x in ('POSTPONED','CANCEL','ABANDON','SUSPEND')):
            raise AccountError('Rencontre reportée ou annulée.',409)
        with database() as db:
            db.execute('''INSERT INTO account_predictions(user_id,event_id,league,market,probability,label,home_id,away_id,starts_at,created_at,status)
              VALUES(?,?,?,?,?,?,?,?,?,?,'pending') ON CONFLICT(user_id,event_id,market) DO NOTHING''',
              (user['id'],event,league,market,probability,result.get('home_name','Domicile')+' – '+result.get('away_name','Extérieur'),info['home_id'],info['away_id'],int(info['date'].timestamp()),now))
        return jsonify(status='recorded')

    @bp.get('/api/tracking/performance')
    def performance():
        user=current_user();rate_limit('tracking-read',20,900,user['id']);errors=0
        with database() as db:
            pending=db.execute("SELECT DISTINCT event_id,league FROM account_predictions WHERE user_id=? AND status='pending' AND starts_at<? ORDER BY event_id LIMIT 20",(user['id'],int(time.time()))).fetchall()
        with ThreadPoolExecutor(max_workers=6) as pool:
            jobs=[(row,pool.submit(source,row['league'],row['event_id'],60)) for row in pending]
        for row,job in jobs:
            try:
                info=job.result()
                void=any(x in info['name'] for x in ('CANCEL','ABANDON'))
                if not void and not (info['state']=='post' and info['completed']):continue
                # Ordinary goal markets settle at 90 minutes; do not count ET/penalty totals.
                if info['period'] is not None and int(info['period'])>2:void=True
                if any(x in info['name'] for x in ('EXTRA_TIME','PENALT','FINAL_AET','AFTER_EXTRA')):void=True
                hg=ag=None
                if not void:hg,ag=score(info['home'].get('score')),score(info['away'].get('score'))
                with database() as db:
                    picks=db.execute("SELECT market,home_id,away_id FROM account_predictions WHERE user_id=? AND event_id=? AND status='pending'",(user['id'],row['event_id'])).fetchall()
                    for pick in picks:
                        if pick['home_id']!=info['home_id'] or pick['away_id']!=info['away_id']:continue
                        status='void' if void else 'won' if resolve(pick['market'],hg,ag) else 'lost'
                        db.execute("UPDATE account_predictions SET status=?,home_score=?,away_score=?,settled_at=? WHERE user_id=? AND event_id=? AND market=? AND status='pending'",(status,hg,ag,int(time.time()),user['id'],row['event_id'],pick['market']))
            except (requests.RequestException,ValueError,KeyError,TypeError,StopIteration):errors+=1
        with database() as db:
            counts={r['status']:r['n'] for r in db.execute('SELECT status,count(*) AS n FROM account_predictions WHERE user_id=? GROUP BY status',(user['id'],)).fetchall()}
            recent=[dict(r) for r in db.execute('SELECT event_id,label,market,probability,status,home_score,away_score,starts_at FROM account_predictions WHERE user_id=? ORDER BY created_at DESC,event_id,market LIMIT 100',(user['id'],)).fetchall()]
        won,lost=counts.get('won',0),counts.get('lost',0)
        return jsonify(won=won,lost=lost,pending=counts.get('pending',0),void=counts.get('void',0),
                       success_pct=round(100*won/(won+lost),1) if won+lost else None,
                       scope='personal_selections_only',
                       total=sum(counts.values()),recent=recent,source_errors=errors,
                       note='Sélections personnelles enregistrées avant le coup d’envoi. Réussite = gagnés / (gagnés + perdus). En attente et annulées exclues du pourcentage. Chaque marché est compté une fois par match et par compte ; les sélections peuvent être corrélées. Les anciens paris non enregistrés ne sont pas reconstitués.')
    app.register_blueprint(bp)


