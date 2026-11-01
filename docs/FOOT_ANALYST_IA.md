# FOOT ANALYST IA

Le formulaire statistique manuel V36 est remplacé par une zone de demande en texte libre.

## Disponible sans connexion modèle

Le calculateur construit un combiné de 2 à 8 rencontres distinctes à partir de 12 sélections maximum fournies par l’utilisateur. Exemple :

```
Crée un ticket entre 30 et 50
Marseille – Toulouse | 1X + les deux marquent | 3,5
Match B | X2 + plus de 2,5 buts | 3
Match C | Les deux marquent | 4
```

Le produit vaut 42. Ces cotes sont saisies par l’utilisateur et ne sont pas vérifiées auprès de Winamax. Deux lignes portant le même nom de rencontre ne sont pas combinées. Pour plusieurs conditions sur un match, saisir la cote du pari combiné proposée par le bookmaker. Le calculateur ne mesure pas la fiabilité sportive et ne place aucun pari.

## Activation du modèle conversationnel

Configurer uniquement sur le serveur Render :
- `OPENAI_API_KEY` : secret du projet API ; jamais dans GitHub, HTML ou messages.
- `OPENAI_MODEL` : identifiant du modèle Responses disponible sur ce projet.

Le service utilise `POST https://api.openai.com/v1/responses`, avec `store: false`, et un délai de 45 secondes. Aucun budget API ni paiement n’a été activé par cette modification. La conversation utilise le prompt, jusqu’à six messages précédents et au plus trois rapports sportifs du compte. Les profils, mots de passe et jetons de session ne sont pas transmis.

Sans ces deux variables, la conversation reste indisponible et les erreurs ne consomment pas d’essai. Les demandes Winamax sans cotes retournent une demande d’informations, sans inventer de cotes. Aucune connexion Winamax ni recherche web n’est implémentée.

Les échanges aboutis et les calculs réussis sont soumis au quota et au contrôle Premium existants, enregistrés dans l’historique du compte. Le propriétaire conserve son accès gratuit.
