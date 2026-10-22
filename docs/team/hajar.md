# Brief de travail — Hajar

## Mission attribuée

Posséder et achever l'ingestion des données et l'infrastructure locale. Cette tâche est déjà commencée dans la branche `codex/person-a-ingestion`; l'objectif est de rendre la base testable et de l'intégrer avec les trois chantiers attribués aux autres membres.

## Résultat attendu

Fournir aux autres membres un environnement reproductible, des événements Kafka conformes au contrat et un historique utilisable. Garder Reddit optionnel afin que l'absence d'accès OAuth ne bloque pas la démo.

## À lire avant de coder

- [`Contexte général`](../project-context.md)
- [`Contrats Kafka et MongoDB`](../contracts.md)
- [`README du dépôt`](../../README.md)

## Base déjà présente

La branche actuelle comprend Docker Compose (Kafka, MongoDB, Spark), topics, collecteur Binance, collecteurs RSS et Reddit, chargeur historique Binance, service de sentiment, contrat initial et vérifications unitaires de normalisation. La pile complète n'a pas encore été confirmée en fonctionnement de bout en bout dans l'environnement de l'équipe.

## Tâches

1. Vérifier le dépôt distant et convenir avec le groupe d'une branche d'intégration; ne pas présumer que `main` ou `develop` sont prêts.
2. Démarrer Compose sur une machine d'équipe, vérifier santé/logs et documenter tout changement requis.
3. Inspecter des messages réels `crypto-trades` et `crypto-news`; comparer précisément les champs, types et timestamps à `docs/contracts.md`.
4. Tester une importation historique réduite (un symbole, un mois), confirmer le nombre de documents, la précision, les dates UTC et l'idempotence.
5. Vérifier la publication du sentiment dans `crypto-sentiment`; documenter que VADER est un baseline en anglais et signaler les erreurs/limites.
6. Si OAuth Reddit est disponible, tester le profil Reddit avec `.env`; sinon documenter le statut et garder le chemin principal sans Reddit fonctionnel.
7. Coordonner avec Ali les noms de topics et la gestion de redémarrage/replay; ne pas modifier le contrat sans prévenir les consommateurs.
8. Intégrer les services Spark/API/frontend au Compose si l'équipe le retient, en gardant les ports et variables documentés.
9. Maintenir README et instructions de démarrage, et ne jamais committer `.env`, tokens ou données privées.

## Handoff / dépendances

- Ali a besoin de topics alimentés et d'exemples JSON conformes; partager payloads réels et comportements de redémarrage.
- Mossab a besoin du nom de base Mongo, du réseau/URL interne et des commandes de lancement.
- Mohammed a besoin d'un environnement local stable et d'un plan de secours/mock si les sources externes sont indisponibles.
- Les contrats sont partagés; changements annoncés et documentés avant intégration.

## Définition de terminé

- Compose démarre et les services clés sont vérifiés par commandes/logs documentés.
- Binance et RSS produisent des événements conformes; Reddit est testé ou clairement désactivé avec raison.
- Import historique réduit vérifié et répétable; sentiment publié ou blocage clairement expliqué.
- Les autres membres peuvent lancer l'infrastructure sans secrets committés; PR/branche et instructions partagées.

## Hors périmètre principal

Ne pas implémenter les transformations métier Spark, l'API ou le dashboard; aider à intégrer leurs services et diagnostiquer les interfaces.
