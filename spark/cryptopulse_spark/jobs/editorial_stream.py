"""Editorial job: `crypto-news`, `crypto-social`, `crypto-sentiment` -> `news`, `social_posts`, `sentiment`.

Run `--once` to drain what is currently in Kafka and stop.
"""

import argparse
import logging
import time

from pyspark.sql import SparkSession

from cryptopulse_spark import editorial, mongo_sink, silver
from cryptopulse_spark.config import Settings

LOG = logging.getLogger("editorial_stream")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--once", action="store_true", help="process available data, then stop")
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")

    settings = Settings.from_env()
    spark = (SparkSession.builder.appName("cryptopulse-editorial")
             .config("spark.sql.session.timeZone", "UTC").getOrCreate())
    database = mongo_sink.connect(settings.mongo_uri, settings.mongo_database)

    raw = (
        spark.readStream.format("kafka")
        .option("kafka.bootstrap.servers", settings.kafka_bootstrap)
        .option("subscribe", ",".join(editorial.TOPICS))
        .option("startingOffsets", "earliest")
        .option("maxOffsetsPerTrigger", settings.max_offsets_per_trigger)
        .option("failOnDataLoss", "false")
        .load()
    )
    # News can be republished for days (RSS), so keep dedup state for a day, not minutes.
    parsed = silver.deduplicate(editorial.parse_editorial(raw), settings.editorial_watermark)

    def write_batch(batch, batch_id: int) -> None:
        started = time.monotonic()
        counts = mongo_sink.write_editorial_batch(database, batch)
        LOG.info("batch %s: %s, %.1fs", batch_id, counts, time.monotonic() - started)

    writer = (
        parsed.writeStream.foreachBatch(write_batch)
        .option("checkpointLocation", f"{settings.checkpoint_dir}/editorial")
    )
    query = (writer.trigger(availableNow=True) if args.once else writer.trigger(processingTime="10 seconds")).start()
    query.awaitTermination()


if __name__ == "__main__":
    main()
