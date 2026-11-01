# Sécurité des données — préparation, à valider dans Play Console

Ce relevé décrit le code inspecté le 1 novembre 2026. Il ne constitue pas une déclaration déjà envoyée à Google. La définition Google de collecte, partage et traitement éphémère doit être appliquée à l’hébergement réel et à tous les fournisseurs.

| Donnée réellement traitée | Finalité constatée | Caractère / point à confirmer |
| --- | --- | --- |
| E-mail, pseudo, identifiant interne | Création et gestion du compte | Nécessaires aux fonctions de compte ; calendrier et avis public utilisables sans compte. Choisir les sous-catégories Google correspondant à ces champs. |
| Empreinte du mot de passe et du code de récupération | Authentification et sécurité | Secrets non conservés en clair ; ne pas déclarer une absence de données de compte. |
| Analyses, noms des rencontres, sélections personnelles, résultats, compteur d’essais | Fonctionnement, historique, suivi | Liés au compte ; exportables, supprimés avec celui-ci. Valider les rubriques d’activité/interactions dans le formulaire Google. |
| Cookie de connexion et jeton serveur protégé | Session et sécurité | Expiration maximale quatorze jours. Aucun stockage de mot de passe dans localStorage. |
| IP et métadonnées de requêtes, empreintes de compteurs de sécurité | Infrastructure et lutte contre les abus | Contrôler les journaux de Render, la durée, les accès et la définition Google des identifiants de l’appareil/autres identifiants. Ne pas les déclarer anonymes sans justification. |
| Requêtes d’écussons à des domaines externes | Affichage des contenus sportifs | Les fournisseurs d’images reçoivent l’IP et des métadonnées réseau. Évaluer le rôle de ces fournisseurs et les obligations de déclaration. |
| État Premium et date de validité | Gestion des droits | Pas d’achat opérationnel actuellement. Réviser la déclaration et la confidentialité avant intégration de Google Play Billing. |

## Constatations techniques

- Échanges applicatifs et chargements d’images configurés en HTTPS ; l’APK n’autorise pas le trafic HTTP en clair.
- Aucune permission caméra, microphone, contacts, localisation, SMS ou stockage partagé n’est demandée par le manifeste inspecté.
- Aucun SDK publicitaire ou d’analytics ajouté dans le projet Android inspecté.
- Aucun numéro de carte ni donnée bancaire recueilli dans la version actuelle.
- Les choix publics d’Avis du jour ne contiennent pas d’identifiant utilisateur.
- Suppression possible dans Profil et sur `https://foot-analyst-pro.onrender.com/account-deletion` sans application installée, après vérification de la possession du compte.
- La suppression ne doit pas être déclarée comme une purge immédiate des sauvegardes : indiquer les durées réellement configurées et les éventuelles obligations de conservation.

## Avant validation du formulaire

1. Compléter la politique de confidentialité avec éditeur et contact réels, conservation, hébergement, transferts et droits.
2. Confirmer l’absence d’autres services ajoutés dans le compte d’hébergement, la variante signée ou le CDN.
3. Relire le formulaire selon les définitions Google, en particulier la distinction entre prestataires techniques et partage avec des tiers.
4. Définir l’accès de l’examinateur sans ajouter de contournement public des quotas ou du Premium.
5. Si un compte de test dédié est nécessaire, créer un compte à données fictives contrôlé par l’éditeur et fournir ses accès uniquement dans l’espace privé prévu par Play Console.
6. Ne pas sélectionner « aucune donnée collectée » : la création de comptes et l’historique serveur collectent des données.
