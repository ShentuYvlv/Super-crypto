from __future__ import annotations

import httpx
import polars as pl

from super_crypto.common.config import load_yaml
from super_crypto.common.http import binance_offline_cache_enabled
from super_crypto.common.paths import DATA_ROOT, ensure_parent
from super_crypto.data.binance_client import BinanceFuturesClient
from super_crypto.data.data_quality import summarize_ohlcv_quality
from super_crypto.data.normalize_ohlcv import normalize_klines

TIMEFRAME_TO_MINUTES = {"1m": 1, "5m": 5, "15m": 15, "1h": 60}


def kline_limit(days: int, timeframe: str) -> int:
    bars_per_day = (24 * 60) // TIMEFRAME_TO_MINUTES[timeframe]
    return min(days * bars_per_day, 1500)


def run(
    config_path: str, symbols: list[str] | None = None, timeframes: list[str] | None = None
) -> dict:
    config = load_yaml(config_path)
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
                    rows = client.klines(
                        symbol,
                        timeframe,
                        limit=kline_limit(config["history_days"][timeframe], timeframe),
                    )
                    frame = normalize_klines(symbol, timeframe, rows)
                except httpx.HTTPError:
                    if not processed_path.exists():
                        raise
                    frame = pl.read_parquet(processed_path)
                    used_cache = True
                frame.write_parquet(raw_path)
                frame.write_parquet(processed_path)
                symbol_quality[timeframe] = summarize_ohlcv_quality(
                    frame,
                    timeframe,
                    config["quality"]["max_gap_minutes"][timeframe],
                )
                symbol_quality[timeframe]["used_cache"] = used_cache
            results[symbol] = symbol_quality
    return results
