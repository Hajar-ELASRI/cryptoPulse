# CryptoPulse — Spark pipeline (Ali)

Contracts for the output collections are in [`contracts.md`](contracts.md#spark-output-contracts-proposed-v1-ali).

## Silver trades job

`spark/cryptopulse_spark/jobs/trades_stream.py` reads `crypto-trades` from Kafka and writes MongoDB `trades` (valid, deduplicated, enriched) and `trades_rejected` (quarantine with reason and raw message).

| Step | Where |
|---|---|
| Explicit schema, decimal and UTC conversion, validation reasons | `silver.parse_trades` |
| Deduplication by `event_id` within a watermark (default 10 minutes) | `silver.deduplicate` |
| `quote_volume = price × quantity`, `window_start`, `processed_at` | `silver.silver_trades` |
| Quarantine rows | `silver.rejected_trades` |
| Idempotent bulk upserts on `_id` | `mongo_sink` |

Worked example: price `65000.50` × quantity `0.02` gives `quote_volume = 1300.01` USDT (exact, `Decimal128`).

Prices and quantities are cast to `DECIMAL(18,8)`. A value with more than 8 decimals is rounded and one above 10 digits before the point is rejected as `invalid_price` / `invalid_quantity`.

### Run

```sh
docker compose up -d --build kafka-init mongo-init spark-worker binance-collector
docker compose --profile spark up -d --build spark-trades
docker compose logs -f spark-trades
```

The first start downloads the Kafka connector jar into the `spark-ivy` volume. Spark UI: `http://localhost:8080` (port can be overridden locally, see below). To drain the topic and stop, append `--once` to the command (`docker compose --profile spark run --rm spark-trades <spark-submit command> ... trades_stream.py --once`).

Checkpoints live in the `spark-checkpoints` volume under `silver-trades`. Restarting resumes from the checkpoint; to reprocess from the beginning, stop the job and remove that checkpoint directory.

Inspect results:

```sh
docker compose exec mongo mongosh --quiet crypto_pulse --eval 'db.trades.find().sort({event_time:-1}).limit(3)'
docker compose exec mongo mongosh --quiet crypto_pulse --eval 'db.trades_rejected.find().limit(3)'
```

Run `docker compose up mongo-init` again once after pulling this change so `trades_rejected` exists.

## Gold: indicators, alerts and replay

| Piece | Where |
|---|---|
| One-minute aggregates per symbol (count, base/quote volume, min/max/avg, open/close) | `gold.minute_aggregates` |
| `change_pct`, previous window, 20-window volume baseline and ratio | `gold.add_context` |
| `VOLUME_SPIKE`, `PRICE_MOVE` alerts | `gold.window_alerts` |
| `LARGE_TRADE` alerts (written by the Silver job on every valid trade) | `gold.large_trade_alerts` |
| Live job, Kafka -> `indicators` | `jobs/indicators_stream.py` (service `spark-indicators`) |
| Replay of `trades_history` | `jobs/replay.py` |

Both modes call `mongo_sink.process_windows`, which reads up to 20 earlier windows of the same run from `indicators` and applies the same functions, so live and replay follow identical rules.

Worked example (one minute): trades 100 × 1, 102 × 2, 98 × 1 give `trade_count 3`, `base_volume 4`, `quote_volume 402`, min 98, max 102, `avg_price 100`, open 100, close 98. If the previous close was 100 the next minute closing at 101 has `change_pct = 100 × (101 − 100) / 100 = 1.0`. If the previous 20 minutes averaged 1,000 USDT and this minute traded 3,000 USDT, the ratio is 3.0 and a `VOLUME_SPIKE` is raised (threshold 2.0).

Thresholds are environment variables with demo defaults: `ALERT_VOLUME_SPIKE_FACTOR=2.0`, `ALERT_VOLUME_LOOKBACK_MINUTES=20`, `ALERT_WARMUP_MINUTES=20`, `ALERT_PRICE_MOVE_PCT=0.5`, `ALERT_LARGE_TRADE_QUOTE=100000`, `ALERT_MAX_GAP_MINUTES=5`, `GOLD_WATERMARK=1 minute`. They are starting points to tune after looking at real data.

### Run live

```sh
docker compose --profile spark up -d --build spark-trades
docker compose --profile spark up -d spark-indicators     # start after spark-trades has fetched the Kafka jar
docker compose logs -f spark-indicators
```

Windows appear about two minutes after their minute, and a trade later than the Gold watermark is not counted in its indicator (it is still in `trades`). With the 1 GB worker, run at most these two jobs next to each other.

### Replay a period

```sh
docker compose --profile spark run --rm --no-deps spark-trades /opt/spark/bin/spark-submit \
  --master 'local[2]' --conf spark.sql.shuffle.partitions=4 \
  /opt/cryptopulse/cryptopulse_spark/jobs/replay.py \
  --run-id replay-btc-demo --symbols BTCUSDT --start 2026-07-01T00:00:00Z --end 2026-07-01T06:00:00Z
```

The run id must start with `replay-`. Output goes to `indicators` and `alerts` with `mode: "replay"` and that `run_id`; the job first deletes that run's documents, so repeating the command gives the same result. Live documents are never touched. Trades are loaded in chunks (`--chunk-minutes`, default 30) aligned to minutes, and context for the 20-window baseline is carried between chunks through MongoDB. It needs data in `trades_history` (see the ingestion runbook); a replay of 701 synthetic trades ran in about 12 s.

Inspect:

```sh
docker compose exec mongo mongosh --quiet crypto_pulse --eval 'db.alerts.find({run_id:"replay-btc-demo"}).sort({event_time:1}).limit(5)'
```

Run `docker compose up mongo-init` once after pulling this change to create the new indexes.

## News, social posts and sentiment

`jobs/editorial_stream.py` (service `spark-editorial`) reads `crypto-news`, `crypto-social` and `crypto-sentiment` and upserts `news`, `social_posts` and `sentiment` (`_id` = `event_id`). Messages are validated on `event_id` and `event_time`, deduplicated by `event_id` (watermark 1 day, since RSS republishes), and typed per topic. News and posts need a non-empty title; sentiment needs a label in `positive/neutral/negative`, a score in [-1, 1] and a `source_event_id`. Rejected messages go to `editorial_rejected` with the reason and raw text. Every document has `stored_at` (Spark write time).

`sentiment` also gets `trade_symbols`: each asset in `symbols` plus `USDT` (`BTC` becomes `BTCUSDT`), so the API can join sentiment to `indicators`. This is a convention (all tracked pairs are quoted in USDT) for the team to confirm.

```sh
docker compose --profile spark up -d --build spark-editorial
docker compose exec mongo mongosh --quiet crypto_pulse --eval 'db.sentiment.find({"symbols.0":{$exists:true}}).sort({event_time:-1}).limit(3)'
```

Checked on a live run: 55 RSS articles and 55 sentiment events became 55 `news` and 55 `sentiment` documents with none rejected. No Reddit data was available (no credentials), so `social_posts` is covered by unit tests only.

### Tests

```sh
docker compose --profile test run --rm --build spark-test
```

Runs the Silver and Gold tests in the Spark image with a local Spark session: hand-computed aggregates, change and spike rules, a streaming dedup/window test and, with Mongo up, idempotent upserts. Stop the live jobs first; the test JVM can run out of memory next to them.

### Local port clashes

If `9092` or `8080` is taken on your machine, create an untracked `docker-compose.override.yml`:

```yaml
services:
  kafka:
    ports: !override []
  spark-master:
    ports: !override
      - "18080:8080"
      - "7077:7077"
```

### Limits

- Micro-batches are collected on the driver and bulk-written with pymongo. `SPARK_MAX_OFFSETS_PER_TRIGGER` (default 50000) bounds batch size; this is enough for the live Binance feed of two symbols but is not a distributed sink.
- The worker is limited to 2 cores and 1 GB; the job asks for 1 core and 512 MB.
- The job runs as root in its container so it can write the checkpoint volume.
- Dedup state is bounded by the watermark: a duplicate arriving later than that may be processed again, but the upsert on `_id = event_id` still leaves one document.
