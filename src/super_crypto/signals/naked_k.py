from __future__ import annotations

import pandas as pd


def pump_context(frame: pd.DataFrame, threshold_low: float = 0.2, threshold_high: float = 0.5) -> pd.Series:
    return (frame["pump_return_lookback"] >= threshold_low) & (
        frame["pump_return_lookback"] <= threshold_high
    )

