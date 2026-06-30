from __future__ import annotations


def summarize_result(experiment: dict) -> dict:
    metrics = experiment["metrics"]
    return {
        "net_return": metrics["net_return"],
        "trade_count": metrics["trade_count"],
        "drawdown": metrics["max_drawdown"],
        "cost_pressure": metrics["fee_cost"] + metrics["slippage_cost"] + metrics["funding_cost"],
    }
