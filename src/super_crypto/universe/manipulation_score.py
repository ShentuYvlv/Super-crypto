from __future__ import annotations

from datetime import datetime

import pandas as pd
import polars as pl

from super_crypto.common.time import parse_timestamp
from super_crypto.common.types import ScoreRecord


def _bucket(score: float, thresholds: dict[str, float]) -> str:
    if score >= thresholds["ultra_high"]:
        return "ultra_high"
    if score >= thresholds["high"]:
        return "high"
    if score >= thresholds["medium"]:
        return "medium"
    return "low"


def score_symbols(
    cycles: pd.DataFrame,
    *,
    cutoff_time: datetime,
    config: dict,
    derivatives_by_symbol: dict[str, pd.DataFrame] | None = None,
) -> list[ScoreRecord]:
    derivatives_by_symbol = derivatives_by_symbol or {}
    cutoff = parse_timestamp(cutoff_time)
    if cycles.empty:
        return []
    results: list[ScoreRecord] = []
    lookback_days = config["lookback_days"]
    start_time = cutoff - pd.Timedelta(days=lookback_days)
    filtered = cycles[(cycles["pump_start"] >= start_time) & (cycles["pump_start"] <= cutoff)]
    for symbol, group in filtered.groupby("symbol"):
        cycle_count = int(len(group))
        avg_pump = float(group["pump_return"].mean())
        avg_dump = float(group["dump_return"].mean())
        deriv = derivatives_by_symbol.get(symbol)
        oi_momentum = 0.0
        funding_extremes = 0.0
        if deriv is not None and not deriv.empty:
            deriv = deriv.copy()
            time_column = "snapshot_time" if "snapshot_time" in deriv.columns else "open_time"
            if time_column in deriv.columns:
                deriv[time_column] = pd.to_datetime(deriv[time_column], utc=True)
                deriv = deriv[deriv[time_column] <= cutoff]
            if "oi_change_24h" in deriv.columns:
                oi_momentum = float(deriv["oi_change_24h"].iloc[-1]) if not deriv.empty else 0.0
            elif "open_interest" in deriv.columns and len(deriv) > 24:
                oi_momentum = float(deriv["open_interest"].pct_change(24).fillna(0.0).iloc[-1])
            if "funding_rate" in deriv.columns:
                funding_extremes = (
                    float(deriv["funding_rate"].abs().iloc[-1]) if not deriv.empty else 0.0
                )
        data_completeness = 1.0 if deriv is not None and not deriv.empty else 0.8
        score = (
            cycle_count * config["weights"]["cycle_frequency"] * 10
            + avg_pump * config["weights"]["avg_pump_return"] * 100
            + avg_dump * config["weights"]["avg_dump_return"] * 100
            + oi_momentum * config["weights"]["oi_momentum"] * 100
            + funding_extremes * config["weights"]["funding_extremes"] * 200
            + data_completeness * config["weights"]["data_completeness"] * 100
        )
        score = max(0.0, min(100.0, score))
        results.append(
            ScoreRecord(
                symbol=symbol,
                score=score,
                bucket=_bucket(score, config["buckets"]),
                cycle_count=cycle_count,
                avg_pump_return=avg_pump,
                avg_dump_return=avg_dump,
                point_in_time_cutoff=cutoff,
                data_completeness=data_completeness,
                components={
                    "cycle_frequency": cycle_count,
                    "avg_pump_return": avg_pump,
                    "avg_dump_return": avg_dump,
                    "oi_momentum": oi_momentum,
                    "funding_extremes": funding_extremes,
                },
            )
        )
    return sorted(results, key=lambda item: item.score, reverse=True)


def write_scores(path: str, scores: list[ScoreRecord]) -> str:
    frame = pl.DataFrame([score.model_dump(mode="json") for score in scores])
    output = __import__("pathlib").Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    frame.write_parquet(output)
    return str(output)
