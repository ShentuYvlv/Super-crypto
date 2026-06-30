from __future__ import annotations

from super_crypto.common.config import load_yaml
from super_crypto.common.paths import DATA_ROOT, ensure_parent
from super_crypto.data.binance_client import BinanceFuturesClient
from super_crypto.data.normalize_derivatives import normalize_funding


def run(config_path: str, symbols: list[str] | None = None) -> dict:
    config = load_yaml(config_path)
    selected_symbols = symbols or config["symbols"]
    result: dict[str, int] = {}
    with BinanceFuturesClient() as client:
        for symbol in selected_symbols:
            history = client.funding_rate_history(symbol)
            frame = normalize_funding(symbol, history)
            raw_path = ensure_parent(
                DATA_ROOT / "raw" / "binance" / "funding" / f"{symbol}.parquet"
            )
            processed_path = ensure_parent(
                DATA_ROOT / "processed" / "derivatives" / f"funding_{symbol}.parquet"
            )
            frame.write_parquet(raw_path)
            frame.write_parquet(processed_path)
            result[symbol] = frame.height
    return result
