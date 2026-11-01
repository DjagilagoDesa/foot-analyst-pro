# FOOT ANALYST PRO V42 — prototype tickets quotidiens

## Ajouts
- Bouton « Générer les tickets du jour » dans Mes analyses.
- Endpoint `GET /api/v42/daily-tickets` : consulte les rencontres à venir du jour (Europe/Paris), vérifie les données historiques, propose 3 profils de 2, 3 et 4 matchs distincts.
- Paris spéciaux proposés : double chance, over 1,5 / 2,5, les deux équipes marquent, et victoires simples. Pas de corners, cartons, buteurs faute de données adaptées.
- Affichage explicite des probabilités du modèle, des cotes équitables **théoriques** (pas de cotes bookmaker), de la couverture partielle et des limites.
- Pas de fabrication de ticket lorsque les données ou le nombre de rencontres sont insuffisants.

## Limitations à ne pas masquer
- Génération **à la demande**, non automatique en arrière-plan. Un vrai rendez-vous quotidien requiert un scheduler, une base persistante et des tâches asynchrones.
- Les probabilités ne sont ni calibrées ni validées hors échantillon. Les probabilités combinées supposent une indépendance approximative.
- **Aucun taux de réussite de l'IA n'est affiché** tant qu'un journal horodaté et persistant des prédictions, avec comparaison aux résultats officiels, n'existe pas.
- L'API ESPN utilisée est non officielle et sa couverture varie. Les statistiques avancées, enjeux, compositions, blessures, actualités et modèle génératif personnalisé restent à intégrer.
- Les essais Premium par compte et la facturation ne sont pas activés. Ne pas présenter l'application comme un service Premium fonctionnel.

## Déploiement
Nouvelle branche `v42-test`, service Render distinct, Dockerfile inclus. Conserver V41 et la production inchangées.
