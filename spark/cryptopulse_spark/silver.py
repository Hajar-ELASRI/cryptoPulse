"""Silver layer: parse, validate and enrich raw `crypto-trades` messages.

`parse_trades` is a pure DataFrame transformation, so the same code serves the
Kafka stream, the tests and the replay job. Every row keeps a `reason` column:
null for a valid trade, otherwise the documented rejection reason.
"""

from pyspark.sql import Column, DataFrame, functions as F, types as T

# 18 digits with 8 decimals covers Binance prices and quantities; the product has scale 16.
DECIMAL = T.DecimalType(18, 8)

TRADE_SCHEMA = T.StructType([
    T.StructField("event_id", T.StringType()),
    T.StructField("source", T.StringType()),
    T.StructField("symbol", T.StringType()),
    T.StructField("trade_id", T.LongType()),
    T.StructField("price", T.StringType()),
    T.StructField("quantity", T.StringType()),
    T.StructField("event_time", T.StringType()),
    T.StructField("ingested_at", T.StringType()),
    T.StructField("is_buyer_maker", T.BooleanType()),
])

REQUIRED_FIELDS = ["event_id", "symbol", "trade_id", "price", "quantity", "event_time"]


def _missing(name: str) -> Column:
    column = F.col(name)
    if name in ("event_id", "symbol", "price", "quantity", "event_time"):
        return column.isNull() | (F.trim(column) == "")
    return column.isNull()


def parse_trades(raw: DataFrame, symbols: list[str]) -> DataFrame:
    """Parse Kafka-shaped rows (`value`, `topic`, `partition`, `offset`, `timestamp`).

    Returns the typed trade columns plus `raw`, Kafka coordinates and `reason`.
    """
    parsed = (
        raw.select(
            F.col("value").cast("string").alias("raw"),
            "topic", "partition", "offset",
            F.col("timestamp").alias("kafka_time"),
        )
        .withColumn("json", F.from_json("raw", TRADE_SCHEMA))
        # from_json returns a struct of nulls for malformed text, so check the syntax separately.
        .select("raw", "topic", "partition", "offset", "kafka_time",
                (F.get_json_object("raw", "$").isNull() | F.col("json").isNull()).alias("not_json"),
                "json.*")
        .withColumn("symbol", F.upper(F.trim("symbol")))
        .withColumn("price_d", F.col("price").cast(DECIMAL))
        .withColumn("quantity_d", F.col("quantity").cast(DECIMAL))
        .withColumn("event_ts", F.to_timestamp("event_time"))
    )
    reason = F.coalesce(
        F.when(F.col("not_json"), F.lit("invalid_json")),
        *[F.when(_missing(name), F.lit(f"missing_field:{name}")) for name in REQUIRED_FIELDS],
        F.when(F.col("price_d").isNull(), F.lit("invalid_price")),
        F.when(F.col("quantity_d").isNull(), F.lit("invalid_quantity")),
        F.when(F.col("price_d") <= 0, F.lit("non_positive_price")),
        F.when(F.col("quantity_d") <= 0, F.lit("non_positive_quantity")),
        F.when(~F.col("symbol").isin(symbols), F.lit("unknown_symbol")),
        F.when(F.col("event_ts").isNull(), F.lit("bad_timestamp")),
        F.when(F.col("event_ts") > F.current_timestamp() + F.expr("INTERVAL 1 DAY"),
               F.lit("bad_timestamp")),
    )
    return parsed.withColumn("reason", reason)


def deduplicate(parsed: DataFrame, watermark: str) -> DataFrame:
    """Streaming dedup by `event_id` within the watermark.

    Invalid rows have no usable id, so their Kafka coordinates are the key and they
    are never merged with each other. The watermark runs on the exchange time, or on
    the Kafka timestamp when the message has none.
    """
    return (
        parsed
        .withColumn("dedup_key", F.coalesce(
            F.when(F.col("reason").isNull(), F.col("event_id")),
            F.concat_ws(":", "topic", "partition", "offset")))
        .withColumn("watermark_time", F.coalesce("event_ts", "kafka_time"))
        .withWatermark("watermark_time", watermark)
        .dropDuplicatesWithinWatermark(["dedup_key"])
    )


def silver_trades(parsed: DataFrame) -> DataFrame:
    """Enrich the valid rows: normalised types, `quote_volume`, minute window."""
    return (
        parsed.filter(F.col("reason").isNull())
        .select(
            "event_id",
            F.coalesce(F.col("source"), F.lit("binance")).alias("source"),
            "symbol",
            "trade_id",
            F.col("price_d").alias("price"),
            F.col("quantity_d").alias("quantity"),
            (F.col("price_d") * F.col("quantity_d")).alias("quote_volume"),
            F.col("event_ts").alias("event_time"),
            F.date_trunc("minute", "event_ts").alias("window_start"),
            F.to_timestamp("ingested_at").alias("ingested_at"),
            F.current_timestamp().alias("processed_at"),
            F.coalesce("is_buyer_maker", F.lit(False)).alias("is_buyer_maker"),
        )
    )


def rejected_trades(parsed: DataFrame) -> DataFrame:
    return parsed.filter(F.col("reason").isNotNull()).select(
        "reason", "raw", "topic", "partition", "offset",
        F.current_timestamp().alias("rejected_at"),
    )
