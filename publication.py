"""Public publication documents; missing publisher settings remain explicitly flagged."""
import os
from flask import Blueprint, current_app, jsonify, render_template_string

bp = Blueprint('publication', __name__)
FIELDS = ('PUBLIC_PUBLISHER_NAME', 'PUBLIC_SUPPORT_EMAIL', 'PUBLIC_BACKUP_RETENTION_DAYS', 'PUBLIC_LOG_RETENTION_DAYS')


def settings():
    return {key: str(current_app.config.get(key, os.environ.get(key, ''))).strip() for key in FIELDS}


def missing_fields(values):
    missing = [key for key in FIELDS if not values[key]]
    if values['PUBLIC_SUPPORT_EMAIL'] and ('@' not in values['PUBLIC_SUPPORT_EMAIL'] or '\n' in values['PUBLIC_SUPPORT_EMAIL']):
        missing.append('PUBLIC_SUPPORT_EMAIL')
    for key in FIELDS[2:]:
        if values[key] and (not values[key].isdigit() or int(values[key]) > 3650):
            missing.append(key)
    return sorted(set(missing))


@bp.get('/api/publication/status')
def publication_status():
    missing = missing_fields(settings())
    response = jsonify(privacy_fields_complete=not missing, missing_public_settings=missing,
        account_deletion_url='/account-deletion', privacy_url='/privacy', terms_url='/terms',
        billing_available=False, store_submission_ready=False,
        note='La signature Android, les déclarations Play Console, la licence des données et le paiement Premium doivent aussi être vérifiés avant soumission.')
    response.headers['Cache-Control'] = 'no-store'
    return response


STYLE = '''<style>:root{color-scheme:dark}*{box-sizing:border-box}body{max-width:760px;margin:32px auto;padding:20px;background:#102119;color:#fff9df;font:16px/1.65 system-ui}h1,h2,a{color:#ffdc79}h1{font-size:26px}h2{font-size:20px;margin-top:28px}.draft{padding:16px;border:1px solid #e1ae58;border-radius:12px;background:#382c15}nav{display:flex;flex-wrap:wrap;gap:16px}table{width:100%;border-collapse:collapse}td,th{border:1px solid #7d7959;padding:9px;text-align:left;vertical-align:top}code{overflow-wrap:anywhere}</style>'''
FRAME = '''<!doctype html><html lang="fr"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>{{ title }} — FOOT ANALYST PRO</title>{{ style|safe }}</head><body><nav><a href="/">Application</a><a href="/privacy">Confidentialité</a><a href="/account-deletion">Supprimer mon compte</a><a href="/terms">Conditions</a></nav>{{ body|safe }}</body></html>'''


@bp.get('/privacy')
def privacy():
    values = settings()
    missing = missing_fields(values)
    body = render_template_string('''<h1>Politique de confidentialité</h1><p>FOOT ANALYST PRO · version préparée le 1 novembre 2026</p>
    {% if missing %}<p class="draft"><strong>Version préparatoire.</strong> Les coordonnées de l’éditeur et les durées de conservation de l’hébergeur doivent être confirmées avant la publication sur Google Play. Ce document ne constitue pas une validation de conformité.</p>{% endif %}
    <h2>Responsable et contact</h2><p>Service concerné : FOOT ANALYST PRO. Éditeur responsable : <strong>{{ v.PUBLIC_PUBLISHER_NAME or 'à confirmer avant publication' }}</strong>.</p>
    <p>Contact relatif aux données : {% if valid_email %}<a href="mailto:{{ v.PUBLIC_SUPPORT_EMAIL }}">{{ v.PUBLIC_SUPPORT_EMAIL }}</a>{% else %}à confirmer avant publication.{% endif %}</p>
    <h2>Données traitées et finalités</h2><table><tr><th>Données</th><th>Utilisation</th></tr>
    <tr><td>E-mail, pseudo, identifiant de compte et date de création</td><td>Création et gestion du compte, connexion et personnalisation du profil.</td></tr>
    <tr><td>Empreinte sécurisée du mot de passe et du code de récupération</td><td>Authentification et récupération du compte. Les mots de passe ne sont pas conservés en clair.</td></tr>
    <tr><td>Compteur des trois essais, analyses, sélections personnelles et leurs résultats</td><td>Fonctionnement de l’offre d’essai, accès aux analyses, historique et suivi personnel.</td></tr>
    <tr><td>État Premium et éventuelle date de fin d’accès</td><td>Contrôle des droits d’accès. Aucun paiement ni numéro de carte bancaire n’est collecté par la version actuelle.</td></tr>
    <tr><td>Jetons de session protégés, cookie de connexion et compteurs de sécurité</td><td>Maintien de la connexion et protection contre les abus. La session expire au plus tard quatorze jours après sa création.</td></tr>
    <tr><td>Adresses IP et informations techniques pouvant figurer dans les requêtes et journaux de l’hébergeur</td><td>Fourniture du service, diagnostic et sécurité. Des empreintes d’identifiants/IP servent à limiter les tentatives ; elles ne sont pas considérées comme anonymes.</td></tr></table>
    <p>Les choix publics d’« Avis du jour » concernent des rencontres de football et ne contiennent pas l’identité des utilisateurs. Leur bilan officiel est indépendant des comptes et sélections personnels.</p>
    <h2>Fondements et choix</h2><p>Les traitements nécessaires au compte et aux fonctionnalités demandées servent à fournir le service. Les mesures de sécurité servent à protéger le service et ses utilisateurs. La consultation du calendrier et de l’avis public reste possible sans compte. La case de lecture des informations ne vaut pas accord pour de la publicité.</p>
    <h2>Destinataires et services techniques</h2><p>Le service et sa base de données sont hébergés chez Render. Les données sportives et certains écussons proviennent de sources externes, notamment ESPN ; leurs serveurs d’images peuvent recevoir votre adresse IP et les informations techniques de la requête lors de leur chargement. Le code actuel n’intègre ni SDK publicitaire ni outil tiers de mesure d’audience.</p>
    <p>Les destinataires et garanties applicables aux éventuels transferts hors de l’Espace économique européen doivent être vérifiés dans les contrats et réglages réels de Render et des fournisseurs avant publication commerciale ; ils ne sont pas présumés ici.</p>
    <h2>Conservation et suppression</h2><p>Les données du compte sont conservées pendant son utilisation, jusqu’à sa suppression. L’action de suppression retire immédiatement le compte, les sessions, les analyses et les sélections personnelles de la base active. Les compteurs temporaires expirent selon leur fenêtre de sécurité et sont purgés lors des opérations suivantes.</p>
    <p>Conservation maximale des sauvegardes de l’hébergeur : <strong>{{ backup }}</strong>. Conservation des journaux techniques : <strong>{{ logs }}</strong>. Les durées doivent correspondre aux paramètres contractuels et techniques effectivement appliqués.</p>
    <h2>Vos droits et vos démarches</h2><p>Depuis Profil, vous pouvez modifier le pseudo, afficher/exporter vos données et supprimer votre compte. Une démarche de suppression est également disponible sans réinstaller l’application sur <a href="/account-deletion">la page dédiée</a>. La vérification du compte protège contre une suppression par un tiers.</p>
    <p>Pour les demandes d’accès, de rectification, d’effacement, de limitation, de portabilité ou d’opposition applicables, contactez l’éditeur. Vous pouvez adresser une réclamation à la CNIL ou à l’autorité de contrôle compétente. Les demandes doivent être traitées conformément aux règles applicables.</p>
    <h2>Sécurité et public concerné</h2><p>Les échanges applicatifs utilisent HTTPS. La connexion repose sur un cookie protégé ; le code de l’application ne stocke pas les mots de passe dans le stockage local. Conservez votre code de récupération dans un endroit sûr.</p>
    <p>Le service propose des analyses statistiques de football et des pronostics. Il ne permet ni dépôt d’argent, ni placement de mises, ni versement de gains. Le périmètre de lancement et la classification d’âge doivent être déclarés fidèlement dans Google Play. Aucun gain n’est garanti.</p>''', v=values, missing=missing,
        valid_email='PUBLIC_SUPPORT_EMAIL' not in missing,
        backup=values['PUBLIC_BACKUP_RETENTION_DAYS']+' jours' if 'PUBLIC_BACKUP_RETENTION_DAYS' not in missing else 'à confirmer avant publication',
        logs=values['PUBLIC_LOG_RETENTION_DAYS']+' jours' if 'PUBLIC_LOG_RETENTION_DAYS' not in missing else 'à confirmer avant publication')
    response = current_app.make_response(render_template_string(FRAME, title='Confidentialité', style=STYLE, body=body))
    response.headers['Cache-Control'] = 'no-store'
    if missing:
        response.headers['X-Robots-Tag'] = 'noindex'
    return response


@bp.get('/terms')
def terms():
    body = '''<h1>Conditions du service</h1><p class="draft">Informations fonctionnelles de la version de préparation. Les coordonnées légales de l’éditeur et les conditions commerciales définitives restent à confirmer avant la vente.</p>
    <h2>Fonctionnement</h2><p>FOOT ANALYST PRO présente un calendrier de football, des statistiques, des analyses, des sélections personnalisées et un avis quotidien. Les compétitions couvertes et la disponibilité des sources sont limitées. Une connexion Internet est nécessaire.</p>
    <h2>Essai et Premium</h2><p>Trois analyses abouties sont offertes par nouveau compte, sans carte bancaire et sans abonnement automatique. Les résultats déjà enregistrés restent accessibles. Le tarif prévu de Premium est de 29,90 € par mois ; les achats ne sont pas disponibles dans cette version. Aucun prélèvement n’est déclenché par la création du compte.</p>
    <h2>Limites des analyses</h2><p>Les probabilités sont des estimations statistiques fondées sur des résultats historiques accessibles. Le modèle actuel ne vérifie pas les compositions, blessures ou dernières actualités. Un pourcentage de réussite passé ne garantit aucun résultat futur. Les choix d’Avis du jour restent figés après leur publication ; seuls leurs résultats sont mis à jour.</p>
    <h2>Absence de prise de paris</h2><p>L’application ne reçoit pas de mises, ne place pas de paris et ne verse pas de gains. Les probabilités et cotes théoriques ne sont pas des cotes bookmaker. Aucun contenu ne constitue une promesse de gain.</p>
    <h2>Compte</h2><p>Protégez votre mot de passe et votre code de récupération. Vous pouvez supprimer votre compte depuis Profil ou via <a href="/account-deletion">la page Web de suppression</a>. Les données sont décrites dans <a href="/privacy">la politique de confidentialité</a>.</p>'''
    response = current_app.make_response(render_template_string(FRAME, title='Conditions', style=STYLE, body=body))
    response.headers['X-Robots-Tag'] = 'noindex'
    return response


def init_app(app):
    app.register_blueprint(bp)
