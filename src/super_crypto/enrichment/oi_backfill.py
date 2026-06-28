from __future__ import annotations

import pandas as pd


def backfill_oi_changes(frame: pd.DataFrame) -> pd.DataFrame:
    if frame.empty:
        return frame
    result = frame.copy()
    result["oi_change_1h"] = result["open_interest"].pct_change().fillna(0.0)
    result["oi_change_6h"] = result["open_interest"].pct_change(6).fillna(0.0)
    result["oi_change_24h"] = result["open_interest"].pct_change(24).fillna(0.0)
    result["oi_acceleration"] = result["oi_change_1h"] - result["oi_change_6h"] / 6.0
    return result

