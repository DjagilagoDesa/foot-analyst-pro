"""Google Play subscriptions. Only Google's server response can grant access."""
import hashlib
import json
import os
import re
import time
from datetime import datetime
from urllib.parse import quote

from flask import Blueprint, jsonify, request
from accounts import AccountError, body, current_user, database, public_user, rate_limit, write_guard

bp = Blueprint('billing', __name__)
PACKAGE = 'fr.footanalystpro.app'
PRODUCT = 'foot_analyst_pro_premium_monthly'
BASE_PLAN = 'monthly'
SCHEMA = '''CREATE TABLE IF NOT EXISTS account_play_subscriptions (
 token_hash TEXT PRIMARY KEY, user_id TEXT NOT NULL REFERENCES account_users(id) ON DELETE CASCADE,
 purchase_token TEXT NOT NULL, expires_at BIGINT NOT NULL, state TEXT NOT NULL,
 checked_at BIGINT NOT NULL)'''
GRANTED = {'SUBSCRIPTION_STATE_ACTIVE', 'SUBSCRIPTION_STATE_IN_GRACE_PERIOD', 'SUBSCRIPTION_STATE_CANCELED'}


def enabled():
    return os.environ.get('PLAY_BILLING_ENABLED') == 'true' and bool(os.environ.get('GOOGLE_PLAY_SERVICE_ACCOUNT_JSON'))


def account_id(user_id):
    return hashlib.sha256(('foot-analyst-pro:'+user_id).encode()).hexdigest()


def play_request(method, path, payload=None):
    if not enabled():
        raise AccountError('Le paiement Google Play est en cours de configuration.', 503, 'billing_unavailable')
    try:
        from google.oauth2 import service_account
        from google.auth.transport.requests import AuthorizedSession
        credentials = service_account.Credentials.from_service_account_info(
            json.loads(os.environ['GOOGLE_PLAY_SERVICE_ACCOUNT_JSON']),
            scopes=['https://www.googleapis.com/auth/androidpublisher'])
        with AuthorizedSession(credentials) as session:
            response = session.request(method, 'https://androidpublisher.googleapis.com/androidpublisher/v3/applications/'+PACKAGE+path,
                                       json=payload, timeout=12)
            if response.status_code in (404, 410):
                raise AccountError('Cet achat Google Play est introuvable ou expiré.', 400, 'purchase_invalid')
            if response.status_code >= 400:
                raise AccountError('Vérification Google Play indisponible. Réessaie la restauration.', 503, 'billing_unavailable')
            return response.json() if response.content else {}
    except AccountError:
        raise
    except Exception:
        # Never expose purchase tokens, Google's response or credentials in logs/errors.
        raise AccountError('Vérification Google Play indisponible. Réessaie la restauration.', 503, 'billing_unavailable') from None


def verified_purchase(user_id, token):
    data = play_request('GET', '/purchases/subscriptionsv2/tokens/'+quote(token, safe=''))
    identity = (data.get('externalAccountIdentifiers') or {}).get('obfuscatedExternalAccountId')
    if identity != account_id(user_id):
        raise AccountError('Cet abonnement est lié à un autre compte. Connecte-toi au compte utilisé pour l’achat.', 409, 'purchase_account_mismatch')
    items = [item for item in data.get('lineItems', []) if item.get('productId') == PRODUCT
             and (item.get('offerDetails') or {}).get('basePlanId') == BASE_PLAN]
    if not items:
        raise AccountError('Cet achat ne correspond pas à cet abonnement Premium.', 400, 'purchase_invalid')
    try:
        expiry = max(int(datetime.fromisoformat(item['expiryTime'].replace('Z', '+00:00')).timestamp()) for item in items)
    except (KeyError, TypeError, ValueError):
        raise AccountError('La confirmation Google Play est incomplète.', 503, 'billing_unavailable') from None
    state = data.get('subscriptionState', '')
    granted_until = expiry if state in GRANTED and expiry > int(time.time()) else 0
    return data, state, granted_until


def sync_purchase(user_id, token):
    if not isinstance(token, str) or not 1 <= len(token) <= 4096 or any(ord(c) < 33 for c in token):
        raise AccountError('Confirmation d’achat invalide.', 400, 'purchase_invalid')
    digest = hashlib.sha256(token.encode()).hexdigest()
    data, state, expiry = verified_purchase(user_id, token)
    with database() as db:
        db.execute('UPDATE account_users SET premium_until=premium_until WHERE id=?', (user_id,))
        existing = db.execute('SELECT user_id FROM account_play_subscriptions WHERE token_hash=?', (digest,)).fetchone()
        if existing and existing['user_id'] != user_id:
            raise AccountError('Cet achat appartient à un autre compte.', 409, 'purchase_account_mismatch')
        db.execute('''INSERT INTO account_play_subscriptions(token_hash,user_id,purchase_token,expires_at,state,checked_at)
            VALUES(?,?,?,?,?,?) ON CONFLICT(token_hash) DO UPDATE SET expires_at=excluded.expires_at,
            state=excluded.state,checked_at=excluded.checked_at''', (digest,user_id,token,expiry,state,int(time.time())))
        until = db.execute('SELECT MAX(expires_at) AS n FROM account_play_subscriptions WHERE user_id=?', (user_id,)).fetchone()['n'] or 0
        db.execute('UPDATE account_users SET premium_until=? WHERE id=?', (until,user_id))
    # Acknowledge after persisting the entitlement. Retry on restore if Google's call fails.
    if expiry and data.get('acknowledgementState') == 'ACKNOWLEDGEMENT_STATE_PENDING':
        play_request('POST', '/purchases/subscriptions/'+PRODUCT+'/tokens/'+quote(token, safe='')+':acknowledge', {})
    return expiry


def refresh_entitlement(user):
    with database() as db:
        rows = db.execute('SELECT purchase_token,checked_at,expires_at FROM account_play_subscriptions WHERE user_id=?', (user['id'],)).fetchall()
    if not rows:
        return user
    now = int(time.time())
    for row in rows:
        if row['checked_at'] <= now-300 or (row['expires_at'] and row['expires_at'] <= now):
            # Fail closed if Google cannot revalidate an existing paid entitlement.
            try:
                sync_purchase(user['id'], row['purchase_token'])
            except AccountError as error:
                if error.kind != 'purchase_invalid':
                    raise
                # A previously verified token can disappear after expiry/revocation.
                with database() as db:
                    db.execute('UPDATE account_play_subscriptions SET expires_at=0,checked_at=? WHERE user_id=? AND purchase_token=?', (now,user['id'],row['purchase_token']))
                    until = db.execute('SELECT MAX(expires_at) AS n FROM account_play_subscriptions WHERE user_id=?', (user['id'],)).fetchone()['n'] or 0
                    db.execute('UPDATE account_users SET premium_until=? WHERE id=?', (until,user['id']))
    with database() as db:
        fresh = db.execute('SELECT premium_until FROM account_users WHERE id=?', (user['id'],)).fetchone()
    result = dict(user)
    result['premium_until'] = fresh['premium_until']
    return result


@bp.post('/api/billing/context')
def context():
    write_guard(); user = current_user(csrf=True)
    return jsonify(available=enabled(), account_id=account_id(user['id']), product_id=PRODUCT, base_plan_id=BASE_PLAN)


@bp.post('/api/billing/verify')
def verify():
    write_guard(); user = current_user(csrf=True)
    rate_limit('billing-verify', 20, 900, user['id'])
    expiry = sync_purchase(user['id'], body().get('purchase_token'))
    with database() as db:
        fresh = db.execute('SELECT * FROM account_users WHERE id=?', (user['id'],)).fetchone()
    return jsonify(status='active' if expiry > int(time.time()) else 'inactive', user=public_user(fresh))


@bp.post('/api/billing/notifications')
def notifications():
    # Pub/Sub push is authenticated with a dedicated Google service account.
    audience = os.environ.get('PLAY_RTDN_AUDIENCE', '')
    expected_email = os.environ.get('PLAY_RTDN_SERVICE_EMAIL', '')
    header = request.headers.get('Authorization', '')
    if not audience or not expected_email or not header.startswith('Bearer '):
        raise AccountError('Notification non autorisée.', 401, 'notification_unauthorized')
    try:
        from google.oauth2 import id_token
        from google.auth.transport.requests import Request
        claims = id_token.verify_oauth2_token(header[7:], Request(), audience=audience)
        if claims.get('email') != expected_email or claims.get('email_verified') is not True:
            raise ValueError('identity')
    except Exception:
        raise AccountError('Notification non autorisée.', 401, 'notification_unauthorized') from None
    try:
        import base64
        payload = json.loads(base64.b64decode((request.get_json() or {})['message']['data'], validate=True))
    except Exception:
        raise AccountError('Notification invalide.', 400) from None
    if payload.get('packageName') != PACKAGE:
        raise AccountError('Application incorrecte.', 400)
    token = (payload.get('subscriptionNotification') or {}).get('purchaseToken')
    if token:
        digest = hashlib.sha256(token.encode()).hexdigest()
        with database() as db:
            user = db.execute('SELECT user_id FROM account_play_subscriptions WHERE token_hash=?', (digest,)).fetchone()
        if user:
            sync_purchase(user['user_id'], token)
        # Unknown purchases are linked by the authenticated app verification flow.
        # Notification bodies never grant access on their own.
    return jsonify(received=True)


def init_app(app):
    app.register_blueprint(bp)
