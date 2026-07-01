from __future__ import annotations

import httpx
import polars as pl

from super_crypto.common.config import load_yaml
from super_crypto.common.http import binance_offline_cache_enabled
from super_crypto.common.paths import DATA_ROOT, ensure_parent
from super_crypto.data.binance_client import BinanceFuturesClient
from super_crypto.data.normalize_derivatives import normalize_funding


def run(config_path: str, symbols: list[str] | None = None) -> dict:
    config = load_yaml(config_path)
    selected_symbols = symbols or config["symbols"]
    offline_cache = binance_offline_cache_enabled()
    result: dict[str, int] = {}
    with BinanceFuturesClient() as client:
        for symbol in selected_symbols:
            raw_path = ensure_parent(
                DATA_ROOT / "raw" / "binance" / "funding" / f"{symbol}.parquet"
            )
            processed_path = ensure_parent(
                DATA_ROOT / "processed" / "derivatives" / f"funding_{symbol}.parquet"
            )
            used_cache = False
            try:
                if offline_cache:
                    raise httpx.ConnectError("offline cache mode")
                history = client.funding_rate_history(symbol)
                frame = normalize_funding(symbol, history)
            except httpx.HTTPError:
                if not processed_path.exists():
                    raise
                frame = pl.read_parquet(processed_path)
                used_cache = True
            frame.write_parquet(raw_path)
            frame.write_parquet(processed_path)
            result[symbol] = {"rows": frame.height, "used_cache": used_cache}
    return result
