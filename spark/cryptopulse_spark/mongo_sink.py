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
