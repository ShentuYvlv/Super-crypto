from __future__ import annotations

from dataclasses import asdict

import pandas as pd

from super_crypto.backtest.bar_engine import iter_bars
from super_crypto.backtest.execution_costs import (
    estimate_fee_cost,
    estimate_funding_cost,
    estimate_slippage_cost,
)
from super_crypto.backtest.exits import should_stop_out, should_trail_exit
from super_crypto.backtest.fill_model import short_entry_price, short_exit_price
from super_crypto.backtest.position_sizing import fixed_notional_size
from super_crypto.backtest.strategy_state import PositionState
from super_crypto.common.types import SignalRecord, TradeRecord


def run_event_backtest(
    ohlcv: pd.DataFrame,
    signals: list[SignalRecord],
    *,
    split: str,
    capital_per_trade_usdt: float,
    fee_bps: float,
    default_slippage_bps: float,
    max_hold_bars: int,
) -> list[TradeRecord]:
    frame = ohlcv.sort_values("open_time").reset_index(drop=True).copy()
    frame["open_time"] = pd.to_datetime(frame["open_time"], utc=True)
    signal_by_time = {pd.Timestamp(signal.decision_time): signal for signal in signals}
    trades: list[TradeRecord] = []
    occupied_until: dict[str, pd.Timestamp] = {}
    for idx, row in frame.iloc[:-1].iterrows():
        decision_time = pd.Timestamp(row["open_time"])
        signal = signal_by_time.get(decision_time)
        if signal is None:
            continue
        if occupied_until.get(signal.symbol, pd.Timestamp("1970-01-01", tz="UTC")) > decision_time:
            continue
        entry_row = frame.iloc[idx + 1]
        slippage_bps = max(default_slippage_bps, signal.orderbook_slippage_bps or 0.0)
        entry_price = short_entry_price(float(entry_row["open"]), slippage_bps)
        state = PositionState(
            signal_id=signal.signal_id,
            symbol=signal.symbol,
            strategy=signal.strategy,
            entry_time=entry_row["open_time"].to_pydatetime(),
            entry_price=entry_price,
            stop_loss_pct=signal.stop_loss,
            trailing_stop_pct=signal.trailing_stop,
            lowest_price=float(entry_row["low"]),
            highest_adverse_price=float(entry_row["high"]),
        )
        exit_price = float(entry_row["close"])
        exit_time = entry_row["close_time"].to_pydatetime()
        exit_reason = "max_hold"
        last_idx = idx + 1
        for bar_idx, bar in iter_bars(frame, idx + 1):
            last_idx = bar_idx
            state.lowest_price = min(state.lowest_price, float(bar["low"]))
            state.highest_adverse_price = max(state.highest_adverse_price, float(bar["high"]))
            if should_stop_out(state, float(bar["high"])):
                exit_price = short_exit_price(state.entry_price * (1 + state.stop_loss_pct), slippage_bps)
                exit_time = bar["close_time"].to_pydatetime()
                exit_reason = "stop_loss"
                break
            if should_trail_exit(state, float(bar["close"])):
                exit_price = short_exit_price(float(bar["close"]), slippage_bps)
                exit_time = bar["close_time"].to_pydatetime()
                exit_reason = "trailing_stop"
                break
            if bar_idx - (idx + 1) + 1 >= max_hold_bars:
                exit_price = short_exit_price(float(bar["close"]), slippage_bps)
                exit_time = bar["close_time"].to_pydatetime()
                exit_reason = "max_hold"
                break
        occupied_until[signal.symbol] = pd.Timestamp(exit_time)
        holding_minutes = (exit_time - state.entry_time).total_seconds() / 60
        gross_return = (entry_price - exit_price) / entry_price
        fee_cost = estimate_fee_cost(fee_bps)
        slip_cost = estimate_slippage_cost(slippage_bps)
        funding_rate = float(row.get("funding_rate", 0.0))
        funding_cost = estimate_funding_cost(funding_rate, holding_minutes / 60)
        mae = -(state.highest_adverse_price / entry_price - 1)
        mfe = entry_price / state.lowest_price - 1 if state.lowest_price else 0.0
        trades.append(
            TradeRecord(
                trade_id=f"{signal.signal_id}-{last_idx}",
                signal_id=signal.signal_id,
                symbol=signal.symbol,
                strategy=signal.strategy,
                split=split,  # type: ignore[arg-type]
                source="backtest",
                side="SHORT",
                entry_time=state.entry_time,
                entry_price=entry_price,
                exit_time=exit_time,
                exit_price=exit_price,
                gross_return=gross_return,
                fee_cost=fee_cost,
                slippage_cost=slip_cost,
                funding_cost=funding_cost,
                net_return=gross_return - fee_cost - slip_cost - funding_cost,
                exit_reason=exit_reason,
                holding_minutes=holding_minutes,
                mae=mae,
                mfe=mfe,
                orderbook_snapshot_status="healthy" if signal.orderbook_slippage_bps else "partial",
            )
        )
    return trades
