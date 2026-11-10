# Premium Google Play — activation

## Code livré

- Application : `fr.footanalystpro.app` (à vérifier contre la fiche Play existante avant tout envoi).
- Produit : `foot_analyst_pro_premium_monthly`.
- Forfait de base : `monthly`, renouvellement automatique mensuel, prix France **29,90 EUR**.
- Pas d’offre d’essai Google : l’offre gratuite est de **3 analyses par semaine**, lundi minuit Europe/Paris, sans achat.
- Bibliothèque Billing 9.1.0 ; pont WebMessage limité au document principal `https://foot-analyst-pro.onrender.com`.
- Prix et confirmation d’achat fournis par Google Play. Aucun stockage local de carte ou de jeton d’achat.
- Le serveur vérifie l’état, le produit, le forfait, la date d’expiration et l’identifiant de compte SHA-256 avant d’accorder Premium. Les jetons de paiement sont conservés dans la base pour revalidation, jamais dans l’export ou les erreurs.
- Annulation : accès conservé jusqu’à expiration ; pause, suspension, paiement en attente et expiration : pas d’accès. Période de grâce : accès maintenu selon la date Google.
- Acquittement côté serveur après enregistrement de l’accès ; restauration idempotente et réessai en cas d’erreur.
- Revalidation des accès payants au plus toutes les cinq minutes lors des requêtes authentifiées, et dès expiration. Si Google est indisponible lors d’une revalidation obligatoire, l’accès échoue avec une erreur temporaire.

## Configuration externe nécessaire

1. Dans la bonne application Play Console, vérifier l’identifiant de package ci-dessus, le profil de paiement et les coordonnées de l’éditeur.
2. Créer l’abonnement et son forfait `monthly`, fixer France à 29,90 EUR/mois puis activer les territoires choisis. Ne pas ajouter d’essai récurrent Google.
3. Activer Android Publisher API pour un compte de service et lui accorder les droits nécessaires sur cette seule application (lecture des commandes/abonnements et gestion des commandes pour acquittement). Ces accès doivent être accordés par le propriétaire.
4. Fournir la clé JSON **uniquement comme secret Render**, `GOOGLE_PLAY_SERVICE_ACCOUNT_JSON`. Ne jamais la coller dans une conversation, un dépôt ou l’APK.
5. Configurer les notifications en temps réel Google Play (RTDN) vers un topic Pub/Sub. Google Play doit pouvoir publier dans ce topic ; créer une souscription push authentifiée vers `/api/billing/notifications` avec un compte de service dédié. Configurer `PLAY_RTDN_AUDIENCE` (audience de ce push) et `PLAY_RTDN_SERVICE_EMAIL` (identité Google de ce compte). Les renouvellements, annulations, remboursements et révocations déclenchent une relecture de l’API Google.
6. Passer `PLAY_BILLING_ENABLED=true` seulement lorsque le produit, les droits et les notifications sont prêts. Sans cette variable et sans clé serveur, le paiement reste fermé.
7. Construire et signer un nouvel AAB avec un `versionCode` supérieur à tous les précédents. Le code Web seul ne met pas à jour le module Android. Le workflow existant `Signed Android bundle for Google Play` nécessite les quatre secrets de signature et la confirmation du package.
8. Charger cet AAB sur la piste de test interne ; installer depuis Google Play avec un compte testeur de licence, puis tester les moyens de paiement de test. Ne pas effectuer de paiement réel pour valider le développement.

## Recette réelle requise avant vente

- Achat test : confirmation Google, Premium actif sur le bon compte, acquittement reçu.
- Fermeture entre paiement et vérification : « Restaurer mon achat » récupère l’accès.
- Réinstallation : connexion au même compte puis restauration.
- Paiement annulé/en attente/refusé : pas d’accès gratuit indu.
- Un autre compte de l’application ne peut pas récupérer le jeton déjà lié.
- Renouvellement accéléré de test, annulation, fin de période, suspension, grâce et révocation : accès conforme, RTDN reçu.
- Retour à 3 analyses gratuites par semaine après expiration.

## État

L’intégration peut être testée avec des réponses API simulées et compilée sans clé de paiement. Cela ne prouve pas la configuration du produit, les autorisations Google, la signature Play, ni le succès d’un achat réel de test. La vente doit rester fermée jusqu’à cette recette.
