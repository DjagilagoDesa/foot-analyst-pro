# Espace Profil V47 — activation

## Fonctionnalités livrées

- Inscription e-mail / pseudo / mot de passe (12 caractères minimum).
- Session persistante pendant 14 jours, déconnexion et révocation serveur.
- Code de récupération aléatoire remis une seule fois ; réinitialisation sans SMTP. L’e-mail n’est pas vérifié et aucun e-mail de récupération n’est envoyé. La vérification d’adresse et le changement d’e-mail ne sont pas implémentés.
- Modification du pseudo ; changement du mot de passe avec révocation des autres sessions et nouveau code de récupération.
- 3 analyses réussies par compte, compteur atomique côté serveur et historique privé. Une demande identique réutilise son résultat ; une erreur, une entrée invalide ou des données insuffisantes ne consomment pas d’essai. Réservations inachevées remboursées après 10 minutes lors d’une nouvelle demande.
- Consultation et export JSON des données ; suppression avec confirmation et mot de passe, puis suppression en cascade des sessions et analyses dans la base active.
- Paiement et validation des achats Google Play non implémentés. Le client ne peut pas activer Premium ; aucun abonnement automatique ni carte demandée.

## Activation Render obligatoire AVANT la fusion/déploiement

Les comptes ne doivent pas utiliser le disque temporaire du serveur gratuit. Aucune base de production n’a été créée automatiquement et aucun secret n’a été ajouté au dépôt.

1. Disposer d’une base PostgreSQL permanente accessible au service Render. Prévoir ses sauvegardes et sa durée de conservation.
2. Dans le service web Render → Environment, ajouter `DATABASE_URL` avec l’URL privée de connexion fournie par l’hébergeur. Ne pas partager cette URL dans une conversation, capture ou commit.
3. Ajouter `PUBLIC_ORIGIN=https://foot-analyst-pro.onrender.com` (valeur par défaut actuelle). Adapter cette valeur si l’adresse publique change. Conserver HTTPS.
4. Fusionner la PR une fois la base configurée. Le Dockerfile lance `python init_accounts.py` avant Gunicorn pour créer les tables. Si le déploiement utilise une commande native plutôt que ce Dockerfile, utiliser `python init_accounts.py && gunicorn --bind 0.0.0.0:$PORT --workers 2 --timeout 90 app:app`.
5. Vérifier `/api/account` : `available:true`, puis créer un compte de test et conserver le code personnel. Ne pas créer de vrais comptes avant validation de la confidentialité et du stockage.

Sans DATABASE_URL, les matchs restent publics et l’onglet Profil annonce son activation à venir. Les analyses nécessitent désormais un compte ; elles ne seront donc pas utilisables tant que les comptes ne sont pas activés.

## Protection des comptes

Empreintes scrypt via Werkzeug ; identifiants de sessions aléatoires stockés uniquement sous empreinte ; cookie Secure/HttpOnly/SameSite=Lax ; contrôle Origin, JSON et jeton CSRF sur les modifications et analyses ; limitation des tentatives dans PostgreSQL ; secrets et mots de passe absents du navigateur et des exports ; compteurs et historiques privés.

La confiance proxy est limitée au dernier reverse proxy pour IP/protocole (ProxyFix x_for=1, x_proto=1), à conserver seulement derrière le proxy Render. Le serveur de développement ne doit pas être exposé publiquement.

Les e-mails ne sont pas vérifiés : des inscriptions multiples restent possibles. Le quota est par compte, pas une promesse de quota unique par personne. Il faudra une vérification d’e-mail et éventuellement une protection anti-robot avant un lancement à grande échelle.

## Vérification PostgreSQL en CI

Le workflow Backend and calendar checks teste l’authentification, les quotas et leur concurrence sur SQLite temporaire puis sur un service PostgreSQL de CI. SQLite est accepté uniquement lorsque Flask TESTING=True.

## Avant le Play Store

Finaliser les coordonnées de l’éditeur, le contact d’assistance, la politique de confidentialité publique, la conservation des sauvegardes et les déclarations de sécurité des données selon l’hébergeur effectivement choisi. `/account-deletion` fournit le parcours public de suppression ; le texte doit être finalisé avec la politique de conservation réelle. Ne pas présenter cette version comme prête pour un lancement payant.
