"""Job settings read from environment variables."""

import os
from dataclasses import dataclass


def _csv(value: str) -> list[str]:
    return [item.strip().upper() for item in value.split(",") if item.strip()]


@dataclass(frozen=True)
class Settings:
    kafka_bootstrap: str
    mongo_uri: str
    mongo_database: str
    symbols: list[str]
    checkpoint_dir: str
    watermark: str
    gold_watermark: str
    editorial_watermark: str
    max_offsets_per_trigger: int

    @classmethod
    def from_env(cls) -> "Settings":
        return cls(
            kafka_bootstrap=os.getenv("KAFKA_BOOTSTRAP_SERVERS", "kafka:19092"),
            mongo_uri=os.getenv("MONGO_URI", "mongodb://mongo:27017"),
            mongo_database=os.getenv("MONGO_DATABASE", "crypto_pulse"),
            symbols=_csv(os.getenv("BINANCE_SYMBOLS", "btcusdt,ethusdt")),
            checkpoint_dir=os.getenv("SPARK_CHECKPOINT_DIR", "/opt/spark/checkpoints"),
            watermark=os.getenv("SILVER_WATERMARK", "10 minutes"),
            gold_watermark=os.getenv("GOLD_WATERMARK", "1 minute"),
            editorial_watermark=os.getenv("EDITORIAL_WATERMARK", "1 day"),
            max_offsets_per_trigger=int(os.getenv("SPARK_MAX_OFFSETS_PER_TRIGGER", "50000")),
        )
