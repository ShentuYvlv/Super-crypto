from __future__ import annotations

import pandas as pd


def add_onchain_analysis_fields(
    frame: pd.DataFrame,
    transfers: pd.DataFrame | None = None,
) -> pd.DataFrame:
    result = frame.copy()
    if transfers is None or transfers.empty:
        result["cex_inflow_usd"] = 0.0
        result["cex_outflow_usd"] = 0.0
        result["whale_transfer_count"] = 0.0
        result["onchain_data_quality"] = "missing"
        return result

    events = transfers.copy()
    time_column = "transfer_time" if "transfer_time" in events.columns else "timeStamp"
    events[time_column] = pd.to_datetime(events[time_column], utc=True, errors="coerce")
    events = events.dropna(subset=[time_column])
    if "amount_usd" not in events.columns:
        value = pd.to_numeric(events.get("value", 0.0), errors="coerce").fillna(0.0)
        events["amount_usd"] = value
    if "direction" not in events.columns:
        events["direction"] = "unknown"
    if "is_whale" not in events.columns:
        events["is_whale"] = pd.to_numeric(events["amount_usd"], errors="coerce").fillna(0.0) > 100_000
    events["open_time"] = events[time_column].dt.floor("h")
    grouped = (
        events.assign(
            cex_inflow_usd=lambda data: data["amount_usd"].where(data["direction"] == "inflow", 0.0),
            cex_outflow_usd=lambda data: data["amount_usd"].where(data["direction"] == "outflow", 0.0),
            whale_transfer_count=lambda data: data["is_whale"].astype(float),
        )
        .groupby("open_time", as_index=False)
        .agg(
            cex_inflow_usd=("cex_inflow_usd", "sum"),
            cex_outflow_usd=("cex_outflow_usd", "sum"),
            whale_transfer_count=("whale_transfer_count", "sum"),
        )
    )
    result["open_time"] = pd.to_datetime(result["open_time"], utc=True)
    result = result.merge(grouped, on="open_time", how="left")
    for column in ("cex_inflow_usd", "cex_outflow_usd", "whale_transfer_count"):
        result[column] = result[column].fillna(0.0)
    result["onchain_data_quality"] = "healthy"
    return result
