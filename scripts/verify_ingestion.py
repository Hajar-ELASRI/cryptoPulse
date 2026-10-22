"""Bounded, read-only verification of the ingestion handoff; no offsets committed."""

import argparse
import json
import os
import time
import uuid
from datetime import datetime, timezone
from decimal import Decimal


TOPICS = ("crypto-trades", "crypto-news", "crypto-sentiment")


def validate_event(topic: str, event: dict, key: bytes | None) -> None:
    if not isinstance(event, dict) or not event.get("event_id") or not event.get("source"):
        raise ValueError("Missing event_id/source")
    if key != event["event_id"].encode("utf-8"):
        raise ValueError("Kafka key differs from event_id")
    stamp = datetime.fromisoformat(event["event_time"].replace("Z", "+00:00"))
    if stamp.tzinfo is None or stamp.utcoffset().total_seconds() != 0:
        raise ValueError("event_time must include the UTC timezone")
    if topic == "crypto-trades":
        if event["event_id"] != f"binance:{event['symbol']}:{event['trade_id']}":
            raise ValueError("Unstable trade identifier")
        if type(event["trade_id"]) is not int or type(event["is_buyer_maker"]) is not bool:
            raise ValueError("Invalid trade identifier/maker types")
        for field in ("price", "quantity"):
            if not isinstance(event[field], str):
                raise ValueError(f"{field} must remain a decimal string")
            number = Decimal(event[field])
            if not number.is_finite() or number <= 0:
                raise ValueError(f"Invalid {field}")
        if not event.get("ingested_at"):
            raise ValueError("Missing ingested_at")
    elif topic == "crypto-news":
        if not event["event_id"].startswith("rss:") or not event.get("title") or not event.get("url"):
            raise ValueError("Invalid news payload")
        for field in ("summary", "published_at", "ingested_at"):
            if field not in event:
                raise ValueError(f"Missing {field}")
    elif topic == "crypto-sentiment":
        score = event["score"]
        if type(score) not in (float, int) or not -1 <= score <= 1:
            raise ValueError("Invalid sentiment score")
        label = "positive" if score >= 0.05 else "negative" if score <= -0.05 else "neutral"
        if event["label"] != label or not isinstance(event["symbols"], list):
            raise ValueError("Invalid sentiment label/symbols")
        if event["event_id"] != f"sentiment:{event['source_event_id']}":
            raise ValueError("Invalid sentiment lineage identifier")
        if event["source_topic"] not in ("crypto-news", "crypto-social"):
            raise ValueError("Invalid sentiment source topic")
        if not event.get("processed_at") or not event.get("model"):
            raise ValueError("Missing sentiment processing metadata")


def check_topics(sample_count: int, timeout: int) -> dict:
    from confluent_kafka import Consumer, TopicPartition

    consumer = Consumer({
        "bootstrap.servers": os.getenv("KAFKA_BOOTSTRAP_SERVERS", "localhost:9092"),
        "group.id": f"cryptopulse-verification-{uuid.uuid4()}",
        "enable.auto.commit": False,
        "enable.auto.offset.store": False,
        "auto.offset.reset": "earliest",
    })
    samples = {topic: [] for topic in TOPICS}
    errors = []
    partitions = {}
    deadline = time.monotonic() + timeout
    try:
        metadata = consumer.list_topics(timeout=15)
        assignment = []
        for topic in (*TOPICS, "crypto-social"):
            entry = metadata.topics.get(topic)
            if entry is None or entry.error:
                raise ValueError(f"Topic unavailable: {topic}")
            partitions[topic] = len(entry.partitions)
            if partitions[topic] != 3:
                raise ValueError(f"Expected 3 partitions for {topic}, got {partitions[topic]}")
            if topic == "crypto-social":
                continue  # Credentials optional; check topic creation, not Reddit availability.
            for partition in entry.partitions:
                low, high = consumer.get_watermark_offsets(TopicPartition(topic, partition), timeout=5)
                assignment.append(TopicPartition(topic, partition, max(low, high - sample_count)))
        consumer.assign(assignment)
        while time.monotonic() < deadline and any(len(items) < sample_count for items in samples.values()):
            message = consumer.poll(1)
            if message is None:
                continue
            if message.error():
                raise RuntimeError(str(message.error()))
            topic = message.topic()
            if len(samples[topic]) >= sample_count:
                continue
            try:
                event = json.loads(message.value())
                validate_event(topic, event, message.key())
                samples[topic].append({"partition": message.partition(), "offset": message.offset(), "event": event})
            except (ValueError, KeyError, TypeError, AttributeError, ArithmeticError) as error:
                errors.append(f"{topic}/{message.partition()}/{message.offset()}: {error}")
                break
        missing = [topic for topic, items in samples.items() if len(items) < sample_count]
        if missing:
            errors.append(f"Insufficient messages within {timeout}s: {', '.join(missing)}")
        return {"ok": not errors, "partitions": partitions, "errors": errors, "samples": samples}
    finally:
        consumer.close()


def check_mongo() -> dict:
    from pymongo import MongoClient

    with MongoClient(os.getenv("MONGO_URI", "mongodb://localhost:27017"), serverSelectionTimeoutMS=10000) as client:
        client.admin.command("ping")
        db = client[os.getenv("MONGO_DATABASE", "crypto_pulse")]
        required = {"trades_history", "trades", "news", "social_posts", "indicators", "alerts", "sentiment"}
        missing = sorted(required - set(db.list_collection_names()))
        indexes = db.trades_history.index_information()
        unique_trade_index = any(index.get("unique") and index["key"] == [("symbol", 1), ("trade_id", 1)] for index in indexes.values())
        return {"ok": not missing and unique_trade_index, "missing_collections": missing, "history_unique_index": unique_trade_index}


def check_spark(timeout: int) -> dict:
    import requests

    endpoint = os.getenv("SPARK_MASTER_UI", "http://spark-master:8080")
    deadline = time.monotonic() + timeout
    last_error = "No registered worker"
    while time.monotonic() < deadline:
        try:
            response = requests.get(f"{endpoint.rstrip('/')}/json/", timeout=5)
            response.raise_for_status()
            workers = [worker for worker in response.json()["workers"] if worker["state"] == "ALIVE"]
            if workers:
                return {"ok": True, "alive_workers": len(workers)}
        except (requests.RequestException, ValueError, KeyError) as error:
            last_error = str(error)
        time.sleep(1)
    return {"ok": False, "error": last_error}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--samples", type=int, default=3)
    parser.add_argument("--timeout", type=int, default=90)
    args = parser.parse_args()
    if args.samples < 1 or args.timeout < 1:
        parser.error("--samples and --timeout must be positive")
    report = {"checked_at": datetime.now(timezone.utc).isoformat(), "checks": {}}
    for name, check in (("mongo", check_mongo), ("spark", lambda: check_spark(args.timeout)), ("kafka_events", lambda: check_topics(args.samples, args.timeout))):
        try:
            report["checks"][name] = check()
        except Exception as error:
            report["checks"][name] = {"ok": False, "error": str(error)}
    report["ok"] = all(result["ok"] for result in report["checks"].values())
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
