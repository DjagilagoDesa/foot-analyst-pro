import json
import tempfile
import unittest
from pathlib import Path
from uuid import uuid4
from unittest.mock import patch

from flask import Flask
from accounts import database, init_schema
from publication import init_app
import app as server


class PublicDocumentTests(unittest.TestCase):
    def setUp(self):
        self.app = Flask(__name__)
        self.app.config.update(TESTING=True, PUBLIC_PUBLISHER_NAME='', PUBLIC_SUPPORT_EMAIL='',
                               PUBLIC_BACKUP_RETENTION_DAYS='', PUBLIC_LOG_RETENTION_DAYS='')
        init_app(self.app)
        self.client = self.app.test_client()

    def test_missing_legal_details_are_not_claimed_ready(self):
        response = self.client.get('/api/publication/status')
        self.assertFalse(response.json['store_submission_ready'])
        self.assertFalse(response.json['privacy_fields_complete'])
        page = self.client.get('/privacy')
        self.assertIn('Version préparatoire', page.text)
        self.assertEqual(page.headers['X-Robots-Tag'], 'noindex')

    def test_validated_settings_are_escaped_and_not_invented(self):
        self.app.config.update(PUBLIC_PUBLISHER_NAME='Éditeur <test>', PUBLIC_SUPPORT_EMAIL='privacy@example.invalid',
                               PUBLIC_BACKUP_RETENTION_DAYS='7', PUBLIC_LOG_RETENTION_DAYS='14')
        page = self.client.get('/privacy')
        self.assertIn('Éditeur &lt;test&gt;', page.text)
        self.assertIn('7 jours', page.text)
        self.assertNotIn('à confirmer avant publication', page.text)
        status = self.client.get('/api/publication/status').json
        self.assertTrue(status['privacy_fields_complete'])
        self.assertFalse(status['store_submission_ready'])

    def test_invalid_retention_values_keep_draft_state(self):
        self.app.config['PUBLIC_BACKUP_RETENTION_DAYS'] = '-1'
        self.assertIn('PUBLIC_BACKUP_RETENTION_DAYS', self.client.get('/api/publication/status').json['missing_public_settings'])

    def test_public_document_and_web_deletion_routes(self):
        with server.app.test_client() as client:
            for path in ('/privacy', '/terms', '/account-deletion'):
                with client.get(path) as response:
                    self.assertEqual(response.status_code, 200)
        html = Path('account-deletion.html').read_text()
        self.assertIn('id="webDeleteLogin"', html)
        self.assertIn('id="webDeleteConfirm"', html)
        self.assertIn('X-CSRF-Token', html)
        self.assertNotIn('localStorage', html)


class AccountDataTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.previous = {k: server.app.config.get(k) for k in ('TESTING','ACCOUNT_DATABASE_URL','ACCOUNT_SECURE_COOKIE')}
        server.app.config.update(TESTING=True, ACCOUNT_DATABASE_URL='sqlite:///'+self.temp.name+'/accounts.sqlite', ACCOUNT_SECURE_COOKIE=False)
        init_schema(server.app)
        self.client = server.app.test_client()
        self.password = uuid4().hex + uuid4().hex
        self.headers = {'Origin':'https://foot-analyst-pro.onrender.com', 'X-App-Request':'1'}
        response = self.client.post('/api/account/register', json=dict(email=uuid4().hex+'@example.invalid', nickname='Test', password=self.password, accept_privacy=True), headers=self.headers)
        self.assertEqual(response.status_code, 201)
        self.uid = response.json['user']['id']
        self.headers['X-CSRF-Token'] = response.json['csrf_token']
        with server.app.app_context(), database() as db:
            db.execute('''INSERT INTO account_predictions(user_id,event_id,league,market,probability,label,home_id,away_id,starts_at,created_at,status)
                VALUES(?,?,?,?,?,?,?,?,?,?,?)''', (self.uid,'1','fra.1','home',70,'Test','1','2',0,0,'pending'))

    def tearDown(self):
        server.app.config.update(self.previous)
        self.temp.cleanup()

    def test_export_includes_personal_selections_and_no_authentication_secrets(self):
        response = self.client.get('/api/account/export')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.json['selections']), 1)
        self.assertNotIn(self.password, response.text)
        for key in ('password_hash', 'recovery_hash', 'token_hash'):
            self.assertNotIn(key, response.text)

    def test_existing_owner_access_survives_private_configuration_change(self):
        from accounts import initialize_owner_access
        with server.app.app_context(), database() as db:
            db.execute("INSERT INTO account_owner_access(slot,user_id) VALUES('owner',?) ON CONFLICT(slot) DO UPDATE SET user_id=excluded.user_id", (self.uid,))
        with patch.dict('os.environ', {'OWNER_ACCOUNT_EMAIL': uuid4().hex+'@example.invalid'}):
            initialize_owner_access(server.app)
        with server.app.app_context(), database() as db:
            self.assertEqual(db.execute("SELECT user_id FROM account_owner_access WHERE slot='owner'").fetchone()['user_id'], self.uid)

    def test_delete_removes_selections_sessions_and_owner_reference(self):
        with server.app.app_context(), database() as db:
            db.execute("INSERT INTO account_owner_access(slot,user_id) VALUES('owner',?) ON CONFLICT(slot) DO UPDATE SET user_id=excluded.user_id", (self.uid,))
        response = self.client.post('/api/account/delete', json=dict(password=self.password, confirmation='SUPPRIMER'), headers=self.headers)
        self.assertEqual(response.status_code, 200)
        with server.app.app_context(), database() as db:
            self.assertEqual(db.execute('SELECT count(*) AS n FROM account_predictions').fetchone()['n'], 0)
            self.assertEqual(db.execute('SELECT count(*) AS n FROM account_sessions').fetchone()['n'], 0)
            self.assertEqual(db.execute("SELECT user_id FROM account_owner_access WHERE slot='owner'").fetchone()['user_id'], 'unassigned')
