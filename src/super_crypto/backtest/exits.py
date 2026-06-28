from __future__ import annotations

from super_crypto.backtest.strategy_state import PositionState


def should_stop_out(state: PositionState, bar_high: float) -> bool:
    return bar_high >= state.entry_price * (1 + state.stop_loss_pct)


def should_trail_exit(state: PositionState, bar_close: float) -> bool:
    return bar_close >= state.lowest_price * (1 + state.trailing_stop_pct)

