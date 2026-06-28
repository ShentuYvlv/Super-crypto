from __future__ import annotations

from typing import Any

import polars as pl


def normalize_funding(symbol: str, rows: list[dict[str, Any]]) -> pl.DataFrame:
    if not rows:
        return pl.DataFrame(
            schema={
                "symbol": pl.String,
                "funding_time": pl.Datetime(time_zone="UTC"),
                "funding_rate": pl.Float64,
                "mark_price": pl.Float64,
            }
        )
    return (
        pl.DataFrame(rows)
        .with_columns(
            [
                pl.lit(symbol).alias("symbol"),
                pl.from_epoch(pl.col("fundingTime"), time_unit="ms")
                .dt.replace_time_zone("UTC")
                .alias("funding_time"),
                pl.col("fundingRate").cast(pl.Float64).alias("funding_rate"),
                pl.col("markPrice").cast(pl.Float64).alias("mark_price"),
            ]
        )
        .select("symbol", "funding_time", "funding_rate", "mark_price")
        .sort("funding_time")
    )


def normalize_open_interest(symbol: str, rows: list[dict[str, Any]]) -> pl.DataFrame:
    if not rows:
        return pl.DataFrame(
            schema={
                "symbol": pl.String,
                "snapshot_time": pl.Datetime(time_zone="UTC"),
                "open_interest": pl.Float64,
                "oi_value_usd": pl.Float64,
            }
        )
    return (
        pl.DataFrame(rows)
        .with_columns(
            [
                pl.lit(symbol).alias("symbol"),
                pl.col("snapshot_time").str.to_datetime(time_zone="UTC"),
                pl.col("open_interest").cast(pl.Float64),
                pl.col("oi_value_usd").cast(pl.Float64),
            ]
        )
        .select("symbol", "snapshot_time", "open_interest", "oi_value_usd")
        .sort("snapshot_time")
    )
