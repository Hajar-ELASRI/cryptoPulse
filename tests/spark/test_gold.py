"""Gold layer checks with hand-computed expectations."""

import json
import os
import shutil
import tempfile
import unittest
from datetime import datetime, timedelta
from decimal import Decimal

from pyspark.sql import SparkSession, functions as F

from cryptopulse_spark import gold, mongo_sink, silver

T0 = datetime(2026, 10, 16, 9, 0, 0)
PARAMS = gold.AlertParams()


def spark_session():
    return (SparkSession.builder.master("local[2]").appName("gold-tests")
            .config("spark.sql.session.timeZone", "UTC")
            .config("spark.sql.shuffle.partitions", "2")
            .config("spark.ui.enabled", "false").getOrCreate())


def trade_rows(spark, rows):
    """rows: (event_id, symbol, trade_id, price, quantity, event_time)."""
    df = spark.createDataFrame(
        [(e, s, i, str(p), str(q), t) for e, s, i, p, q, t in rows],
        "event_id string, symbol string, trade_id long, price string, quantity string, event_time timestamp")
    df = (df.withColumn("price", F.col("price").cast(silver.DECIMAL))
          .withColumn("quantity", F.col("quantity").cast(silver.DECIMAL)))
    return df.withColumn("quote_volume", F.col("price") * F.col("quantity"))


def window_rows(spark, closes_and_volumes, symbol="BTCUSDT"):
    """One window per minute from T0: (close_price, quote_volume)."""
    rows = [(symbol, T0 + timedelta(minutes=i), T0 + timedelta(minutes=i + 1), 1,
             Decimal("1"), Decimal(v), Decimal(c), Decimal(c), Decimal(c), Decimal(c), Decimal(c))
            for i, (c, v) in enumerate(closes_and_volumes)]
    return spark.createDataFrame(
        rows, "symbol string, window_start timestamp, window_end timestamp, trade_count int, "
              "base_volume decimal(28,8), quote_volume decimal(38,16), min_price decimal(18,8), "
              "max_price decimal(18,8), avg_price decimal(18,8), open_price decimal(18,8), close_price decimal(18,8)")


class GoldTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.spark = spark_session()

    @classmethod
    def tearDownClass(cls):
        cls.spark.stop()

    def test_minute_aggregates_match_a_hand_calculation(self):
        trades = trade_rows(self.spark, [
            ("a", "BTCUSDT", 1, "100", "1", T0 + timedelta(seconds=5)),
            ("b", "BTCUSDT", 3, "98", "1", T0 + timedelta(seconds=50)),
            ("c", "BTCUSDT", 2, "102", "2", T0 + timedelta(seconds=20)),
            ("d", "BTCUSDT", 4, "110", "1", T0 + timedelta(seconds=61)),
        ])
        rows = {r.window_start: r for r in gold.minute_aggregates(trades).collect()}
        first = rows[T0]
        self.assertEqual(first.window_end, T0 + timedelta(minutes=1))
        self.assertEqual(first.trade_count, 3)
        self.assertEqual(first.base_volume, Decimal("4"))
        self.assertEqual(first.quote_volume, Decimal("402"))   # 100 + 2 x 102 + 98
        self.assertEqual((first.min_price, first.max_price), (Decimal("98"), Decimal("102")))
        self.assertEqual(first.avg_price, Decimal("100"))
        self.assertEqual((first.open_price, first.close_price), (Decimal("100"), Decimal("98")))
        self.assertEqual(rows[T0 + timedelta(minutes=1)].close_price, Decimal("110"))

    def test_open_and_close_break_ties_by_trade_id(self):
        trades = trade_rows(self.spark, [
            ("a", "BTCUSDT", 2, "11", "1", T0), ("b", "BTCUSDT", 1, "10", "1", T0), ("c", "BTCUSDT", 3, "12", "1", T0)])
        row = gold.minute_aggregates(trades).collect()[0]
        self.assertEqual((row.open_price, row.close_price), (Decimal("10"), Decimal("12")))

    def test_change_and_volume_baseline(self):
        series = [(100, 1000)] * 25 + [(101, 3000)]          # minute 25: +1 % and 3x the baseline
        context = {r.window_start: r for r in gold.add_context(window_rows(self.spark, series), PARAMS).collect()}
        self.assertIsNone(context[T0].change_pct)                       # first window
        self.assertEqual(context[T0 + timedelta(minutes=1)].change_pct, 0.0)
        self.assertIsNone(context[T0 + timedelta(minutes=19)].volume_ratio)   # warm-up: 19 prior windows
        self.assertEqual(context[T0 + timedelta(minutes=20)].volume_ratio, 1.0)
        last = context[T0 + timedelta(minutes=25)]
        self.assertEqual(last.change_pct, 1.0)                          # 100 x (101 - 100) / 100
        self.assertEqual(last.prev_window_start, T0 + timedelta(minutes=24))
        self.assertEqual(last.volume_ratio, 3.0)                        # 3000 / mean(1000 x 20)

    def test_change_uses_latest_earlier_window_when_a_minute_is_missing(self):
        rows = window_rows(self.spark, [(100, 10), (110, 10), (121, 10)])
        gapped = rows.filter(F.col("window_start") != T0 + timedelta(minutes=1))
        last = [r for r in gold.add_context(gapped, PARAMS).collect() if r.window_start == T0 + timedelta(minutes=2)][0]
        self.assertEqual(last.change_pct, 21.0)
        self.assertEqual(last.prev_window_start, T0)

    def test_window_alerts_carry_value_threshold_and_reason(self):
        series = [(100, 1000)] * 25 + [(101, 3000)] + [(101, 1000)]
        context = gold.add_context(window_rows(self.spark, series), PARAMS)
        alerts = {r.type: r for r in gold.window_alerts(context, PARAMS).collect()}
        self.assertEqual(set(alerts), {"VOLUME_SPIKE", "PRICE_MOVE"})
        spike, move = alerts["VOLUME_SPIKE"], alerts["PRICE_MOVE"]
        self.assertEqual((spike.observed_value, spike.threshold, spike.severity), (3.0, 2.0, "warning"))
        self.assertEqual(spike.baseline, 1000.0)
        self.assertEqual(spike.event_time, T0 + timedelta(minutes=26))   # window end
        self.assertIn("3.0x", spike.reason)
        self.assertIn("USDT", spike.reason)
        self.assertEqual((move.observed_value, move.threshold, move.severity), (1.0, 0.5, "critical"))
        self.assertIn("+1.00%", move.reason)

    def test_price_move_alert_is_suppressed_after_a_long_gap(self):
        rows = window_rows(self.spark, [(100, 10), (110, 10), (120, 10)])
        gapped = rows.filter(F.col("window_start") != T0 + timedelta(minutes=1)).withColumn(
            "window_start", F.when(F.col("window_start") == T0 + timedelta(minutes=2),
                                   F.lit(T0 + timedelta(hours=3))).otherwise(F.col("window_start")))
        alerts = gold.window_alerts(gold.add_context(gapped, PARAMS), PARAMS)
        self.assertEqual(alerts.filter("type = 'PRICE_MOVE'").count(), 0)   # 20 % but 3 hours after the previous row

    def test_no_spike_during_warmup(self):
        series = [(100, 1000)] * 5 + [(100, 9000)]
        context = gold.add_context(window_rows(self.spark, series), PARAMS)
        self.assertEqual(gold.window_alerts(context, PARAMS).filter("type = 'VOLUME_SPIKE'").count(), 0)

    def test_large_trade_alerts(self):
        trades = trade_rows(self.spark, [
            ("big", "BTCUSDT", 1, "65000.50", "2", T0),           # 130001 USDT
            ("small", "BTCUSDT", 2, "65000.50", "1", T0),         # 65000.50 USDT
            ("huge", "ETHUSDT", 3, "2400", "100", T0)])           # 240000 USDT >= 2 x threshold
        alerts = {r.ref_event_id: r for r in gold.large_trade_alerts(trades, PARAMS).collect()}
        self.assertEqual(set(alerts), {"big", "huge"})
        self.assertEqual(alerts["big"].observed_value, 130001.0)
        self.assertEqual(alerts["big"].severity, "warning")
        self.assertEqual(alerts["huge"].severity, "critical")
        self.assertIn("130001 USDT", alerts["big"].reason)

    def test_streaming_windows_are_emitted_once_closed_and_deduplicated(self):
        directory = tempfile.mkdtemp()
        try:
            source, checkpoint = os.path.join(directory, "in"), os.path.join(directory, "ck")
            os.makedirs(source)

            def message(trade_id, price, qty, at):
                return json.dumps({"event_id": f"binance:BTCUSDT:{trade_id}", "source": "binance", "symbol": "BTCUSDT",
                                   "trade_id": trade_id, "price": price, "quantity": qty,
                                   "event_time": at.strftime("%Y-%m-%dT%H:%M:%SZ"),
                                   "ingested_at": at.strftime("%Y-%m-%dT%H:%M:%SZ"), "is_buyer_maker": False})
            base = datetime.utcnow().replace(second=0, microsecond=0) - timedelta(hours=1)
            lines = [message(1, "100", "1", base + timedelta(seconds=5)),
                     message(1, "100", "1", base + timedelta(seconds=5)),            # duplicate
                     message(2, "102", "1", base + timedelta(seconds=40)),
                     message(3, "104", "1", base + timedelta(minutes=1, seconds=10)),
                     message(4, "90", "1", base + timedelta(minutes=10))]            # moves the watermark on
            with open(os.path.join(source, "a.json"), "w") as handle:
                handle.write("\n".join(lines) + "\n")
            stream = (self.spark.readStream.format("text").load(source)
                      .withColumn("topic", F.lit("crypto-trades")).withColumn("partition", F.lit(0))
                      .withColumn("offset", F.xxhash64("value")).withColumn("timestamp", F.current_timestamp()))
            deduped = silver.deduplicate(silver.parse_trades(stream, ["BTCUSDT"]), "1 minute")
            windows = gold.minute_aggregates(silver.silver_trades(deduped))
            emitted = []
            (windows.writeStream.outputMode("append")
             .foreachBatch(lambda batch, _id: emitted.extend(batch.collect()))
             .trigger(availableNow=True).option("checkpointLocation", checkpoint).start().awaitTermination())
            by_start = {r.window_start: r for r in emitted}
            self.assertEqual(sorted(by_start), [base, base + timedelta(minutes=1)])   # the last window is still open
            self.assertEqual(by_start[base].trade_count, 2)                          # duplicate counted once
            self.assertEqual(by_start[base].quote_volume, Decimal("202"))
            self.assertEqual(by_start[base + timedelta(minutes=1)].close_price, Decimal("104"))
        finally:
            shutil.rmtree(directory, ignore_errors=True)


class DocumentTests(unittest.TestCase):
    def test_indicator_document_id_and_decimals(self):
        row = {"symbol": "BTCUSDT", "window_start": T0, "window_end": T0 + timedelta(minutes=1), "trade_count": 3,
               "base_volume": Decimal("4"), "quote_volume": Decimal("402"), "min_price": Decimal("98"),
               "max_price": Decimal("102"), "avg_price": Decimal("100"), "open_price": Decimal("100"),
               "close_price": Decimal("98"), "change_pct": None, "prev_window_start": None}
        doc = mongo_sink.indicator_document(row, "live", "live", T0)
        self.assertEqual(doc["_id"], "live:BTCUSDT:2026-10-16T09:00:00Z")
        self.assertEqual(str(doc["close_price"].to_decimal()), "98")
        self.assertIsNone(doc["change_pct"])

    def test_alert_document_id_uses_window_or_trade(self):
        base = {"type": "VOLUME_SPIKE", "severity": "warning", "symbol": "BTCUSDT", "event_time": T0,
                "window_start": T0, "observed_value": 3.0, "threshold": 2.0, "baseline": 1.0, "unit": "ratio",
                "reason": "r", "ref_event_id": None}
        self.assertEqual(mongo_sink.alert_document(base, "replay-x", "replay", T0)["_id"],
                         "replay-x:VOLUME_SPIKE:BTCUSDT:2026-10-16T09:00:00Z")
        trade = dict(base, type="LARGE_TRADE", ref_event_id="binance:BTCUSDT:7")
        self.assertEqual(mongo_sink.alert_document(trade, "live", "live", T0)["_id"],
                         "live:LARGE_TRADE:BTCUSDT:binance:BTCUSDT:7")


@unittest.skipUnless(os.getenv("MONGO_TEST_URI"), "MONGO_TEST_URI is not set")
class ProcessWindowsTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.spark = spark_session()

    @classmethod
    def tearDownClass(cls):
        cls.spark.stop()

    def test_context_comes_from_stored_windows_and_rewrites_are_idempotent(self):
        from pymongo import MongoClient
        client = MongoClient(os.environ["MONGO_TEST_URI"])
        name = f"gold_test_{os.getpid()}"
        database = client[name]
        try:
            series = [(100, 1000)] * 25 + [(101, 3000)]
            windows = window_rows(self.spark, series)
            early = windows.filter(F.col("window_start") < T0 + timedelta(minutes=25))
            late = windows.filter(F.col("window_start") >= T0 + timedelta(minutes=25))
            mongo_sink.process_windows(self.spark, database, early, "live", "live", PARAMS, T0)
            self.assertEqual(database["alerts"].count_documents({}), 0)
            for _ in range(2):                                   # the second pass rewrites the same documents
                mongo_sink.process_windows(self.spark, database, late, "live", "live", PARAMS, T0)
            self.assertEqual(database["indicators"].count_documents({}), 26)
            self.assertEqual(sorted(a["type"] for a in database["alerts"].find()), ["PRICE_MOVE", "VOLUME_SPIKE"])
            last = database["indicators"].find_one({"_id": "live:BTCUSDT:2026-10-16T09:25:00Z"})
            self.assertEqual(last["change_pct"], 1.0)
            self.assertEqual(last["prev_window_start"], T0 + timedelta(minutes=24))
        finally:
            client.drop_database(name)


if __name__ == "__main__":
    unittest.main()
