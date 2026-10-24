"""News, social posts and sentiment: parse, validate and shape for MongoDB.

The three topics share one stream. Messages are validated on `event_id` and
`event_time`, deduplicated with `silver.deduplicate`, then typed per topic.
"""

from pyspark.sql import DataFrame, functions as F, types as T

BASE_SCHEMA = T.StructType([
    T.StructField("event_id", T.StringType()),
    T.StructField("event_time", T.StringType()),
])

STRING, LONG, DOUBLE = T.StringType(), T.LongType(), T.DoubleType()

TOPICS = {
    # topic: (collection, schema fields, timestamp fields)
    "crypto-news": ("news", {
        "source": STRING, "title": STRING, "summary": STRING, "url": STRING,
        "published_at": STRING, "ingested_at": STRING}, ["published_at", "ingested_at"]),
    "crypto-social": ("social_posts", {
        "source": STRING, "subreddit": STRING, "title": STRING, "text": STRING, "url": STRING,
        "score": LONG, "num_comments": LONG, "ingested_at": STRING}, ["ingested_at"]),
    "crypto-sentiment": ("sentiment", {
        "source_event_id": STRING, "source_topic": STRING, "source": STRING,
        "symbols": T.ArrayType(STRING), "label": STRING, "score": DOUBLE, "model": STRING,
        "processed_at": STRING}, ["processed_at"]),
}
LABELS = ["positive", "neutral", "negative"]
QUOTE_ASSET = "USDT"


def parse_editorial(raw: DataFrame) -> DataFrame:
    """Kafka-shaped rows -> columns expected by `silver.deduplicate`, plus `reason`."""
    parsed = (
        raw.select(F.col("value").cast("string").alias("raw"), "topic", "partition", "offset",
                   F.col("timestamp").alias("kafka_time"))
        .withColumn("json", F.from_json("raw", BASE_SCHEMA))
        .select("raw", "topic", "partition", "offset", "kafka_time",
                (F.get_json_object("raw", "$").isNull() | F.col("json").isNull()).alias("not_json"),
                "json.*")
        .withColumn("event_ts", F.to_timestamp("event_time"))
    )
    reason = F.coalesce(
        F.when(F.col("not_json"), F.lit("invalid_json")),
        F.when(F.col("event_id").isNull() | (F.trim("event_id") == ""), F.lit("missing_field:event_id")),
        F.when(F.col("event_time").isNull(), F.lit("missing_field:event_time")),
        F.when(F.col("event_ts").isNull(), F.lit("bad_timestamp")),
    )
    return parsed.withColumn("reason", reason)


def typed(parsed: DataFrame, topic: str) -> DataFrame:
    """Typed documents of one topic from valid rows; invalid payloads are dropped by the caller."""
    _, fields, timestamps = TOPICS[topic]
    schema = T.StructType([T.StructField(name, kind) for name, kind in fields.items()])
    rows = (parsed.filter((F.col("topic") == topic) & F.col("reason").isNull())
            .withColumn("json", F.from_json("raw", schema))
            .select("event_id", F.col("event_ts").alias("event_time"), "json.*"))
    for name in timestamps:
        rows = rows.withColumn(name, F.to_timestamp(name))
    if topic == "crypto-sentiment":
        rows = rows.filter(F.col("label").isin(LABELS) & F.col("score").between(-1, 1)
                           & F.col("source_event_id").isNotNull())
        rows = rows.withColumn("symbols", F.coalesce("symbols", F.array().cast("array<string>")))
        rows = rows.withColumn("trade_symbols", F.transform("symbols", lambda s: F.concat(s, F.lit(QUOTE_ASSET))))
    else:
        rows = rows.filter(F.trim(F.coalesce("title", F.lit(""))) != "")
        rows = rows.withColumn("title", F.trim("title"))
    return rows.withColumn("stored_at", F.current_timestamp())


def rejected(parsed: DataFrame) -> DataFrame:
    return parsed.filter(F.col("reason").isNotNull()).select(
        "reason", "raw", "topic", "partition", "offset", F.current_timestamp().alias("rejected_at"))
