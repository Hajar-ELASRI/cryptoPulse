# CryptoPulse data contracts (proposed v1)

Hajar publishes UTF-8 JSON to Kafka. Ali should confirm this contract before implementing Spark. All timestamps in Kafka are ISO 8601 UTC strings, such as `2026-10-16T09:00:00Z`. `event_id` is stable across retries and is the deduplication key. Prices and quantities are decimal **strings** to preserve exchange precision; Spark should cast them to `DecimalType`, not floating point.

## Topics

- `crypto-trades`: key and `event_id` = `binance:<SYMBOL>:<trade_id>`; fields `source`, `symbol`, `trade_id`, `price`, `quantity`, `event_time`, `ingested_at`, `is_buyer_maker`.
- `crypto-news`: key and `event_id` = `rss:<SHA256 of article id or URL>`; fields `source`, `title`, `summary`, `url`, `event_time`, `published_at`, `ingested_at`.
- `crypto-social`: key and `event_id` = `reddit:<post_id>`; fields `source`, `subreddit`, `title`, `text`, `url`, `score`, `num_comments`, `event_time`, `ingested_at`.
- `crypto-sentiment`: key and `event_id` = `sentiment:<source_event_id>`; fields `source_event_id`, `source_topic`, `source`, `symbols`, `label` (`positive`, `neutral`, `negative`), `score` (VADER compound score from -1 to 1), `model`, `event_time`, `processed_at`. This is Hajar's proposed handoff to Ali for MongoDB storage; confirm it together.

Example trade:

```json
{"event_id":"binance:BTCUSDT:123456","source":"binance","symbol":"BTCUSDT","trade_id":123456,"price":"67000.10","quantity":"0.025","event_time":"2026-10-16T09:00:00Z","ingested_at":"2026-10-16T09:00:01Z","is_buyer_maker":false}
```

## MongoDB history

Database `crypto_pulse`, collection `trades_history`. The historical loader inserts `event_id`, `source`, `symbol`, `trade_id`, `price`, `quantity`, `quote_quantity`, `event_time` (BSON UTC datetime), `is_buyer_maker` and `is_best_match`. It inserts in batches and tolerates duplicate trade keys so a restart does not duplicate rows or overwrite existing records. The initial indexes are `(symbol, trade_id)` unique and `(symbol, event_time)` descending. Other collections initialized for Ali are `trades`, `news`, `social_posts`, `indicators`, `alerts`, and `sentiment`; Ali owns their final schemas.

Hajar also owns the operational `history_imports` collection: one document per archive filename (`_id`), with `symbol`, `sha256`, `archive_bytes`, `rows_processed`, `csv_records`, `first_trade_id`, `last_trade_id`, `inserted_total`, `status` (`running`, `sampled`, `complete`) and `updated_at` (BSON UTC date). These are committed import checkpoints, not market indicators. On recovery the importer checks the archive fingerprint and count of stored trades in the checkpoint's ID range before skipping prior CSV records. A crash after insertion but before a checkpoint can replay one batch safely. `running` records the last committed progress and does not prove a container is still running; inspect Docker status as well.

## Processing expectations for Ali

- Parse trade `event_time` as a timestamp and cast `price` and `quantity` to decimal values.
- Deduplicate live trades by `event_id` with a watermark; the producers can resend after a restart.
- News and social events should also deduplicate by `event_id`.
- Consume `crypto-sentiment` if sentiment is to appear in MongoDB and the dashboard.
- Read `trades_history` for replay. Its `event_time` is already a BSON date.

## Spark output contracts (proposed v1, Ali)

Proposed by Ali for review by Hajar, Mossab and Mohammed. Nothing here is implemented until the matching Spark PR merges; once agreed, field or type changes must be announced before consumers change their code. All collections live in database `crypto_pulse`. Timestamps are BSON UTC dates. Money and quantity fields are BSON `Decimal128` (Spring Data maps them to `BigDecimal`); they are never floats.

### Live vs replay

Every `indicators` and `alerts` document carries `run_id` and `mode`. Live streaming writes `mode: "live"`, `run_id: "live"`. A replay of `trades_history` writes `mode: "replay"` and `run_id: "replay-<name>"` (for example `replay-btc-2026-07-01`). Re-running a replay with the same `run_id` overwrites its own documents only, so it is reproducible and never touches live data. The API should filter `mode: "live"` unless a replay `run_id` is requested.

### `trades` (Silver)

One document per valid, deduplicated live trade. `_id` = `event_id`, so writes are idempotent upserts.

| Field | Type | Notes |
|---|---|---|
| `_id`, `event_id` | string | `binance:<SYMBOL>:<trade_id>` |
| `source` | string | `binance` |
| `symbol` | string | upper-case pair, e.g. `BTCUSDT` |
| `trade_id` | long | |
| `price`, `quantity` | Decimal128 | exact values from Kafka |
| `quote_volume` | Decimal128 | `price × quantity`, in the quote currency (USDT for BTCUSDT/ETHUSDT) |
| `event_time` | date | exchange time, UTC |
| `window_start` | date | `event_time` truncated to the minute |
| `ingested_at`, `processed_at` | date | collector time and Spark time, for latency measures |
| `is_buyer_maker` | bool | |

Validation: required fields present; `price > 0` and `quantity > 0` and parseable as decimals; `symbol` in the configured list; `event_time` not more than 1 day in the future. Deduplication is by `event_id` with a watermark of 10 minutes (configurable); a duplicate older than the watermark may be written again but the upsert on `_id` keeps one document.

### `trades_rejected` (quarantine)

Messages that fail validation are kept, not dropped: `_id` (`<topic>:<partition>:<offset>`), `reason` (`invalid_json`, `missing_field:<name>`, `non_positive_price`, `non_positive_quantity`, `unknown_symbol`, `bad_timestamp`), `raw` (original string), `topic`, `partition`, `offset`, `rejected_at`.

### `indicators` (Gold, one row per symbol and minute)

`_id` = `<run_id>:<symbol>:<window_start ISO>`.

| Field | Type | Notes |
|---|---|---|
| `run_id`, `mode` | string | see above |
| `symbol` | string | |
| `window_start`, `window_end` | date | one-minute tumbling window, `[start, end)` |
| `trade_count` | int | |
| `base_volume` | Decimal128 | sum of `quantity` (BTC, ETH) |
| `quote_volume` | Decimal128 | sum of `quote_volume` (USDT) |
| `min_price`, `max_price`, `avg_price` | Decimal128 | `avg_price` is the simple mean of trade prices |
| `open_price`, `close_price` | Decimal128 | first and last trade of the window by `(event_time, trade_id)` |
| `change_pct` | double or null | `100 × (close_price − prev_close_price) / prev_close_price`; null when no previous window exists |
| `prev_window_start` | date or null | window the change is measured against: the latest earlier window of the same symbol and `run_id` (it can be more than one minute earlier if a minute had no trades) |
| `updated_at` | date | |

**Price choice:** the variation uses the **close** price, which is unambiguous and can be checked by hand. `avg_price` is stored as well, for display. This is a proposal for the team to confirm.

Windows are updated while late trades arrive within the watermark, so a recent window can change between two reads (`updated_at` shows when). Index: `(run_id, symbol, window_start desc)`.

### `alerts` (Gold)

`_id` = `<run_id>:<type>:<symbol>:<key>` where `key` is the `window_start` ISO for window alerts and the `event_id` for `LARGE_TRADE`. Re-evaluating the same window overwrites the same alert.

| Field | Type | Notes |
|---|---|---|
| `run_id`, `mode`, `symbol` | string | |
| `type` | string | `VOLUME_SPIKE`, `PRICE_MOVE`, `LARGE_TRADE` |
| `severity` | string | `warning` when the threshold is crossed, `critical` at twice the threshold |
| `event_time` | date | `window_end` for window alerts, trade time for `LARGE_TRADE` |
| `window_start` | date or null | |
| `observed_value` | Decimal128 or double | measured value (see below) |
| `threshold` | Decimal128 or double | value that was exceeded |
| `baseline` | Decimal128 or double or null | e.g. the 20-minute average volume |
| `unit` | string | `ratio`, `percent`, `USDT`… |
| `reason` | string | readable sentence for the dashboard |
| `ref_event_id` | string or null | trade that triggered a `LARGE_TRADE` |
| `created_at` | date | |

Rules and **demo** defaults (configurable, not market constants; to be tuned after observing the data):

- `VOLUME_SPIKE`: `quote_volume` of the minute ÷ mean `quote_volume` of the previous 20 windows ≥ `ALERT_VOLUME_SPIKE_FACTOR` (2.0). Active only after `ALERT_WARMUP_MINUTES` (20) of history in the same run. `observed_value` is the ratio, `threshold` the factor, `baseline` the 20-minute mean.
- `PRICE_MOVE`: `|change_pct|` ≥ `ALERT_PRICE_MOVE_PCT` (0.5). `observed_value` is `change_pct`, in percent.
- `LARGE_TRADE`: one trade's `quote_volume` ≥ `ALERT_LARGE_TRADE_QUOTE` (100000 USDT). Evaluated on every Silver trade.

Index: `(run_id, symbol, event_time desc)` and `(run_id, type, event_time desc)`.

### Not yet specified

`news`, `social_posts` and `sentiment` Silver documents, and the mapping between sentiment assets (`BTC`) and trade pairs (`BTCUSDT`), will be proposed in a follow-up PR once the trade pipeline is in.

### Open questions for the team

1. Close price (proposed) or mean price for `change_pct`?
2. Is the live/replay separation by `run_id` and `mode` acceptable for the API and dashboard?
3. Are the demo thresholds a good start, and who tunes them?
4. Is `Decimal128` acceptable for Mossab, or should the API contract expect strings?
