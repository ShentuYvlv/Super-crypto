from __future__ import annotations

import pytest

from super_crypto.features.price_features import add_price_features
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


@pytest.mark.parametrize(
    "support_type",
    ["rolling_low", "rolling_close_low", "confirmed_pivot_low", "pump_since_low"],
)
def test_support_type_is_point_in_time(sample_ohlcv, support_type):
    features = add_price_features(
        sample_ohlcv,
        lookback_bars=6,
        support_window=3,
        peak_window=4,
        support_type=support_type,
    )
    assert "support_level" in features.columns
    for idx, support in features["support_level"].dropna().items():
        prior = features.iloc[:idx]
        assert not prior.empty
        assert prior["low"].min() <= support <= prior["high"].max()


def test_unsupported_support_type_fails(sample_ohlcv):
    with pytest.raises(ValueError):
        add_price_features(sample_ohlcv, support_type="future_low")
