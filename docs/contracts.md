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
