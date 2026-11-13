"""Account budget ledger. Only user-confirmed bets debit the balance."""
import time
import json
import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from zoneinfo import ZoneInfo
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from flask import jsonify
from accounts import database, body, write_guard, AccountError


def cents(value, minimum=0, maximum=100000000):
    try:
        n=Decimal(str(value).replace(',', '.'))*100
        if not n.is_finite() or n != n.to_integral_value() or not minimum<=n<=maximum:raise ValueError()
        return int(n)
    except (InvalidOperation, ValueError, TypeError):raise AccountError('Montant en euros non valide.')


def snapshot(db, uid):
    config=db.execute('SELECT * FROM account_bankroll WHERE user_id=?',(uid,)).fetchone()
    if not config:return {'configured':False}
    bets=[dict(r) for r in db.execute('''SELECT b.*,t.title FROM account_bankroll_bets b
        JOIN account_tickets t ON t.id=b.ticket_id WHERE b.user_id=? ORDER BY b.created_at DESC,b.ticket_id''',(uid,)).fetchall()]
    manual=[dict(r) for r in db.execute('SELECT * FROM account_bankroll_manual WHERE user_id=? ORDER BY created_at DESC,id',(uid,)).fetchall()]
    for bet in manual:
        bet['ticket_id']=bet.pop('id');bet['automatic']=True
        bet['selections']=json.loads(bet['selections'])
        bets.append(bet)
    bets.sort(key=lambda b:(b['created_at'],b['ticket_id']),reverse=True)
    available=config['initial_cents']+sum((b['payout_cents'] or 0)-b['stake_cents'] for b in bets)
    pending=sum(b['stake_cents'] for b in bets if b['payout_cents'] is None)
    profit=sum(b['payout_cents']-b['stake_cents'] for b in bets if b['payout_cents'] is not None)
    now=datetime.now(ZoneInfo('Europe/Paris'));day=now.replace(hour=0,minute=0,second=0,microsecond=0).timestamp()
    # Conservative cap: stakes returned during the day do not replenish the daily allowance.
    today=sum(b['stake_cents'] for b in bets if b['created_at']>=day)
    daily_bps=max(500,config['risk_bps'])
    cap=config['initial_cents']*daily_bps//10000
    suggested=min(available*config['risk_bps']//10000, max(0,cap-today), available)
    return dict(configured=True,initial_cents=config['initial_cents'],risk_bps=config['risk_bps'],available_cents=available,
                pending_cents=pending,profit_cents=profit,total_cents=available+pending,
                suggested_cents=max(0,suggested),daily_remaining_cents=max(0,cap-today),daily_limit_bps=daily_bps,bets=bets)


def match_metadata(info):
    result={'date':info['date'].isoformat(),'match_state':info['state'],'match_status':info['name'],'match_completed':info['completed']}
    for side in ('home','away'):
        team=info[side].get('team') or {};logos=team.get('logos') or []
        result[side+'_name']=team.get('displayName') or team.get('name') or ''
        url=team.get('logo') or (logos[0].get('href') if logos else '')
        result[side+'_badge']=url if isinstance(url,str) and url.startswith('https://') else ''
        value=info[side].get('score')
        if isinstance(value,dict):value=value.get('displayValue',value.get('value'))
        if value is not None:result['live_'+side+'_score']=str(value)
    return result


def scorer_player(info, event_id, player_id, team_id):
    if info.get('event_id')!=str(event_id) or str(team_id) not in (info['home_id'],info['away_id']):
        raise AccountError('Identité du match ou de l’équipe à revérifier.')
    for block in info.get('rosters') or []:
        if str((block.get('team') or {}).get('id'))!=str(team_id):continue
        for row in block.get('roster') or []:
            athlete=row.get('athlete') or {}
            if str(athlete.get('id'))==str(player_id) and athlete.get('displayName'):
                return row
    raise AccountError('Présence du buteur ou de la buteuse non vérifiée.')


def scorer_result(info, leg):
    from daily_scorer import stats
    try:player=scorer_player(info,leg['event_id'],leg['player']['id'],leg['player']['team_id'])
    except AccountError:return None
    values=stats(player.get('stats'));apps=values.get('appearances');goals=values.get('totalGoals')
    if apps==0 and goals in (None,0):return 'void'
    if apps!=1 or goals is None or not goals.is_integer() or not 0<=goals<=20:return None
    return 'won' if goals>0 else 'lost'


def register(bp, user, source, leagues, resolve, score):
    @bp.get('/api/bankroll')
    def get_bankroll():
        uid=user()['id']
        errors=refresh_results(uid,source,resolve,score)
        with database() as db:
            state=snapshot(db,uid);state['source_errors']=errors
            return jsonify(state)

    @bp.post('/api/bankroll')
    def configure_bankroll():
        write_guard();uid=user(True)['id'];data=body()
        initial=cents(data.get('initial'),100)
        risk=data.get('risk_bps',100)
        if type(risk) is not int or risk not in (50,*range(100,1001,100)):raise AccountError('Profil de mise non valide.')
        with database() as db:
            db.execute('INSERT INTO account_bankroll(user_id,initial_cents,risk_bps) VALUES(?,?,?) ON CONFLICT(user_id) DO NOTHING',(uid,initial,risk))
            db.execute('SELECT * FROM account_bankroll WHERE user_id=?'+('' if db.sqlite else ' FOR UPDATE'),(uid,)).fetchone()
            old=snapshot(db,uid)
            if old['bets'] and initial!=old['initial_cents']:raise AccountError('Le capital de départ reste conservé après la première mise.')
            db.execute('UPDATE account_bankroll SET initial_cents=?,risk_bps=? WHERE user_id=?',(initial,risk,uid))
            return jsonify(snapshot(db,uid))

    @bp.post('/api/bankroll/bets')
    def confirm_bet():
        write_guard();uid=user(True)['id'];data=body();tid=str(data.get('ticket_id',''))
        if 'odds' in data:
            prices=data['odds']
            with database() as db:
                rows=db.execute('''SELECT p.*,t.title AS ticket_title FROM account_tickets t JOIN account_ticket_legs l ON l.ticket_id=t.id
                  JOIN account_predictions p ON p.user_id=t.user_id AND p.event_id=l.event_id AND p.market=l.market
                  WHERE t.id=? AND t.user_id=? ORDER BY l.position''',(tid,uid)).fetchall()
                old=db.execute('SELECT ticket_id FROM account_bankroll_bets WHERE user_id=? AND ticket_id=?',(uid,tid)).fetchone()
            if old:
                with database() as db:return jsonify(snapshot(db,uid))
            if not rows or not isinstance(prices,list) or len(prices)!=len(rows):raise AccountError('Renseigne la cote de chaque sélection.')
            selections=[]
            for i,r in enumerate(rows):
                leg=dict(league=r['league'],event_id=r['event_id'],home_id=r['home_id'],away_id=r['away_id'],market=r['market'],odds=prices[i])
                if r['market'].startswith('scorer:'):
                    pid=r['market'].split(':',1)[1]
                    info=source(r['league'],r['event_id'],30)
                    team=next((str(b.get('team',{}).get('id')) for b in info.get('rosters',[]) if any(str(p.get('athlete',{}).get('id'))==pid for p in b.get('roster',[]))),None)
                    if not team:raise AccountError('Présence du buteur à revérifier.')
                    leg.update(market='anytime_scorer',player=dict(id=pid,team_id=team))
                selections.append(leg)
            payload=dict(data,request_key='archive:'+tid,title=rows[0]['ticket_title'],selections=selections)
            return create_manual(uid,payload)
        with database() as db:
            db.execute('SELECT * FROM account_bankroll WHERE user_id=?'+('' if db.sqlite else ' FOR UPDATE'),(uid,)).fetchone()
            state=snapshot(db,uid)
            if not state['configured']:raise AccountError('Configure ta bankroll avant de confirmer une mise.')
            if any(b['ticket_id']==tid or b.get('request_key')=='archive:'+tid for b in state['bets']):return jsonify(state)
            legs=db.execute('''SELECT p.starts_at,p.status FROM account_tickets t JOIN account_ticket_legs l ON l.ticket_id=t.id
              JOIN account_predictions p ON p.user_id=t.user_id AND p.event_id=l.event_id AND p.market=l.market
              WHERE t.id=? AND t.user_id=?''',(tid,uid)).fetchall()
            if not legs or any(p['starts_at']<=time.time() or p['status']!='pending' for p in legs):raise AccountError('Ticket indisponible ou déjà commencé.')
            stake=cents(data.get('stake'),1)
            if stake>state['suggested_cents']:raise AccountError('Mise supérieure au plafond actuel de ta bankroll.')
            db.execute('INSERT INTO account_bankroll_bets VALUES(?,?,?,?,?)',(uid,tid,stake,None,int(time.time())))
            return jsonify(snapshot(db,uid))

    def create_manual(uid,data):
        from tracking import MARKETS
        key=data.get('request_key');rows=data.get('selections');title=data.get('title','Mon pari')
        if not isinstance(key,str) or not 1<=len(key)<=100:raise AccountError('Identifiant de saisie non valide.')
        if not isinstance(title,str) or not 1<=len(title.strip())<=100:raise AccountError('Nom du ticket non valide.')
        stake=cents(data.get('stake'),1)
        with database() as db:
            previous=db.execute('SELECT id FROM account_bankroll_manual WHERE user_id=? AND request_key=?',(uid,key)).fetchone()
            if previous:return jsonify(snapshot(db,uid))
        if not isinstance(rows,list) or not 1<=len(rows)<=8:raise AccountError('Ajoute de 1 à 8 matchs.')
        seen=set();selections=[];potential=Decimal(stake)
        for row in rows:
            if not isinstance(row,dict):raise AccountError('Sélection non valide.')
            league=row.get('league');event=str(row.get('event_id',''));market=row.get('market')
            if not isinstance(league,str) or league not in leagues or not event.isdigit() or not isinstance(market,str) or market not in MARKETS|{'anytime_scorer'}:raise AccountError('Match ou pronostic non pris en charge.')
            if (league,event) in seen:raise AccountError('Un même match ne peut être ajouté deux fois au combiné.')
            seen.add((league,event))
            try:
                odds=Decimal(str(row.get('odds','')).replace(',','.'))
                if not odds.is_finite() or not Decimal('1')<odds<=10000 or odds!=odds.quantize(Decimal('.01')):raise ValueError()
            except (InvalidOperation,ValueError):raise AccountError('Cote non valide : exemple 1,85.')
            try:info=source(league,event,30)
            except Exception:raise AccountError('Vérification du match indisponible. Réessaie.',503)
            if info['home_id']!=str(row.get('home_id')) or info['away_id']!=str(row.get('away_id')):raise AccountError('Les équipes du match ne correspondent pas.')
            if info['completed'] or info['state'] not in ('pre','in') or any(x in info['name'] for x in ('CANCEL','ABANDON','POSTPON','SUSPEND')):raise AccountError('Ce match ne peut plus être ajouté.')
            player=None
            if market=='anytime_scorer':
                supplied=row.get('player') or {}
                if not isinstance(supplied,dict) or not str(supplied.get('id','')).isdigit():raise AccountError('Buteur ou buteuse non valide.')
                verified=scorer_player(info,event,supplied['id'],str(supplied.get('team_id','')))
                player=dict(id=str(supplied['id']),team_id=str(supplied['team_id']),name=verified['athlete']['displayName'])
            label=info['home'].get('team',{}).get('displayName') or info['home'].get('team',{}).get('name') or info['home_id']
            label+=' – '+(info['away'].get('team',{}).get('displayName') or info['away'].get('team',{}).get('name') or info['away_id'])
            selections.append(dict(league=league,event_id=event,home_id=info['home_id'],away_id=info['away_id'],label=label,market=market,odds=str(odds),status='pending',**match_metadata(info),bookmaker=str(row.get('bookmaker',''))[:100],automatic_odds=row.get('automatic_odds') is True))
            if player:selections[-1]['player']=player
            potential*=odds
        if potential>1000000000000:raise AccountError('Retour potentiel trop élevé.')
        with database() as db:
            db.execute('SELECT * FROM account_bankroll WHERE user_id=?'+('' if db.sqlite else ' FOR UPDATE'),(uid,)).fetchone()
            previous=db.execute('SELECT id FROM account_bankroll_manual WHERE user_id=? AND request_key=?',(uid,key)).fetchone()
            if previous:return jsonify(snapshot(db,uid))
            state=snapshot(db,uid)
            if not state['configured']:raise AccountError('Configure ta bankroll avant d’ajouter un pari.')
            if stake>state['available_cents']:raise AccountError('Solde disponible insuffisant.')
            # These are bets already played: record their actual stake, even above the suggested limit.
            db.execute('INSERT INTO account_bankroll_manual VALUES(?,?,?,?,?,?,?,?)',(uuid.uuid4().hex,uid,key,title.strip(),stake,None,int(time.time()),json.dumps(selections)))
            return jsonify(snapshot(db,uid))

    @bp.post('/api/bankroll/manual')
    def add_manual():
        write_guard();uid=user(True)['id']
        return create_manual(uid,body())

    @bp.post('/api/bankroll/settle')
    def settle_bet():
        write_guard();uid=user(True)['id'];data=body();tid=str(data.get('ticket_id',''));payout=cents(data.get('payout'))
        with database() as db:
            db.execute('SELECT * FROM account_bankroll WHERE user_id=?'+('' if db.sqlite else ' FOR UPDATE'),(uid,)).fetchone()
            bet=db.execute('SELECT * FROM account_bankroll_bets WHERE user_id=? AND ticket_id=?',(uid,tid)).fetchone()
            if not bet:raise AccountError('Mise introuvable.',404)
            if bet['payout_cents'] is None:
                db.execute('UPDATE account_bankroll_bets SET payout_cents=? WHERE user_id=? AND ticket_id=? AND payout_cents IS NULL',(payout,uid,tid))
            return jsonify(snapshot(db,uid))



def refresh_results(uid,source,resolve,score):
    """Fetch without a DB lock; settle once after locking the account ledger."""
    with database() as db:
        pending=[dict(r) for r in db.execute('SELECT id,selections FROM account_bankroll_manual WHERE user_id=? ORDER BY CASE WHEN payout_cents IS NULL THEN 0 ELSE 1 END,created_at DESC LIMIT 60',(uid,)).fetchall()]
    events={}
    for row in pending:
        for leg in json.loads(row['selections']):
            if leg['status']=='pending' or 'home_name' not in leg:events[(leg['league'],leg['event_id'])]=None
    chosen=list(events)[:30];errors=0;results={}
    with ThreadPoolExecutor(max_workers=5) as pool:
        jobs={key:pool.submit(source,*key,60) for key in chosen}
        for key,job in jobs.items():
            try:results[key]=job.result()
            except Exception:errors+=1
    if not pending:return errors
    with database() as db:
        db.execute('SELECT * FROM account_bankroll WHERE user_id=?'+('' if db.sqlite else ' FOR UPDATE'),(uid,)).fetchone()
        for item in pending:
            row=db.execute('SELECT * FROM account_bankroll_manual WHERE id=? AND user_id=?',(item['id'],uid)).fetchone()
            if not row:continue
            legs=json.loads(row['selections'])
            for leg in legs:
                info=results.get((leg['league'],leg['event_id']))
                if not info:continue
                try:
                    if leg['home_id']!=info['home_id'] or leg['away_id']!=info['away_id']:continue
                    leg.update(match_metadata(info))
                    if leg['status']!='pending':continue
                    # A postponed or abandoned match needs bookmaker-specific handling; keep it pending.
                    if any(x in info['name'] for x in ('ABANDON','POSTPON','SUSPEND')):continue
                    void='CANCEL' in info['name']
                    if not void and not (info['state']=='post' and info['completed']):continue
                    if not void and ((info['period'] is not None and int(info['period'])>2) or any(x in info['name'] for x in ('EXTRA','PENALT','FINAL_AET'))):continue
                    if void:leg['status']='void'
                    else:
                        hg,ag=score(info['home'].get('score')),score(info['away'].get('score'))
                        if leg['market']=='anytime_scorer':
                            outcome=scorer_result(info,leg)
                            if outcome is None:continue
                        else:outcome='won' if resolve(leg['market'],hg,ag) else 'lost'
                        leg.update(status=outcome,home_score=hg,away_score=ag)
                except (ValueError,TypeError,KeyError):errors+=1
            payout=row['payout_cents']
            if payout is None and any(l['status']=='lost' for l in legs):payout=0
            elif payout is None and all(l['status'] in ('won','void') for l in legs):
                value=Decimal(row['stake_cents'])
                for leg in legs:
                    if leg['status']=='won':value*=Decimal(leg['odds'])
                payout=int(value.quantize(Decimal('1'),rounding=ROUND_HALF_UP))
            db.execute('UPDATE account_bankroll_manual SET selections=?,payout_cents=? WHERE id=? AND user_id=?',(json.dumps(legs),payout,row['id'],uid))
    return errors
