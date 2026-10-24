# Brief de travail — Mossab

> Implémentation locale : [`backend/`](../../backend/) ; lancement, contrat REST et exemples pour Mohammed dans le [guide API](../api.md). L'API utilise les sorties Spark d'Ali récupérées depuis `main` (`2ff9e21`) et les besoins frontend de Mohammed. La validation réelle Spark/Mongo/React et la revue d'équipe restent à effectuer.

## Mission attribuée

Construire l'API backend Spring Boot pour CryptoPulse. Cette répartition parmi les trois chantiers encore libres (Spark, API, frontend) a été tirée au hasard; Hajar conserve l'ingestion déjà commencée.

## Résultat attendu

Fournir une API stable qui lit les données transformées dans MongoDB et permet au tableau de bord d'accéder au marché live, aux alertes, au sentiment, aux analyses et au replay.

## À lire avant de coder

- [`Contexte général`](../project-context.md)
- [`Contrats Kafka et MongoDB`](../contracts.md)
- [`Plan de travail d'origine`](../plan-travail.md)

Coordonner les schémas Mongo avec Ali (Spark), les besoins d'affichage avec Mohammed (React) et les procédures de lancement avec Hajar.

## Tâches

1. Mettre en place le projet Spring Boot, configuration par variables d'environnement et connexion MongoDB.
2. Définir les modèles DTO/API séparément des documents de persistance si cela rend le contrat plus stable.
3. Implémenter les routes prévues : `GET /api/live`, `GET /api/alerts`, `GET /api/sentiment`, `GET /api/analytics` et les routes de replay nécessaires (convenir précisément de la méthode et des paramètres).
4. Ajouter filtres utiles : symbole, période, limite/pagination, type d'alerte. Valider les paramètres et retourner des erreurs claires.
5. Fournir des réponses JSON cohérentes avec timestamps ISO UTC et exemples. Documenter l'API avec OpenAPI si le temps le permet.
6. Gérer les collections vides, indisponibilité Mongo et erreurs d'entrée sans exposer de secrets ni de stack traces aux clients.
7. Ajouter configuration CORS pour le frontend local, health check et Dockerfile si le déploiement local le requiert.
8. Fournir à Mohammed les exemples d'appels/réponses et une URL de service stable; intégrer les vraies données quand le job Spark d'Ali est prêt.
9. Documenter lancement, configuration `.env` et routes dans le README ou un document API.

## Handoff / dépendances

- Ali définit les documents Gold dans `indicators`, `alerts`, `sentiment` et les champs de `trades`; l'API doit consommer ce contrat validé.
- Mohammed indique les besoins d'écran et consomme les réponses de routes; convenir ensemble des noms JSON et du comportement de chargement/erreur.
- Hajar valide que les adresses de services et réseau Docker correspondent à l'environnement Compose.
- Ne pas coder en dur des URLs, credentials ou seuils sensibles.

## Définition de terminé

- Les routes documentées retournent les collections prévues avec données de démonstration et données réelles intégrées quand disponibles.
- Filtres temporels/symbole et pagination sont validés; réponse stable pour collection vide et erreur Mongo.
- Mohammed peut brancher le frontend sans transformation métier cachée côté client.
- API peut démarrer localement (idéalement via Compose) et est documentée; PR revue par un autre membre.

## Hors périmètre principal

Ne pas dupliquer les transformations Spark ni implémenter le dashboard React. Si un traitement métier semble nécessaire dans l'API, valider avec Ali s'il doit plutôt être fait dans Spark.
