"""Gold live job: Kafka `crypto-trades` -> MongoDB `indicators` and window alerts.

Trades are parsed and deduplicated like the Silver job, aggregated per symbol and
minute, and emitted once the window is closed by the Gold watermark (append mode).
Windows are therefore final when written, but appear about window + watermark late,
and a trade later than the watermark is not counted in its indicator.
"""

import argparse
import logging
import time
from datetime import datetime

from pyspark.sql import SparkSession

from cryptopulse_spark import gold, mongo_sink, silver
from cryptopulse_spark.config import Settings

LOG = logging.getLogger("indicators_stream")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--once", action="store_true", help="process available data, then stop")
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")

    settings = Settings.from_env()
    params = gold.AlertParams.from_env()
    spark = (SparkSession.builder.appName("cryptopulse-gold-indicators")
             .config("spark.sql.session.timeZone", "UTC").getOrCreate())
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
    deduped = silver.deduplicate(silver.parse_trades(raw, settings.symbols), settings.gold_watermark)
    windows = gold.minute_aggregates(silver.silver_trades(deduped))

    def write_batch(batch, batch_id: int) -> None:
        started = time.monotonic()
        indicators, alerts = mongo_sink.process_windows(
            spark, database, batch, "live", "live", params, datetime.utcnow())
        LOG.info("batch %s: %s indicators, %s alerts, %.1fs", batch_id, indicators, alerts, time.monotonic() - started)

    writer = (
        windows.writeStream.outputMode("append").foreachBatch(write_batch)
        .option("checkpointLocation", f"{settings.checkpoint_dir}/gold-indicators")
    )
    query = (writer.trigger(availableNow=True) if args.once else writer.trigger(processingTime="10 seconds")).start()
    query.awaitTermination()


if __name__ == "__main__":
    main()
