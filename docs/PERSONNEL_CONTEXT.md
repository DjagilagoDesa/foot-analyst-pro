# Effectifs signalés pour toutes les compétitions couvertes

Le contrôle d'effectifs n'est plus limité à la Ligue des champions : il est appelé
pour les treize compétitions couvertes par l'API de l'application, sur une rencontre
identifiée par son événement et ses deux équipes. Cette extension n'implique pas
que le fournisseur dispose d'informations pour tous les matchs ou championnats.

Les compositions et signalements d'absence viennent de la fiche ESPN du match.
Les titulaires signalés ne sont jamais présentés comme une composition officiellement
confirmée par le club. Seuls les signalements d'indisponibilité datés de moins de
sept jours sont retenus. Absence d'information ne signifie pas effectif complet ;
une suspension n'est pas supposée applicable à une autre compétition.
Les contradictions entre blessure et présence parmi les titulaires sont explicites.
L'impact est décrit conditionnellement par rôle ; l'importance individuelle du joueur
n'est pas chiffrée. Aucun coefficient de buts ni pourcentage n'est corrigé à partir
de ces informations.

## Actualisation et historique

Une analyse réussie garde son instant de génération et ses probabilités d'origine.
Les états des effectifs sont ajoutés à `personnel_snapshots` lors d'un changement,
sans dupliquer une simple nouvelle consultation du même état. Les états initiaux,
y compris indisponibles, sont conservés. `personnel_context` désigne la dernière
consultation vérifiée. Les instantanés sont inclus dans l'historique et l'export
personnel existants et supprimés avec le compte, sans table ou migration supplémentaire.

Le bouton « Actualiser les effectifs » utilise une analyse déjà enregistrée. La route
POST `/api/account/analysis/<analysis_id>/personnel` exige session, origine, CSRF et
propriété de l'analyse. Elle n'effectue aucune réservation ni aucun prélèvement d'essai.
Un résultat de source est mis en cache deux minutes et les contrôles d'une analyse
sont espacés d'au moins cinq minutes. Les écritures vérifient le résultat initial en
base pour qu'une réponse lente ne puisse pas écraser un état plus récent.

Sur une analyse affichée, un contrôle automatique est prévu toutes les cinq minutes
avant le coup d'envoi. Il n'émet pas de requêtes quand la page est masquée et s'arrête
lors d'un changement d'écran ou d'une déconnexion. Au retour de l'application
au premier plan (ou d'une page restaurée), un contrôle reprend immédiatement si
la dernière tentative date d'au moins cinq minutes. Les événements de reprise
rapprochés ne lancent pas plusieurs requêtes concurrentes. L'historique possède les mêmes
commandes pour les rencontres encore à venir. Un ancien état passé est figé ; une
source en panne, une rencontre commencée, reportée ou incorrecte n'écrase pas la
dernière information vérifiée. L'heure est recontrôlée après la réponse réseau.

Les informations ne sont pas mises à jour en tâche de fond lorsque l'application
est fermée. Aucune alerte ou notification n'est envoyée.

## Contrôles

Tests API : couverture des treize compétitions, états inconnus, ancienneté et dates
invalides, contradictions, conservation des instantanés, forfaits non certifiés,
source revenant après le coup d'envoi, absence de consommation d'essai, contrôles de
propriétaire et CSRF, export, et refus d'un écrasement concurrent.
Test navigateur sur écran de téléphone : bouton, historique daté, échappement des
noms de joueurs, actualisation automatique et absence de requête sur écran masqué.
Les tests de compte, du calendrier, des tickets, du suivi et de l'expérience prospective
restent exécutés avec SQLite et PostgreSQL.
