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

### Tests

```sh
docker compose --profile test run --rm --build spark-test
```

Runs the Silver tests in the Spark image with a local Spark session (includes a streaming deduplication test and, with Mongo up, an idempotent upsert test).

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
