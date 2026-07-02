from __future__ import annotations

from pathlib import Path

import httpx
import polars as pl

from super_crypto.common.config_symbols import data_config_with_resolved_symbols
from super_crypto.common.http import binance_offline_cache_enabled
from super_crypto.common.paths import DATA_ROOT, ensure_parent
from super_crypto.common.time import to_iso, utc_now
from super_crypto.data.binance_client import BinanceFuturesClient
from super_crypto.data.normalize_derivatives import normalize_open_interest


def _snapshot_path(symbol: str) -> Path:
    return DATA_ROOT / "processed" / "derivatives" / f"open_interest_{symbol}.parquet"


def _load_existing(symbol: str) -> pl.DataFrame:
    path = _snapshot_path(symbol)
    if not path.exists():
        return pl.DataFrame(
            schema={
                "symbol": pl.String,
                "snapshot_time": pl.Datetime(time_zone="UTC"),
                "open_interest": pl.Float64,
                "oi_value_usd": pl.Float64,
            }
        )
    return pl.read_parquet(path)


def run(config_path: str, symbols: list[str] | None = None) -> dict:
    config = data_config_with_resolved_symbols(config_path)
    selected_symbols = symbols or config["symbols"]
    offline_cache = binance_offline_cache_enabled()
    results: dict[str, dict] = {}
    with BinanceFuturesClient() as client:
        for symbol in selected_symbols:
            existing = _load_existing(symbol)
            used_cache = False
            try:
                if offline_cache:
                    raise httpx.ConnectError("offline cache mode")
                open_interest = client.open_interest(symbol)
                mark_price = client.current_funding(symbol).get("markPrice", 0)
                snapshot = {
                    "snapshot_time": to_iso(utc_now()),
                    "open_interest": open_interest.get("openInterest", 0),
                    "oi_value_usd": float(open_interest.get("openInterest", 0))
                    * float(mark_price or 0),
                }
                frame = normalize_open_interest(symbol, [snapshot])
            except httpx.HTTPError:
                if existing.is_empty():
                    raise
                frame = existing.tail(1)
                used_cache = True
            combined = (
                pl.concat([existing, frame], how="vertical_relaxed")
                .unique(subset=["snapshot_time"], keep="last")
                .sort("snapshot_time")
            )
            raw_path = ensure_parent(
                DATA_ROOT / "raw" / "binance" / "open_interest" / f"{symbol}.parquet"
            )
            processed_path = ensure_parent(_snapshot_path(symbol))
            combined.write_parquet(raw_path)
            combined.write_parquet(processed_path)
            latest = combined.tail(24)
            changes = latest.select(
                [
                    ((pl.col("open_interest").last() / pl.col("open_interest").first()) - 1)
                    .fill_nan(0)
                    .alias("oi_change_window")
                ]
            )
            results[symbol] = {
                "rows": combined.height,
                "used_cache": used_cache,
                "oi_change_window": float(changes["oi_change_window"][0])
                if latest.height > 1
                else 0.0,
            }
    return results
