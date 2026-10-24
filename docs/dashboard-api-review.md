# Vérification des besoins frontend de Mohammed

> **Suivi après alignement :** le contrat d'Ali a été récupéré sur `origin/main` (`2ff9e21`). Les écarts décrits ci-dessous concernent la première version et sont conservés comme historique de revue. L'API utilise maintenant les noms Spark, `run_id/mode`, `trade_symbols`, les types d'alertes majuscules, les filtres severity/label, les tableaux JSON et le tri analytics chronologique. `/api/replay/runs` et `/api/replay/{runId}` sont implémentés. Les exemples actuels sont dans [api.md](api.md). Le résumé analytics et les titres/URLs restent optionnels et absents, comme autorisé par Mohammed. Compilation et 36 tests réussis ; 3 tests réels Mongo ignorés, Docker Engine étant indisponible. La validation sur le frontend et les données réelles reste à réaliser.

Revue du 24 octobre 2026, avant push. Source : [dashboard-api-needs.md](dashboard-api-needs.md), copie du document reçu dans Downloads. Ce document exprime des besoins et des options ; il ne constitue pas un contrat validé par Ali ou une instruction de modifier toutes les routes.

**Verdict : les besoins sont compréhensibles, mais le dashboard décrit ne peut pas encore consommer directement l'API actuelle.** La réussite des tests de l'API valide son contrat actuel, pas sa compatibilité avec les mocks de Mohammed.

La section « Spark output contracts » citée par Mohammed n'existe pas dans le `docs/contracts.md` de cette copie. `spark/cryptopulse_spark/jobs/replay.py`, `docs/spark-operations.md` et `dashboard/src/api.js` sont également absents. Le contrat Gold local est explicitement une proposition de Mossab. Il faut récupérer le contrat Spark auquel Mohammed se réfère avant de décider des noms et des règles définitifs.

## Écarts bloquants

### 1. Séparation live/replay : risque de mélange avec les documents décrits

Le frontend attend `mode: "live" | "replay"` et `run_id`. L'API filtre exclusivement `session_id` : absent ou null = live. Un document Spark marqué `mode: "replay"` et `run_id: "replay-btc-demo"`, sans `session_id`, satisfait donc le filtre live actuel. À l'inverse, chercher ce replay avec `session_id=replay-btc-demo` ne le retrouverait pas.

Les paramètres inconnus étant ignorés par les contrôleurs, `/api/alerts?run_id=replay-btc-demo` et `/api/analytics?run_id=replay-btc-demo` lisent actuellement le live. `/api/replay?run_id=replay-btc-demo` retourne 400 car `session_id` est obligatoire.

Preuves : `backend/src/main/java/com/cryptopulse/api/MarketRepository.java`, méthode `query` ; `MarketController.java`, méthodes `indicators`, `alerts`, `replay`.

**À résoudre avant intégration :** confirmer le contrat Spark et utiliser le même couple `mode`/`run_id` dans les requêtes, les DTO, les fixtures et les index si ce contrat est celui retenu. Un renommage du paramètre HTTP seul ne suffirait pas.

### 2. Indicateurs : champs absents et sens de la variation à confirmer

| Attendu par Mohammed | API actuelle | Conséquence |
|---|---|---|
| `min_price` | `price_min` | Nom différent |
| `max_price` | `price_max` | Nom différent |
| `avg_price` | `price_avg` | Nom différent |
| `close_price` | `price_last` | Équivalence à confirmer avec Ali |
| `change_pct` | `price_change_pct` | Nom et formule à confirmer |
| `open_price` | absent | Impossible à reconstituer depuis les DTO actuels |
| `prev_window_start`, `updated_at` | absents | Contexte de fenêtre/fraîcheur indisponible |
| `mode`, `run_id` | `session_id` uniquement | Contrat de partition différent |

Le mapper lit aussi les **anciens noms dans Mongo**. Si Spark écrit seulement `min_price`, `avg_price`, etc., l'API renverra actuellement des valeurs null pour ces prix. Renommer uniquement le JSON de sortie ne corrige pas la lecture.

La proposition locale calcule la variation entre prix **moyens** de fenêtres. Le document de Mohammed affiche une clôture avec `change_pct`, mais ne précise pas sa formule. Ne pas annoncer une variation entre clôtures sans confirmation d'Ali. Ne pas inventer un `open_price` ni recalculer les indicateurs dans React.

Preuves : `MarketService.java`, méthode `indicators` ; `ApiModels.java`, record `Indicator` ; `docs/contracts.md`, proposition Gold.

### 3. Sentiment : le filtre ne vise pas le même champ Mongo

Mohammed attend `symbols: ["BTC"]` et `trade_symbols: ["BTCUSDT"]`, avec recherche du symbole de marché dans `trade_symbols`. L'API cherche actuellement `BTCUSDT` dans `symbols`. Sur le document donné en exemple par Mohammed, cette recherche retourne une liste vide.

Le DTO ne fournit pas `trade_symbols` ni `source_topic`. Le filtre `label` n'existe pas : le paramètre serait ignoré. `title` et `url` sont absents, mais Mohammed les déclare optionnels ; l'affichage de `source_event_id` est une solution acceptable sans jointure.

Preuves : `MarketRepository.java`, méthode `query` ; `MarketController.java`, méthode `sentiment` ; `ApiModels.java`, record `Sentiment`.

### 4. Alertes : types incompatibles et informations manquantes

`type=VOLUME_SPIKE`, `PRICE_MOVE` ou `LARGE_TRADE` retourne 400 : l'API accepte `volume_spike`, `price_movement`, `large_trade`. Attention, `PRICE_MOVE` n'est pas seulement une différence de casse avec `price_movement`.

Le filtre `severity` n'est pas implémenté et serait ignoré. Le DTO expose déjà `severity`, `observed_value`, `threshold`, `reason` et `event_time`, mais pas `baseline`, `unit`, `window_start`, `ref_event_id`, `created_at`. Ces informations sont demandées pour expliquer les alertes : les lire depuis les sorties Spark lorsqu'elles seront confirmées, sans les fabriquer côté API.

Preuves : `MarketFilter.java`, méthode `parse` ; `MarketController.java`, méthode `alerts` ; `ApiModels.java`, record `Alert`.

### 5. Navigation dans les replays : liste des runs absente

`GET /api/replay/runs` n'existe pas (404), alors que Mohammed le désigne comme son seul besoin spécifiquement indispensable au replay. `GET /api/replay/{runId}` n'existe pas non plus. Cette seconde route est optionnelle si analytics/alerts prennent correctement en charge `run_id`.

La liste doit distinguer les vrais replays du live et définir la portée de `start`, `end`, `symbols`, `indicator_count`, `alert_count` (notamment les runs avec des alertes mais aucun indicateur). Elle décrit les résultats présents ; elle ne prouve pas qu'un job est terminé. Une agrégation de métadonnées ou un registre de runs Spark peut fournir ces informations sans recalculer le marché.

## Écarts d'interface à convenir

| Sujet | Demande frontend | API actuelle | Proposition |
|---|---|---|---|
| Listes | Tableau ou Spring Page avec `content` | `{data,page,limit,has_next}` | Garder une pagination bornée ; Mohammed peut lire `body.data` dans son adaptateur, à confirmer explicitement |
| Collection vide | `200 []` | `200 {data:[],...}` | Même état métier vide, mais adapter le décodage ; ce n'est pas le format accepté explicitement dans le document |
| Live par défaut | BTCUSDT obligatoire ou par défaut, limite 60 | Symbole optionnel, tous symboles, limite 100 | Aligner les valeurs ou envoyer explicitement `symbol=BTCUSDT&limit=60` |
| Sentiment par défaut | Limite 50 | Limite 100 | Envoyer `limit=50` ou modifier le défaut convenu |
| Analytics | `symbol`, `from`, `to` obligatoires ; ancien → récent | Paramètres optionnels ; récent → ancien | Séparer le comportement analytics du live ; trier avant de paginer pour parcourir toute la période chronologiquement |
| Analytics JSON | Indicateurs, éventuellement dans `{indicators,summary}` | Page `data` | Documenter le format retenu ; `summary` est facultatif et aucun calcul supplémentaire n'est requis |
| Replay chronologique | Ancien → récent | Récent → ancien | Définir le tri et la pagination ensemble |

Inverser une seule page reçue côté frontend ne permet pas de parcourir correctement une période entière dans l'ordre croissant. Si le frontend conserve la pagination actuelle, il doit suivre `has_next` pour éviter de tronquer silencieusement les graphiques.

## Points déjà compatibles

- URL prévue : `http://localhost:8081`, donc `VITE_API_URL=http://localhost:8081` si l'adaptateur ajoute `/api` (ou `http://localhost:8081/api` s'il ne l'ajoute pas). Le fichier frontend étant absent, son mode de concaténation reste à vérifier.
- CORS autorise `http://localhost:5173`.
- Dates ISO-8601 UTC et décimaux sous forme de chaînes, acceptées par Mohammed.
- Erreurs avec statut HTTP non-2xx, `message` lisible et sans stack trace. Le format d'exemple `{status,error,message}` n'est pas imposé par son document.
- Collection vide : 200 ; le format de l'enveloppe reste à accorder.
- `/actuator/health` est disponible ; aucun `/api/health` supplémentaire n'est nécessaire.
- Polling HTTP toutes les 30 secondes : compatible, sans SSE.
- Replay en lecture seule : accord sur le fait que Spark lance les traitements.
- Pas de résumé analytique ni de jointure titre/URL imposés : ces options peuvent attendre.

## Suite recommandée avant de présenter la livraison comme intégrée

1. Obtenir la branche ou le commit d'Ali contenant les « Spark output contracts » cités ; comparer aussi ses règles de variation, types d'alertes et clés d'idempotence.
2. Aligner Mongo → requêtes → DTO → fixtures sur ce contrat, en particulier live/replay et `trade_symbols`.
3. Ajouter les filtres convenus et la liste des runs ; choisir le tri analytics et un seul format de listes avec Mohammed.
4. Tester les exemples de Mohammed contre l'API, dont un document replay dépourvu de `session_id`, une recherche sentiment par `trade_symbols`, les trois types d'alertes et une période dépassant une page.
5. Exécuter l'intégration sur MongoDB puis faire valider l'adaptateur réel du frontend. Un push de branche de travail peut servir à la revue ; la compatibilité frontend/Spark ne doit pas encore être annoncée comme validée.

Message proposé à Mohammed (à transmettre par Mossab) :

> J'ai vérifié ton document. Port confirmé : 8081 ; CORS pour 5173 ; dates UTC ; décimaux en chaînes ; health via `/actuator/health`. Ton document cite un contrat Spark d'Ali qui n'est pas dans ma copie du dépôt. Peux-tu m'indiquer sa branche ou son commit ? Nous devons surtout aligner `mode/run_id`, les champs de prix, les types d'alertes et `trade_symbols`. Mon API renvoie actuellement `{data,page,limit,has_next}` : est-ce que tu peux accepter cette enveloppe dans ton adaptateur ? La liste des runs reste à ajouter. Le résumé analytics et les titres/URLs de sentiment peuvent rester optionnels.

## Vérification technique

La comparaison ci-dessus porte sur le code local et le document reçu, sans accès aux mocks React ni aux jobs Spark cités. Aucune modification du contrat ou des routes n'est effectuée dans cette revue. Le rapport et une copie du document source sont ajoutés au dépôt pour rendre les décisions à prendre consultables par l'équipe.

Vérifications relancées : `mvn -o -B -f backend/pom.xml "-Dmaven.repo.local=C:/Users/Mossaab/Desktop/projects/cryptoPulse/tmp/m2" verify` réussit, avec 27 tests exécutés avec succès et 2 tests MongoDB ignorés. `git diff --check` est propre. Docker Engine est toujours indisponible ; aucune compatibilité avec une vraie base Gold ni avec le dashboard n'est revendiquée.
