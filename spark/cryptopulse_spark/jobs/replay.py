"""Replay a period of MongoDB `trades_history` through the Gold logic.

Output goes to `indicators` and `alerts` under its own `run_id` (`replay-<name>`) with
`mode: "replay"`, never mixed with live data. Re-running with the same run id first
removes that run's documents, so the result is reproducible.

Example:
  replay.py --run-id replay-btc-demo --symbols BTCUSDT \
      --start 2026-07-01T00:00:00Z --end 2026-07-01T06:00:00Z
"""

import argparse
import logging
import time
from datetime import datetime, timedelta, timezone

from pyspark.sql import SparkSession, functions as F

from cryptopulse_spark import gold, mongo_sink, silver
from cryptopulse_spark.config import Settings

LOG = logging.getLogger("replay")
HISTORY_SCHEMA = "event_id string, symbol string, trade_id long, price string, quantity string, event_time timestamp"


def parse_time(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(timezone.utc).replace(tzinfo=None)


def history_row(d):
    """One `trades_history` document as a HISTORY_SCHEMA tuple.

    Mongo returns large trade ids as bson Int64, which PySpark's schema check rejects
    for `long`: convert to a plain int.
    """
    return (d["event_id"], d["symbol"], int(d["trade_id"]), str(d["price"]), str(d["quantity"]), d["event_time"])


def history_trades(df):
    """`trades_history` rows in the same shape the Silver job produces."""
    typed = (df.withColumn("price", F.col("price").cast(silver.DECIMAL))
             .withColumn("quantity", F.col("quantity").cast(silver.DECIMAL)))
    return (typed.filter((F.col("price") > 0) & (F.col("quantity") > 0))
            .withColumn("quote_volume", F.col("price") * F.col("quantity")))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--run-id", required=True, help="must start with 'replay-'")
    parser.add_argument("--symbols", required=True, help="comma separated, e.g. BTCUSDT,ETHUSDT")
    parser.add_argument("--start", required=True, help="inclusive UTC time, e.g. 2026-07-01T00:00:00Z")
    parser.add_argument("--end", required=True, help="exclusive UTC time")
    parser.add_argument("--chunk-minutes", type=int, default=30, help="minutes of trades loaded at once")
    args = parser.parse_args()
    if not args.run_id.startswith("replay-"):
        parser.error("--run-id must start with 'replay-' so live data is never overwritten")
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")

    settings = Settings.from_env()
    params = gold.AlertParams.from_env()
    spark = (SparkSession.builder.appName(f"cryptopulse-{args.run_id}")
             .config("spark.sql.session.timeZone", "UTC").getOrCreate())
    database = mongo_sink.connect(settings.mongo_uri, settings.mongo_database)
    symbols = [s.strip().upper() for s in args.symbols.split(",") if s.strip()]
    start, end = parse_time(args.start).replace(second=0, microsecond=0), parse_time(args.end)

    for name in ("indicators", "alerts"):
        removed = database[name].delete_many({"run_id": args.run_id}).deleted_count
        LOG.info("cleared %s documents of %s from %s", removed, args.run_id, name)

    cursor, totals = start, [0, 0, 0, 0]
    began = time.monotonic()
    while cursor < end:
        upper = min(cursor + timedelta(minutes=args.chunk_minutes), end)
        rows = [history_row(d)
                for d in database["trades_history"].find(
                    {"symbol": {"$in": symbols}, "event_time": {"$gte": cursor, "$lt": upper}},
                    {"event_id": 1, "symbol": 1, "trade_id": 1, "price": 1, "quantity": 1, "event_time": 1})]
        if rows:
            trades = history_trades(spark.createDataFrame(rows, HISTORY_SCHEMA)).cache()
            now = datetime.utcnow()
            indicators, alerts = mongo_sink.process_windows(
                spark, database, gold.minute_aggregates(trades), args.run_id, "replay", params, now)
            large = mongo_sink.write_large_trade_alerts(
                database, gold.large_trade_alerts(trades, params), args.run_id, "replay", now)
            totals = [totals[0] + len(rows), totals[1] + indicators, totals[2] + alerts, totals[3] + large]
            trades.unpersist()
        LOG.info("%s -> %s: %s trades", cursor.isoformat(), upper.isoformat(), len(rows))
        cursor = upper
    LOG.info("replay %s done in %.1fs: %s trades, %s indicators, %s window alerts, %s large-trade alerts",
             args.run_id, time.monotonic() - began, *totals)


if __name__ == "__main__":
    main()
