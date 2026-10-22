# CryptoPulse — plan de travail de l'équipe

> Document de cadrage initial avec trois rôles A/B/C. Pour la répartition actuelle entre quatre membres et l'état vérifié, utiliser le [contexte général](project-context.md), les [briefs individuels](team/README.md) et le [rapport d'ingestion](validation-ingestion.md). Les mentions d'une validation Docker encore à faire ci-dessous décrivent l'état initial.

## Objectif

CryptoPulse ne doit pas seulement archiver les transactions. Le pipeline doit transformer les flux bruts en données propres, enrichies et agrégées, puis fournir des indicateurs et des alertes que le tableau de bord peut expliquer.

## État actuel

- Le dépôt GitHub est `Hajar-ELASRI/cryptoPulse`. La base de la partie A a été poussée sur `codex/person-a-ingestion`.
- Le dépôt contient le Compose local Kafka, MongoDB et Spark, les collecteurs Binance/RSS/Reddit, l'import historique, le service de sentiment, le README et le contrat initial dans [`contracts.md`](contracts.md).
- Les tests unitaires de normalisation ont déjà été exécutés avec succès. Le démarrage de toute la pile et le flux de bout en bout restent à vérifier avec Docker.
- Le dépôt n'a pas encore de branches d'équipe `main` et `develop`. À décider au kickoff : le coordinateur crée `develop` pour l'intégration et `main` pour la version de démonstration, puis les PR des membres visent `develop`.
- Le contrat des événements est une proposition de départ. A, B et C doivent le relire ensemble avant de figer les noms, champs et types.

## La transformation à présenter au professeur

### 1. Flux brut

Binance envoie notamment `symbol`, `price`, `quantity`, `trade_id`, `event_time` et `is_buyer_maker`. Les nombres de prix et quantité sont conservés en chaînes à l'entrée pour ne pas perdre de précision.

### 2. Données nettoyées et normalisées (couche Silver)

Le traitement Spark doit :

- valider les champs obligatoires et écarter prix ou quantités nuls, négatifs ou illisibles ;
- convertir prix et quantité en types décimaux, et `event_time` en timestamp UTC ;
- dédupliquer avec `event_id` et une fenêtre d'eau (*watermark*) ;
- uniformiser les symboles et conserver la source ;
- calculer `quote_volume = price × quantity` en USDT pour BTCUSDT/ETHUSDT ;
- calculer `window_start` pour ranger la transaction dans sa minute.

Exemple : une transaction à 65 000,50 USDT pour 0,02 BTC devient un volume coté de **1 300,01 USDT**.

### 3. Indicateurs agrégés (couche Gold)

Par symbole et par fenêtre d'une minute, Spark calcule au minimum : nombre de transactions, prix moyen, prix minimum/maximum, volume en crypto, volume coté en USDT et variation par rapport à la minute précédente.

Formule de variation : `100 × (prix_moyen_courant - prix_moyen_précédent) / prix_moyen_précédent`.

### 4. Valeur ajoutée : alertes et contexte

- **Pic de volume :** comparer le volume de la minute à sa moyenne glissante précédente (par exemple les 20 minutes précédentes). Émettre une alerte si le volume dépasse un seuil défini par l'équipe, par exemple 2 fois cette moyenne. Prévoir une période de chauffe avant d'activer la règle.
- **Variation forte :** créer une alerte quand la variation dépasse le seuil convenu par l'équipe.
- **Grande transaction :** signaler une transaction dont le montant coté dépasse le seuil configurable.
- **Actualités et sentiment :** nettoyer et dédupliquer les articles/posts, calculer un score de sentiment, associer les symboles détectés et montrer le sentiment agrégé près des indicateurs de prix. Présenter cela comme une corrélation observée, pas comme une preuve que l'actualité a causé le mouvement.

Les seuils doivent être configurables et expliqués dans le rapport. Commencez avec des valeurs choisies pour la démonstration et ajustez-les après observation des données.

### Résultats MongoDB attendus

- `trades` : événements valides nettoyés et enrichis, avec `quote_volume` et timestamp BSON ;
- `indicators` : une ligne par symbole et minute avec les agrégats ;
- `alerts` : type, gravité, symbole, heure, valeur observée et seuil déclencheur ;
- `news`, `social_posts`, `sentiment` : éléments nettoyés et scores de sentiment ;
- `trades_history` : historique importé, utilisable par le replay.

Personne B confirme les schémas de sortie avec A et C et les ajoute au contrat avant d'implémenter les traitements.

## Répartition des tâches

### Personne A — ingestion et infrastructure

**Déjà préparé dans la branche actuelle :** Compose Kafka/MongoDB/Spark, topics, normalisation des messages Binance, collecteurs RSS et Reddit, chargement historique par lots, service de sentiment, exemple de `.env` et contrat initial.

**À faire maintenant :**

1. Relire le contrat avec B et C et convenir des types/horodatages avant l'intégration.
2. Démarrer Docker et valider Compose, Kafka, MongoDB et Spark sur la machine de l'équipe.
3. Vérifier les messages réels des topics `crypto-trades` et `crypto-news`; pour Reddit, configurer les accès nécessaires dans `.env` sans les committer.
4. Faire un petit import historique (un symbole, un mois), vérifier les dates et les doublons, puis augmenter le volume.
5. Confirmer avec B où le résultat du sentiment sera stocké et tester la publication dans `crypto-sentiment`.
6. Documenter les limites, erreurs de connexion et commandes de relance.

**Livrable A :** les topics d'entrée sont alimentés et conformes au contrat ; l'historique est consultable ; les événements de sentiment sont disponibles pour B.

### Personne B — transformations Big Data avec Spark

1. Créer les jobs Spark Structured Streaming qui lisent `crypto-trades`, `crypto-news`, `crypto-social` et `crypto-sentiment`.
2. Implémenter la couche Silver : schéma explicite, conversions Decimal/timestamp, validation, déduplication avec watermark et traitement des événements en retard.
3. Enrichir les transactions avec `quote_volume` et fenêtre temporelle.
4. Calculer les indicateurs par minute et les moyennes glissantes ; définir les seuils et règles d'anomalie avec l'équipe.
5. Écrire les événements transformés dans les collections MongoDB convenues, avec checkpoint Spark et index nécessaires.
6. Permettre le replay : la même logique d'indicateurs et d'alertes doit pouvoir traiter l'historique.
7. Mesurer et documenter le débit, le délai, les partitions, les checkpoints et les limites du prototype.

**Livrable B :** les collections `trades`, `indicators` et `alerts` contiennent des résultats transformés et expliqués, pas seulement les messages d'origine.

### Personne C — API et tableau de bord

1. Démarrer avec des données simulées conformes au contrat afin de travailler sans attendre les flux réels.
2. Exposer les routes Spring Boot : `/api/live`, `/api/alerts`, `/api/sentiment`, `/api/replay` et `/api/analytics`.
3. Construire d'abord les vues Live, Alertes et Sentiment ; ajouter Replay et Analytique ensuite.
4. Montrer les indicateurs produits par B : volume par minute, prix moyen, variation, score de sentiment et raison/seuil de chaque alerte.
5. Ajouter l'actualisation périodique ou SSE/WebSocket, puis Dockeriser l'API et React.

**Livrable C :** le tableau de bord présente les données transformées, et l'utilisateur peut voir pourquoi une alerte s'est déclenchée.

### Travail collectif

- Confirmer les contrats Kafka, MongoDB et REST dans `docs/contracts.md` avant le développement parallèle ; toute modification est validée par les trois membres.
- Écrire une issue par tâche. Utiliser le tableau `To do → Doing → Review → Done`.
- Travailler sur des branches de fonctionnalité ; ouvrir une PR vers `develop`, demander une revue d'un autre membre, et ne pas pousser directement sur `main`/`develop`.
- Faire un point court tous les deux jours pour signaler blocages et changements de contrat.
- Garder `.env` local et ne jamais ajouter de secrets, clés API ou tokens au dépôt.

## Ordre de travail et points de passage

### Étape 0 — Kickoff (tous)

- Confirmer la visibilité et les branches de travail du dépôt ; initialiser `main` et `develop` si l'équipe adopte le workflow prévu.
- Valider les quatre contrats (topics Kafka, collections MongoDB, routes REST, types/timestamps) et décider des seuils de démonstration.
- Créer les issues assignées aux personnes A, B et C.

### Étape 1 — Construire en parallèle

- A valide l'infrastructure et le flux Binance réel.
- B implémente le job Spark et ses transformations avec des messages d'exemple.
- C monte l'API et les vues principales avec des données simulées conformes au contrat.

**Passage à l'étape suivante lorsque :** Spark lit un message de test, écrit un document transformé dans MongoDB et l'API peut le retourner.

### Étape 2 — Ajouter la valeur ajoutée

- A ajoute les flux RSS/Reddit, l'historique et le sentiment.
- B calcule les fenêtres, indicateurs, alertes et replay à partir du flux et de l'historique.
- C ajoute les vues Sentiment, Alertes, Replay et Analytique en consommant les sorties réelles.

**Passage à l'intégration lorsque :** une transaction réelle produit un indicateur minute, et un scénario artificiel déclenche l'alerte attendue.

### Étape 3 — Intégration

- Remplacer les données simulées par les données réelles.
- Vérifier les noms de champs, types, fuseaux horaires, déduplication, redémarrage et erreurs réseau.
- Suivre un même événement de la source jusqu'à MongoDB puis jusqu'à l'écran.

### Étape 4 — Préparer la soutenance

- Préparer un jeu de démonstration reproductible : démarrer les collecteurs, montrer le flux, déclencher une alerte connue, afficher le sentiment et rejouer une période historique.
- Présenter le schéma avant/après transformation, les formules des indicateurs, les seuils et une mesure du délai de traitement.
- Garder une démonstration de secours avec les données simulées si une source externe tombe.

## Critères de réussite

- Un message brut devient un document propre avec types et temps normalisés, déduplication et volume coté calculé.
- Les agrégats par minute et les alertes sont vérifiables avec un exemple chiffré.
- L'API et le tableau de bord utilisent les collections transformées.
- Le replay reproduit les indicateurs/alertes d'une période passée.
- Le rapport distingue clairement données d'entrée, transformations, résultats et limites du modèle de sentiment.
