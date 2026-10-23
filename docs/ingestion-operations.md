# CryptoPulse — exploitation et transmission de la partie Hajar

## Démarrage

Installer Docker Desktop avec le moteur Linux actif et Git. Copier `.env.example` vers `.env` si ce fichier local n'existe pas encore, puis exécuter à la racine :

```sh
docker compose up --build -d
docker compose ps -a
docker compose logs --tail 30 binance-collector rss-collector sentiment
```

Les services ponctuels `kafka-storage-init`, `kafka-init` et `mongo-init` doivent terminer avec le code 0. Leur état `Exited (0)` est normal. Le premier corrige les droits du volume Kafka neuf pour l'utilisateur 1000 du broker; les deux suivants créent topics, collections et index de manière répétable.

Les images par défaut sont Kafka `4.3.1`, MongoDB `8.0` et Spark `3.5.9-scala2.12-java17-python3-ubuntu`. `KAFKA_IMAGE` et `SPARK_IMAGE` permettent des substitutions explicites dans `.env`; les membres doivent utiliser les mêmes versions. Ne pas rétrograder un broker sur un volume initialisé avec une version plus récente.

## Vérification opérationnelle reproductible

```sh
docker compose --profile verify run --build --rm ingestion-check
```

Cette commande retourne un rapport JSON et le code 0 si les contrôles réussissent, le code 1 sinon. Elle vérifie :

- la connexion MongoDB, les sept collections attendues et l'index historique unique;
- l'enregistrement d'au moins un worker Spark;
- l'existence des quatre topics Kafka avec trois partitions chacun;
- trois événements récents disponibles par topic `crypto-trades`, `crypto-news` et `crypto-sentiment`, avec leurs types, identifiants, clés Kafka, timestamps et métadonnées.

Le contrôle lit des événements sans modifier les offsets des consommateurs existants. Il attend jusqu'à 90 secondes par phase qui nécessite une attente; cette durée et le nombre d'échantillons sont configurables :

```sh
docker compose --profile verify run --rm ingestion-check python -m scripts.verify_ingestion --samples 5 --timeout 120
```

Il s'agit d'une vérification d'échantillons d'ingestion et de l'infrastructure. Elle ne valide pas les futurs calculs Spark, les routes API ou le dashboard. Le topic Reddit est contrôlé même si aucun message social n'est disponible; le flux social n'est pas obligatoire pour réussir ce contrôle.

## Historique : commencer par un échantillon

Pour une vérification peu volumineuse et reproductible, utiliser le mois de janvier 2025 sur `BNBBTC` et limiter le nombre de lignes traitées par archive :

```sh
docker compose --profile history run --build --rm -e HISTORY_SYMBOLS=BNBBTC -e HISTORY_PERIODS=2025-01 -e HISTORY_MAX_ROWS=1000 historical-loader
```

`HISTORY_PERIODS` contient des mois terminés au format `YYYY-MM`, séparés par des virgules; il remplace `HISTORY_MONTHS`. `HISTORY_MAX_ROWS=1000` importe au plus les 1 000 premières lignes valides de chaque archive. Le ZIP complet est néanmoins téléchargé et mis en cache sous `data/history`.

Relancer exactement la même commande permet de vérifier l'idempotence : si les 1 000 lignes sont déjà présentes, le log indique `0 new trades`. L'import utilise des insertions par lots, tolère les doublons de l'index unique `(symbol, trade_id)` et conserve les documents existants. Les lots validés sont suivis dans `history_imports`.

Pour importer le mois entier du symbole choisi :

```sh
docker compose --profile history run --rm -e HISTORY_SYMBOLS=BNBBTC -e HISTORY_PERIODS=2025-01 -e HISTORY_MAX_ROWS=0 historical-loader
```

Pour les trois derniers mois terminés de BTC/ETH, laisser `HISTORY_PERIODS` vide, remettre `HISTORY_MAX_ROWS=0` et configurer `HISTORY_SYMBOLS` / `HISTORY_MONTHS` dans `.env`. Les archives BTC/ETH sont beaucoup plus volumineuses que l'échantillon d'intégration : augmenter progressivement le volume retenu par l'équipe.

```sh
docker compose exec mongo mongosh --quiet crypto_pulse --eval 'db.trades_history.countDocuments({symbol:"BNBBTC"})'
```

Les prix et quantités historiques restent des chaînes décimales. `event_time` est une date BSON UTC, y compris pour les archives Binance récentes dont l'horodatage source est en microsecondes. Les valeurs non finies, nulles, négatives et les booléens CSV mal formés sont rejetés.

## Adresses pour chaque membre

- Ali / Spark dans Docker : Kafka `kafka:19092`, Mongo `mongodb://mongo:27017`, base `crypto_pulse`, master `spark://spark-master:7077`. Choisir des checkpoints persistants pour ses jobs; le volume existant du master ne configure pas automatiquement les checkpoints d'un futur driver.
- Mossab / Spring Boot sur la machine : Mongo `mongodb://localhost:27017/crypto_pulse`. Dans le réseau Compose : `mongodb://mongo:27017/crypto_pulse`.
- Mohammed : l'application consommera l'API de Mossab; elle n'accède pas directement à Kafka/Mongo. L'UI Spark de diagnostic est accessible sur `http://localhost:8080`.
- Les membres qui exécutent un consommateur Kafka sur la machine utilisent `localhost:9092`; les conteneurs du réseau Compose utilisent `kafka:19092`.

Le contrat Kafka existant n'a pas changé. Les prix/quantités live sont des chaînes décimales; les clés sont les `event_id`. Les RSS peuvent republier après redémarrage avec le même identifiant stable. Ali doit donc conserver la déduplication prévue et les écritures Mongo idempotentes. Le sentiment est livré au moins une fois : son offset source est validé après livraison, et un arrêt entre ces deux opérations peut produire le même identifiant une seconde fois.

Les symboles de transactions sont des paires (`BTCUSDT`), ceux du sentiment des actifs (`BTC`, `ETH`). Ali doit définir et documenter l'association avant d'agréger les deux flux. VADER traite du texte anglais et reconnaît maintenant aussi les symboles ponctués et cashtags comme `$BTC`; ce n'est pas une analyse causale du marché.

## Reddit

Reddit est optionnel. Configurer localement `REDDIT_CLIENT_ID`, `REDDIT_CLIENT_SECRET` et un vrai `REDDIT_USER_AGENT`, puis :

```sh
docker compose --profile reddit up --build -d reddit-collector
docker compose logs --tail 30 reddit-collector
```

Sans ces identifiants, laisser le profil désactivé. `.env`, les données et les fichiers temporaires sont exclus du dépôt. Le contexte de construction Docker exclut également `.env`, Git et les données téléchargées.

## Diagnostic et arrêt

- Erreur de téléchargement d'image : relancer le téléchargement; ne pas interpréter un échec réseau comme une validation de l'application.
- Kafka ne démarre pas : lire `docker compose logs kafka kafka-storage-init`. Le correctif des droits du volume est intégré; vérifier que l'init termine avec succès.
- Aucun événement RSS/transaction : inspecter les logs des collecteurs et la connectivité aux sources; le contrôle d'ingestion doit échouer s'il manque un flux obligatoire.
- Spark absent du rapport : vérifier `docker compose logs spark-master spark-worker` et la présence d'un worker `ALIVE` dans l'UI. Le worker est limité à 2 cœurs et 1 Go pour ce prototype.
- Les données sources absentes ne doivent pas être présentées comme un flux réel; préparer les mocks identifiés du frontend et les archives déjà importées pour la soutenance.

```sh
docker compose stop
docker compose up -d
```

Ces commandes conservent les volumes et le cache historique. Les paramètres et résultats de la validation effective sont dans [`validation-ingestion.md`](validation-ingestion.md).

## Import long avec reprise

Le téléchargeur garde un fichier `*.zip.part` et reprend avec HTTP Range après une coupure. Si le serveur renvoie le fichier entier, le fichier partiel est remplacé plutôt que concaténé. Le ZIP est contrôlé avant import. Les tentatives réseau sont limitées à huit par appel.

Dans Mongo, chaque lot validé est suivi dans `history_imports`. Pour reprendre, l'empreinte SHA-256 du fichier et le nombre de transactions déjà stockées dans la plage d'identifiants doivent correspondre au checkpoint. Un import terminé et cohérent est ignoré. Un checkpoint incohérent provoque une relecture avec conservation des lignes existantes. Les archives ne sont pas décompressées en entier sur disque.

`HISTORY_MIN_FREE_GB=10` garde une réserve sur le disque partagé avec `data/history`. Si cette réserve est atteinte, le processus échoue en conservant les données et son point de reprise. Une panne après une insertion mais avant son checkpoint peut faire rejouer un lot, sans créer de doublons. Exécuter un seul importeur à la fois sur ces archives.

Pour lancer BTC/ETH sur juillet à septembre 2026 dans un conteneur nommé, depuis un terminal à la racine :

```sh
docker compose --profile history build historical-loader
docker compose --profile history run -d --name cryptopulse-history-btc-eth -e HISTORY_SYMBOLS=BTCUSDT,ETHUSDT -e HISTORY_PERIODS=2026-07,2026-08,2026-09 -e HISTORY_MAX_ROWS=0 historical-loader
docker update --restart=on-failure:3 cryptopulse-history-btc-eth
docker logs --tail 20 cryptopulse-history-btc-eth
```

Le nom doit être libre au premier lancement. Ne pas relancer `run` si le conteneur existe déjà :

```sh
docker inspect cryptopulse-history-btc-eth --format '{{.State.Status}} exit={{.State.ExitCode}}'
docker start cryptopulse-history-btc-eth
```

L'option `docker update` est explicite car `compose run` n'a pas conservé la politique de redémarrage lors du lancement contrôlé. La politique retente jusqu'à trois sorties en erreur; elle ne remplace pas un démarrage manuel après arrêt du moteur Docker. Le téléchargement et l'import restent longs : un conteneur démarré ne prouve pas que les six archives sont terminées.

Contrôler les points de reprise :

```sh
docker compose exec mongo mongosh --quiet crypto_pulse --eval 'db.history_imports.find({}, {_id:1,symbol:1,rows_processed:1,status:1,updated_at:1}).toArray()'
```

Les six documents doivent avoir `status: "complete"` pour confirmer la fin de la série. Aucun document n'est créé avant le premier lot Mongo validé : consulter aussi les logs pendant le téléchargement. Le statut `running` indique le dernier lot validé, pas la santé actuelle du processus.

Un rapport récapitulatif en JSON est également disponible. `--verify` recompte les plages stockées et `--require-complete` retourne le code 1 tant que la série n'est pas finie :

Pour le conteneur nommé encore actif :

```sh
docker exec cryptopulse-history-btc-eth python -m scripts.history_status --verify
```

Pour un contrôle indépendant, même après la fin du conteneur :

```sh
docker compose --profile history run --rm --no-deps -e HISTORY_PERIODS=2026-07,2026-08,2026-09 historical-loader python -m scripts.history_status --verify --require-complete
```

Si Docker est indisponible, les archives peuvent être préparées depuis Windows avec Python et `requests` déjà installé, sans MongoDB. Arrêter le téléchargement indépendant avant de laisser un importeur télécharger les mêmes fichiers en parallèle :

```powershell
$env:HISTORY_DIR = 'data/history'
$env:HISTORY_SYMBOLS = 'BTCUSDT,ETHUSDT'
$env:HISTORY_PERIODS = '2026-07,2026-08,2026-09'
python -m scripts.history_download
```

L'inventaire `data/history/download-inventory.json` est mis à jour après chaque ZIP validé. Les fichiers partiels sont conservés en cas de coupure; le même outil peut être relancé. La préparation des ZIP n'est pas un import dans MongoDB.

Vérifications de récupération (une base de test distincte et jetable est créée puis supprimée par chaque test) :

```powershell
docker compose --profile history run --rm -v "${PWD}/tests:/app/tests:ro" -e MONGO_TEST_URI=mongodb://mongo:27017 historical-loader python -m unittest discover -s tests -v
```
