"""Demo only: publish a short burst of synthetic trades to trigger live alerts on stage.

The trades go to `crypto-trades` like Binance trades, but are marked `source: "demo-burst"`
and use `demo-burst:` event ids, so they can always be told apart (and removed) in `trades`.
They are priced at the latest close, so they never fake a PRICE_MOVE.

    docker compose run --rm --build --no-deps binance-collector python -m scripts.demo_burst --symbol BTCUSDT
    docker compose run --rm --build --no-deps binance-collector python -m scripts.demo_burst --symbol BTCUSDT --volume-factor 3

Alerts appear on the dashboard about 2 minutes later (end of the minute + Spark watermark).
"""
import argparse
import json
import logging
import os
import time
import urllib.request
from decimal import Decimal

from collectors.common import producer, publish, utc_now

LOG = logging.getLogger("demo_burst")
API_URL = os.getenv("DEMO_API_URL", "http://api:8081")
LARGE_TRADE_QUOTE = Decimal(os.getenv("ALERT_LARGE_TRADE_QUOTE", "100000"))
# Ids far above Binance trade ids, so a synthetic trade never replaces a real one.
ID_BASE = 9_000_000_000_000_000


def latest_windows(symbol: str, limit: int) -> list[dict]:
    with urllib.request.urlopen(f"{API_URL}/api/live?symbol={symbol}&limit={limit}", timeout=10) as response:
        return json.load(response)


def trade(symbol: str, seq: int, price: Decimal, quote: Decimal) -> dict:
    trade_id = ID_BASE + time.time_ns() // 1_000 % 10**12 + seq
    quantity = (quote / price).quantize(Decimal("0.00001"))
    return {
        "event_id": f"demo-burst:{symbol}:{trade_id}",
        "source": "demo-burst",
        "symbol": symbol,
        "trade_id": trade_id,
        "price": str(price),
        "quantity": str(quantity),
        "event_time": utc_now(),
        "ingested_at": utc_now(),
        "is_buyer_maker": False,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Publish synthetic trades that trigger demo alerts.")
    parser.add_argument("--symbol", default="BTCUSDT", choices=["BTCUSDT", "ETHUSDT"])
    parser.add_argument("--large", type=int, default=3, help="large trades to send (last one is critical), 0 to skip")
    parser.add_argument("--volume-factor", type=float, default=0, help="extra volume as a multiple of the 20-minute mean, 0 to skip")
    args = parser.parse_args()

    windows = latest_windows(args.symbol, 20)
    if not windows:
        raise SystemExit(f"No live window for {args.symbol} yet: start the pipeline and wait a few minutes.")
    price = Decimal(windows[0]["close_price"])
    mean_quote = sum(Decimal(w["quote_volume"]) for w in windows) / len(windows)
    LOG.info("%s latest close %s, mean quote volume %.0f over %d windows", args.symbol, price, mean_quote, len(windows))

    events = []
    for i in range(args.large):
        factor = Decimal("2.5") if i == args.large - 1 else Decimal("1.5")  # 2x the threshold or more is critical
        events.append(trade(args.symbol, i, price, LARGE_TRADE_QUOTE * factor))
    if args.volume_factor > 0:
        extra = mean_quote * Decimal(str(args.volume_factor))
        pieces = 40
        # Stay below the large-trade threshold so each kind of alert can be shown on its own.
        piece = min(extra / pieces, LARGE_TRADE_QUOTE * Decimal("0.9"))
        events += [trade(args.symbol, 100 + i, price, piece) for i in range(pieces)]

    client = producer()
    for event in events:
        publish(client, "crypto-trades", event)
    client.flush(20)
    total = sum(Decimal(e["price"]) * Decimal(e["quantity"]) for e in events)
    LOG.info("Published %d synthetic trades (%.0f %s) marked source=demo-burst", len(events), total, args.symbol[-4:])


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    main()
