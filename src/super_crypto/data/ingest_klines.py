from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

import httpx
import polars as pl

from super_crypto.common.config_symbols import data_config_with_resolved_symbols
from super_crypto.common.http import binance_offline_cache_enabled
from super_crypto.common.paths import DATA_ROOT, ensure_parent
from super_crypto.data.binance_client import BinanceFuturesClient
from super_crypto.data.data_quality import summarize_ohlcv_quality
from super_crypto.data.normalize_ohlcv import normalize_klines

TIMEFRAME_TO_MINUTES = {"1m": 1, "5m": 5, "15m": 15, "1h": 60}


def kline_limit(days: int, timeframe: str) -> int:
    bars_per_day = (24 * 60) // TIMEFRAME_TO_MINUTES[timeframe]
    return min(days * bars_per_day, 1500)


def _timestamp_ms(value: datetime) -> int:
    return int(value.timestamp() * 1000)


def fetch_klines_history(
    client: BinanceFuturesClient,
    symbol: str,
    timeframe: str,
    days: int,
    *,
    end_time: datetime | None = None,
) -> list[list[Any]]:
    interval_ms = TIMEFRAME_TO_MINUTES[timeframe] * 60 * 1000
    end_time = end_time or datetime.now(tz=UTC)
    start_time = end_time - timedelta(days=days)
    cursor_ms = _timestamp_ms(start_time)
    end_ms = _timestamp_ms(end_time)
    rows: list[list] = []
    while cursor_ms <= end_ms:
        batch = client.klines(
            symbol,
            timeframe,
            limit=1500,
            start_time_ms=cursor_ms,
            end_time_ms=end_ms,
        )
        if not batch:
            break
        rows.extend(batch)
        next_cursor = int(batch[-1][0]) + interval_ms
        if next_cursor <= cursor_ms:
            break
        cursor_ms = next_cursor
        if len(batch) < 1500:
            break
    return rows


def run(
    config_path: str, symbols: list[str] | None = None, timeframes: list[str] | None = None
) -> dict:
    config = data_config_with_resolved_symbols(config_path)
    selected_symbols = symbols or config["symbols"]
    selected_timeframes = timeframes or config["timeframes"]
    offline_cache = binance_offline_cache_enabled()
    results: dict[str, dict] = {}
    with BinanceFuturesClient() as client:
        for symbol in selected_symbols:
            symbol_quality: dict[str, dict] = {}
            for timeframe in selected_timeframes:
                raw_path = ensure_parent(
                    DATA_ROOT / "raw" / "binance" / "klines" / timeframe / f"{symbol}.parquet"
                )
                processed_path = ensure_parent(
                    DATA_ROOT / "processed" / "ohlcv" / timeframe / f"{symbol}.parquet"
                )
                used_cache = False
                try:
                    if offline_cache:
                        raise httpx.ConnectError("offline cache mode")
                    rows = fetch_klines_history(
                        client,
                        symbol,
                        timeframe,
                        int(config["history_days"][timeframe]),
                    )
                    frame = normalize_klines(symbol, timeframe, rows)
                except httpx.HTTPError as exc:
                    if not processed_path.exists():
                        symbol_quality[timeframe] = {
                            "status": "failed",
                            "used_cache": False,
                            "error": "network_error_no_cache",
                        }
                        continue
                    frame = pl.read_parquet(processed_path)
                    used_cache = True
                    cache_reason = type(exc).__name__
                frame.write_parquet(raw_path)
                frame.write_parquet(processed_path)
                symbol_quality[timeframe] = summarize_ohlcv_quality(
                    frame,
                    timeframe,
                    config["quality"]["max_gap_minutes"][timeframe],
                )
                symbol_quality[timeframe]["used_cache"] = used_cache
                if used_cache:
                    symbol_quality[timeframe]["cache_reason"] = cache_reason
            results[symbol] = symbol_quality
    return results
