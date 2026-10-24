"""Idempotent MongoDB writes for micro-batches.

Batches are collected on the driver (they are bounded by maxOffsetsPerTrigger) and
written with bulk upserts keyed on `_id`, so a replayed batch overwrites itself.
"""

import logging
from decimal import Decimal
from typing import Iterable

from bson.decimal128 import Decimal128
from pymongo import MongoClient, ReplaceOne

LOG = logging.getLogger(__name__)

TRADE_DECIMALS = ("price", "quantity", "quote_volume")


def trade_document(row: dict) -> dict:
    doc = dict(row)
    for name in TRADE_DECIMALS:
        doc[name] = Decimal128(Decimal(doc[name]))
    doc["_id"] = doc["event_id"]
    return doc


def rejected_document(row: dict) -> dict:
    doc = dict(row)
    doc["_id"] = f"{doc['topic']}:{doc['partition']}:{doc['offset']}"
    return doc


def bulk_upsert(collection, documents: Iterable[dict]) -> int:
    operations = [ReplaceOne({"_id": doc["_id"]}, doc, upsert=True) for doc in documents]
    if operations:
        collection.bulk_write(operations, ordered=False)
    return len(operations)


def write_silver_batch(database, valid_df, rejected_df) -> tuple[int, int]:
    valid = bulk_upsert(
        database["trades"], (trade_document(row.asDict()) for row in valid_df.collect()))
    rejected = bulk_upsert(
        database["trades_rejected"], (rejected_document(row.asDict()) for row in rejected_df.collect()))
    return valid, rejected


def connect(uri: str, database: str):
    return MongoClient(uri, serverSelectionTimeoutMS=10_000)[database]


# ---- Gold -----------------------------------------------------------------------------

INDICATOR_DECIMALS = ("base_volume", "quote_volume", "min_price", "max_price", "avg_price",
                      "open_price", "close_price")
INDICATOR_FIELDS = ("symbol", "window_start", "window_end", "trade_count", *INDICATOR_DECIMALS,
                    "change_pct", "prev_window_start")


def _iso(value) -> str:
    return value.strftime("%Y-%m-%dT%H:%M:%SZ")


def indicator_document(row: dict, run_id: str, mode: str, now) -> dict:
    doc = {name: row[name] for name in INDICATOR_FIELDS}
    for name in INDICATOR_DECIMALS:
        doc[name] = Decimal128(Decimal(doc[name]))
    doc.update(run_id=run_id, mode=mode, updated_at=now,
               _id=f"{run_id}:{doc['symbol']}:{_iso(doc['window_start'])}")
    return doc


def alert_document(row: dict, run_id: str, mode: str, now) -> dict:
    doc = {name: row[name] for name in (
        "type", "severity", "symbol", "event_time", "window_start", "observed_value",
        "threshold", "baseline", "unit", "reason", "ref_event_id")}
    key = doc["ref_event_id"] or _iso(doc["window_start"])
    doc.update(run_id=run_id, mode=mode, created_at=now, _id=f"{run_id}:{doc['type']}:{doc['symbol']}:{key}")
    return doc


def context_rows(database, run_id: str, first_starts: dict, lookback: int) -> list[tuple]:
    """Up to `lookback` windows before each symbol's first new window, as context for lag and baseline."""
    rows = []
    for symbol, start in first_starts.items():
        cursor = database["indicators"].find(
            {"run_id": run_id, "symbol": symbol, "window_start": {"$lt": start}},
            {"window_start": 1, "close_price": 1, "quote_volume": 1},
        ).sort("window_start", -1).limit(lookback)
        rows.extend((symbol, d["window_start"], d["close_price"].to_decimal(), d["quote_volume"].to_decimal())
                    for d in cursor)
    return rows


def process_windows(spark, database, windows, run_id: str, mode: str, params, now) -> tuple[int, int]:
    """Add change and baseline to new windows, then upsert indicators and alerts.

    Used by the live stream (finalised windows) and by replay (one chunk at a time), so
    both apply the same rules. Prior windows come from `indicators` for the same run.
    """
    from pyspark.sql import functions as F
    from cryptopulse_spark import gold

    firsts = {r.symbol: r.first for r in windows.groupBy("symbol").agg(F.min("window_start").alias("first")).collect()}
    if not firsts:
        return 0, 0
    history = spark.createDataFrame(
        context_rows(database, run_id, firsts, params.lookback_minutes),
        "symbol string, window_start timestamp, close_price decimal(18,8), quote_volume decimal(38,16)")
    columns = {f.name: f.dataType for f in windows.schema.fields}
    history = history.select(*[F.col(c).cast(columns[c]) for c in history.columns]).withColumn("is_new", F.lit(False))
    combined = history.unionByName(windows.withColumn("is_new", F.lit(True)), allowMissingColumns=True)
    context = gold.add_context(combined, params).filter("is_new")
    indicators = [indicator_document(r.asDict(), run_id, mode, now) for r in context.collect()]
    alerts = [alert_document(r.asDict(), run_id, mode, now)
              for r in gold.window_alerts(context, params).collect()]
    return bulk_upsert(database["indicators"], indicators), bulk_upsert(database["alerts"], alerts)


def write_large_trade_alerts(database, alerts_df, run_id: str, mode: str, now) -> int:
    return bulk_upsert(database["alerts"], (alert_document(r.asDict(), run_id, mode, now) for r in alerts_df.collect()))
