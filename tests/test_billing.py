import time
import unittest
from unittest.mock import patch
from datetime import datetime, timezone
import accounts
import billing
import app as server
from test_accounts import AccountTests

class BillingTests(AccountTests):
    def purchase(self, uid, state='SUBSCRIPTION_STATE_ACTIVE', expiry=None, ack='ACKNOWLEDGEMENT_STATE_ACKNOWLEDGED'):
        expiry=expiry or int(time.time())+86400
        return dict(externalAccountIdentifiers={'obfuscatedExternalAccountId':billing.account_id(uid)},
                    lineItems=[dict(productId=billing.PRODUCT,expiryTime=datetime.fromtimestamp(expiry,timezone.utc).isoformat(),offerDetails={'basePlanId':'monthly'})],
                    subscriptionState=state,acknowledgementState=ack)

    def test_context_auth_csrf_and_disabled_catalog(self):
        self.assertEqual(self.post('/api/billing/context',{}).status_code,401)
        user=self.register()['user']
        response=self.post('/api/billing/context',{})
        self.assertEqual(response.json['account_id'],billing.account_id(user['id']))
        self.assertFalse(response.json['available'])
        self.assertEqual(response.headers['Cache-Control'],'no-store')
        self.assertFalse(self.client.get('/api/billing/catalog').json['purchase_available'])
        self.assertEqual(self.post('/api/billing/verify',{'purchase_token':'x'},headers={**self.headers,'X-CSRF-Token':'bad'}).status_code,403)

    def test_verified_activation_restore_and_acknowledgement(self):
        user=self.register()['user']
        data=self.purchase(user['id'],ack='ACKNOWLEDGEMENT_STATE_PENDING')
        with patch.object(billing,'play_request',side_effect=[data,{},data,{}]) as api:
            for _ in range(2):
                result=self.post('/api/billing/verify',{'purchase_token':'confirmed-token'})
                self.assertEqual(result.status_code,200,result.json)
                self.assertTrue(result.json['user']['premium_active'])
            self.assertIn(':acknowledge',api.call_args_list[1].args[1])
        with server.app.app_context(),accounts.database() as db:
            self.assertEqual(db.execute('SELECT COUNT(*) AS n FROM account_play_subscriptions').fetchone()['n'],1)
        self.assertTrue(self.client.get('/api/account').json['user']['premium_active'])
        # Paid users do not consume weekly analyses.
        self.assertEqual(self.post('/api/analyse-statistique',self.manual()).status_code,200)
        self.assertEqual(self.client.get('/api/account').json['user']['trial_remaining'],3)

    def test_invalid_identity_product_plan_and_pending_never_grant(self):
        user=self.register()['user']
        wrong=self.purchase('another-account')
        bad_product=self.purchase(user['id']);bad_product['lineItems'][0]['productId']='fake'
        bad_plan=self.purchase(user['id']);bad_plan['lineItems'][0]['offerDetails']['basePlanId']='annual'
        for payload in (wrong,bad_product,bad_plan):
            with patch.object(billing,'play_request',return_value=payload):
                self.assertIn(self.post('/api/billing/verify',{'purchase_token':'token'}).status_code,(400,409))
            self.assertFalse(self.client.get('/api/account').json['user']['premium_active'])
        for state in ('SUBSCRIPTION_STATE_PENDING','SUBSCRIPTION_STATE_ON_HOLD','SUBSCRIPTION_STATE_PAUSED','SUBSCRIPTION_STATE_EXPIRED'):
            with patch.object(billing,'play_request',return_value=self.purchase(user['id'],state)):
                result=self.post('/api/billing/verify',{'purchase_token':'token-'+state})
                self.assertEqual(result.json['status'],'inactive')
                self.assertFalse(result.json['user']['premium_active'])

    def test_cancellation_keeps_paid_period_and_revocation_removes_it(self):
        user=self.register()['user']
        with patch.object(billing,'play_request',return_value=self.purchase(user['id'],'SUBSCRIPTION_STATE_CANCELED')):
            self.assertTrue(self.post('/api/billing/verify',{'purchase_token':'cancelled'}).json['user']['premium_active'])
        with server.app.app_context(),accounts.database() as db:
            db.execute('UPDATE account_play_subscriptions SET checked_at=0')
        with patch.object(billing,'play_request',return_value=self.purchase(user['id'],'SUBSCRIPTION_STATE_EXPIRED')):
            self.assertFalse(self.client.get('/api/account').json['user']['premium_active'])

    def test_expiration_revalidates_renewal_and_outage_is_closed(self):
        user=self.register()['user']
        with patch.object(billing,'play_request',return_value=self.purchase(user['id'])):
            self.post('/api/billing/verify',{'purchase_token':'renewable'})
        with server.app.app_context(),accounts.database() as db:
            db.execute('UPDATE account_play_subscriptions SET expires_at=?,checked_at=0',(int(time.time())-1,))
        with patch.object(billing,'play_request',return_value=self.purchase(user['id'],expiry=int(time.time())+172800)):
            self.assertTrue(self.client.get('/api/account').json['user']['premium_active'])
        with server.app.app_context(),accounts.database() as db:
            db.execute('UPDATE account_play_subscriptions SET checked_at=0')
        with patch.object(billing,'play_request',side_effect=accounts.AccountError('Google unavailable',503,'billing_unavailable')):
            self.assertEqual(self.post('/api/analyse-statistique',self.manual()).status_code,503)

    def test_token_cannot_be_reassigned_and_no_secret_export(self):
        user=self.register()['user']
        with patch.object(billing,'play_request',return_value=self.purchase(user['id'])):
            self.post('/api/billing/verify',{'purchase_token':'private-token'})
        self.assertNotIn('private-token',self.client.get('/api/account/export').get_data(as_text=True))
        other=self.register('other@example.com')['user']
        with patch.object(billing,'play_request',return_value=self.purchase(other['id'])):
            self.assertEqual(self.post('/api/billing/verify',{'purchase_token':'private-token'}).status_code,409)

    def test_notifications_require_google_identity_and_reverify(self):
        import base64, json, os
        user=self.register()['user']
        with patch.object(billing,'play_request',return_value=self.purchase(user['id'])):
            self.post('/api/billing/verify',{'purchase_token':'rtdn-token'})
        payload={'message':{'data':base64.b64encode(json.dumps({'packageName':billing.PACKAGE,'subscriptionNotification':{'purchaseToken':'rtdn-token'}}).encode()).decode()}}
        self.assertEqual(self.client.post('/api/billing/notifications',json=payload).status_code,401)
        with patch.dict(os.environ,{'PLAY_RTDN_AUDIENCE':'https://example.test/rtdn','PLAY_RTDN_SERVICE_EMAIL':'push@example.test'}):
            with patch('google.oauth2.id_token.verify_oauth2_token',return_value={'email':'wrong@example.test','email_verified':True}):
                self.assertEqual(self.client.post('/api/billing/notifications',json=payload,headers={'Authorization':'Bearer fake'}).status_code,401)
            with patch('google.oauth2.id_token.verify_oauth2_token',return_value={'email':'push@example.test','email_verified':True}), patch.object(billing,'play_request',return_value=self.purchase(user['id'],'SUBSCRIPTION_STATE_EXPIRED')):
                self.assertEqual(self.client.post('/api/billing/notifications',json=payload,headers={'Authorization':'Bearer fake'}).status_code,200)
        self.assertFalse(self.client.get('/api/account').json['user']['premium_active'])

    def test_disappeared_old_token_revokes_without_locking_account(self):
        user=self.register()['user']
        with patch.object(billing,'play_request',return_value=self.purchase(user['id'])):
            self.post('/api/billing/verify',{'purchase_token':'disappeared'})
        with server.app.app_context(),accounts.database() as db:
            db.execute('UPDATE account_play_subscriptions SET checked_at=0')
        with patch.object(billing,'play_request',side_effect=accounts.AccountError('Gone',400,'purchase_invalid')):
            response=self.client.get('/api/account')
            self.assertEqual(response.status_code,200)
            self.assertFalse(response.json['user']['premium_active'])

if __name__=='__main__':unittest.main()
