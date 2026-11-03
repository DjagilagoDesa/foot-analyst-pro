# Comparaison prospective en arrière-plan

## Hypothèse figée avant activation

Version `opponent-normalized-daily10-shadow-v1`. La référence reproduit le calcul
« Avis du jour » : dix résultats par équipe, mêmes moyennes arrondies, même fonction
Poisson. Le candidat prend exactement ces dix mêmes résultats et applique la
normalisation des buts par note d'adversaire, paramètres inchangés (1500, K=20,
échelle 400, normalisation 800, facteur borné 0,75–1,33).

C'est une variante **daily10** distincte du candidat historique adaptive20. Les gains
rétrospectifs du comparateur adaptive20 ne sont donc pas présentés comme sa validation.
L'expérience mesure les probabilités des marchés sur une sélection bornée de matchs,
pas la réussite des tickets ni celle des choix effectivement publiés dans l'application.

## Fonctionnement

- Worker distinct, vérification environ toutes les quinze minutes quand le serveur est
  actif. Les réveils existants de l'application démarrent aussi ce worker.
- Huit compétitions : Angleterre, Espagne, Italie, Allemagne, France, Portugal,
  Pays-Bas et Ligue des champions. Au maximum deux tentatives par cycle et douze
  paires enregistrées par jour de Paris. Les échecs tournent entre rencontres pour
  qu'un match inexploitable ne bloque pas les autres.
- Le worker vérifie les tableaux du jour UTC et des deux jours précédents. Une
  interruption plus longue peut laisser des trous d'historique : ces matchs sont
  écartés si les entrées ne peuvent pas être raccordées, jamais inventés.
- Une source de rencontre distincte est relue juste avant enregistrement : équipes,
  date, état avant match et absence de report sont contrôlés. L'heure est recontrôlée
  dans la transaction, avec une marge d'au moins une minute avant le coup d'envoi.
- Une seule paire immuable par expérience/compétition/rencontre. Les entrées, notes
  d'adversaires et versions sont conservées avec leurs empreintes SHA-256. Les
  probabilités et la date d'enregistrement ne sont jamais remplacées.
- PostgreSQL conserve les paires, résultats observés, tentatives et lease du worker.
  Quatre tables distinctes `shadow_*` sont créées de façon additive. Aucun compte,
  quota d'essai, ticket ou taux officiel n'est modifié par ce code.
- Après résultat confirmé, les marchés sont évalués à 90 minutes. Reports, annulations,
  changements d'horaire, prolongations et durée inconnue sont exclus ; une panne de
  source laisse la paire en attente. Les contrôles de résultats tournent entre
  rencontres, au maximum douze par cycle.

## Notes et données d'initialisation

Le fichier `shadow_seed.json.gz` contient une archive rétrospective jusqu'au
1er novembre 2026, utilisée uniquement pour initialiser les notes et raccorder les
anciens résultats. Ce n'est pas une collection de prédictions prospectives.
Sa couverture et ses erreurs sont conservées dans `research/shadow-seed-manifest.json`.
La disponibilité historique des résultats y est supposée à coup d'envoi +24h.
Les corrections historiques du fournisseur et les compétitions manquantes restent
une limite. L'empreinte de l'archive compressée est figée dans chaque nouvelle paire.

Les résultats supplémentaires lus après activation reçoivent leur véritable première
heure d'observation par ce worker, conservée lors des lectures suivantes. Les notes
sont reconstruites chronologiquement : un résultat observé après un coup d'envoi
ne peut pas modifier la note mémorisée pour ce coup d'envoi. Un résultat ou un score
contradictoire entre l'historique demandé et les notes disponibles exclut la paire.

## Bilan et décision

`GET /api/shadow-experiment` expose uniquement les compteurs, les motifs de couverture,
l'état du dernier cycle et les comparaisons agrégées des rencontres terminées.
Aucun second pronostic à venir ni historique personnel n'y est publié.
Les marchés sont plus/moins de 1,5 et 2,5 buts, BTTS oui/non et doubles chances 1X/X2.
Le bilan garde les Brier et écarts de calibration séparés par marché et compétition.
Les intervalles par semaines sont descriptifs, indisponibles avant huit semaines,
non corrigés pour comparaisons multiples ; les clubs et marchés restent corrélés.

La première fenêtre d'évaluation est fixée **avant activation** à 90 jours à partir
de la première paire enregistrée. Les coups d'envoi hors de cette fenêtre n'entrent
pas dans ce premier bilan, même si le worker continue de conserver les nouvelles
paires. L'API expose les bornes exactes dès le premier enregistrement.
Aucun ajustement automatique, arrêt anticipé sur bon résultat ou promotion n'existe.
Il faudra une revue après cette fenêtre avant tout changement des probabilités affichées. Le service de comparaison n'est actif qu'après déploiement
et première requête à l'application ; les tests locaux ne constituent pas un démarrage
sur le serveur de production.

## Validation

Tests automatiques SQLite et PostgreSQL : doublons, disponibilité des résultats,
entrées identiques entre modèles, heure après requête réseau, lease expiré, changement
d'équipes ou d'horaire, reports/prolongations, conservation après panne de source,
rotation des tentatives et isolement du bilan public. Tests mobiles existants conservés.
