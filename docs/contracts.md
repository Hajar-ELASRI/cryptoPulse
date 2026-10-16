# CryptoPulse data contracts (proposed v1)

Person A publishes UTF-8 JSON to Kafka. Person B should confirm this contract before implementing Spark. All timestamps in Kafka are ISO 8601 UTC strings, such as `2026-10-16T09:00:00Z`. `event_id` is stable across retries and is the deduplication key. Prices and quantities are decimal **strings** to preserve exchange precision; Spark should cast them to `DecimalType`, not floating point.

## Topics

- `crypto-trades`: key and `event_id` = `binance:<SYMBOL>:<trade_id>`; fields `source`, `symbol`, `trade_id`, `price`, `quantity`, `event_time`, `ingested_at`, `is_buyer_maker`.
- `crypto-news`: key and `event_id` = `rss:<SHA256 of article id or URL>`; fields `source`, `title`, `summary`, `url`, `event_time`, `published_at`, `ingested_at`.
- `crypto-social`: key and `event_id` = `reddit:<post_id>`; fields `source`, `subreddit`, `title`, `text`, `url`, `score`, `num_comments`, `event_time`, `ingested_at`.
- `crypto-sentiment`: key and `event_id` = `sentiment:<source_event_id>`; fields `source_event_id`, `source_topic`, `source`, `symbols`, `label` (`positive`, `neutral`, `negative`), `score` (VADER compound score from -1 to 1), `model`, `event_time`, `processed_at`. This is A's proposed handoff to B for MongoDB storage; confirm it together.

Example trade:

```json
{"event_id":"binance:BTCUSDT:123456","source":"binance","symbol":"BTCUSDT","trade_id":123456,"price":"67000.10","quantity":"0.025","event_time":"2026-10-16T09:00:00Z","ingested_at":"2026-10-16T09:00:01Z","is_buyer_maker":false}
```

## MongoDB history

Database `crypto_pulse`, collection `trades_history`. The historical loader inserts `event_id`, `source`, `symbol`, `trade_id`, `price`, `quantity`, `quote_quantity`, `event_time` (BSON UTC datetime), `is_buyer_maker` and `is_best_match`. It upserts on `(symbol, trade_id)` so a restart does not duplicate rows. The initial indexes are `(symbol, trade_id)` unique and `(symbol, event_time)` descending. Other collections initialized for B are `trades`, `news`, `social_posts`, `indicators`, `alerts`, and `sentiment`; B owns their final schemas.

## Processing expectations for B

- Parse trade `event_time` as a timestamp and cast `price` and `quantity` to decimal values.
- Deduplicate live trades by `event_id` with a watermark; the producers can resend after a restart.
- News and social events should also deduplicate by `event_id`.
- Consume `crypto-sentiment` if sentiment is to appear in MongoDB and the dashboard.
- Read `trades_history` for replay. Its `event_time` is already a BSON date.

