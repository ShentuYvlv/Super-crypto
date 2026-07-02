from __future__ import annotations

from hashlib import sha1
from typing import Any

import pandas as pd

from super_crypto.common.types import CycleRecord


def _timeframe_minutes(frame: pd.DataFrame, config: dict[str, Any]) -> float:
    configured = str(config.get("timeframe") or "").strip().lower()
    if configured.endswith("m") and configured[:-1].isdigit():
        return float(configured[:-1])
    if configured.endswith("h") and configured[:-1].isdigit():
        return float(configured[:-1]) * 60
    if configured.endswith("d") and configured[:-1].isdigit():
        return float(configured[:-1]) * 24 * 60
    if "timeframe" in frame.columns and not frame.empty:
        return _timeframe_minutes(pd.DataFrame(), {"timeframe": frame["timeframe"].iloc[0]})
    if len(frame) >= 2:
        ordered = frame.sort_values("open_time")
        delta = pd.Timestamp(ordered.iloc[1]["open_time"]) - pd.Timestamp(
            ordered.iloc[0]["open_time"]
        )
        minutes = delta.total_seconds() / 60
        if minutes > 0:
            return minutes
    return 60.0


def _hours_to_bars(hours: float, timeframe_minutes: float) -> int:
    if float(hours) <= 0:
        return 0
    return max(1, int(round((float(hours) * 60) / timeframe_minutes)))


def _rule_id(config: dict[str, Any]) -> str:
    if config.get("rule_id"):
        return str(config["rule_id"])
    return (
        f"rule_p{float(config['pump_threshold_min']):g}"
        f"_d{float(config.get('dump_return_min', 0.0)):g}"
        f"_r{float(config['dump_retrace_ratio']):g}"
        f"_h{int(float(config['max_cycle_hours']))}"
    )


def _cycle_quality(
    *,
    pump_return: float,
    dump_return: float,
    duration_hours: float,
    config: dict[str, Any],
) -> float:
    min_pump = max(float(config["pump_threshold_min"]), 0.000001)
    dump_min = max(float(config.get("dump_return_min", 0.0)), 0.000001)
    max_hours = max(float(config["max_cycle_hours"]), 1.0)
    pump_score = min(pump_return / min_pump, 2.0) / 2.0
    dump_score = min(dump_return / dump_min, 2.0) / 2.0 if dump_min > 0 else 0.5
    duration_score = max(0.0, 1.0 - (duration_hours / max_hours))
    return round(0.45 * pump_score + 0.35 * dump_score + 0.20 * duration_score, 6)


def _overlap_ratio(left: CycleRecord, right: CycleRecord) -> float:
    left_start = pd.Timestamp(left.pump_start)
    left_end = pd.Timestamp(left.dump_end)
    right_start = pd.Timestamp(right.pump_start)
    right_end = pd.Timestamp(right.dump_end)
    latest_start = max(left_start, right_start)
    earliest_end = min(left_end, right_end)
    overlap = max(0.0, (earliest_end - latest_start).total_seconds())
    left_duration = max(1.0, (left_end - left_start).total_seconds())
    right_duration = max(1.0, (right_end - right_start).total_seconds())
    return overlap / min(left_duration, right_duration)


def _dedupe_cycles(cycles: list[CycleRecord], config: dict[str, Any]) -> list[CycleRecord]:
    if not cycles:
        return []
    overlap_threshold = float(config.get("overlap_dedupe_threshold", 0.5))
    dedupe_gap = pd.Timedelta(hours=float(config.get("dedupe_gap_hours", 0.0)))
    deduped: list[CycleRecord] = []
    for cycle in sorted(
        cycles,
        key=lambda item: (
            pd.Timestamp(item.peak_time),
            -item.quality_score,
            -item.pump_return,
        ),
    ):
        duplicate_index = None
        for index, existing in enumerate(deduped):
            peak_gap = abs(pd.Timestamp(cycle.peak_time) - pd.Timestamp(existing.peak_time))
            if _overlap_ratio(cycle, existing) >= overlap_threshold or (
                dedupe_gap > pd.Timedelta(0) and peak_gap <= dedupe_gap
            ):
                duplicate_index = index
                break
        if duplicate_index is None:
            deduped.append(cycle)
            continue
        existing = deduped[duplicate_index]
        if (cycle.quality_score, cycle.pump_return) > (
            existing.quality_score,
            existing.pump_return,
        ):
            deduped[duplicate_index] = cycle
    return sorted(deduped, key=lambda item: pd.Timestamp(item.pump_start))


def detect_cycles(frame: pd.DataFrame, symbol: str, config: dict) -> list[CycleRecord]:
    ordered = frame.sort_values("open_time").reset_index(drop=True)
    if ordered.empty:
        return []
    timeframe_minutes = _timeframe_minutes(ordered, config)
    timeframe = str(config.get("timeframe") or f"{timeframe_minutes:g}m")
    max_bars = _hours_to_bars(float(config["max_cycle_hours"]), timeframe_minutes)
    min_pump = float(config["pump_threshold_min"])
    max_pump = float(config["pump_threshold_max"])
    dump_ratio = float(config["dump_retrace_ratio"])
    dump_min = float(config.get("dump_return_min", 0.0))
    min_peak_distance_bars = _hours_to_bars(
        float(config.get("min_peak_distance_from_start_hours", 0.0)),
        timeframe_minutes,
    )
    min_pump_duration_hours = float(config.get("min_pump_duration_hours", 0.0))
    max_pump_duration_hours = float(
        config.get("max_pump_duration_hours", config["max_cycle_hours"])
    )
    cycles: list[CycleRecord] = []
    rule_id = _rule_id(config)
    for start_idx in range(len(ordered) - 3):
        start_row = ordered.iloc[start_idx]
        window = ordered.iloc[start_idx : start_idx + max_bars + 1]
        if window.empty:
            continue
        peak_idx = window["high"].idxmax()
        if peak_idx - start_idx < min_peak_distance_bars:
            continue
        peak_row = ordered.loc[peak_idx]
        pump_return = peak_row["high"] / start_row["low"] - 1
        if not (min_pump <= pump_return <= max_pump):
            continue
        pump_duration_hours = (
            (peak_row["open_time"] - start_row["open_time"]).total_seconds() / 3600
        )
        if pump_duration_hours < min_pump_duration_hours:
            continue
        if pump_duration_hours > max_pump_duration_hours:
            continue
        post_peak = ordered.iloc[peak_idx : start_idx + max_bars + 1]
        if post_peak.empty:
            continue
        trough_idx = post_peak["low"].idxmin()
        trough_row = ordered.loc[trough_idx]
        dump_return = 1 - trough_row["low"] / peak_row["high"]
        if dump_return < max(dump_min, dump_ratio * pump_return):
            continue
        duration_hours = (trough_row["open_time"] - start_row["open_time"]).total_seconds() / 3600
        dump_duration_hours = (
            (trough_row["open_time"] - peak_row["open_time"]).total_seconds() / 3600
        )
        quality_score = _cycle_quality(
            pump_return=float(pump_return),
            dump_return=float(dump_return),
            duration_hours=float(duration_hours),
            config=config,
        )
        cycle_id = sha1(
            (
                f"{symbol}|{rule_id}|{start_row['open_time']}|"
                f"{peak_row['open_time']}|{trough_row['open_time']}"
            ).encode()
        ).hexdigest()[:12]
        cycles.append(
            CycleRecord(
                cycle_id=cycle_id,
                symbol=symbol,
                timeframe=timeframe,
                pump_start=start_row["open_time"].to_pydatetime(),
                peak_time=peak_row["open_time"].to_pydatetime(),
                dump_end=trough_row["open_time"].to_pydatetime(),
                pump_return=float(pump_return),
                dump_return=float(dump_return),
                pump_duration_hours=float(pump_duration_hours),
                dump_duration_hours=float(dump_duration_hours),
                duration_hours=float(duration_hours),
                rule_id=rule_id,
                quality_score=quality_score,
                detection_rule=(
                    f"pump>={min_pump:g}, dump>={max(dump_min, dump_ratio * pump_return):g}, "
                    f"cycle<={float(config['max_cycle_hours']):g}h"
                ),
                score_context={
                    "timeframe_minutes": timeframe_minutes,
                    "max_cycle_bars": max_bars,
                    "pump_threshold_min": min_pump,
                    "pump_threshold_max": max_pump,
                    "dump_return_min": dump_min,
                    "dump_retrace_ratio": dump_ratio,
                    "min_peak_distance_from_start_hours": float(
                        config.get("min_peak_distance_from_start_hours", 0.0)
                    ),
                },
            )
        )
    return _dedupe_cycles(cycles, config)
