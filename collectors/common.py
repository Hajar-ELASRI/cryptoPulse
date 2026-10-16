"""Shared schemas and Kafka publishing for ingestion services."""

import json
import logging
import os
from datetime import datetime, timezone


LOG = logging.getLogger(__name__)


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def iso_from_epoch(value: float | int) -> str:
    """Normalize Binance millisecond/microsecond and Reddit second timestamps."""
    number = float(value)
    if number > 1e14:
        number /= 1_000_000
    elif number > 1e11:
        number /= 1_000
    return datetime.fromtimestamp(number, timezone.utc).isoformat().replace("+00:00", "Z")


def producer():
    from confluent_kafka import Producer

    return Producer({
        "bootstrap.servers": os.getenv("KAFKA_BOOTSTRAP_SERVERS", "localhost:9092"),
        "client.id": "cryptopulse-ingestion",
        "enable.idempotence": True,
        "acks": "all",
    })


def publish(client, topic: str, event: dict, *, wait: bool = False) -> None:
    payload = json.dumps(event, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    key = str(event["event_id"]).encode("utf-8")
    delivery_errors = []

    def delivered(error, message):
        if error:
            LOG.error("Kafka delivery failed for %s: %s", event["event_id"], error)
            delivery_errors.append(error)

    while True:
        try:
            client.produce(topic, key=key, value=payload, on_delivery=delivered)
            break
        except BufferError:
            client.poll(1)
    client.poll(0)
    if wait:
        if client.flush(20) != 0:
            raise TimeoutError(f"Kafka delivery timeout for {event['event_id']}")
        if delivery_errors:
            raise RuntimeError(f"Kafka delivery failed for {event['event_id']}: {delivery_errors[0]}")
