"""Silver trades job: Kafka `crypto-trades` -> MongoDB `trades` / `trades_rejected`.

Run `--once` to drain what is currently in Kafka and stop (useful for checks and demos).
"""

import argparse
import logging
import time

from pyspark.sql import SparkSession

from cryptopulse_spark import mongo_sink, silver
from cryptopulse_spark.config import Settings

LOG = logging.getLogger("trades_stream")


def build_session() -> SparkSession:
    return (
        SparkSession.builder.appName("cryptopulse-silver-trades")
        .config("spark.sql.session.timeZone", "UTC")
        .getOrCreate()
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--once", action="store_true", help="process available data, then stop")
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")

    settings = Settings.from_env()
    spark = build_session()
    database = mongo_sink.connect(settings.mongo_uri, settings.mongo_database)

    raw = (
        spark.readStream.format("kafka")
        .option("kafka.bootstrap.servers", settings.kafka_bootstrap)
        .option("subscribe", "crypto-trades")
        .option("startingOffsets", "earliest")
        .option("maxOffsetsPerTrigger", settings.max_offsets_per_trigger)
        .option("failOnDataLoss", "false")
        .load()
    )
    parsed = silver.deduplicate(silver.parse_trades(raw, settings.symbols), settings.watermark)

    def write_batch(batch, batch_id: int) -> None:
        started = time.monotonic()
        valid, rejected = mongo_sink.write_silver_batch(
            database, silver.silver_trades(batch), silver.rejected_trades(batch))
        LOG.info("batch %s: %s trades upserted, %s rejected, %.1fs",
                 batch_id, valid, rejected, time.monotonic() - started)

    writer = (
        parsed.writeStream.foreachBatch(write_batch)
        .option("checkpointLocation", f"{settings.checkpoint_dir}/silver-trades")
    )
    query = (writer.trigger(availableNow=True) if args.once else writer.trigger(processingTime="5 seconds")).start()
    query.awaitTermination()


if __name__ == "__main__":
    main()
