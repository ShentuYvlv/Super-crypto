from __future__ import annotations

import math

import numpy as np
import pandas as pd

from super_crypto.common.types import ExperimentMetrics


def equity_curve(trades: pd.DataFrame) -> pd.DataFrame:
    if trades.empty:
        return pd.DataFrame(columns=["exit_time", "equity", "drawdown"])
    ordered = trades.sort_values("exit_time").copy()
    ordered["equity"] = (1 + ordered["net_return"]).cumprod()
    ordered["peak_equity"] = ordered["equity"].cummax()
    ordered["drawdown"] = ordered["equity"] / ordered["peak_equity"] - 1
    return ordered[["exit_time", "equity", "drawdown"]]


def summarize_metrics(trades: pd.DataFrame) -> ExperimentMetrics:
    if trades.empty:
        return ExperimentMetrics(
            net_return=0.0,
            sharpe=0.0,
            sortino=0.0,
            max_drawdown=0.0,
            profit_factor=0.0,
            win_rate=0.0,
            avg_win=0.0,
            avg_loss=0.0,
            trade_count=0,
            median_holding_minutes=0.0,
            fee_cost=0.0,
            slippage_cost=0.0,
            funding_cost=0.0,
            top5_removed_net_return=0.0,
        )
    returns = trades["net_return"].to_numpy(dtype=float)
    downside = returns[returns < 0]
    sharpe = 0.0 if returns.std() == 0 else returns.mean() / returns.std() * math.sqrt(len(returns))
    downside_std = downside.std() if downside.size else 0.0
    sortino = 0.0 if downside_std == 0 else returns.mean() / downside_std * math.sqrt(len(returns))
    curve = equity_curve(trades)
    gross_profit = trades.loc[trades["net_return"] > 0, "net_return"].sum()
    gross_loss = abs(trades.loc[trades["net_return"] < 0, "net_return"].sum())
    top5_removed = trades["net_return"].sort_values(ascending=False).iloc[5:]
    return ExperimentMetrics(
        net_return=float((1 + trades["net_return"]).prod() - 1),
        sharpe=float(sharpe),
        sortino=float(sortino),
        max_drawdown=float(curve["drawdown"].min() if not curve.empty else 0.0),
        profit_factor=float(gross_profit / gross_loss) if gross_loss else float(gross_profit),
        win_rate=float((trades["net_return"] > 0).mean()),
        avg_win=float(trades.loc[trades["net_return"] > 0, "net_return"].mean() or 0.0),
        avg_loss=float(trades.loc[trades["net_return"] < 0, "net_return"].mean() or 0.0),
        trade_count=int(len(trades)),
        median_holding_minutes=float(trades["holding_minutes"].median()),
        fee_cost=float(trades["fee_cost"].sum()),
        slippage_cost=float(trades["slippage_cost"].sum()),
        funding_cost=float(trades["funding_cost"].sum()),
        top5_removed_net_return=float((1 + top5_removed).prod() - 1) if not top5_removed.empty else 0.0,
    )

