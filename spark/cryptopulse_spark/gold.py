"""Gold layer: one-minute indicators and explainable alerts.

Everything here is a DataFrame transformation that works on batch data (replay) and
streaming data (live), so both modes share the same rules.
"""

import os
from dataclasses import dataclass

from pyspark.sql import Column, DataFrame, Window, functions as F

from cryptopulse_spark.silver import DECIMAL


@dataclass(frozen=True)
class AlertParams:
    """Demo thresholds. They are configuration, not market constants."""

    volume_spike_factor: float = 2.0
    lookback_minutes: int = 20
    warmup_minutes: int = 20
    price_move_pct: float = 0.5
    large_trade_quote: float = 100_000.0
    max_gap_minutes: int = 5

    @classmethod
    def from_env(cls) -> "AlertParams":
        return cls(
            volume_spike_factor=float(os.getenv("ALERT_VOLUME_SPIKE_FACTOR", "2.0")),
            lookback_minutes=int(os.getenv("ALERT_VOLUME_LOOKBACK_MINUTES", "20")),
            warmup_minutes=int(os.getenv("ALERT_WARMUP_MINUTES", "20")),
            price_move_pct=float(os.getenv("ALERT_PRICE_MOVE_PCT", "0.5")),
            large_trade_quote=float(os.getenv("ALERT_LARGE_TRADE_QUOTE", "100000")),
            max_gap_minutes=int(os.getenv("ALERT_MAX_GAP_MINUTES", "5")),
        )


def minute_aggregates(trades: DataFrame) -> DataFrame:
    """Per symbol and one-minute window from Silver-shaped trades.

    Needs `symbol, trade_id, price, quantity, quote_volume, event_time`. Open and close
    are the first and last trade ordered by `(event_time, trade_id)`.
    """
    order = F.struct("event_time", "trade_id")
    grouped = trades.groupBy(F.window("event_time", "1 minute").alias("w"), "symbol").agg(
        F.count(F.lit(1)).cast("int").alias("trade_count"),
        F.sum("quantity").alias("base_volume"),
        F.sum("quote_volume").alias("quote_volume"),
        F.min("price").alias("min_price"),
        F.max("price").alias("max_price"),
        F.avg("price").cast(DECIMAL).alias("avg_price"),
        F.min_by("price", order).alias("open_price"),
        F.max_by("price", order).alias("close_price"),
    )
    return grouped.select(
        "symbol",
        F.col("w.start").alias("window_start"),
        F.col("w.end").alias("window_end"),
        "trade_count", "base_volume", "quote_volume",
        "min_price", "max_price", "avg_price", "open_price", "close_price",
    )


def add_context(windows: DataFrame, params: AlertParams) -> DataFrame:
    """Add the change against the previous window and the volume baseline.

    `change_pct = 100 × (close − previous close) / previous close`, where the previous
    window is the latest earlier row of the same symbol (minutes without trades have no
    row). The baseline is the mean `quote_volume` of the `lookback_minutes` rows before
    the current one, and the ratio stays null until `warmup_minutes` rows exist.
    """
    ordered = Window.partitionBy("symbol").orderBy("window_start")
    prior = ordered.rowsBetween(-params.lookback_minutes, -1)
    previous = F.lag("close_price").over(ordered)
    return (
        windows
        .withColumn("prev_close_price", previous)
        .withColumn("prev_window_start", F.lag("window_start").over(ordered))
        .withColumn("change_pct", F.when(
            F.col("prev_close_price") > 0,
            F.round(((F.col("close_price") - F.col("prev_close_price")) * 100
                     / F.col("prev_close_price")).cast("double"), 6)))
        .withColumn("baseline_quote_volume", F.avg("quote_volume").over(prior))
        .withColumn("baseline_windows", F.count("quote_volume").over(prior))
        .withColumn("volume_ratio", F.when(
            (F.col("baseline_windows") >= params.warmup_minutes) & (F.col("baseline_quote_volume") > 0),
            (F.col("quote_volume") / F.col("baseline_quote_volume")).cast("double")))
    )


def _unit(symbol: Column) -> Column:
    """Quote currency of a Binance pair, for readable reasons."""
    return F.coalesce(F.nullif(F.regexp_extract(symbol, r"(USDT|USDC|FDUSD|BTC|ETH|BNB)$", 1), F.lit("")),
                      F.lit("quote"))


def _severity(ratio: Column, threshold: float) -> Column:
    return F.when(ratio >= 2 * threshold, F.lit("critical")).otherwise(F.lit("warning"))


ALERT_COLUMNS = ["type", "severity", "symbol", "event_time", "window_start", "observed_value",
                 "threshold", "baseline", "unit", "reason", "ref_event_id"]


def window_alerts(context: DataFrame, params: AlertParams) -> DataFrame:
    """VOLUME_SPIKE and PRICE_MOVE alerts from `add_context` output."""
    spike = context.filter(F.col("volume_ratio") >= params.volume_spike_factor).select(
        F.lit("VOLUME_SPIKE").alias("type"),
        _severity(F.col("volume_ratio"), params.volume_spike_factor).alias("severity"),
        "symbol",
        F.col("window_end").alias("event_time"),
        "window_start",
        F.col("volume_ratio").alias("observed_value"),
        F.lit(params.volume_spike_factor).alias("threshold"),
        F.col("baseline_quote_volume").cast("double").alias("baseline"),
        F.lit("ratio").alias("unit"),
        F.format_string(
            "Volume of %.0f %s in this minute is %.1fx the mean of the previous %d minutes (%.0f %s); threshold %.1fx",
            F.col("quote_volume").cast("double"), _unit(F.col("symbol")), F.col("volume_ratio"),
            F.lit(params.lookback_minutes), F.col("baseline_quote_volume").cast("double"),
            _unit(F.col("symbol")), F.lit(params.volume_spike_factor)).alias("reason"),
        F.lit(None).cast("string").alias("ref_event_id"),
    )
    # After an outage the previous window can be hours old; that is not a one-minute move.
    recent = (F.col("window_start").cast("long") - F.col("prev_window_start").cast("long")) <= params.max_gap_minutes * 60
    move = context.filter((F.abs("change_pct") >= params.price_move_pct) & recent).select(
        F.lit("PRICE_MOVE").alias("type"),
        _severity(F.abs("change_pct"), params.price_move_pct).alias("severity"),
        "symbol",
        F.col("window_end").alias("event_time"),
        "window_start",
        F.col("change_pct").alias("observed_value"),
        F.lit(params.price_move_pct).alias("threshold"),
        F.col("prev_close_price").cast("double").alias("baseline"),
        F.lit("percent").alias("unit"),
        F.format_string(
            "Close moved %+.2f%% versus the previous window (%s to %s); threshold %.2f%%",
            F.col("change_pct"), F.col("prev_close_price").cast("string"),
            F.col("close_price").cast("string"), F.lit(params.price_move_pct)).alias("reason"),
        F.lit(None).cast("string").alias("ref_event_id"),
    )
    return spike.unionByName(move)


def large_trade_alerts(trades: DataFrame, params: AlertParams) -> DataFrame:
    """LARGE_TRADE alerts from Silver-shaped trades (needs `event_id`)."""
    return trades.filter(F.col("quote_volume") >= params.large_trade_quote).select(
        F.lit("LARGE_TRADE").alias("type"),
        _severity(F.col("quote_volume").cast("double"), params.large_trade_quote).alias("severity"),
        "symbol",
        F.col("event_time"),
        F.date_trunc("minute", "event_time").alias("window_start"),
        F.col("quote_volume").cast("double").alias("observed_value"),
        F.lit(params.large_trade_quote).alias("threshold"),
        F.lit(None).cast("double").alias("baseline"),
        _unit(F.col("symbol")).alias("unit"),
        F.format_string(
            "Single trade of %.0f %s (%s at %s) reaches the %.0f threshold",
            F.col("quote_volume").cast("double"), _unit(F.col("symbol")),
            F.col("quantity").cast("string"), F.col("price").cast("string"),
            F.lit(params.large_trade_quote)).alias("reason"),
        F.col("event_id").alias("ref_event_id"),
    )
