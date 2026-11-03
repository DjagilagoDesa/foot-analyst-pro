# Crée mon ticket

Le mode conversationnel et sa connexion OpenAI sont retirés. Aucun service IA externe n’est nécessaire. Un flux indicatif de cotes ESPN est utilisé lorsqu’il fournit le marché exact.

Dans Analyse, choisir :
- les prochaines rencontres de la date choisie, ou tous les matchs du ticket personnalisé ;
- de 2 à 8 matchs (en mode personnel, le nombre suit la sélection) ;
- prudent (75 % minimum par choix), équilibré (60–80 %), offensif (45–65 %) ;
- tous les marchés simples, double chance, buts, BTTS ou double chance + buts sur le même match.

Le moteur ne force pas une sélection en dehors de la plage demandée. Il examine au maximum 16 rencontres en mode automatique, dans l’ordre horaire. Toutes les nouvelles analyses abouties utilisent les essais habituels ; le compte propriétaire conserve son accès gratuit. Les résultats déjà enregistrés sont réutilisés. Une composition incomplète n’est pas présentée comme un ticket terminé.

La cote affichée est théorique et la probabilité combinée suppose des matchs indépendants. Pour une double condition sur un match, la probabilité est calculée sur l’intersection des scores possibles. Les sélections sont envoyées au suivi pré-match existant ; une impossibilité d’enregistrement est signalée.


## Cotes et simulation de ticket

Les fiches affichent les prix 1X2 et les totaux effectivement fournis dans le
scoreboard ESPN, en décimal, avec le bookmaker et l’heure de consultation. Le flux
ne fournit pas systématiquement une date de modification de chaque prix : cette
limite est affichée. Seule la ligne courante `close` est utilisée, jamais la ligne
d’ouverture. La rencontre, les équipes et le statut avant-match sont vérifiés.
L’API ne renvoie aucune URL d’affiliation.

La récupération est mise en cache 60 secondes côté serveur et client. Une
consultation est utilisable au maximum cinq minutes, sans dépasser le coup
d’envoi ; les cotes expirées ne permettent plus le calcul et peuvent être
actualisées manuellement. Il ne s’agit pas d’une garantie de fraîcheur du prix chez
le bookmaker. Le bouton Actualiser réinterroge le serveur, dont le cache reste
applicable. Une panne ne produit jamais de cote inventée.

Dans chaque profil, les marchés cotés sont triés par probabilité du modèle × cote,
avec le premier bookmaker retourné par la source. Si aucun marché admissible
n’est coté, le tri historique par probabilité est conservé. Les modèles,
pourcentages, Avis du jour et l’expérience prospective ne sont pas modifiés.
La couverture peut donc influer sur la sélection, sans prouver un avantage ou
une rentabilité. Les tickets quotidiens partagent le même mécanisme de choix.

Les tickets personnel, guidé et quotidiens disposent d’un simulateur. Une seule
source bookmaker est choisie dans chaque simulateur ; les cotes d’autres
bookmakers ne sont pas automatiquement multipliées ensemble. Un champ reste à
renseigner lorsqu’un marché exact est absent. L’utilisateur peut aussi choisir
la saisie personnelle et recopier toutes les cotes de son bookmaker ; ces cotes
sont explicitement non vérifiées. Une double chance + buts requiert la cote de
cette double condition, jamais le produit de deux cotes du même match.

La cote totale est le produit des cotes renseignées, le retour potentiel est la
mise × cote totale et le bénéfice potentiel retranche la mise. Aucun résultat
n’est calculé si une ligne ou la mise est invalide, si une consultation automatique
est expirée, si un match a commencé ou si une équipe revient sur plusieurs lignes.
Les limites d’acceptation, les plafonds, les arrondis et les règles d’annulation
d’un bookmaker ne sont pas simulés. Rien n’est misé, payé ou enregistré comme un
pari effectivement placé. Les cotes et la mise ne sont pas persistées.
