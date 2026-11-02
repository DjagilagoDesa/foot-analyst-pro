"""Persistent accounts, opaque sessions and atomic three-analysis trials."""
import hashlib
import json
import os
import re
import secrets
import sqlite3
import time
import uuid
from contextlib import contextmanager
from functools import wraps

from flask import Blueprint, current_app, jsonify, request
from werkzeug.security import generate_password_hash, check_password_hash

bp = Blueprint('accounts', __name__)
COOKIE = 'foot_session'
SESSION_DAYS = 14
DUMMY_HASH = generate_password_hash(secrets.token_urlsafe(24))
DAILY_OPINION_SCHEMA = '''CREATE TABLE IF NOT EXISTS daily_opinion_boards (
 day TEXT PRIMARY KEY, payload TEXT NOT NULL, checked_at BIGINT NOT NULL DEFAULT 0,
 lease_until BIGINT NOT NULL DEFAULT 0, lease_token TEXT NOT NULL DEFAULT '')'''
SCHEMA = (
    DAILY_OPINION_SCHEMA,


    '''CREATE TABLE IF NOT EXISTS account_owner_access (slot TEXT PRIMARY KEY, user_id TEXT NOT NULL)''',
    '''CREATE TABLE IF NOT EXISTS account_users (
      id TEXT PRIMARY KEY, email TEXT NOT NULL UNIQUE, nickname TEXT NOT NULL,
      password_hash TEXT NOT NULL, recovery_hash TEXT NOT NULL,
      created_at BIGINT NOT NULL, trial_used INTEGER NOT NULL DEFAULT 0,
      premium_until BIGINT NOT NULL DEFAULT 0)''',
    """CREATE TABLE IF NOT EXISTS account_predictions (
      user_id TEXT NOT NULL REFERENCES account_users(id) ON DELETE CASCADE,
      event_id TEXT NOT NULL, league TEXT NOT NULL, market TEXT NOT NULL,
      probability REAL NOT NULL, label TEXT NOT NULL, home_id TEXT NOT NULL, away_id TEXT NOT NULL,
      starts_at BIGINT NOT NULL, created_at BIGINT NOT NULL, status TEXT NOT NULL,
      home_score INTEGER, away_score INTEGER, settled_at BIGINT,
      PRIMARY KEY(user_id,event_id,market))""",
    '''CREATE TABLE IF NOT EXISTS account_sessions (
      token_hash TEXT PRIMARY KEY, user_id TEXT NOT NULL REFERENCES account_users(id) ON DELETE CASCADE,
      csrf_hash TEXT NOT NULL, expires_at BIGINT NOT NULL)''',
    '''CREATE TABLE IF NOT EXISTS account_analyses (
      id TEXT PRIMARY KEY, user_id TEXT NOT NULL REFERENCES account_users(id) ON DELETE CASCADE,
      request_key TEXT NOT NULL, label TEXT NOT NULL, status TEXT NOT NULL,
      charged INTEGER NOT NULL, created_at BIGINT NOT NULL, result TEXT,
      UNIQUE(user_id, request_key))''',
    '''CREATE TABLE IF NOT EXISTS account_rate_limits (
      key TEXT PRIMARY KEY, hits INTEGER NOT NULL, expires_at BIGINT NOT NULL)'''
)

class AccountError(Exception):
    def __init__(self, message, code=400, kind='account_error'):
        self.message, self.code, self.kind = message, code, kind


def digest(value):
    return hashlib.sha256(value.encode()).hexdigest()


def configured():
    url = current_app.config.get('ACCOUNT_DATABASE_URL', '')
    return url.startswith(('postgres://', 'postgresql://')) or (
        current_app.testing and url.startswith('sqlite:///'))


class DB:
    def __init__(self, conn, sqlite=False):
        self.conn, self.sqlite = conn, sqlite
    def execute(self, sql, params=()):
        return self.conn.execute(sql if self.sqlite else sql.replace('?', '%s'), params)


@contextmanager
def database():
    if not configured():
        raise AccountError('Les comptes sont en cours d’activation. Réessaie prochainement.', 503, 'accounts_unavailable')
    url = current_app.config['ACCOUNT_DATABASE_URL']
    if url.startswith('sqlite:///'):
        conn = sqlite3.connect(url[len('sqlite:///'):], timeout=15)
        conn.row_factory = sqlite3.Row
        conn.execute('PRAGMA foreign_keys = ON')
        conn.execute('BEGIN IMMEDIATE')
        db = DB(conn, True)
    else:
        import psycopg
        from psycopg.rows import dict_row
        conn = psycopg.connect(url, row_factory=dict_row, connect_timeout=5)
        db = DB(conn)
    try:
        yield db
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def init_schema(app):
    with app.app_context():
        with database() as db:
            for sql in SCHEMA:
                db.execute(sql)


def initialize_owner_access(app):
    # Pin the pre-existing account once. A missing account is recorded as missing;
    # later signups or recreation after deletion never acquire owner privileges.
    with app.app_context():
        if not configured():return
        with database() as db:
            for sql in SCHEMA:db.execute(sql)
            db.execute("CREATE TABLE IF NOT EXISTS account_owner_access (slot TEXT PRIMARY KEY, user_id TEXT NOT NULL)")
            existing=db.execute("SELECT user_id FROM account_owner_access WHERE slot='owner'").fetchone()
            if existing:return
            owner_email = os.environ.get('OWNER_ACCOUNT_EMAIL', '').strip().lower()
            row = db.execute("SELECT id FROM account_users WHERE lower(email)=?", (owner_email,)).fetchone() if owner_email else None
            db.execute("INSERT INTO account_owner_access(slot,user_id) VALUES('owner',?) ON CONFLICT(slot) DO NOTHING",(row['id'] if row else 'unassigned',))


def owner_access(user_id, db=None):
    if db is None:
        with database() as connection:
            return owner_access(user_id,connection)
    row=db.execute("SELECT user_id FROM account_owner_access WHERE slot='owner'").fetchone()
    return bool(row and row['user_id']!='unassigned' and row['user_id']==user_id)


def initialize_review_access(app):
    """Grant an existing review account once, pinned to its immutable user ID.

    The operator sets PLAY_REVIEW_ACCOUNT_EMAIL for this one-time grant.
    No account is created, and deleting/recreating it never repeats the grant.
    """
    email = os.environ.get('PLAY_REVIEW_ACCOUNT_EMAIL', '').strip().lower()
    if not email:
        return
    with app.app_context():
        if not configured():
            return
        with database() as db:
            existing = db.execute("SELECT user_id FROM account_owner_access WHERE slot='play-review'").fetchone()
            if existing:
                return
            user = db.execute('SELECT id FROM account_users WHERE lower(email)=?', (email,)).fetchone()
            if not user:
                app.logger.warning('Play review account must exist before access can be granted.')
                return
            pinned = db.execute("INSERT INTO account_owner_access(slot,user_id) VALUES('play-review',?) ON CONFLICT(slot) DO NOTHING RETURNING user_id", (user['id'],)).fetchone()
            if pinned:
                # Reusable review access through 2100, without owner privileges.
                db.execute('UPDATE account_users SET premium_until=? WHERE id=? AND premium_until<?', (4102444800, user['id'], 4102444800))
                app.logger.info('Play review Premium access initialized.')


def init_app(app):
    app.config.setdefault('ACCOUNT_DATABASE_URL', os.environ.get('DATABASE_URL', ''))
    app.config.setdefault('ACCOUNT_SECURE_COOKIE', True)
    app.config.setdefault('ACCOUNT_PUBLIC_ORIGIN', os.environ.get('PUBLIC_ORIGIN', 'https://foot-analyst-pro.onrender.com'))
    initialize_owner_access(app)
    initialize_review_access(app)
    app.register_blueprint(bp)
    app.register_error_handler(AccountError, lambda e: (jsonify(error=e.kind, message=e.message), e.code))

    @app.after_request
    def private_headers(response):
        if request.path.startswith(('/api/account','/api/tracking')) or request.path in ('/api/analyze', '/api/ticket', '/api/analyse-statistique', '/api/assistant'):
            response.headers['Cache-Control'] = 'no-store'
            response.headers['Vary'] = 'Cookie'
        response.headers['X-Content-Type-Options'] = 'nosniff'
        response.headers['Referrer-Policy'] = 'strict-origin-when-cross-origin'
        return response

    @app.cli.command('init-accounts')
    def init_command():
        """Create account tables in the configured PostgreSQL database."""
        init_schema(app)
        print('Account tables ready.')


def body():
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        raise AccountError('Formulaire invalide.')
    return data


def write_guard():
    # Cross-site JSON requests are rejected even when public sports APIs allow CORS.
    origin = request.headers.get('Origin')
    if origin and origin.rstrip('/') != current_app.config['ACCOUNT_PUBLIC_ORIGIN'].rstrip('/'):
        raise AccountError('Origine de la requête refusée.', 403)
    if request.headers.get('X-App-Request') != '1' or not request.is_json:
        raise AccountError('Requête non autorisée.', 403)


def rate_limit(purpose, limit=20, seconds=900, identity=None):
    now = int(time.time())
    key = digest(purpose + ':' + (identity or request.remote_addr or 'unknown') + ':' + str(now // seconds))
    with database() as db:
        db.execute('DELETE FROM account_rate_limits WHERE expires_at < ?', (now,))
        row = db.execute('''INSERT INTO account_rate_limits(key,hits,expires_at) VALUES(?,1,?)
          ON CONFLICT(key) DO UPDATE SET hits=account_rate_limits.hits+1 RETURNING hits''', (key, now + seconds)).fetchone()
    if row['hits'] > limit:
        raise AccountError('Trop de tentatives. Réessaie dans quelques minutes.', 429, 'rate_limited')


def email_value(value):
    email = str(value or '').strip().lower()
    if len(email) > 254 or not re.fullmatch(r'[^\s@]+@[^\s@]+\.[^\s@]+', email):
        raise AccountError('Saisis une adresse e-mail valide.')
    return email


def password_value(value):
    if not isinstance(value, str) or not 12 <= len(value) <= 128:
        raise AccountError('Choisis un mot de passe de 12 à 128 caractères.')
    return value


def nickname_value(value):
    name = str(value or '').strip()
    if not 2 <= len(name) <= 32 or any(ord(c) < 32 for c in name):
        raise AccountError('Le pseudo doit contenir de 2 à 32 caractères.')
    return name


def recovery_code():
    return secrets.token_urlsafe(24)


def public_user(row):
    owner=owner_access(row['id'])
    return dict(id=row['id'], email=row['email'], nickname=row['nickname'], created_at=row['created_at'],
                trial_used=row['trial_used'], trial_remaining=max(0, 3-row['trial_used']),
                premium_active=owner or row['premium_until'] > int(time.time()), premium_until=row['premium_until'], complimentary_premium=owner)


def current_user(required=True, csrf=False):
    token = request.cookies.get(COOKIE, '')
    row = None
    if token:
        with database() as db:
            row = db.execute('''SELECT u.*, s.csrf_hash FROM account_sessions s JOIN account_users u ON u.id=s.user_id
              WHERE s.token_hash=? AND s.expires_at>?''', (digest(token), int(time.time()))).fetchone()
    if row is None:
        if required:
            raise AccountError('Connecte-toi pour accéder à ton compte et à tes analyses.', 401, 'login_required')
        return None
    if csrf and not secrets.compare_digest(row['csrf_hash'], digest(request.headers.get('X-CSRF-Token', ''))):
        raise AccountError('Ta session doit être actualisée. Rouvre ton profil.', 403, 'csrf_invalid')
    return row


def session_response(user, recovery=None):
    token = secrets.token_urlsafe(32)
    csrf = digest('csrf:'+token)
    now = int(time.time())
    with database() as db:
        db.execute('DELETE FROM account_sessions WHERE expires_at<?', (now,))
        old = request.cookies.get(COOKIE)
        if old:
            db.execute('DELETE FROM account_sessions WHERE token_hash=?', (digest(old),))
        db.execute('INSERT INTO account_sessions(token_hash,user_id,csrf_hash,expires_at) VALUES(?,?,?,?)',
                   (digest(token), user['id'], digest(csrf), now+SESSION_DAYS*86400))
    result = dict(user=public_user(user), csrf_token=csrf)
    if recovery:
        result['recovery_code'] = recovery
    response = jsonify(result)
    response.set_cookie(COOKIE, token, max_age=SESSION_DAYS*86400, secure=current_app.config['ACCOUNT_SECURE_COOKIE'], httponly=True, samesite='Lax', path='/')
    return response


@bp.get('/api/account')
def me():
    if not configured():
        return jsonify(available=False, user=None, message='L’espace compte sera disponible après son activation.')
    user = current_user(False)
    if not user:
        return jsonify(available=True, user=None)
    csrf = digest('csrf:'+request.cookies[COOKIE])
    return jsonify(available=True, user=public_user(user), csrf_token=csrf)


@bp.post('/api/account/register')
def register():
    write_guard()
    rate_limit('register', 5, 3600)
    data = body()
    if data.get('accept_privacy') is not True:
        raise AccountError('Consulte et accepte les informations sur tes données personnelles.')
    email = email_value(data.get('email'))
    name = nickname_value(data.get('nickname'))
    pw = password_value(data.get('password'))
    code = recovery_code()
    user_id = str(uuid.uuid4())
    with database() as db:
        inserted = db.execute('''INSERT INTO account_users(id,email,nickname,password_hash,recovery_hash,created_at)
            VALUES(?,?,?,?,?,?) ON CONFLICT(email) DO NOTHING RETURNING id''',
            (user_id,email,name,generate_password_hash(pw),digest(code),int(time.time()))).fetchone()
        if inserted is None:
            raise AccountError('Cette adresse possède déjà un compte. Connecte-toi ou utilise ton code de récupération.', 409)
        user = db.execute('SELECT * FROM account_users WHERE id=?', (user_id,)).fetchone()
    return session_response(user, code), 201


@bp.post('/api/account/login')
def login():
    write_guard()
    rate_limit('login')
    data = body()
    email = email_value(data.get('email'))
    rate_limit('login-email', 20, 900, email)
    pw = data.get('password')
    if not isinstance(pw,str) or len(pw)>128:
        raise AccountError('Adresse e-mail ou mot de passe incorrect.',401)
    with database() as db:
        user = db.execute('SELECT * FROM account_users WHERE email=?', (email,)).fetchone()
    valid = check_password_hash(user['password_hash'] if user else DUMMY_HASH,pw)
    if not user or not valid:
        raise AccountError('Adresse e-mail ou mot de passe incorrect.',401)
    return session_response(user)


@bp.post('/api/account/logout')
def logout():
    write_guard()
    current_user(csrf=True)
    with database() as db:
        db.execute('DELETE FROM account_sessions WHERE token_hash=?', (digest(request.cookies[COOKIE]),))
    response = jsonify(ok=True)
    response.delete_cookie(COOKIE, path='/', secure=current_app.config['ACCOUNT_SECURE_COOKIE'], httponly=True, samesite='Lax')
    return response


@bp.post('/api/account/profile')
def update_profile():
    write_guard()
    user = current_user(csrf=True)
    name = nickname_value(body().get('nickname'))
    with database() as db:
        db.execute('UPDATE account_users SET nickname=? WHERE id=?', (name,user['id']))
        updated = db.execute('SELECT * FROM account_users WHERE id=?',(user['id'],)).fetchone()
    return jsonify(user=public_user(updated))


@bp.post('/api/account/password')
def change_password():
    write_guard()
    user = current_user(csrf=True)
    rate_limit('password')
    data = body()
    pw = password_value(data.get('password'))
    if not check_password_hash(user['password_hash'],str(data.get('current_password') or '')[:128]):
        raise AccountError('Mot de passe actuel incorrect.',401)
    code = recovery_code()
    with database() as db:
        db.execute('UPDATE account_users SET password_hash=?, recovery_hash=? WHERE id=?', (generate_password_hash(pw),digest(code),user['id']))
        db.execute('DELETE FROM account_sessions WHERE user_id=?',(user['id'],))
    return session_response(user,code)


@bp.post('/api/account/recover')
def recover():
    write_guard()
    rate_limit('recover',10)
    data = body()
    email = email_value(data.get('email'))
    pw = password_value(data.get('password'))
    supplied = str(data.get('recovery_code') or '')[:200]
    new_code = recovery_code()
    with database() as db:
        # Consume the code with one conditional UPDATE to prevent concurrent reuse.
        user = db.execute('''UPDATE account_users SET password_hash=?,recovery_hash=?
            WHERE email=? AND recovery_hash=? RETURNING *''', (generate_password_hash(pw),digest(new_code),email,digest(supplied))).fetchone()
        if not user:
            raise AccountError('Adresse e-mail ou code de récupération incorrect.',401)
        db.execute('DELETE FROM account_sessions WHERE user_id=?',(user['id'],))
    return session_response(user,new_code)


@bp.post('/api/account/delete')
def delete_account():
    write_guard()
    user = current_user(csrf=True)
    rate_limit('delete')
    data = body()
    if data.get('confirmation') != 'SUPPRIMER' or not check_password_hash(user['password_hash'],str(data.get('password') or '')[:128]):
        raise AccountError('Confirme avec ton mot de passe et le mot SUPPRIMER.',400)
    with database() as db:
        db.execute("UPDATE account_owner_access SET user_id='unassigned' WHERE user_id=?", (user['id'],))
        db.execute('DELETE FROM account_users WHERE id=?',(user['id'],))
    response = jsonify(ok=True)
    response.delete_cookie(COOKIE, path='/', secure=current_app.config['ACCOUNT_SECURE_COOKIE'], httponly=True, samesite='Lax')
    return response


@bp.get('/api/account/history')
def history():
    user = current_user()
    with database() as db:
        rows=db.execute('''SELECT id,label,created_at,result FROM account_analyses
             WHERE user_id=? AND status='complete' ORDER BY created_at DESC LIMIT 50''',(user['id'],)).fetchall()
    return jsonify(analyses=[dict(id=r['id'],label=r['label'],created_at=r['created_at'],result=json.loads(r['result'])) for r in rows])


@bp.get('/api/account/export')
def export_data():
    user = current_user()
    with database() as db:
        rows=db.execute("SELECT label,created_at,result FROM account_analyses WHERE user_id=? AND status='complete' ORDER BY created_at",(user['id'],)).fetchall()
    with database() as db:
        selections=[dict(r) for r in db.execute('SELECT event_id,league,market,probability,label,home_id,away_id,starts_at,created_at,status,home_score,away_score,settled_at FROM account_predictions WHERE user_id=? ORDER BY created_at',(user['id'],)).fetchall()]
    response=jsonify(profile=public_user(user),analyses=[dict(label=r['label'],created_at=r['created_at'],result=json.loads(r['result'])) for r in rows],selections=selections)
    response.headers['Content-Disposition']='attachment; filename=foot-analyst-pro-mes-donnees.json'
    return response


def reserve_analysis(user, key, label):
    now = int(time.time())
    with database() as db:
        # Lock the account for quota, deletion, and duplicate-request consistency.
        db.execute('UPDATE account_users SET trial_used=trial_used WHERE id=?',(user['id'],))
        stale=db.execute("SELECT id,charged FROM account_analyses WHERE user_id=? AND status='pending' AND created_at<?",(user['id'],now-600)).fetchall()
        if stale:
            db.execute('UPDATE account_users SET trial_used=MAX(0,trial_used-?) WHERE id=?' if db.sqlite else 'UPDATE account_users SET trial_used=GREATEST(0,trial_used-?) WHERE id=?',(sum(r['charged'] for r in stale),user['id']))
            db.execute("DELETE FROM account_analyses WHERE user_id=? AND status='pending' AND created_at<?",(user['id'],now-600))
        existing=db.execute('SELECT * FROM account_analyses WHERE user_id=? AND request_key=?',(user['id'],key)).fetchone()
        if existing:
            if existing['status']=='complete': return None,json.loads(existing['result'])
            raise AccountError('Cette analyse est déjà en cours. Réessaie dans un instant.',409,'analysis_pending')
        fresh=db.execute('SELECT * FROM account_users WHERE id=?',(user['id'],)).fetchone()
        if not fresh:
            raise AccountError('Reconnecte-toi pour continuer.',401,'login_required')
        charged=int(fresh['premium_until']<=now and not owner_access(user['id'],db))
        if charged:
            row=db.execute('UPDATE account_users SET trial_used=trial_used+1 WHERE id=? AND trial_used<3 RETURNING id',(user['id'],)).fetchone()
            if not row: raise AccountError('Tes 3 analyses offertes sont utilisées. L’abonnement Premium sera disponible prochainement.',402,'trial_exhausted')
        analysis_id=str(uuid.uuid4())
        db.execute('INSERT INTO account_analyses(id,user_id,request_key,label,status,charged,created_at) VALUES(?,?,?,?,?,?,?)',
                   (analysis_id,user['id'],key,label[:150],'pending',charged,now))
    return analysis_id,None


def finish_analysis(user_id, analysis_id, result=None):
    with database() as db:
        db.execute('UPDATE account_users SET trial_used=trial_used WHERE id=?',(user_id,))
        row=db.execute("SELECT charged FROM account_analyses WHERE id=? AND user_id=? AND status='pending'",(analysis_id,user_id)).fetchone()
        if not row: return
        if result is not None:
            db.execute("UPDATE account_analyses SET status='complete',result=? WHERE id=?",(json.dumps(result,ensure_ascii=False),analysis_id))
        else:
            db.execute('UPDATE account_users SET trial_used=trial_used-? WHERE id=?',(row['charged'],user_id))
            db.execute('DELETE FROM account_analyses WHERE id=?',(analysis_id,))


def metered_analysis(func):
    @wraps(func)
    def wrapper(*args,**kwargs):
        write_guard()
        user=current_user(csrf=True)
        rate_limit('analysis',30,900,user['id'])
        data=body()
        # Include fixture id for automatic analyses; identical manual inputs reuse a result.
        key=digest(request.path+':'+json.dumps(data,sort_keys=True,ensure_ascii=False))
        label=str(data.get('label') or (str(data.get('home','Domicile'))+' – '+str(data.get('away','Extérieur'))))
        try:
            analysis_id,cached=reserve_analysis(user,key,label)
        except AccountError as error:
            if error.kind != 'trial_exhausted':
                raise
            # Compute privately, but never expose premium results in HTML, JSON or history.
            response=current_app.make_response(func(*args,**kwargs))
            result=response.get_json(silent=True)
            if (response.status_code != 200 or not isinstance(result,dict)
                    or 'error' in result or result.get('status','ok') != 'ok'):
                return response
            return jsonify(status='locked', analysis_generated=True,
                           message='Tes 3 analyses offertes sont utilisées. Passe à Premium pour lire cette analyse.',
                           offer={'price_eur':'29.90','period':'month','page':'subscription'},
                           preview_sections=['Jugement du match','Arguments des deux équipes',
                                             'Surprises possibles','Confrontations passées','Probabilités'])
        if cached is not None:
            if cached.get('league') == 'uefa.champions' and not cached.get('domestic_context'):
                import app as server
                from champions_context import collect
                from analysis_report import domestic_section, REPORT_VERSION
                context = collect(server, cached.get('home_id'), cached.get('away_id'), cached.get('event_id', ''))
                # Enrich a still-upcoming cached fixture without using another free analysis.
                # Archived match reports keep their original pre-match context.
                if context['fixture_verified']:
                    cached['domestic_context'] = context
                    if cached.get('report'):
                        for section in cached['report']['sections']:
                            section['text'] = section['text'].replace('La forme en championnat national, le classement européen et le score cumulé', 'Le classement européen et le score cumulé')
                        cached['report']['sections'].append(domestic_section(cached))
                        cached['report']['version'] = REPORT_VERSION
                    with database() as db:
                        db.execute("UPDATE account_analyses SET result=? WHERE user_id=? AND request_key=? AND status='complete'", (json.dumps(cached,ensure_ascii=False),user['id'],key))
            if (cached.get('prediction') and cached.get('home') and cached.get('away')
                    and 'home_or_draw_and_btts' not in cached['prediction'].get('markets',{})):
                from app import probabilities
                cached['prediction']=probabilities(cached['home'],cached['away'])
                with database() as db:
                    db.execute("UPDATE account_analyses SET result=? WHERE user_id=? AND request_key=? AND status='complete'",(json.dumps(cached,ensure_ascii=False),user['id'],key))
            from analysis_report import report
            if cached.get('prediction') and not cached.get('report'):
                cached['report']=report(cached)
            return jsonify(cached)
        try:
            response=current_app.make_response(func(*args,**kwargs))
            result=response.get_json(silent=True)
            success=response.status_code==200 and isinstance(result,dict) and 'error' not in result and result.get('status','ok')=='ok'
            if success:
                result['tracking_id']=analysis_id
                response.set_data(json.dumps(result,ensure_ascii=False))
            finish_analysis(user['id'],analysis_id,result if success else None)
            return response
        except Exception:
            finish_analysis(user['id'],analysis_id)
            raise
    return wrapper








