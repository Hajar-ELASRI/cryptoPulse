# Demo procedure (draft, Mohammed)

Goal: show the full flow from raw events to an explained alert on the dashboard, in about 10 minutes, with a fallback if an external source is down. This draft uses only what is already on `main` (Hajar's ingestion, Ali's Spark jobs) plus the dashboard. The API steps are to complete once Mossab's API is merged.

## 0. Before the presentation (the day before)

1. `docker compose up --build -d` (Kafka, MongoDB, Spark, collectors): see `README.md`.
2. Make sure `trades_history` has July 2026 BTCUSDT data (`docs/ingestion-operations.md`, historical import).
3. Prepare the reproducible replay (same result every time, see `docs/spark-operations.md`):
   ```sh
   docker compose --profile spark run --rm --no-deps spark-trades /opt/spark/bin/spark-submit \
     --master 'local[2]' --conf spark.sql.shuffle.partitions=4 \
     /opt/cryptopulse/cryptopulse_spark/jobs/replay.py \
     --run-id replay-btc-demo --symbols BTCUSDT --start 2026-07-01T00:00:00Z --end 2026-07-01T06:00:00Z
   ```
4. Start the live jobs at least 25 minutes before the talk, so the 20-minute warm-up of `VOLUME_SPIKE` is over:
   ```sh
   docker compose --profile spark up -d spark-trades
   docker compose --profile spark up -d spark-indicators
   ```
5. Start the API (Mossab, command to add) and the dashboard with `VITE_USE_MOCKS=false`.
6. Take screenshots of each view as a fallback.

## 1. Script

| Step | Show | Say |
|---|---|---|
| 1 | Architecture (`docs/project-context.md` §4) | Sources → Kafka → Spark (Silver/Gold) → MongoDB → API → dashboard. |
| 2 | A raw `crypto-trades` message and the matching `trades` document | Before/after: types, dedup, `quote_volume`. |
| 3 | **Live** | One row per symbol and minute; change is close vs previous close; ~2 min delay because of the watermark. |
| 4 | **Alerts**, filter on a type | Each alert shows observed value, threshold, baseline and the reason sentence; thresholds are demo settings. |
| 5 | **Sentiment** | Score/label per article, linked pair, “observed correlation, not cause”, VADER limits. |
| 6 | **Analytics**, choose a period | Same indicators over a period, alerts on the chart. |
| 7 | **Replay** → `replay-btc-demo` | Same rules on history, separated by `run_id`; re-running gives identical results. |

## 2. Fallbacks

| Problem | Fallback |
|---|---|
| Binance / RSS unreachable | Use **Replay** (data already in MongoDB) and Analytics on an earlier period. |
| API down | Restart the dashboard with `VITE_USE_MOCKS=true`: the synthetic fixtures (clearly badged **DEMO DATA**) show every view. |
| Everything down | Screenshots from step 0.6. |

## 3. To complete

- API start command and URL (Mossab).
- A synthetic scenario that triggers an alert live (e.g. a script that publishes a burst of trades to `crypto-trades`), to agree with Hajar and Ali, since it touches ingestion.
- Final screenshots after integration.
