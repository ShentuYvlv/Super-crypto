from __future__ import annotations

import pandas as pd


def remove_top_trades(trades: pd.DataFrame, count: int = 5) -> pd.DataFrame:
    if trades.empty:
        return trades.copy()
    return trades.sort_values("net_return", ascending=False).iloc[count:].copy()


def by_symbol(trades: pd.DataFrame) -> pd.DataFrame:
    if trades.empty:
        return pd.DataFrame()
    return (
        trades.groupby("symbol")
        .agg(net_return=("net_return", "sum"), trade_count=("trade_id", "count"))
        .reset_index()
        .sort_values("net_return", ascending=False)
    )


def by_month(trades: pd.DataFrame) -> pd.DataFrame:
    if trades.empty:
        return pd.DataFrame()
    result = trades.copy()
    result["month"] = pd.to_datetime(result["exit_time"], utc=True).dt.strftime("%Y-%m")
    return (
        result.groupby("month")
        .agg(net_return=("net_return", "sum"), trade_count=("trade_id", "count"))
        .reset_index()
        .sort_values("month")
    )
