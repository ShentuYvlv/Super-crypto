from __future__ import annotations

import pandas as pd


def summarize_cycles(cycles: pd.DataFrame) -> dict:
    if cycles.empty:
        return {"cycle_count": 0, "avg_pump_return": 0.0, "avg_dump_return": 0.0}
    return {
        "cycle_count": int(len(cycles)),
        "avg_pump_return": float(cycles["pump_return"].mean()),
        "avg_dump_return": float(cycles["dump_return"].mean()),
        "median_duration_hours": float(cycles["duration_hours"].median()),
    }
