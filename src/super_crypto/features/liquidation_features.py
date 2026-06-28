from __future__ import annotations

import pandas as pd


def add_liquidation_analysis_fields(
    frame: pd.DataFrame,
    liquidation: pd.DataFrame | None = None,
) -> pd.DataFrame:
    result = frame.copy()
    if liquidation is None or liquidation.empty:
        result["liq_long_usd"] = 0.0
        result["liq_short_usd"] = 0.0
        result["liq_imbalance"] = 0.0
        result["liquidation_data_quality"] = "missing"
        return result

    liq = liquidation.copy()
    time_column = "open_time" if "open_time" in liq.columns else "snapshot_time"
    liq[time_column] = pd.to_datetime(liq[time_column], utc=True)
    liq = liq.rename(
        columns={
            time_column: "open_time",
            "long_liquidation_usd": "liq_long_usd",
            "short_liquidation_usd": "liq_short_usd",
        }
    )
    for column in ("liq_long_usd", "liq_short_usd"):
        if column not in liq.columns:
            liq[column] = 0.0
    result["open_time"] = pd.to_datetime(result["open_time"], utc=True)
    result = pd.merge_asof(
        result.sort_values("open_time"),
        liq[["open_time", "liq_long_usd", "liq_short_usd"]].sort_values("open_time"),
        on="open_time",
        direction="backward",
    )
    total = result["liq_long_usd"] + result["liq_short_usd"]
    result["liq_imbalance"] = ((result["liq_short_usd"] - result["liq_long_usd"]) / total.replace(0, pd.NA)).fillna(0.0)
    result["liquidation_data_quality"] = "healthy"
    return result
