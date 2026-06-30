from __future__ import annotations

from typing import Any

import polars as pl

KLINE_COLUMNS = [
    "open_time",
    "open",
    "high",
    "low",
    "close",
    "volume",
    "close_time",
    "quote_volume",
    "trade_count",
    "taker_buy_base_volume",
    "taker_buy_quote_volume",
    "ignore",
]


def normalize_klines(symbol: str, timeframe: str, rows: list[list[Any]]) -> pl.DataFrame:
    if not rows:
        return pl.DataFrame(
            schema={
                "symbol": pl.String,
                "timeframe": pl.String,
                "open_time": pl.Datetime(time_zone="UTC"),
                "close_time": pl.Datetime(time_zone="UTC"),
                "open": pl.Float64,
                "high": pl.Float64,
                "low": pl.Float64,
                "close": pl.Float64,
                "volume": pl.Float64,
                "quote_volume": pl.Float64,
                "trade_count": pl.Int64,
                "taker_buy_base_volume": pl.Float64,
                "taker_buy_quote_volume": pl.Float64,
            }
        )
    frame = pl.DataFrame(rows, schema=KLINE_COLUMNS, orient="row").with_columns(
        [
            pl.lit(symbol).alias("symbol"),
            pl.lit(timeframe).alias("timeframe"),
            pl.from_epoch(pl.col("open_time"), time_unit="ms").dt.replace_time_zone("UTC"),
            pl.from_epoch(pl.col("close_time"), time_unit="ms").dt.replace_time_zone("UTC"),
            pl.col(["open", "high", "low", "close", "volume", "quote_volume"]).cast(pl.Float64),
            pl.col("trade_count").cast(pl.Int64),
            pl.col(["taker_buy_base_volume", "taker_buy_quote_volume"]).cast(pl.Float64),
        ]
    )
    return frame.select(
        "symbol",
        "timeframe",
        "open_time",
        "close_time",
        "open",
        "high",
        "low",
        "close",
        "volume",
        "quote_volume",
        "trade_count",
        "taker_buy_base_volume",
        "taker_buy_quote_volume",
    )
