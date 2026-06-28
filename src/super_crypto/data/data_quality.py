from __future__ import annotations

from datetime import datetime

import polars as pl

from super_crypto.common.time import utc_now
from super_crypto.common.types import DataQuality
from super_crypto.data.freshness import classify_freshness


def build_quality(
    *,
    source: str,
    generated_at: datetime | None = None,
    freshness_sec: int = 0,
    missing_fields: list[str] | None = None,
    stale_fields: list[str] | None = None,
    details: dict | None = None,
    stale_after_sec: int = 900,
    blocked_after_sec: int | None = None,
) -> DataQuality:
    missing_fields = missing_fields or []
    stale_fields = stale_fields or []
    state = classify_freshness(freshness_sec, stale_after_sec, blocked_after_sec)
    if missing_fields and state == "healthy":
        state = "partial"
    if stale_fields and state == "healthy":
        state = "stale"
    return DataQuality(
        generated_at=generated_at or utc_now(),
        source=source,
        freshness_sec=freshness_sec,
        data_quality=state,
        missing_fields=missing_fields,
        stale_fields=stale_fields,
        details=details or {},
    )


def summarize_ohlcv_quality(frame: pl.DataFrame, timeframe: str, max_gap_minutes: int) -> dict:
    if frame.is_empty():
        return {
            "row_count": 0,
            "duplicate_timestamps": 0,
            "max_gap_minutes": None,
            "timezone": "UTC",
            "quality": "failed",
        }
    sorted_frame = frame.sort("open_time")
    deltas = (
        sorted_frame.select(
            pl.col("open_time")
            .diff()
            .dt.total_minutes()
            .alias("gap_minutes")
        )
        .drop_nulls()
    )
    max_gap = deltas["gap_minutes"].max() if not deltas.is_empty() else 0
    duplicate_count = (
        sorted_frame.group_by("open_time").len().filter(pl.col("len") > 1).height
    )
    quality = "healthy"
    if duplicate_count:
        quality = "partial"
    if max_gap and max_gap > max_gap_minutes:
        quality = "stale"
    return {
        "timeframe": timeframe,
        "row_count": sorted_frame.height,
        "duplicate_timestamps": duplicate_count,
        "max_gap_minutes": max_gap,
        "timezone": "UTC",
        "quality": quality,
    }

