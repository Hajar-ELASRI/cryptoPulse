"""Replay input conversion (run in the spark-test container: needs pyspark and bson)."""

import unittest
from datetime import datetime

from bson.int64 import Int64
from bson.decimal128 import Decimal128
from pyspark.sql import SparkSession

from cryptopulse_spark.jobs.replay import HISTORY_SCHEMA, history_row


class ReplayRowTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.spark = SparkSession.builder.master("local[1]").appName("replay-tests").getOrCreate()

    @classmethod
    def tearDownClass(cls):
        cls.spark.stop()

    def test_bson_int64_trade_id_is_accepted(self):
        # As read from trades_history: ids above 2^31 come back as Int64.
        doc = {"event_id": "history:BTCUSDT:6466017477", "symbol": "BTCUSDT", "trade_id": Int64(6466017477),
               "price": "107000.10", "quantity": Decimal128("0.002"), "event_time": datetime(2026, 7, 1, 0, 0, 1)}
        row = self.spark.createDataFrame([history_row(doc)], HISTORY_SCHEMA).first()
        self.assertEqual(row.trade_id, 6466017477)
        self.assertEqual(row.quantity, "0.002")


if __name__ == "__main__":
    unittest.main()
