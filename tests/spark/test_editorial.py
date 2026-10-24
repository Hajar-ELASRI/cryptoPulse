"""News, social and sentiment shaping checks."""

import json
import unittest
from datetime import datetime, timezone

from pyspark.sql import SparkSession

from cryptopulse_spark import editorial, mongo_sink

KAFKA_TIME = datetime(2026, 10, 16, 9, 1, tzinfo=timezone.utc)

NEWS = {"event_id": "rss:abc", "source": "coindesk", "title": " Bitcoin rallies ", "summary": "s",
        "url": "https://x", "event_time": "2026-10-16T09:00:00Z", "published_at": "2026-10-16T09:00:00Z",
        "ingested_at": "2026-10-16T09:00:05Z"}
SOCIAL = {"event_id": "reddit:p1", "source": "reddit", "subreddit": "Bitcoin", "title": "moon?", "text": "",
          "url": "https://r", "score": 12, "num_comments": 3, "event_time": "2026-10-16T09:00:00Z",
          "ingested_at": "2026-10-16T09:00:05Z"}
SENTIMENT = {"event_id": "sentiment:rss:abc", "source_event_id": "rss:abc", "source_topic": "crypto-news",
             "source": "coindesk", "symbols": ["BTC", "ETH"], "label": "positive", "score": 0.62,
             "model": "VADER-3.3.2-en", "event_time": "2026-10-16T09:00:00Z", "processed_at": "2026-10-16T09:00:06Z"}


class EditorialTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.spark = (SparkSession.builder.master("local[2]").appName("editorial-tests")
                     .config("spark.sql.session.timeZone", "UTC").config("spark.sql.shuffle.partitions", "2")
                     .config("spark.ui.enabled", "false").getOrCreate())

    @classmethod
    def tearDownClass(cls):
        cls.spark.stop()

    def parsed(self, *messages):
        rows = [(m if isinstance(m, str) else json.dumps(m), topic, 0, i, KAFKA_TIME)
                for i, (topic, m) in enumerate(messages)]
        raw = self.spark.createDataFrame(rows, "value string, topic string, partition int, offset long, timestamp timestamp")
        return editorial.parse_editorial(raw)

    def test_news_is_typed_and_trimmed(self):
        row = editorial.typed(self.parsed(("crypto-news", NEWS)), "crypto-news").collect()[0]
        self.assertEqual(row.title, "Bitcoin rallies")
        self.assertEqual(row.event_time, datetime(2026, 10, 16, 9, 0, 0))
        self.assertEqual(row.ingested_at, datetime(2026, 10, 16, 9, 0, 5))
        self.assertIsNotNone(row.stored_at)

    def test_social_counts_stay_integers(self):
        row = editorial.typed(self.parsed(("crypto-social", SOCIAL)), "crypto-social").collect()[0]
        self.assertEqual((row.subreddit, row.score, row.num_comments), ("Bitcoin", 12, 3))

    def test_sentiment_gets_trade_symbols(self):
        row = editorial.typed(self.parsed(("crypto-sentiment", SENTIMENT)), "crypto-sentiment").collect()[0]
        self.assertEqual(row.symbols, ["BTC", "ETH"])
        self.assertEqual(row.trade_symbols, ["BTCUSDT", "ETHUSDT"])
        self.assertEqual((row.label, row.score), ("positive", 0.62))

    def test_sentiment_without_symbols_is_kept_with_empty_lists(self):
        row = editorial.typed(self.parsed(("crypto-sentiment", dict(SENTIMENT, symbols=[]))), "crypto-sentiment").collect()[0]
        self.assertEqual((row.symbols, row.trade_symbols), ([], []))

    def test_rejections(self):
        parsed = self.parsed(
            ("crypto-news", "not json"),
            ("crypto-news", {k: v for k, v in NEWS.items() if k != "event_id"}),
            ("crypto-news", dict(NEWS, event_time="soon")),
            ("crypto-news", {k: v for k, v in NEWS.items() if k != "event_time"}))
        reasons = [r.reason for r in parsed.orderBy("offset").collect()]
        self.assertEqual(reasons, ["invalid_json", "missing_field:event_id", "bad_timestamp", "missing_field:event_time"])
        self.assertEqual(editorial.rejected(parsed).count(), 4)

    def test_invalid_payloads_do_not_become_documents(self):
        parsed = self.parsed(
            ("crypto-news", dict(NEWS, title="  ")),
            ("crypto-sentiment", dict(SENTIMENT, label="great")),
            ("crypto-sentiment", dict(SENTIMENT, score=3)))
        self.assertEqual(editorial.typed(parsed, "crypto-news").count(), 0)
        self.assertEqual(editorial.typed(parsed, "crypto-sentiment").count(), 0)

    def test_topics_are_not_mixed(self):
        parsed = self.parsed(("crypto-news", NEWS), ("crypto-social", SOCIAL), ("crypto-sentiment", SENTIMENT))
        self.assertEqual([editorial.typed(parsed, t).count() for t in editorial.TOPICS], [1, 1, 1])

    def test_document_id_is_the_event_id(self):
        self.assertEqual(mongo_sink.editorial_document({"event_id": "rss:abc"})["_id"], "rss:abc")


if __name__ == "__main__":
    unittest.main()
