"""Account budget ledger. Only user-confirmed bets debit the balance."""
import time
from datetime import datetime
from zoneinfo import ZoneInfo
from decimal import Decimal, InvalidOperation
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
    available=config['initial_cents']+sum((b['payout_cents'] or 0)-b['stake_cents'] for b in bets)
    pending=sum(b['stake_cents'] for b in bets if b['payout_cents'] is None)
    profit=sum(b['payout_cents']-b['stake_cents'] for b in bets if b['payout_cents'] is not None)
    now=datetime.now(ZoneInfo('Europe/Paris'));day=now.replace(hour=0,minute=0,second=0,microsecond=0).timestamp()
    # Conservative cap: stakes returned during the day do not replenish the daily allowance.
    today=sum(b['stake_cents'] for b in bets if b['created_at']>=day)
    cap=config['initial_cents']*5//100
    suggested=min(available*config['risk_bps']//10000, max(0,cap-today), available)
    return dict(configured=True,initial_cents=config['initial_cents'],risk_bps=config['risk_bps'],available_cents=available,
                pending_cents=pending,profit_cents=profit,total_cents=available+pending,
                suggested_cents=max(0,suggested),daily_remaining_cents=max(0,cap-today),bets=bets)


def register(bp, user):
    @bp.get('/api/bankroll')
    def get_bankroll():
        uid=user()['id']
        with database() as db:return jsonify(snapshot(db,uid))

    @bp.post('/api/bankroll')
    def configure_bankroll():
        write_guard();uid=user(True)['id'];data=body()
        initial=cents(data.get('initial'),100)
        risk=data.get('risk_bps',100)
        if type(risk) is not int or risk not in (50,100,200):raise AccountError('Profil de mise non valide.')
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
        with database() as db:
            db.execute('SELECT * FROM account_bankroll WHERE user_id=?'+('' if db.sqlite else ' FOR UPDATE'),(uid,)).fetchone()
            state=snapshot(db,uid)
            if not state['configured']:raise AccountError('Configure ta bankroll avant de confirmer une mise.')
            if any(b['ticket_id']==tid for b in state['bets']):return jsonify(state)
            legs=db.execute('''SELECT p.starts_at,p.status FROM account_tickets t JOIN account_ticket_legs l ON l.ticket_id=t.id
              JOIN account_predictions p ON p.user_id=t.user_id AND p.event_id=l.event_id AND p.market=l.market
              WHERE t.id=? AND t.user_id=?''',(tid,uid)).fetchall()
            if not legs or any(p['starts_at']<=time.time() or p['status']!='pending' for p in legs):raise AccountError('Ticket indisponible ou déjà commencé.')
            stake=cents(data.get('stake'),1)
            if stake>state['suggested_cents']:raise AccountError('Mise supérieure au plafond actuel de ta bankroll.')
            db.execute('INSERT INTO account_bankroll_bets VALUES(?,?,?,?,?)',(uid,tid,stake,None,int(time.time())))
            return jsonify(snapshot(db,uid))

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
