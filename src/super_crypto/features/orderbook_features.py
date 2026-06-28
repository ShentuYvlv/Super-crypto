from __future__ import annotations

import pandas as pd


def latest_orderbook_metrics(orderbook: pd.DataFrame | None) -> dict[str, float]:
    if orderbook is None or orderbook.empty:
        return {
            "spread_bps": 0.0,
            "imbalance": 0.0,
            "slippage_100": 0.0,
            "slippage_500": 0.0,
            "slippage_1000": 0.0,
            "max_size_under_50bps": 0.0,
        }
    latest = orderbook.sort_values("snapshot_time").iloc[-1]
    sell_side = latest.get("slippage_bps_sell", {})
    return {
        "spread_bps": float(latest.get("spread_bps", 0.0)),
        "imbalance": float(latest.get("imbalance", 0.0)),
        "slippage_100": float(sell_side.get("100", 0.0)),
        "slippage_500": float(sell_side.get("500", 0.0)),
        "slippage_1000": float(sell_side.get("1000", 0.0)),
        "max_size_under_50bps": 1000.0 if float(sell_side.get("1000", 99.0)) <= 50 else 500.0,
    }

