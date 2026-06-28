from __future__ import annotations

import pandas as pd


def add_price_features(
    frame: pd.DataFrame,
    *,
    lookback_bars: int = 24,
    support_window: int = 6,
    peak_window: int = 12,
) -> pd.DataFrame:
    result = frame.copy()
    result["bar_return"] = result["close"].pct_change().fillna(0.0)
    result["pump_return_lookback"] = (
        result["high"].rolling(lookback_bars, min_periods=2).max()
        / result["low"].rolling(lookback_bars, min_periods=2).min()
        - 1
    ).fillna(0.0)
    result["rolling_peak"] = (
        result["high"].rolling(peak_window, min_periods=2).max().shift(1)
    )
    result["support_level"] = (
        result["low"].rolling(support_window, min_periods=2).min().shift(1)
    )
    result["drawdown_from_peak"] = (result["close"] / result["rolling_peak"] - 1).fillna(0.0)
    result["lower_high"] = result["high"] < result["high"].shift(1).rolling(2).max()
    return result

