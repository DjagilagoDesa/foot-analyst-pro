# V43 — suivi empirique des tickets et amélioration des rapports

- Branche GitHub recommandée : `v43-test`. Ne pas écraser main/V40/V41/V42.
- Ouvrir « Mes analyses » charge les 3 profils de tickets du jour et le tableau de performance.
- `/api/v43/performance` enregistre les résultats observés de sélections capturées avant le coup d’envoi; Brier calculé uniquement sur résultats terminés vérifiés via ESPN.
- Le suivi est **temporaire sur Render par défaut** : pour le rendre durable, provisionner un disque persistant et définir `FAP_TRACKING_DB` vers son chemin monté. Le plan gratuit Render ne fournit généralement pas de disque persistant. Pour une production multi-instance, migrer vers PostgreSQL.
- Aucun historique rétroactif inventé, aucun bookmaker ni cote réelle, aucune promesse de gains.
- Pas de planificateur quotidien autonome : génération automatique à l’ouverture de « Mes analyses ». Un cron externe et un stockage durable seront nécessaires pour une génération à heure fixe.
- Les rapports restent statistiques et ne disposent pas encore de classements, blessures, xG, enjeux vérifiés ni de véritable modèle génératif.
- À tester en conditions réelles : API ESPN, compilation, chargement UI, journalisation, règlement des matchs, données insuffisantes, déploiement Render.
