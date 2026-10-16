import unittest
from datetime import date

from collectors.binance import normalize_trade
from collectors.common import iso_from_epoch
from collectors.reddit import normalize_post
from collectors.rss import normalize_article
from scripts.historical_loader import parse_trade_row, previous_months
from sentiment.service import classify


class _Analyzer:
    def polarity_scores(self, text):
        return {"compound": 0.7 if "surge" in text else -0.6}


class IngestionTests(unittest.TestCase):
    def test_binance_trade_schema(self):
        event = normalize_trade({"e": "trade", "s": "BTCUSDT", "t": 42, "p": "64000.10", "q": "0.2", "T": 1735689600000, "m": False})
        self.assertEqual(event["event_id"], "binance:BTCUSDT:42")
        self.assertEqual(event["price"], "64000.10")
        self.assertEqual(event["event_time"], "2025-01-01T00:00:00Z")

    def test_microsecond_history_and_completed_months(self):
        self.assertEqual(iso_from_epoch(1735689600000000), "2025-01-01T00:00:00Z")
        document = parse_trade_row(["42", "64000.10", "0.2", "12800.02", "1735689600000000", "False", "True"], "BTCUSDT")
        self.assertEqual(document["event_id"], "binance:BTCUSDT:42")
        self.assertEqual(document["event_time"].isoformat(), "2025-01-01T00:00:00+00:00")
        self.assertEqual(previous_months(3, date(2026, 1, 16)), ["2025-10", "2025-11", "2025-12"])

    def test_news_dedup_key_is_stable(self):
        article = {"id": "article-1", "link": "https://example.com/a", "title": "<b>BTC</b> rises", "summary": "<p>Big move</p>"}
        first = normalize_article(article, "Test")
        second = normalize_article(article, "Test")
        self.assertEqual(first["event_id"], second["event_id"])
        self.assertEqual(first["title"], "BTC rises")

    def test_reddit_and_sentiment_handoff(self):
        post = normalize_post({"id": "abc", "subreddit": "Bitcoin", "title": "Bitcoin surge", "selftext": "BTC rises", "permalink": "/r/Bitcoin/comments/abc", "created_utc": 1735689600})
        result = classify(post, "crypto-social", _Analyzer())
        self.assertEqual(result["event_id"], "sentiment:reddit:abc")
        self.assertEqual(result["label"], "positive")
        self.assertIn("BTC", result["symbols"])


if __name__ == "__main__":
    unittest.main()

