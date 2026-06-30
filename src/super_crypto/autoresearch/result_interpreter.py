from __future__ import annotations

from pathlib import Path
from typing import Any

import pandas as pd


def summarize_result(experiment: dict) -> dict:
    metrics = experiment["metrics"]
    return {
        "net_return": metrics["net_return"],
        "trade_count": metrics["trade_count"],
        "drawdown": metrics["max_drawdown"],
        "cost_pressure": metrics["fee_cost"] + metrics["slippage_cost"] + metrics["funding_cost"],
    }


def summarize_trades(validation_result: dict[str, Any] | None = None) -> dict[str, Any]:
    trades = (validation_result or {}).get("trades")
    if isinstance(trades, list):
        frame = pd.DataFrame(trades)
    elif isinstance(trades, str) and Path(trades).exists():
        frame = pd.read_csv(trades)
    else:
        frame = pd.DataFrame()
    if frame.empty:
        return {"trade_count": 0, "symbols": [], "exit_reasons": {}, "net_return_by_symbol": {}}
    symbol_column = "symbol" if "symbol" in frame else None
    exit_reasons = (
        {str(key): int(value) for key, value in frame["exit_reason"].value_counts().head(5).to_dict().items()}
        if "exit_reason" in frame
        else {}
    )
    net_return_by_symbol = (
        {
            str(key): float(value)
            for key, value in frame.groupby("symbol")["net_return"]
            .sum()
            .sort_values(ascending=False)
            .head(10)
            .to_dict()
            .items()
        }
        if {"symbol", "net_return"}.issubset(frame.columns)
        else {}
    )
    return {
        "trade_count": int(len(frame)),
        "symbols": sorted(frame[symbol_column].dropna().unique().tolist()) if symbol_column else [],
        "exit_reasons": exit_reasons,
        "net_return_by_symbol": net_return_by_symbol,
    }


def review_result(
    experiment: dict,
    acceptance: dict,
    baseline: dict | None = None,
    validation_result: dict[str, Any] | None = None,
) -> dict:
    metrics = experiment["metrics"]
    baseline_metrics = baseline.get("metrics", {}) if baseline else {}
    trade_summary = summarize_trades(validation_result)
    recommendation = "Keep current config for more validation data."
    if acceptance["reason"] == "trade_count_below_threshold":
        recommendation = "Increase signal coverage before judging profitability."
    elif acceptance["reason"] == "non_positive_net_return":
        recommendation = "Reduce hold time or tighten exits before expanding the universe."
    elif acceptance["reason"] == "no_validation_improvement":
        recommendation = "Reject this branch and try a different trigger family."
    return {
        "summary": summarize_result(experiment),
        "trade_summary": trade_summary,
        "baseline_net_return": baseline_metrics.get("net_return"),
        "decision": acceptance["reason"],
        "recommendation": recommendation,
        "evidence": [
            f"trade_count={metrics['trade_count']}",
            f"net_return={metrics['net_return']:.4f}",
            f"max_drawdown={metrics['max_drawdown']:.4f}",
        ],
    }
