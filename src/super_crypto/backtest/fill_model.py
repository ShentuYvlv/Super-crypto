from __future__ import annotations


def short_entry_price(next_open: float, slippage_bps: float) -> float:
    return next_open * (1 - slippage_bps / 10000.0)


def short_exit_price(reference_price: float, slippage_bps: float) -> float:
    return reference_price * (1 + slippage_bps / 10000.0)

