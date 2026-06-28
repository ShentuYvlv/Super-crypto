from __future__ import annotations

from super_crypto.signals.v4a_early_short import generate
from super_crypto.validation.leakage_checks import assert_next_bar_entry


def test_v4a_generates_next_bar_signals(sample_ohlcv):
    signals = generate(
        sample_ohlcv,
        "MMTUSDT",
        {
            "lookback_bars": 6,
            "support_window": 3,
            "peak_window": 4,
            "first_sell_pressure_threshold": -0.05,
            "support_break_threshold": 0.01,
            "trailing_stop_pct": 0.02,
            "stop_loss_pct": 0.015,
        },
        manipulation_bucket="high",
        orderbook_slippage_bps=25,
    )
    assert signals
    assert_next_bar_entry(signals)
    assert all(signal.strategy == "V4A" for signal in signals)

