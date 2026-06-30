from __future__ import annotations


def fixed_notional_size(capital_per_trade_usdt: float, price: float) -> float:
    return 0.0 if price <= 0 else capital_per_trade_usdt / price
