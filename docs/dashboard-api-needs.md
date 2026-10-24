# Dashboard data needs (Mohammed → Mossab)

What the React dashboard needs from the API, screen by screen. This is a **request**, not a decision: Mossab owns the API, routes and final JSON. It follows Mossab's brief (`docs/team/mossab.md`) and Ali's MongoDB contract (`docs/contracts.md`, "Spark output contracts"). Field names below are Ali's names on purpose, so the API can pass them through without renaming.

Until the API is ready, the dashboard runs on mock files with exactly these shapes (`dashboard/src/mocks/`). When a real route differs, tell me and I change the dashboard; only `dashboard/src/api.js` should need to change.

## General expectations

- Base URL configurable on my side (`VITE_API_URL`). Please confirm the port: Spark UI already uses `8080` in `docker-compose.yml`.
- CORS allowed for the dashboard in development: `http://localhost:5173`.
- Timestamps: ISO 8601 UTC strings, e.g. `2026-10-24T10:15:00Z`.
- Decimals (`Decimal128` in Mongo): either JSON numbers or strings is fine; the dashboard accepts both. Please say which one you choose (Ali's open question 4).
- Lists: a plain JSON array is enough. If you paginate, Spring's `Page` (`content`, `totalElements`, …) also works.
- Live by default: routes return `mode: "live"` data unless a replay `run_id` is asked (Ali's live/replay rule).
- Errors: a non-2xx status with a JSON body that has a readable `message`, e.g. `{"status":400,"error":"Bad Request","message":"Unknown symbol: XYZ"}`. No stack traces.
- Empty collection → `200` with `[]`, not an error: the dashboard shows an "empty" state.
- Health: `GET /api/health` (or Spring Actuator `/actuator/health`) so the dashboard can show "API online/offline".

Symbols in use: `BTCUSDT`, `ETHUSDT`.

## 1. Live — `GET /api/live`

Params: `symbol` (required or default `BTCUSDT`), `limit` (number of most recent minute windows, default 60).

Returns the latest `indicators` documents of that symbol (`mode: "live"`), newest first:

```json
[
  {
    "symbol": "BTCUSDT", "run_id": "live", "mode": "live",
    "window_start": "2026-10-24T10:15:00Z", "window_end": "2026-10-24T10:16:00Z",
    "trade_count": 412, "base_volume": 3.18, "quote_volume": 213450.75,
    "min_price": 67080.1, "max_price": 67190.0, "avg_price": 67121.4,
    "open_price": 67090.0, "close_price": 67170.5,
    "change_pct": 0.12, "prev_window_start": "2026-10-24T10:14:00Z",
    "updated_at": "2026-10-24T10:17:02Z"
  }
]
```

Displayed: close price, `change_pct`, quote/base volume, trade count, min/max, and a chart over the last hour. The dashboard does **not** compute these; it only displays them.

## 2. Alerts — `GET /api/alerts`

Params: `symbol` (optional), `type` (`VOLUME_SPIKE` | `PRICE_MOVE` | `LARGE_TRADE`, optional), `severity` (optional), `from`, `to` (ISO UTC, optional), `limit` (default 100), `run_id` (optional, default live).

Returns `alerts` documents, newest `event_time` first:

```json
[
  {
    "symbol": "BTCUSDT", "run_id": "live", "mode": "live",
    "type": "VOLUME_SPIKE", "severity": "critical",
    "event_time": "2026-10-24T10:16:00Z", "window_start": "2026-10-24T10:15:00Z",
    "observed_value": 4.2, "threshold": 2.0, "baseline": 50820.0, "unit": "ratio",
    "reason": "Volume of 213451 USDT in this minute is 4.2x the mean of the previous 20 minutes (50820 USDT); threshold 2.0x",
    "ref_event_id": null, "created_at": "2026-10-24T10:17:02Z"
  }
]
```

Every field above is shown: an alert must explain itself (value vs threshold, baseline, reason).

## 3. Sentiment — `GET /api/sentiment`

Params: `symbol` (trade pair, e.g. `BTCUSDT`, matched against `trade_symbols`; optional), `from`, `to`, `label` (optional), `limit` (default 50).

Returns `sentiment` documents, newest first. It would help a lot if each item also carried the **title and URL of its source** article/post (from `news` or `social_posts` via `source_event_id`), so the user sees what was scored:

```json
[
  {
    "event_id": "sentiment:rss:ab12…", "source_event_id": "rss:ab12…",
    "source_topic": "crypto-news", "source": "rss",
    "symbols": ["BTC"], "trade_symbols": ["BTCUSDT"],
    "label": "positive", "score": 0.64, "model": "vader",
    "event_time": "2026-10-24T09:58:00Z",
    "title": "Bitcoin ETF inflows rise for a third day",
    "url": "https://example.com/article"
  }
]
```

If you prefer not to join, `title`/`url` can be absent and the dashboard shows the `source_event_id` instead. Alternatively a separate `GET /api/news` (same params) would also work — your choice.

## 4. Analytics — `GET /api/analytics`

Params: `symbol` (required), `from`, `to` (ISO UTC, required; e.g. up to 24 h), `run_id` (optional, default live).

Needed: the `indicators` of the period (same shape as `/api/live`, oldest first for charts). Optionally a `summary` computed **server-side** for the period, if you and Ali agree it belongs in the API:

```json
{
  "symbol": "BTCUSDT", "from": "2026-10-24T00:00:00Z", "to": "2026-10-24T12:00:00Z",
  "indicators": [ { "…": "same as /api/live" } ],
  "summary": {
    "trade_count": 182340, "quote_volume": 98234120.5,
    "open_price": 66810.0, "close_price": 67170.5, "min_price": 66500.2, "max_price": 67320.0,
    "change_pct": 0.54,
    "alert_counts": { "VOLUME_SPIKE": 3, "PRICE_MOVE": 1, "LARGE_TRADE": 7 },
    "sentiment": { "count": 42, "avg_score": 0.11, "positive": 15, "neutral": 20, "negative": 7 }
  }
}
```

If there is no `summary`, the dashboard shows the charts only (it will not calculate a summary itself).

## 5. Replay

Replays are launched by Ali's Spark job (`spark/cryptopulse_spark/jobs/replay.py`, see `docs/spark-operations.md`); the dashboard only **reads** their results.

- `GET /api/replay/runs` → list of available replay runs (distinct `run_id` with `mode: "replay"`):
  ```json
  [ { "run_id": "replay-btc-demo", "symbols": ["BTCUSDT"],
      "start": "2026-07-01T00:00:00Z", "end": "2026-07-01T06:00:00Z",
      "indicator_count": 360, "alert_count": 12 } ]
  ```
- `GET /api/replay/{runId}?symbol=BTCUSDT` → `{ "run_id": …, "indicators": [ … ], "alerts": [ … ] }` (same shapes as above, oldest first).

If you prefer, `/api/analytics?run_id=…` + `/api/alerts?run_id=…` can replace the second route; the runs list is the only replay-specific need.

## Refresh

The dashboard polls Live and Alerts every 30 s (no SSE needed). If you add SSE later, I can switch.
