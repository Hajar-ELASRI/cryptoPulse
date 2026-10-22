# Brief de travail — Mohammed

## Mission attribuée

Construire le tableau de bord React et préparer une démonstration cohérente. Cette répartition parmi les trois chantiers encore libres (Spark, API, frontend) a été tirée au hasard; Hajar conserve l'ingestion déjà commencée.

## Résultat attendu

Donner une interface simple qui rend visibles les transformations Big Data : indicateurs par minute, alertes avec raison et seuil, sentiment avec contexte, analyses et replay. Le dashboard doit consommer l'API de Mossab, et non traiter lui-même les données brutes.

## À lire avant de coder

- [`Contexte général`](../project-context.md)
- [`Contrats Kafka et MongoDB`](../contracts.md)
- [`Plan de travail d'origine`](../plan-travail.md)

Coordonner les besoins des écrans et le format de réponse avec Mossab (API) et Ali (transformations). Démarrer avec mocks conformes au contrat si leurs composants ne sont pas encore disponibles.

## Tâches

1. Créer l'application React avec configuration d'API par variable d'environnement et structure réutilisable.
2. Concevoir une vue Live avec symbole, prix/variation, volume et agrégats temporels provenant de `indicators`.
3. Créer une liste d'alertes filtrable; montrer explicitement type, heure, valeur observée, seuil déclencheur et motif lisible.
4. Ajouter une vue sentiment/articles indiquant période, score/label et symbole associé; signaler clairement que sentiment/cours est une corrélation observée.
5. Ajouter Analytique et Replay avec sélecteur de symbole/période et état de chargement/erreur/vide.
6. Ajouter actualisation périodique (ou SSE si l'API et le temps le permettent) sans rafraîchissement agressif; afficher la date de dernière mise à jour.
7. Rendre l'interface utilisable sur écran de présentation et portable, avec libellés compréhensibles et formatage cohérent des nombres et dates UTC/locales clairement identifiées.
8. Remplacer les mocks quand les routes API de Mossab sont prêtes; ne pas cacher de calcul métier côté client.
9. Préparer une procédure de démo avec scénario synthétique reproductible et captures ou données secours si Binance/RSS est indisponible.

## Handoff / dépendances

- Mossab confirme les routes, paramètres, champs et exemples JSON. Partager les besoins d'affichage tôt.
- Ali confirme les définitions et seuils des indicateurs/alertes; les expliquer dans l'interface sans inventer leur sens.
- Hajar confirme les ports et lancement Compose; mocks restent disponibles pour le développement hors ligne.
- Toute donnée simulée doit être identifiée comme démonstration et séparée des données réelles.

## Définition de terminé

- Les cinq parcours (Live, Alertes, Sentiment, Analytique, Replay) sont accessibles et compréhensibles.
- L'interface consomme les routes réelles, avec états de chargement, vide et erreur; les mocks de secours sont identifiés.
- Une alerte permet de comprendre immédiatement pourquoi elle a été produite.
- Procédure de démo documentée et liée aux données/API disponibles; PR revue par un autre membre.

## Hors périmètre principal

Ne pas recalculer les agrégats/alertes dans React et ne pas accéder directement à MongoDB ou Kafka. Mossab est le seul propriétaire de l'API backend.
