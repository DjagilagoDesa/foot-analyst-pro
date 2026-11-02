# Recherche expérimentale : force des adversaires

Ce code ne modifie ni les pronostics, ni les tickets, ni le taux officiel de l’application.
Il ne fait pas partie de l’image de production. Aucune promotion automatique n’existe.

## Hypothèse figée avant le test

Chaque club commence à 1500 points. Après un résultat disponible, sa note évolue selon
l’écart entre résultat et attente logistique (K=20, échelle=400). Ce ne sont pas des
notes officielles, ni une mesure validée de la force des clubs.

Les buts des anciens matchs sont normalisés avec la note de l’adversaire connue
**au coup d’envoi de cet ancien match**. Facteur `10 ** ((note - 1500) / 800)`, borné
entre 0,75 et 1,33 : buts marqués multipliés, buts encaissés divisés. Ce choix reste
une hypothèse de recherche, pas un ajustement de précision démontrée.
Les moyennes normalisées alimentent la même formule Poisson que la référence.
Aucun coefficient n’est optimisé sur le test final.

Les deux modèles utilisent exactement le même échantillon rejoué : jusqu’à 20 matchs
sur 540 jours, au moins 3. Les règles de compétitions couvertes reprennent le principe
national/Europe de la recherche adaptée. Cela ne reproduit pas les réponses partielles
ni toutes les différences de collecte du service de production.

## Protection chronologique

- Chaque résultat possède une date `available_at` ; il entre dans l’état seulement
  après cette date, strictement avant le match à prédire.
- Le calcul d’une prédiction n’accepte pas le score du match cible.
- Les rencontres d’apprentissage, validation et test final sont chronologiques.
  Les notes peuvent évoluer pendant le test après publication des résultats : c’est
  une évaluation séquentielle, pas un entraînement utilisant les résultats futurs.
- Les identifiants, scores, dates, doublons et durée réglementaire sont contrôlés.
- Des groupes de clubs sans adversaire commun relié ne sont pas artificiellement
  classés entre eux. Leur comparaison est exclue et comptée dans la couverture.

## Archives et limites

Le collecteur lit des tableaux ESPN rétrospectifs. Il accepte les scores terminés
avec période réglementaire explicitement identifiée. Il ne sait pas retrouver la
véritable heure historique de publication du résultat : `available_at` est alors
**supposé à coup d’envoi + 24 heures**, avec `availability_assumed=true` dans chaque
fiche. Les corrections ultérieures du fournisseur et les trous de couverture restent
possibles. Ce n’est donc pas un test sur des archives de publications horodatées.

La première recherche GitHub est bornée à huit compétitions, du 1er septembre au
30 novembre 2025 : septembre initialise les notes, octobre sert de validation,
novembre est le test final. Ces dates et paramètres sont figés dans le commit avant
l’exécution. Si la source échoue, la couverture est sauvegardée ; aucun score de
benchmark n’est inventé. Les nations non couvertes ne sont pas supposées équivalentes.

## Comparaison

Brier 1X2, log-loss 1X2, exactitude du favori, Brier BTTS et plus de 2,5 buts sont
calculés sur les **mêmes matchs** pour les deux modèles. Les résultats nationaux et
UCL sont aussi séparés. Une différence de Brier négative favorise le candidat sur
cet échantillon seulement. Moins de 100 matchs est signalé comme insuffisant ;
100 matchs n’est pas un seuil de validation automatique. Les matchs partagent des
clubs et ne constituent pas tous des observations indépendantes.

Même un meilleur résultat rétrospectif doit être confirmé sur une nouvelle période
et sur des prédictions réellement enregistrées avant match. Ne pas retoucher les
coefficients après lecture de novembre puis présenter novembre comme un test vierge.
Il n’y a pas de mesure de rentabilité sans cotes archivées.

## Commandes

```sh
python tools/collect_opponent_archive.py --leagues fra.1 uefa.champions \
  --start 2025-09-01 --end 2025-11-30 --output /tmp/archive.json
python tools/benchmark_opponents.py --input /tmp/archive.json \
  --validation-from 2025-10-01T00:00:00Z --test-from 2025-11-01T00:00:00Z \
  --output /tmp/benchmark.json
```

Le rapport porte toujours `experimental_only_no_automatic_promotion`. Les données
synthétiques des tests automatisés prouvent le fonctionnement du comparateur,
pas l’efficacité sportive du modèle.

## Premier résultat mesuré le 2 novembre 2026

Recherche GitHub 41541226615, code figé au commit
`4eb5be6971abfb401348c04bbfcdf7323fc768a1`. Collecte : 760 rencontres, 728 requêtes,
aucune erreur remontée. Cela ne garantit pas l’exhaustivité du fournisseur.

Test final : 283 rencontres, Brier 1X2 de 0,606404 pour la référence et 0,606085 pour
le candidat (écart −0,000319). Même nombre d’issues 1X2 correctement désignées,
140 sur 283. Le Brier BTTS global se dégrade très légèrement.

Ligue des champions : 36 rencontres seulement ; Brier 0,588081 contre 0,586246,
19 issues 1X2 correctement désignées sur 36 dans les deux cas. Échantillon trop court
pour valider une amélioration spécifique UCL. Ce taux 1X2 n’est **pas** le taux des
sélections spéciales de l’application ou des avis du jour.

Décision : conserver le candidat expérimental. Pas de gain démontré suffisant pour
remplacer le moteur. Les 760 dates de disponibilité sont toutes des hypothèses
rétrospectives à +24h ; aucune validation prospective réelle n’est revendiquée.
Résumé durable : `research/opponent-benchmark-2026-11-02.json`. Les exécutions suivantes
conservent aussi le jeu de données et son SHA-256 avec les rapports ; une réexécution
identique est un contrôle de reproductibilité, pas un nouvel échantillon indépendant.
