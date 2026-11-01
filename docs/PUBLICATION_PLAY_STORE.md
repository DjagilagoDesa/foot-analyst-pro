# FOOT ANALYST PRO — préparation Google Play V45

## État réel

- Application web Flask existante, 13 compétitions couvertes ; données ESPN non officielles.
- Recherche dès la première lettre ; appels saisonniers et recherches parallèles ; données futures exclues des historiques.
- Analyses : modèle Poisson statistique, pas encore une IA contextuelle. Blessures, compositions, confrontations et calibration non intégrées.
- Comptes, 3 essais serveur, abonnement 29,90 €/mois, historique par compte et tickets quotidiens : non implémentés. Interface marquée « à venir » lorsque nécessaire.
- Projet Android WebView HTTPS, package provisoire `fr.footanalystpro.app`, API cible 36, versionCode 1. Confirmer l'identifiant avant la première soumission ; il devient permanent.
- Le client Android ouvre le serveur Render existant : la branche doit être déployée sur Render pour bénéficier des corrections. Une panne serveur reste une panne de l'application.

## Compilation

Workflow GitHub `Android preview`, déclenché par les changements de cette branche ou manuellement après fusion.
Le workflow teste le backend, compile APK debug + AAB release non signé et exécute lint.
L'APK debug sert aux essais. L'AAB non signé ne peut pas être envoyé sur Google Play.
Aucune clé privée n'est créée ou enregistrée dans ce dépôt.

En local, JDK 17, SDK Android 36, Build Tools 35.0.0 et Gradle 8.11.1 :

```sh
gradle -p android :app:assembleDebug :app:bundleRelease :app:lintDebug
```

## Conditions avant soumission

1. Tester sur téléphone : recherche, écussons, matchs, analyses, réseau coupé, rotation, retour système, petits/grands écrans.
2. Définir le périmètre de lancement gratuit ou terminer les comptes et paiements. Préserver le futur modèle 3 analyses offertes sans carte ni souscription automatique, puis 29,90 €/mois. Aucun quota local ne remplace un compteur serveur par compte.
3. Confirmer l'identifiant Android et créer/conserver une clé d'upload ; signer l'AAB et activer Play App Signing. Ne jamais envoyer le mot de passe ou la clé dans une conversation ou le dépôt.
4. Publier une politique de confidentialité réelle avec éditeur/contact, hébergeur, traitement IP/logs, conservation, destinataires (dont images chargées chez les fournisseurs), droits et suppression si comptes. Aucun texte fictif à présenter comme validé.
5. Vérifier les droits d'utilisation commerciale des données et écussons. L'accès public à une API n'établit pas une licence commerciale.
6. Préparer icône boutique 512×512, bannière 1024×500, vraies captures téléphone, description, catégorie Sport, accès de l'examinateur, classification IARC, déclarations publicité et sécurité des données selon le fonctionnement réel.
7. Évaluer les fonctionnalités de pronostics/tickets avec les règles Google Play sur les jeux d'argent et paiements avant d'activer une offre payante. L'application actuelle ne prend aucune mise ; ne pas présenter cela comme une garantie d'acceptation.
8. Vérifier dans Play Console si le compte personnel est soumis au test fermé : 12 testeurs inscrits en continu pendant 14 jours pour les comptes concernés, puis demande d'accès production. La validation de WCL ne vaut pas automatiquement validation de cette nouvelle application.

## Brouillon fiche boutique (ne pas publier avant validation)

Nom : FOOT ANALYST PRO
Description courte : Calendrier football, recherche d'équipes et probabilités statistiques de matchs.

Explore les rencontres des compétitions couvertes, retrouve une équipe par son nom et consulte son prochain match. Lance une estimation statistique fondée sur les résultats historiques accessibles : victoires, nul, buts et double chance.

Les estimations reposent sur un modèle Poisson simple. Elles ne garantissent aucun résultat ; la disponibilité des données varie. Les blessures et compositions ne sont pas prises en compte actuellement. Une connexion Internet est nécessaire.

Ne pas annoncer les comptes, essais Premium, paiement, IA contextuelle ou tickets quotidiens comme disponibles.

## Sources officielles vérifiées le 1 novembre 2026

- API cible : https://developer.android.com/google/play/requirements/target-sdk
- Tests nouveaux comptes personnels : https://support.google.com/googleplay/android-developer/answer/14151465
- Paiements : https://support.google.com/googleplay/android-developer/answer/9858738
- Jeux d'argent : https://support.google.com/googleplay/android-developer/answer/9877032
- Confidentialité et données : https://support.google.com/googleplay/android-developer/answer/10144311
