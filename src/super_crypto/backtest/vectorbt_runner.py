from __future__ import annotations

from itertools import product
from typing import Any

import numpy as np
import pandas as pd

from super_crypto.backtest.event_backtester import run_event_backtest
from super_crypto.backtest.metrics import summarize_metrics
from super_crypto.common.time import to_iso


def run_parameter_grid(
    *,
    ohlcv,
    signal_factory,
    signal_kwargs: dict,
    parameter_grid: dict[str, list],
    backtest_kwargs: dict,
) -> list[dict]:
    keys = list(parameter_grid.keys())
    combos = [dict(zip(keys, values, strict=True)) for values in product(*(parameter_grid[key] for key in keys))]
    results = []
    for combo in combos:
        signals = signal_factory(**signal_kwargs, config={**signal_kwargs["config"], **combo})
        trades = run_event_backtest(ohlcv, signals, **backtest_kwargs)
        metrics = summarize_metrics(pd.DataFrame([trade.model_dump(mode="json") for trade in trades]))
        results.append({"params": combo, "metrics": metrics.model_dump()})
    return results


def _metric_float(value: Any) -> float:
    try:
        if hasattr(value, "iloc"):
            value = value.iloc[-1]
        if pd.isna(value):
            return 0.0
        return float(value)
    except Exception:
        return 0.0


def _timestamp(value: Any) -> pd.Timestamp:
    return pd.Timestamp(value).tz_convert("UTC") if pd.Timestamp(value).tzinfo else pd.Timestamp(value).tz_localize("UTC")


def run_vectorbt_benchmark(
    *,
    ohlcv_by_symbol: dict[str, pd.DataFrame],
    signals: list[dict],
    split: str,
    backtest_config: dict,
    strategy_config: dict,
) -> dict:
    try:
        import vectorbt as vbt
    except Exception as exc:
        return {
            "status": "unavailable",
            "engine": "vectorbt",
            "reason": f"{type(exc).__name__}: {exc}",
            "split": split,
        }

    signals_by_symbol: dict[str, list[dict]] = {}
    for signal in signals:
        signals_by_symbol.setdefault(str(signal["symbol"]), []).append(signal)

    max_hold_bars = int(
        strategy_config.get(
            "max_hold_bars",
            backtest_config["max_hold_hours"].get(str(strategy_config["strategy"]).lower(), 8),
        )
    )
    fee_rate = float(backtest_config["fee_bps"]) / 10_000
    slippage_rate = float(backtest_config["slippage_bps_floor"]) / 10_000
    init_cash = float(backtest_config["capital_per_trade_usdt"])
    equity_curves = []
    per_symbol = []
    total_initial_cash = 0.0
    total_final_value = 0.0
    trade_count = 0

    for symbol, frame in sorted(ohlcv_by_symbol.items()):
        symbol_signals = signals_by_symbol.get(symbol, [])
        if not symbol_signals or frame.empty:
            continue
        sorted_frame = frame.sort_values("open_time").reset_index(drop=True).copy()
        sorted_frame["open_time"] = pd.to_datetime(sorted_frame["open_time"], utc=True)
        close = pd.Series(
            sorted_frame["close"].to_numpy(dtype=float),
            index=pd.DatetimeIndex(sorted_frame["open_time"]),
            name=symbol,
        )
        short_entries = pd.Series(False, index=close.index)
        short_exits = pd.Series(False, index=close.index)
        index_by_time = {time: idx for idx, time in enumerate(close.index)}
        for signal in symbol_signals:
            decision_time = _timestamp(signal["decision_time"])
            decision_idx = index_by_time.get(decision_time)
            if decision_idx is None or decision_idx + 1 >= len(close):
                continue
            entry_idx = decision_idx + 1
            exit_idx = min(entry_idx + max(max_hold_bars, 1) - 1, len(close) - 1)
            short_entries.iloc[entry_idx] = True
            short_exits.iloc[exit_idx] = True
        if not bool(short_entries.any()):
            continue
        portfolio = vbt.Portfolio.from_signals(
            close,
            short_entries=short_entries,
            short_exits=short_exits,
            init_cash=init_cash,
            fees=fee_rate,
            slippage=slippage_rate,
            freq="1h",
        )
        value = portfolio.value()
        final_value = _metric_float(value.iloc[-1] if hasattr(value, "iloc") else value)
        symbol_trade_count = int(portfolio.trades.count())
        equity_curves.append(value.rename(symbol))
        total_initial_cash += init_cash
        total_final_value += final_value
        trade_count += symbol_trade_count
        per_symbol.append(
            {
                "symbol": symbol,
                "net_return": _metric_float(portfolio.total_return()),
                "max_drawdown": _metric_float(portfolio.max_drawdown()),
                "trade_count": symbol_trade_count,
            }
        )

    if total_initial_cash == 0:
        return {
            "status": "available",
            "engine": "vectorbt",
            "version": getattr(vbt, "__version__", "unknown"),
            "split": split,
            "metrics": {"net_return": 0.0, "max_drawdown": 0.0, "sharpe": 0.0, "sortino": 0.0, "trade_count": 0},
            "per_symbol": [],
            "comment": "No vectorbt benchmark entries were generated.",
        }

    combined = pd.concat(equity_curves, axis=1).ffill().fillna(init_cash).sum(axis=1)
    returns = combined.pct_change().replace([np.inf, -np.inf], np.nan).dropna()
    downside = returns[returns < 0]
    sharpe = 0.0 if returns.empty or returns.std() == 0 else float(returns.mean() / returns.std() * np.sqrt(len(returns)))
    sortino = 0.0 if downside.empty or downside.std() == 0 else float(returns.mean() / downside.std() * np.sqrt(len(returns)))
    drawdown = combined / combined.cummax() - 1
    return {
        "status": "available",
        "engine": "vectorbt",
        "version": getattr(vbt, "__version__", "unknown"),
        "split": split,
        "generated_at": to_iso(pd.Timestamp.utcnow().to_pydatetime()),
        "benchmark_model": "short_entries_next_bar_with_max_hold_exit",
        "metrics": {
            "net_return": float(total_final_value / total_initial_cash - 1),
            "max_drawdown": _metric_float(drawdown.min()),
            "sharpe": sharpe,
            "sortino": sortino,
            "trade_count": trade_count,
        },
        "per_symbol": per_symbol,
        "comment": "Reference benchmark only; event-driven backtest remains the source of truth.",
    }
