"""VADER NLP sentiment enrichment for English crypto news and posts."""

import json
import logging
import os
import re

from collectors.common import publish, producer, utc_now


LOG = logging.getLogger(__name__)

COIN_TERMS = {
    "BTC": ("bitcoin", "btc"),
    "ETH": ("ethereum", "ether", "eth"),
}


def classify(event: dict, source_topic: str, analyzer) -> dict:
    text = " ".join(str(event.get(name) or "") for name in ("title", "summary", "text"))
    score = float(analyzer.polarity_scores(text)["compound"])
    label = "positive" if score >= 0.05 else "negative" if score <= -0.05 else "neutral"
    words = set(re.findall(r"[a-z0-9]+", text.lower()))
    symbols = [coin for coin, terms in COIN_TERMS.items() if words.intersection(terms)]
    return {
        "event_id": f"sentiment:{event['event_id']}",
        "source_event_id": event["event_id"],
        "source_topic": source_topic,
        "source": event.get("source", "unknown"),
        "symbols": symbols,
        "label": label,
        "score": score,
        "model": "VADER-3.3.2-en",
        "event_time": event["event_time"],
        "processed_at": utc_now(),
    }


def run() -> None:
    from confluent_kafka import Consumer
    from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer

    consumer = Consumer({
        "bootstrap.servers": os.getenv("KAFKA_BOOTSTRAP_SERVERS", "localhost:9092"),
        "group.id": os.getenv("SENTIMENT_GROUP_ID", "cryptopulse-sentiment-v1"),
        "auto.offset.reset": "earliest",
        "enable.auto.commit": False,
    })
    client = producer()
    analyzer = SentimentIntensityAnalyzer()
    consumer.subscribe(["crypto-news", "crypto-social"])
    try:
        while True:
            message = consumer.poll(1)
            if message is None:
                continue
            if message.error():
                LOG.error("Kafka consumer error: %s", message.error())
                continue
            try:
                source = json.loads(message.value())
                event = classify(source, message.topic(), analyzer)
            except (json.JSONDecodeError, KeyError, TypeError, ValueError):
                LOG.exception("Skipping malformed %s offset %s", message.topic(), message.offset())
                consumer.commit(message=message, asynchronous=False)
                continue
            # Exit on failed delivery. A container restart replays the uncommitted offset.
            publish(client, "crypto-sentiment", event, wait=True)
            consumer.commit(message=message, asynchronous=False)
    finally:
        consumer.close()
        client.flush(20)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    run()
