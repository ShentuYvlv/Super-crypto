from __future__ import annotations

import pandas as pd


def merge_derivatives(
    ohlcv: pd.DataFrame,
    funding: pd.DataFrame | None = None,
    open_interest: pd.DataFrame | None = None,
) -> pd.DataFrame:
    result = ohlcv.copy()
    if funding is not None and not funding.empty:
        funding_frame = funding.sort_values("funding_time").rename(
            columns={"funding_time": "open_time"}
        )
        result = pd.merge_asof(
            result.sort_values("open_time"),
            funding_frame[["open_time", "funding_rate"]],
            on="open_time",
            direction="backward",
        )
    else:
        result["funding_rate"] = 0.0
    if open_interest is not None and not open_interest.empty:
        oi_frame = open_interest.sort_values("snapshot_time").rename(
            columns={"snapshot_time": "open_time", "open_interest": "oi_level"}
        )
        result = pd.merge_asof(
            result.sort_values("open_time"),
            oi_frame[["open_time", "oi_level", "oi_value_usd"]],
            on="open_time",
            direction="backward",
        )
        for window in (1, 6, 24):
            result[f"oi_change_{window}h"] = (
                result["oi_level"].pct_change(window, fill_method=None).fillna(0.0)
            )
        result["oi_acceleration"] = (result["oi_change_1h"] - result["oi_change_6h"] / 6.0).fillna(
            0.0
        )
    else:
        for column in [
            "oi_level",
            "oi_value_usd",
            "oi_change_1h",
            "oi_change_6h",
            "oi_change_24h",
            "oi_acceleration",
        ]:
            result[column] = 0.0
    return result
