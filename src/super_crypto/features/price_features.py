from __future__ import annotations

import pandas as pd


def add_price_features(
    frame: pd.DataFrame,
    *,
    lookback_bars: int = 24,
    support_window: int = 6,
    peak_window: int = 12,
    support_type: str = "rolling_low",
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
    result["support_level"] = _support_level(result, support_window, support_type)
    result["drawdown_from_peak"] = (result["close"] / result["rolling_peak"] - 1).fillna(0.0)
    result["lower_high"] = result["high"] < result["high"].shift(1).rolling(2).max()
    return result


def _support_level(frame: pd.DataFrame, window: int, support_type: str) -> pd.Series:
    if support_type == "rolling_low":
        return frame["low"].rolling(window, min_periods=2).min().shift(1)
    if support_type == "rolling_close_low":
        return frame["close"].rolling(window, min_periods=2).min().shift(1)
    if support_type == "confirmed_pivot_low":
        pivot = (
            (frame["low"] < frame["low"].shift(1))
            & (frame["low"] < frame["low"].shift(2))
            & (frame["low"] < frame["low"].shift(-1))
            & (frame["low"] < frame["low"].shift(-2))
        )
        # A two-right-bar pivot is only knowable two bars after the pivot bar.
        confirmed = frame["low"].where(pivot).shift(2)
        return confirmed.ffill()
    if support_type == "pump_since_low":
        pump_start = frame["pump_return_lookback"] >= frame["pump_return_lookback"].rolling(
            window, min_periods=2
        ).max().shift(1)
        segment = pump_start.cumsum()
        return frame["low"].groupby(segment).cummin().shift(1)
    raise ValueError(f"Unsupported support_type: {support_type}")
