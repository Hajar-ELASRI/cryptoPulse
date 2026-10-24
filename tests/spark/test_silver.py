"""Silver layer checks. Run inside the Spark image: see docs/spark-operations.md."""

import json
import os
import shutil
import tempfile
import unittest
from datetime import datetime, timezone
from decimal import Decimal

from pyspark.sql import SparkSession, functions as F

from cryptopulse_spark import mongo_sink, silver

SYMBOLS = ["BTCUSDT", "ETHUSDT"]


def trade(**overrides):
    event = {"event_id": "binance:BTCUSDT:1", "source": "binance", "symbol": "BTCUSDT", "trade_id": 1,
             "price": "65000.50", "quantity": "0.02", "event_time": "2026-10-16T09:00:30.250000Z",
             "ingested_at": "2026-10-16T09:00:31Z", "is_buyer_maker": False}
    event.update(overrides)
    return {k: v for k, v in event.items() if v is not None}


class SilverTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.spark = (SparkSession.builder.master("local[2]").appName("silver-tests")
                     .config("spark.sql.session.timeZone", "UTC")
                     .config("spark.sql.shuffle.partitions", "2")
                     .config("spark.ui.enabled", "false").getOrCreate())

    @classmethod
    def tearDownClass(cls):
        cls.spark.stop()

    def raw(self, *messages):
        rows = [(m if isinstance(m, str) else json.dumps(m), "crypto-trades", 0, i,
                 datetime(2026, 10, 16, 9, 1, tzinfo=timezone.utc))
                for i, m in enumerate(messages)]
        return self.spark.createDataFrame(rows, "value string, topic string, partition int, offset long, timestamp timestamp")

    def reasons(self, *messages):
        parsed = silver.parse_trades(self.raw(*messages), SYMBOLS)
        return [row.reason for row in parsed.orderBy("offset").collect()]

    def test_valid_trade_is_enriched_with_exact_quote_volume(self):
        parsed = silver.parse_trades(self.raw(trade()), SYMBOLS)
        row = silver.silver_trades(parsed).collect()[0]
        self.assertEqual(row.quote_volume, Decimal("1300.0100000000000000"))
        self.assertEqual(row.price, Decimal("65000.50000000"))
        self.assertEqual(row.event_time, datetime(2026, 10, 16, 9, 0, 30, 250000))
        self.assertEqual(row.window_start, datetime(2026, 10, 16, 9, 0, 0))
        self.assertEqual(row.symbol, "BTCUSDT")
        self.assertFalse(row.is_buyer_maker)

    def test_symbol_is_normalised(self):
        parsed = silver.parse_trades(self.raw(trade(symbol=" btcusdt ")), SYMBOLS)
        self.assertEqual(silver.silver_trades(parsed).collect()[0].symbol, "BTCUSDT")

    def test_rejection_reasons(self):
        reasons = self.reasons(
            "not json at all",
            trade(price=None),
            trade(price="abc"),
            trade(price="NaN"),
            trade(price="0"),
            trade(price="-5"),
            trade(quantity="0"),
            trade(quantity="x"),
            trade(symbol="DOGEUSDT"),
            trade(event_time="yesterday"),
            trade(event_time="2999-01-01T00:00:00Z"),
            trade(event_id=""),
            trade(trade_id=None),
        )
        self.assertEqual(reasons, [
            "invalid_json", "missing_field:price", "invalid_price", "invalid_price",
            "non_positive_price", "non_positive_price", "non_positive_quantity",
            "invalid_quantity", "unknown_symbol", "bad_timestamp", "bad_timestamp",
            "missing_field:event_id", "missing_field:trade_id"])

    def test_rejected_rows_keep_raw_message_and_kafka_position(self):
        parsed = silver.parse_trades(self.raw("garbage"), SYMBOLS)
        row = silver.rejected_trades(parsed).collect()[0]
        self.assertEqual((row.raw, row.topic, row.partition, row.offset), ("garbage", "crypto-trades", 0, 0))

    def test_streaming_deduplicates_by_event_id_and_keeps_every_invalid_row(self):
        directory = tempfile.mkdtemp()
        try:
            source, checkpoint = os.path.join(directory, "in"), os.path.join(directory, "ck")
            os.makedirs(source)
            with open(os.path.join(source, "a.json"), "w") as handle:
                for message in [trade(), trade(), trade(event_id="binance:BTCUSDT:2", trade_id=2), "bad-1", "bad-2"]:
                    handle.write((message if isinstance(message, str) else json.dumps(message)) + "\n")
            stream = (self.spark.readStream.format("text").load(source)
                      .withColumn("topic", F.lit("crypto-trades"))
                      .withColumn("partition", F.lit(0))
                      .withColumn("offset", F.xxhash64("value"))
                      .withColumn("timestamp", F.current_timestamp()))
            deduped = silver.deduplicate(silver.parse_trades(stream, SYMBOLS), "10 minutes")
            batches = []

            def collect(batch, _id):
                batches.extend(batch.select("event_id", "reason").collect())

            (deduped.writeStream.foreachBatch(collect).trigger(availableNow=True)
             .option("checkpointLocation", checkpoint).start().awaitTermination())
            valid = sorted(r.event_id for r in batches if r.reason is None)
            self.assertEqual(valid, ["binance:BTCUSDT:1", "binance:BTCUSDT:2"])
            self.assertEqual(len([r for r in batches if r.reason == "invalid_json"]), 2)
        finally:
            shutil.rmtree(directory, ignore_errors=True)


class DocumentTests(unittest.TestCase):
    def test_trade_document_uses_event_id_and_exact_decimals(self):
        doc = mongo_sink.trade_document({"event_id": "binance:BTCUSDT:1", "price": Decimal("65000.50"),
                                          "quantity": Decimal("0.02"), "quote_volume": Decimal("1300.01")})
        self.assertEqual(doc["_id"], "binance:BTCUSDT:1")
        self.assertEqual(str(doc["quote_volume"].to_decimal()), "1300.01")

    def test_rejected_document_id_is_the_kafka_position(self):
        doc = mongo_sink.rejected_document({"topic": "crypto-trades", "partition": 2, "offset": 41, "reason": "x"})
        self.assertEqual(doc["_id"], "crypto-trades:2:41")

    @unittest.skipUnless(os.getenv("MONGO_TEST_URI"), "MONGO_TEST_URI is not set")
    def test_bulk_upsert_is_idempotent(self):
        from pymongo import MongoClient
        client = MongoClient(os.environ["MONGO_TEST_URI"])
        name = f"spark_test_{os.getpid()}"
        try:
            collection = client[name]["trades"]
            docs = [{"_id": "a", "v": 1}, {"_id": "b", "v": 2}]
            mongo_sink.bulk_upsert(collection, docs)
            mongo_sink.bulk_upsert(collection, docs)
            self.assertEqual(collection.count_documents({}), 2)
        finally:
            client.drop_database(name)


if __name__ == "__main__":
    unittest.main()
