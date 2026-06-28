from __future__ import annotations

from pathlib import Path

import polars as pl

from super_crypto.common.config import load_yaml
from super_crypto.common.paths import DATA_ROOT, ensure_parent
from super_crypto.data.coinglass_client import CoinGlassClient
from super_crypto.data.normalize_external import normalize_records


ENDPOINT_MAP = {
    "tickers": "/api/futures/tickers",
    "futures_flow": "/api/futures/flow",
    "spot_flow": "/api/spot/flow",
    "coin_info": "/api/coins/info",
}


def run(config_path: str, symbols: list[str] | None = None) -> dict:
    config = load_yaml(config_path)
    selected_symbols = symbols or config.get("symbols", [])
    endpoints = config["coinglass"]["endpoints"]
    results: dict[str, dict] = {}
    with CoinGlassClient() as client:
        for symbol in selected_symbols:
            endpoint_stats: dict[str, int | str] = {}
            for endpoint in endpoints:
                payload = client.get(ENDPOINT_MAP[endpoint], params={"symbol": symbol})
                rows = payload.get("data", []) if isinstance(payload, dict) else []
                frame = normalize_records(symbol, endpoint, rows if isinstance(rows, list) else [rows])
                path = ensure_parent(DATA_ROOT / "raw" / "coinglass" / endpoint / f"{symbol}.parquet")
                frame.write_parquet(path)
                processed = ensure_parent(
                    DATA_ROOT / "processed" / "external_enrichment" / f"{endpoint}_{symbol}.parquet"
                )
                frame.write_parquet(processed)
                endpoint_stats[endpoint] = frame.height if client.enabled else "missing_api_key"
            results[symbol] = endpoint_stats
    return results

