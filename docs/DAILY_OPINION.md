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

Le pied d’un avis réglé affiche uniquement le chiffre de la cote victoire du
vainqueur du match, sans nom, titre, source ou autre texte. La couleur dépend du résultat du pari éditorial : vert si ce pari est
gagné, rouge s’il est perdu, même quand la sélection portait sur les buts ou une
double chance. L’équipe perdante n’est pas affichée. Aucun pied de cote n’est
montré avant le résultat, sur un nul, un avis annulé ou sans cote disponible.
Les titres, liens source et messages d’absence de cote sont retirés de ce pied ;
la provenance et les contrôles de récupération restent conservés dans les données.
Cette présentation remplace les règles d’affichage décrites plus haut.

## Buteur du jour

Une quatrième rubrique repliable publie un seul buteur par date de Paris. Le choix
est conservé dans `scorer`, dans le tableau persistant partagé. Il ne consomme
aucun essai et ne remplace aucun des six avis de matchs. Son bilan cumulé
`scorer_performance` est séparé du taux des six avis et des paris personnels.

La sélection examine au maximum douze rencontres à venir, réparties sur les
horaires de la journée. La fiche ESPN doit confirmer l’événement, les équipes
et le coup d’envoi. Les candidats viennent des leaders en buts de la compétition,
avec au moins deux buts et cinq apparitions documentés. Le classement compare
le rendement buts/apparitions, lissé par un a priori d’un but sur cinq matchs,
et le contexte offensif des équipes sur trois à cinq résultats observés dans
les 90 derniers jours. Aucun taux de réussite individuel ni rôle sur penalty
n’est inventé. Le score de classement interne n’est pas une probabilité calibrée.

Un joueur explicitement remplaçant, non listé dans une composition disponible,
inactif ou signalé incertain/absent est écarté. Sans composition, sa titularisation
est affichée à confirmer. Une indication de titulaire par ESPN n’est pas présentée
comme une confirmation officielle du club. Le choix et sa base statistique restent
figés après publication ; son indication de disponibilité peut être actualisée.
Après les appels réseau, une dernière vérification du temps empêche de publier
une rencontre commencée. En l’absence de données admissibles, la rubrique reste
présente avec un état vide ; elle ne nomme pas un joueur par défaut.

Le résultat utilise uniquement les buts et apparitions individuels de la fiche
du match terminé à 90 minutes. Un but contre son camp ne constitue pas un but
marqué par le joueur. Aucune déduction n’est faite depuis le score d’équipe ou
les statistiques cumulées de saison. Les données manquantes restent en attente ;
une non-participation explicitement documentée, une rencontre annulée/reportée
ou des prolongations non prises en charge donnent un avis annulé. Un avis de
buteur ne matérialise aucune mise ou transaction chez un bookmaker.

## Cote du buteur

Le chiffre affiché à côté du joueur est une cote observée sur le marché Unibet
« Buteur — 90 Mins ». Il ne s’agit ni de la cote de victoire de son équipe, ni
d’un premier buteur, buteur/passeur, pari boosté ou pari portant sur le remplaçant.
La collecte utilise les pages football publiques, sans compte ni clé payante.
L’événement est identifié par ses deux clubs, leur ordre domicile/extérieur et
l’heure exacte, puis le joueur par son nom complet normalisé et unique dans
le marché. Les variantes de noms de clubs reconnues sont explicites ; les
équipes féminines, jeunes ou réserves ne sont pas rapprochées par approximation.

Le point `/api/daily-opinion/scorer-odds` utilise uniquement le buteur déjà publié,
et n’accepte aucun événement ou joueur arbitraire du client. L’index et la fiche
sont mis en cache pendant deux minutes, erreurs incluses. Les données de session
présentes dans le HTML du fournisseur ne sont pas conservées dans ce cache.
Les marchés masqués/suspendus et les prix invalides ou périmés sont écartés.
L’interface affiche un tiret en l’absence d’une cote admissible. Elle interroge
le point après le tableau, sans bloquer l’affichage initial de l’avis.

Une cote observée avant le coup d’envoi est enregistrée avec le bookmaker,
les identifiants source, l’heure et l’URL de consultation. Cette mise à jour
conditionnelle ne peut écraser ni le règlement des résultats, ni un verrou de
génération entre workers. Après le coup d’envoi, la dernière cote avant match
reste consultable ; aucune cote en direct n’est présentée comme une cote initiale.
Le montant ne modifie jamais la sélection du joueur ou son classement statistique.
La valeur reste indicative et peut différer de celle disponible chez un autre
bookmaker ou au moment où l’utilisateur le consulte.
