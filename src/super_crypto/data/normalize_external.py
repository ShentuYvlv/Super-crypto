from __future__ import annotations

from typing import Any

import polars as pl


def normalize_records(symbol: str, endpoint: str, rows: list[dict[str, Any]]) -> pl.DataFrame:
    if not rows:
        return pl.DataFrame(schema={"symbol": pl.String, "endpoint": pl.String})
    return pl.DataFrame(rows).with_columns(
        [pl.lit(symbol).alias("symbol"), pl.lit(endpoint).alias("endpoint")]
    )

