# Demo procedure (draft, Mohammed)

Goal: show the full flow from raw events to an explained alert on the dashboard, in about 10 minutes, with a fallback if an external source is down. It uses what is on `main`: Hajar's ingestion, Ali's Spark jobs, Mossab's API and the dashboard.

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
5. Start the API (`docs/api.md`) and check it, then the dashboard on the real API:
   ```sh
   docker compose up --build -d mongo api
   curl http://localhost:8081/actuator/health
   cd dashboard
   VITE_USE_MOCKS=false npm run dev    # PowerShell: $env:VITE_USE_MOCKS='false'; npm run dev
   ```
   Open http://localhost:5173: the top bar must say "API online" and the demo badge must be gone.
6. Take screenshots of each view as a fallback.

## 1. Script

| Step | Show | Say |
|---|---|---|
| 1 | Landing page (`/`): live price, then "How the data moves" (details in `docs/project-context.md` §4) | Sources → Kafka → Spark (Silver/Gold) → MongoDB → API → dashboard. |
| 2 | A raw `crypto-trades` message and the matching `trades` document | Before/after: types, dedup, `quote_volume`. |
| 3 | **Live** | One row per symbol and minute; change is close vs previous close; ~2 min delay because of the watermark. |
| 4 | Run the burst (below), then **Alerts** two minutes later, filter on a type | Each alert shows observed value, threshold, baseline and the reason sentence; thresholds are demo settings. Say that the burst is synthetic. |
| 5 | **Sentiment** | Score/label per article, linked pair, “observed correlation, not cause”, VADER limits. |
| 6 | **Analytics**, choose a period | Same indicators over a period, alerts on the chart. |
| 7 | **Replay** → `replay-btc-demo` | Same rules on history, separated by `run_id`; re-running gives identical results. |

## 2. Fallbacks

| Problem | Fallback |
|---|---|
| Binance / RSS unreachable | Use **Replay** (data already in MongoDB) and Analytics on an earlier period. |
| API down | Restart the dashboard with `VITE_USE_MOCKS=true`: the synthetic fixtures (clearly badged **Demo data**) show every view. |
| Everything down | Screenshots in `docs/demo-screenshots/` (real data, 24 October 2026: landing, Live, Alerts, Sentiment, Analytics, Replay `replay-btc-demo`). |

## 3. Live alert on stage (synthetic burst)

`scripts/demo_burst.py` publishes a few synthetic trades to `crypto-trades`, priced at the latest close and marked `source: "demo-burst"` (ids `demo-burst:…`), so they can never be mistaken for Binance trades:

```sh
docker compose run --rm --build --no-deps binance-collector python -m scripts.demo_burst --symbol BTCUSDT --volume-factor 3
```

- Default: 3 large trades of 150k, 150k and 250k USDT, giving 2 `LARGE_TRADE` warnings and 1 critical.
- `--volume-factor 3` adds 3x the 20-minute mean volume, giving a `VOLUME_SPIKE` (needs 20 minutes of live data first).
- No `PRICE_MOVE` is faked: the price stays at the last close.
- Alerts show up about 2 minutes later (end of the minute plus the Spark watermark).

Tested on 24 October 2026: 43 trades at 15:53 UTC gave `VOLUME_SPIKE` (2.9x the mean) and 3 `LARGE_TRADE` alerts. To clean up after the demo:

```sh
docker compose exec mongo mongosh --quiet crypto_pulse --eval 'db.trades.deleteMany({source: "demo-burst"})'
```

Alerts already computed from the burst stay in `alerts`; they read as normal alerts, so mention the burst when showing them.
