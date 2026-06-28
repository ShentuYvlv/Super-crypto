from __future__ import annotations


def estimate_fee_cost(fee_bps: float) -> float:
    return (fee_bps / 10000.0) * 2


def estimate_slippage_cost(slippage_bps: float) -> float:
    return slippage_bps / 10000.0


def estimate_funding_cost(funding_rate: float, holding_hours: float) -> float:
    return funding_rate * max(holding_hours, 0.0) / 8.0

