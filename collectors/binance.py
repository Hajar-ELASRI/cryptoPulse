"""Binance Spot trade WebSocket to crypto-trades."""

import json
import logging
import os
import time

from collectors.common import iso_from_epoch, producer, publish, utc_now


LOG = logging.getLogger(__name__)


def normalize_trade(payload: dict) -> dict:
    if payload.get("e") != "trade":
        raise ValueError("Expected Binance trade event")
    symbol = str(payload["s"]).upper()
    trade_id = int(payload["t"])
    price = str(payload["p"])
    quantity = str(payload["q"])
    if float(price) <= 0 or float(quantity) <= 0:
        raise ValueError("Price and quantity must be positive")
    return {
        "event_id": f"binance:{symbol}:{trade_id}",
        "source": "binance",
        "symbol": symbol,
        "trade_id": trade_id,
        "price": price,
        "quantity": quantity,
        "event_time": iso_from_epoch(payload["T"]),
        "ingested_at": utc_now(),
        "is_buyer_maker": bool(payload["m"]),
    }


def run() -> None:
    from websocket import WebSocketApp

    client = producer()
    symbols = [item.strip().lower() for item in os.getenv("BINANCE_SYMBOLS", "btcusdt,ethusdt").split(",") if item.strip()]
    if not symbols:
        raise ValueError("BINANCE_SYMBOLS cannot be empty")
    streams = "/".join(f"{symbol}@trade" for symbol in symbols)
    url = f"wss://stream.binance.com:9443/stream?streams={streams}"
    delay = 1

    def on_message(_app, raw):
        try:
            wrapper = json.loads(raw)
            event = normalize_trade(wrapper.get("data", wrapper))
            publish(client, "crypto-trades", event)
        except (KeyError, TypeError, ValueError, json.JSONDecodeError) as error:
            LOG.warning("Skipped invalid Binance event: %s", error)

    def on_error(_app, error):
        LOG.error("Binance WebSocket error: %s", error)

    while True:
        LOG.info("Connecting to Binance for %s", ", ".join(symbols))
        app = WebSocketApp(url, on_message=on_message, on_error=on_error)
        try:
            app.run_forever(ping_interval=180, ping_timeout=30)
        except Exception:
            LOG.exception("Binance WebSocket disconnected")
        client.flush(20)
        LOG.warning("Reconnecting in %s seconds", delay)
        time.sleep(delay)
        delay = min(delay * 2, 60)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    run()

