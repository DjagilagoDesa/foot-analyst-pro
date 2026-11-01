# Avis du jour

Une sélection commune à tous les utilisateurs est publiée sur l’accueil et dans Tickets du jour : trois choix prudents, deux choix plus difficiles et une surprise. Ce sont six rencontres et douze équipes distinctes ; les places restent vides si les données ou les probabilités sont insuffisantes.

La sélection emploie le modèle Poisson existant sur dix matchs terminés par équipe. Plages : 75–95 % pour Prudent, 50–70 % pour Plus difficile, 25–45 % pour Surprise. La surprise est une victoire du côté moins favori en 1X2, avec au moins cinq points de probabilité d’écart. Les marchés simples sont classés par probabilité dans chaque plage, pas par rentabilité. Aucune cote bookmaker, composition, actualité ou absence non vérifiée n’est inventée.

Au maximum 24 rencontres sont étudiées dans les compétitions couvertes, réparties sur les horaires de la journée. Les données viennent d’ESPN ; la couverture peut être partielle. Un choix prudent n’est pas certain et ces probabilités ne sont pas calibrées. Les six sélections individuelles ne constituent pas un combiné garanti.

La date est celle de Paris, y compris lors des changements d’heure. Le serveur contrôle la sélection environ toutes les quinze minutes pendant son activité. Un workflow GitHub planifié deux fois par heure réveille le serveur et contrôle la date du tableau ; comme tout déclenchement planifié, il peut être retardé par la plateforme. La première requête démarre le traitement en arrière-plan. L’application recharge le tableau automatiquement tant que sa rubrique est visible et au retour au premier plan.

Les tableaux sont stockés dans PostgreSQL, avec un verrou temporaire partagé entre workers. Les sélections publiées, leur heure et leurs probabilités restent figées. Les places manquantes peuvent être complétées uniquement avant le coup d’envoi ; aucune rencontre déjà commencée n’est ajoutée. Les résultats sont vérifiés ensuite : gagné, perdu ou annulé/non réglable. Les totaux après prolongation ou tirs au but sont exclus des marchés à 90 minutes. Les sept derniers tableaux sont revérifiés pour les résultats en attente. Les erreurs de source conservent les choix existants et l’interface signale un retard.

Le taux officiel de l’application, cumulé depuis la première publication, compte les choix gagnés, perdus, en attente et annulés. Le pourcentage exclut les attentes et annulations ; il ne reconstitue aucun ancien pari.

Seuls les choix de Avis du jour entrent dans ce taux officiel. Les analyses et tickets personnels en sont exclus et leur espace affiche uniquement un historique de résultats, sans autre pourcentage de réussite.

Ce tableau public ne consomme aucun essai personnel et ne crée pas de données dans l’historique privé. Les analyses individuelles et le suivi personnel existants conservent leur fonctionnement.
