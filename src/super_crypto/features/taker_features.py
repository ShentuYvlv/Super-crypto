from __future__ import annotations

import pandas as pd


def add_taker_features(frame: pd.DataFrame) -> pd.DataFrame:
    result = frame.copy()
    taker_ratio = result["taker_buy_quote_volume"].replace(0, pd.NA) / result[
        "quote_volume"
    ].replace(0, pd.NA)
    result["taker_buy_ratio"] = taker_ratio.fillna(0.5)
    result["sell_pressure"] = (result["taker_buy_ratio"] - 0.5).fillna(0.0)
    result["first_sell_pressure"] = (result["sell_pressure"] < 0) & (
        result["sell_pressure"].shift(1).fillna(0.0) >= 0
    )
    return result
