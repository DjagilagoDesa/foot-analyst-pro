# FOOT ANALYST PRO — préparation Google Play 1.0.0

État vérifié le 1 novembre 2026. Ce document remplace le bilan V45 devenu obsolète. **L’application n’est pas encore prête à être soumise comme offre Premium payante.**

## Réalisé dans le code

- Comptes persistants, récupération par code personnel, trois analyses offertes sans carte bancaire, historique et accès propriétaire.
- Calendrier, recherche d’équipe, analyses Poisson documentées, sélections personnalisées et Avis du jour automatique 3/2/1.
- Taux officiel fondé exclusivement sur les choix d’Avis du jour, cumulés depuis la première publication.
- Suppression du compte dans l’application et sur `/account-deletion`, avec connexion et confirmation explicite. Suppression des données liées en cascade ; l’ancienne référence d’accès propriétaire est également retirée.
- Export JSON incluant maintenant les sélections personnelles, sans empreintes de mots de passe ni jetons de session.
- `/privacy` et `/terms` accessibles et reliés au profil. Les informations non confirmées sont explicitement signalées comme préparatoires ; aucune durée d’hébergement ou coordonnée d’éditeur n’est inventée.
- Android : package existant `fr.footanalystpro.app`, API cible et compilation 36, minimum Android 8, versionName 1.0.0 et versionCode paramétrable, valeur par défaut 2.
- Compilation automatique APK debug + AAB release non signé, lint debug/release et mapping R8. L’artefact est clairement marqué UNSIGNED.
- Workflow séparé pour produire un AAB signé à partir de secrets privés, avec confirmation du package et versionCode. Il ne publie pas automatiquement et échoue si la signature manque.
- Icône boutique 512×512, bannière 1024×500, brouillon de fiche et workflow de captures réelles à 1080×1920. Les captures ne contiennent pas de compte personnel ni de matchs fictifs.

## Blocages avant soumission

| Point | Ce qui reste à vérifier ou configurer |
| --- | --- |
| Compte Play Console | Connexion au compte développeur réel ; vérifier les applications existantes, le statut de vérification et les conditions de production. Aucune session connectée n’est disponible dans le navigateur consulté. |
| Identifiant et version | Confirmer le package dans la fiche exacte. Le versionCode signé doit dépasser tous les codes déjà déposés ; ne pas présumer que 2 est libre. |
| Signature | Utiliser la clé d’upload du projet si elle existe ; sinon créer et conserver une clé appropriée. Activer Play App Signing selon la situation réelle. Ne jamais remplacer une clé existante ni envoyer une clé ou un mot de passe dans le chat ou le dépôt. |
| Premium 29,90 €/mois | Google Play Billing absent du client ; vérification serveur des achats, liaison au compte, restauration, acquittement et suivi des renouvellements/révocations absents. Les achats restent désactivés. Ne pas présenter la version actuelle comme une souscription opérationnelle. |
| Confidentialité et éditeur | Confirmer le responsable/contact, les durées réelles de journaux/sauvegardes et les garanties/transferts des hébergeurs. Les pages préparatoires ne doivent pas être déclarées définitives. |
| Sources sportives | Vérifier les droits d’usage commercial des données et écussons ESPN et autres fournisseurs. Un accès API public ne prouve pas une licence commerciale. |
| Déclarations Play | Sécurité des données, publicité, accès de l’examinateur, questionnaire de classification, pays et prix de téléchargement, coordonnées développeur. |
| Accès à la production | Pour les comptes personnels concernés, test fermé avec au moins 12 testeurs inscrits en continu pendant 14 jours puis demande d’accès production. La situation doit être vérifiée pour cette application. |
| Contrôle fonctionnel | Pré-lancement Android et test réel de connexion, navigation, rotation, retour, coupure réseau, suppression, différents écrans ; achats réels de test avant monétisation. |

## Signature : configuration préparée

Les secrets GitHub nécessaires au workflow manuel `Signed Android bundle for Google Play` sont :

- `ANDROID_KEYSTORE_BASE64` : fichier de la clé d’upload encodé en base64 ;
- `ANDROID_KEYSTORE_PASSWORD` ;
- `ANDROID_KEY_ALIAS` ;
- `ANDROID_KEY_PASSWORD`.

Le workflow les utilise dans un fichier temporaire à accès restreint, exige les quatre valeurs, vérifie la signature du bundle, puis retire le fichier temporaire. Aucun de ces secrets n’a été créé ou ajouté par cette préparation. Ne jamais utiliser une clé de debug pour une soumission de production. Conserver une sauvegarde sûre de la clé d’upload.

L’adresse du propriétaire n’est plus inscrite en dur dans le code. Les droits déjà épinglés dans la base sont conservés. Pour une nouvelle base, définir `OWNER_ACCOUNT_EMAIL` de manière privée avant l’initialisation du propriétaire ; une base initialisée sans propriétaire n’accorde pas d’accès privilégié automatiquement à une inscription ultérieure.

Le workflow de prévisualisation ne fournit pas un fichier prêt à envoyer sur Play : son AAB est non signé. Le workflow signé n’effectue pas de soumission. La génération d’une signature ne vaut pas validation des règles Google Play.

## Informations publiques à confirmer

Configurer les valeurs exactes suivantes côté serveur, sans laisser de valeur fictive :

```text
PUBLIC_PUBLISHER_NAME=
PUBLIC_SUPPORT_EMAIL=
PUBLIC_BACKUP_RETENTION_DAYS=
PUBLIC_LOG_RETENTION_DAYS=
```

`/api/publication/status` distingue les champs manquants et ne prétend jamais que l’application est prête à la soumission. Les contrats de sous-traitance, pays de traitement et garanties de transfert doivent aussi être examinés et reflétés dans la politique définitive.

## Fiche et assets

- Texte français : `store-assets/listing-fr.md` ; il décrit le fonctionnement actuel et n’annonce pas un paiement disponible.
- Sources vectorielles et exports PNG : `store-assets/icon.*` et `store-assets/feature-graphic.*`.
- Le workflow `Google Play store assets` capture l’interface publique réelle et fournit un artefact contenant les images et leur date de capture. Reprendre les captures après une modification importante avant soumission.
- La déclaration Sécurité des données est préparée dans `docs/DATA_SAFETY_DRAFT.md` ; elle doit être validée avec les réglages des fournisseurs.

## Sources officielles consultées

- API cible 36 : https://developer.android.com/google/play/requirements/target-sdk
- Signature de bundle : https://developer.android.com/build/building-cmdline
- Test fermé : https://support.google.com/googleplay/android-developer/answer/14151465
- Données et confidentialité : https://support.google.com/googleplay/android-developer/answer/10144311
- Suppression externe : https://support.google.com/googleplay/android-developer/answer/13327111
- Assets boutique : https://support.google.com/googleplay/android-developer/answer/9866151
- Jeux d’argent et publicités : https://support.google.com/googleplay/android-developer/answer/9877032

La présence de pronostics et d’un suivi ne permet pas, à elle seule, de conclure à l’acceptation ou au refus. Ne pas ajouter de prise de mises, de liens d’affiliation ou de publicités bookmaker sans nouvelle évaluation du fonctionnement et des règles applicables.
