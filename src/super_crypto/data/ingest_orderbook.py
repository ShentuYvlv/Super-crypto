from __future__ import annotations

from typing import Any

import polars as pl

from super_crypto.common.config import load_yaml
from super_crypto.common.paths import DATA_ROOT, ensure_parent
from super_crypto.common.time import to_iso, utc_now
from super_crypto.data.binance_client import BinanceFuturesClient


def _estimate_slippage(side_levels: list[list[str]], notionals: list[int]) -> dict[str, float]:
    estimates: dict[str, float] = {}
    if not side_levels:
        return {str(notional): 0.0 for notional in notionals}
    best_price = float(side_levels[0][0])
    for notional in notionals:
        remaining = float(notional)
        spent = 0.0
        acquired = 0.0
        for price_raw, size_raw in side_levels:
            price = float(price_raw)
            size = float(size_raw)
            level_notional = price * size
            take = min(remaining, level_notional)
            if take <= 0:
                break
            qty = take / price
            acquired += qty
            spent += qty * price
            remaining -= take
        avg_price = spent / acquired if acquired else best_price
        estimates[str(notional)] = ((avg_price / best_price) - 1) * 10000
    return estimates


def _imbalance(payload: dict[str, Any]) -> float:
    bids = sum(float(level[1]) for level in payload.get("bids", []))
    asks = sum(float(level[1]) for level in payload.get("asks", []))
    total = bids + asks
    return 0.0 if total == 0 else (bids - asks) / total


def run(config_path: str, symbols: list[str] | None = None) -> dict:
    config = load_yaml(config_path)
    selected_symbols = symbols or config.get("symbols", [])
    notionals = config["binance_orderbook"]["notionals_usdt"]
    results: dict[str, dict] = {}
    with BinanceFuturesClient() as client:
        for symbol in selected_symbols:
            payload = client.orderbook(symbol, limit=config["binance_orderbook"]["levels"])
            best_bid = float(payload["bids"][0][0]) if payload.get("bids") else 0.0
            best_ask = float(payload["asks"][0][0]) if payload.get("asks") else 0.0
            spread_bps = ((best_ask / best_bid) - 1) * 10000 if best_bid and best_ask else 0.0
            snapshot = {
                "symbol": symbol,
                "snapshot_time": to_iso(utc_now()),
                "spread_bps": spread_bps,
                "imbalance": _imbalance(payload),
                "slippage_bps_buy": _estimate_slippage(payload.get("asks", []), notionals),
                "slippage_bps_sell": _estimate_slippage(payload.get("bids", []), notionals),
                "bids": payload.get("bids", []),
                "asks": payload.get("asks", []),
            }
            frame = pl.DataFrame([snapshot])
            path = ensure_parent(DATA_ROOT / "raw" / "binance" / "orderbook" / f"{symbol}.parquet")
            frame.write_parquet(path)
            processed = ensure_parent(
                DATA_ROOT / "processed" / "orderbook_features" / f"{symbol}.parquet"
            )
            frame.write_parquet(processed)
            results[symbol] = {
                "spread_bps": spread_bps,
                "imbalance": snapshot["imbalance"],
                "slippage_bps_sell": snapshot["slippage_bps_sell"],
            }
    return results
