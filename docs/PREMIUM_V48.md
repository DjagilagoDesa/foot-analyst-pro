# V48 : analyses et abonnement

L’analyse rédigée est calculée à partir des moyennes et bilans réellement récupérés. Elle ne prétend pas intégrer des actualités non recherchées. Les anciens résultats Poisson enregistrés sont enrichis à la consultation via le bouton Analyser, sans consommer un nouvel essai.

L’espace abonnement affiche l’état du compte et les essais restants, le tarif prévu à 29,90 €/mois et le lien de gestion Google Play. Les achats restent désactivés ; aucun paiement n’est simulé.

Pour ACTIVER réellement les achats, il reste un chantier d’intégration distinct :
1. Confirmer/créer l’application dans Play Console avec le package définitif et le profil marchand.
2. Configurer l’abonnement `foot_analyst_pro_premium_monthly`, son forfait mensuel et son prix de 29,90 EUR, pays et conditions.
3. Intégrer Google Play Billing dans le client Android, avec achat, annulation, attente et restauration. L’APK debug actuel n’a pas cette intégration.
4. Relier un compte de service autorisé à l’API Google Play Developer, conserver les secrets uniquement sur Render.
5. Vérifier chaque achat côté serveur (produit, état, expiration, liaison au compte et unicité du token), acquitter les achats valides et synchroniser renouvellements, remboursements et révocations via notifications et revalidation serveur.
6. Tester sur piste Google Play avec testeurs de licence avant ouverture commerciale.

Ne pas attribuer Premium depuis un bouton, un paramètre client, un prix affiché ou une capture de paiement. Le serveur dispose de `premium_until`, mais aucune route publique ne permet de le modifier.
