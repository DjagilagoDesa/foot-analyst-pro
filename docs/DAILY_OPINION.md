# Avis du jour

Une sélection commune à tous les utilisateurs est publiée sur l’accueil et dans Tickets du jour : trois choix prudents, deux choix plus difficiles et une surprise. Ce sont six rencontres et douze équipes distinctes ; les places restent vides si les données ou les probabilités sont insuffisantes.

La sélection emploie le modèle Poisson existant sur dix matchs terminés par équipe. Plages : 75–95 % pour Prudent, 50–70 % pour Plus difficile, 25–45 % pour Surprise. La surprise est une victoire du côté moins favori en 1X2, avec au moins cinq points de probabilité d’écart. Les marchés simples sont classés par probabilité dans chaque plage, pas par rentabilité. Aucune cote bookmaker, composition, actualité ou absence non vérifiée n’est inventée.

Au maximum 24 rencontres sont étudiées dans les compétitions couvertes, réparties sur les horaires de la journée. Les données viennent d’ESPN ; la couverture peut être partielle. Un choix prudent n’est pas certain et ces probabilités ne sont pas calibrées. Les six sélections individuelles ne constituent pas un combiné garanti.

La date est celle de Paris, y compris lors des changements d’heure. Le serveur contrôle la sélection environ toutes les quinze minutes pendant son activité. Un workflow GitHub planifié deux fois par heure réveille le serveur et contrôle la date du tableau ; comme tout déclenchement planifié, il peut être retardé par la plateforme. La première requête démarre le traitement en arrière-plan. L’application recharge le tableau automatiquement tant que sa rubrique est visible et au retour au premier plan.

Les tableaux sont stockés dans PostgreSQL, avec un verrou temporaire partagé entre workers. Les sélections publiées, leur heure et leurs probabilités restent figées. Les places manquantes peuvent être complétées uniquement avant le coup d’envoi ; aucune rencontre déjà commencée n’est ajoutée. Les résultats sont vérifiés ensuite : gagné, perdu ou annulé/non réglable. Les totaux après prolongation ou tirs au but sont exclus des marchés à 90 minutes. Les sept derniers tableaux sont revérifiés pour les résultats en attente. Les erreurs de source conservent les choix existants et l’interface signale un retard.

Le taux officiel de l’application, cumulé depuis la première publication, compte les choix gagnés, perdus, en attente et annulés. Le pourcentage exclut les attentes et annulations ; il ne reconstitue aucun ancien pari.

Seuls les choix de Avis du jour entrent dans ce taux officiel. Les analyses et tickets personnels en sont exclus et leur espace affiche uniquement un historique de résultats, sans autre pourcentage de réussite.

Ce tableau public ne consomme aucun essai personnel et ne crée pas de données dans l’historique privé. Les analyses individuelles et le suivi personnel existants conservent leur fonctionnement.

## Cotes victoire archivées

Chaque avis peut conserver un instantané 1X2 ESPN (bookmaker et consultation)
observé avant le coup d’envoi. Les choix déjà publiés encore à venir peuvent
recevoir leur premier instantané au rafraîchissement suivant, sans modifier leur
marché, leur probabilité ou leur historique de résultat. Une cote conservée est
figée ; les anciens matchs terminés ne sont jamais complétés rétroactivement.
Les données périmées, futures, incomplètes ou concernant d’autres équipes sont
écartées. Aucune migration ni modification du taux officiel.

En bas à droite de chaque avis, les cotes victoire des équipes utilisent le score
final à 90 minutes : vainqueur vert, perdant rouge. En cas de nul, les deux cotes
victoire sont rouges et celle du nul est verte. Ces couleurs sont indépendantes
du gain ou de la perte du pari éditorial (buts, double chance, etc.). Les avis non
réglés restent neutres ; une absence d’archive est explicitement indiquée. Les
prix sont indicatifs, avec la même limite de fraîcheur source qu’ailleurs.


## Récupération des anciennes cotes

Sur un avis réglé sans instantané initial, les champs explicitement nommés `close`
dans la fiche ESPN peuvent fournir un triplet 1X2. L’événement, les deux équipes,
le coup d’envoi, le score final et la fin à 90 minutes sont vérifiés. Une ligne
d’ouverture seule ne suffit pas. Une archive déjà conservée n’est jamais écrasée.
La récupération concerne les choix du jour et les avis des sept derniers jours
lors de leur actualisation ; les autres résultats continuent leur règlement normal.

Ces données sont étiquetées « Cotes de clôture récupérées » avec le bookmaker et un
lien ESPN. Elles portent une date de récupération après match ; aucune date de
consultation avant match ni heure de mise à jour source n’est inventée. Ce sont
les champs de clôture fournis par ESPN, pas une preuve que l’application connaissait
ces prix lors de son pronostic. Les choix, résultats, probabilités et taux officiel
ne sont pas révisés. Une archive incomplète ou indisponible reste absente.


## Présentation finale des cotes dans les avis

Le pied d’un avis réglé affiche seulement le nom du vainqueur du match et sa cote
victoire. La couleur dépend du résultat du pari éditorial : vert si ce pari est
gagné, rouge s’il est perdu, même quand la sélection portait sur les buts ou une
double chance. L’équipe perdante n’est pas affichée. Aucun pied de cote n’est
montré avant le résultat, sur un nul, un avis annulé ou sans cote disponible.
Les titres, liens source et messages d’absence de cote sont retirés de ce pied ;
la provenance et les contrôles de récupération restent conservés dans les données.
Cette présentation remplace les règles d’affichage décrites plus haut.
