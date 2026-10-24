# API CryptoPulse — contrat frontend

API Java 17 / Spring Boot, basée sur les sorties Spark de `origin/main` au commit `2ff9e21`. Les champs Mongo sont ceux d'Ali dans [contracts.md](contracts.md#spark-output-contracts-proposed-v1-ali). Les [besoins de Mohammed](dashboard-api-needs.md) sont pris en charge par les routes ci-dessous.

## Lancement et configuration

URL locale : **http://localhost:8081**. Le port 8080 reste celui de Spark. CORS autorise par défaut `http://localhost:5173` et `http://localhost:3000`.

Depuis la racine, Docker Desktop démarré :

```powershell
# Seulement si .env n'existe pas :
Copy-Item .env.example .env
docker compose up --build -d mongo api
Invoke-RestMethod http://localhost:8081/actuator/health
```

En Java local, Mongo doit être accessible :

```powershell
$env:API_MONGO_URI = 'mongodb://localhost:27017/crypto_pulse?serverSelectionTimeoutMS=3000&connectTimeoutMS=3000&socketTimeoutMS=5000'
$env:MONGO_DATABASE = 'crypto_pulse'
mvn -f backend/pom.xml spring-boot:run
```

Spring Boot lancé via Maven ne charge pas automatiquement `.env`. Exporter les variables dans le terminal ou l'IDE. Compose utilise l'interpolation de `.env`.

| Variable | Défaut local | Usage |
|---|---|---|
| `API_PORT` | `8081` | Port HTTP ; dans Compose, port hôte, conteneur fixé à 8081 |
| `API_MONGO_URI` | Mongo localhost, délais 3/3/5 s | Dans Compose le nom DNS est `mongo` |
| `MONGO_DATABASE` | `crypto_pulse` | Prioritaire sur le nom de base dans l'URI |
| `API_CORS_ORIGINS` | localhost:5173 et localhost:3000 | Origines exactes séparées par virgules |

Conserver les délais dans une URI personnalisée. Aucun secret dans Git. API de développement en lecture seule, sans authentification.

## Contrat commun

Toutes les routes sont des `GET`. Décimaux et scores : **chaînes JSON**, y compris les valeurs issues de doubles Mongo. Compteurs : nombres entiers. Dates : ISO-8601 UTC. `null` reste null (première variation, baseline absente, etc.). Les `_id` Mongo ne sont pas exposés.

**Listes : tableaux JSON simples**, sans enveloppe `data` ou Spring Page. Une collection vide donne `200 []`. Analytics et détail replay enveloppent leurs tableaux comme indiqué ci-dessous.

Pagination : `page=0` par défaut, entre 0 et 10000 ; `limit` entre 1 et 500. Les valeurs par défaut dépendent de la route. Pour charger une période complète, incrémenter `page` en conservant les mêmes filtres jusqu'à recevoir moins de `limit` éléments (ou un tableau vide). Pour le détail replay, continuer jusqu'à ce que **les deux** tableaux contiennent moins de `limit` éléments. Aucun total ni résumé métier n'est calculé.

Symboles supportés : `BTCUSDT`, `ETHUSDT` (normalisation en majuscules). Paramètres temporels : `from` inclusif, `to` exclusif, date avec fuseau ; `from < to`. Les fenêtres filtrent `window_start`, les alertes/sentiments `event_time`. Tri Mongo **avant** pagination, avec `_id` comme second critère stable.

Les indicateurs et alertes utilisent **les deux** filtres `run_id` et `mode` : par défaut `run_id=live, mode=live` ; autre `run_id` : `mode=replay`. Les documents sans ces marqueurs ne sont pas assimilés au live. Identifiants de run : 1 à 80 lettres, chiffres, tirets ou underscores. Le sentiment est éditorial global, sans partition replay dans le contrat Spark actuel.

## Routes

| Route | Paramètres | Réponse / ordre |
|---|---|---|
| `/api/live` | `symbol=BTCUSDT`, `limit=60`, `page=0` | Tableau d'indicateurs live, récent → ancien |
| `/api/alerts` | `symbol,type,severity,from,to,run_id` optionnels ; `limit=100,page=0` | Tableau d'alertes, récent → ancien |
| `/api/sentiment` | `symbol,label,from,to` optionnels ; `limit=50,page=0` | Tableau de sentiments, récent → ancien |
| `/api/analytics` | `symbol,from,to` obligatoires ; `run_id=live,limit=500,page=0` | `{symbol,from,to,run_id,indicators:[...]}`, ancien → récent |
| `/api/replay/runs` | `limit=100,page=0` | Tableau des runs disponibles, début décroissant |
| `/api/replay/{runId}` | `symbol,from,to` optionnels ; `limit=500,page=0` | `{run_id,indicators:[...],alerts:[...]}`, chaque tableau ancien → récent |

`type` : `VOLUME_SPIKE`, `PRICE_MOVE`, `LARGE_TRADE`. `severity` : `warning`, `critical`. `label` : `positive`, `neutral`, `negative`. `/api/replay/live` est refusé. Un run inconnu donne des tableaux vides, ce qui ne constitue pas un statut de job.

La liste des runs regroupe les documents `mode=replay` d'`indicators` et `alerts`, y compris les runs contenant seulement des alertes. `symbols` est trié ; les compteurs portent sur **tout le run**. `start/end` sont les bornes des résultats stockés (début/fin de fenêtre et heures des alertes), pas nécessairement les bornes demandées au job. Aucun statut terminé/en cours n'est inféré. La requête d'agrégation est limitée à 5 secondes.

## Exemples pour Mohammed

Dans React : `VITE_API_URL=http://localhost:8081` si le client ajoute `/api`. Avec une base incluant déjà `/api`, ne pas l'ajouter une seconde fois. Polling live/alertes toutes les 30 s.

```powershell
Invoke-RestMethod 'http://localhost:8081/api/live?symbol=BTCUSDT&limit=60'
Invoke-RestMethod 'http://localhost:8081/api/alerts?type=VOLUME_SPIKE&severity=critical'
Invoke-RestMethod 'http://localhost:8081/api/sentiment?symbol=BTCUSDT&label=positive'
Invoke-RestMethod 'http://localhost:8081/api/analytics?symbol=BTCUSDT&from=2026-10-16T09:00:00Z&to=2026-10-16T10:00:00Z'
Invoke-RestMethod 'http://localhost:8081/api/replay/runs'
Invoke-RestMethod 'http://localhost:8081/api/replay/replay-btc-demo?symbol=BTCUSDT'
Invoke-RestMethod 'http://localhost:8081/api/analytics?symbol=BTCUSDT&from=2026-10-16T09:00:00Z&to=2026-10-16T10:00:00Z&run_id=replay-btc-demo'
Invoke-RestMethod 'http://localhost:8081/api/alerts?run_id=replay-btc-demo'
```

Élément indicateur (même forme dans live, analytics et replay) :

```json
{"symbol":"BTCUSDT","run_id":"live","mode":"live","window_start":"2026-10-16T09:00:00Z","window_end":"2026-10-16T09:01:00Z","trade_count":10,"base_volume":"1.25","quote_volume":"83750.125","min_price":"67000.10","max_price":"67000.10","avg_price":"67000.10","open_price":"67000.10","close_price":"67000.10","change_pct":null,"prev_window_start":null,"updated_at":"2026-10-16T09:02:00Z"}
```

Élément alerte :

```json
{"symbol":"BTCUSDT","run_id":"live","mode":"live","type":"VOLUME_SPIKE","severity":"critical","event_time":"2026-10-16T09:01:00Z","window_start":"2026-10-16T09:00:00Z","observed_value":"4.2","threshold":"2.0","baseline":"50820.0","unit":"ratio","reason":"Synthetic demo: volume is 4.2 times the previous 20-window mean.","ref_event_id":null,"created_at":"2026-10-16T09:02:00Z"}
```

Élément sentiment :

```json
{"event_id":"sentiment:rss:demo","source_event_id":"rss:demo","source_topic":"crypto-news","source":"rss","symbols":["BTC"],"trade_symbols":["BTCUSDT"],"label":"positive","score":"0.64","model":"vader","event_time":"2026-10-16T09:00:00Z","processed_at":"2026-10-16T09:01:00Z","stored_at":"2026-10-16T09:02:00Z"}
```

Pas de jointure titre/URL : afficher `source_event_id`, solution explicitement acceptée par Mohammed. Pas de `summary` analytics : afficher les graphiques et les valeurs Spark. La variation provient de Spark et utilise les **clôtures** ; aucun recalcul dans l'API ou React.

## Erreurs, santé et OpenAPI

`400 INVALID_ARGUMENT` : filtre invalide/manquant ; `503 DATA_UNAVAILABLE` : Mongo indisponible ; `500 INTERNAL_ERROR` : document illisible ; routes inconnues 404, méthode non supportée 405. Exemple :

```json
{"code":"INVALID_ARGUMENT","message":"Unknown symbol: XYZ","timestamp":"2026-10-24T12:00:00Z"}
```

Pas d'URI, de credentials ou de stack trace côté client. `/actuator/health` et `/actuator/health/readiness` contrôlent Mongo ; `/actuator/health/liveness` contrôle le processus. OpenAPI : `/v3/api-docs` ; Swagger : `/swagger-ui.html`.

## Démo et tests

Seed idempotent, uniquement dans `crypto_pulse_demo`, avec live, replay et sentiment conformes aux champs Spark :

```powershell
docker compose up -d mongo
Get-Content -Raw scripts/api-demo.js | docker compose exec -T mongo mongosh --quiet
$env:MONGO_DATABASE = 'crypto_pulse_demo'
docker compose up --build -d api
```

Retour réel : `$env:MONGO_DATABASE = 'crypto_pulse'`, puis `docker compose up -d api`.

```powershell
mvn -f backend/pom.xml verify
# Pour les tests réels Mongo, dans une base jetable cryptopulse_api_test_<UUID> :
$env:API_TEST_MONGO_URI = 'mongodb://localhost:27017/?serverSelectionTimeoutMS=3000'
mvn -f backend/pom.xml verify
Remove-Item Env:API_TEST_MONGO_URI
```

Les anciens champs `session_id`, `price_min/price_avg/price_last` et types minuscules ne sont plus le contrat de cette API. Régénérer les anciennes fixtures. L'exécution Spark reste extérieure à l'API : aucun POST de lancement replay.

Le contrat et les tests locaux ne remplacent pas une validation du flux réel Spark → Mongo → API → React. La revue initiale et son suivi sont conservés dans [dashboard-api-review.md](dashboard-api-review.md).

Validation du 24 octobre 2026 : compilation et packaging réussis, 36 tests réussis (routes, contrats JSON, requêtes, filtres, erreurs, CORS, Swagger et santé). Trois tests d'intégration Mongo sont disponibles mais ignorés faute de MongoDB accessible ; Docker Engine n'est pas démarré. Aucun test de bout en bout avec React n'est annoncé comme exécuté.

Branche locale préparée : `feature/api-dashboard-contract`, basée sur `main` (`2ff9e21`). La configuration Compose combinant Spark et API est valide. La découverte globale des tests Python après récupération de `main` exécute les tests d'ingestion (9 réussis, 5 Mongo ignorés), mais échoue à importer les trois modules de tests Spark parce que `pyspark` n'est pas installé sur l'hôte. Voir [spark-operations.md](spark-operations.md) pour l'environnement Spark prévu. Ce contrôle ne constitue pas une validation de la partie Spark.

