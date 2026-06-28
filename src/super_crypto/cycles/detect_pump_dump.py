from __future__ import annotations

from hashlib import sha1

import pandas as pd

from super_crypto.common.types import CycleRecord


def detect_cycles(frame: pd.DataFrame, symbol: str, config: dict) -> list[CycleRecord]:
    ordered = frame.sort_values("open_time").reset_index(drop=True)
    if ordered.empty:
        return []
    max_bars = int(config["max_cycle_hours"])
    min_pump = float(config["pump_threshold_min"])
    max_pump = float(config["pump_threshold_max"])
    dump_ratio = float(config["dump_retrace_ratio"])
    dedupe_gap = pd.Timedelta(hours=config.get("dedupe_gap_hours", 6))
    last_peak_time = None
    cycles: list[CycleRecord] = []
    for start_idx in range(len(ordered) - 3):
        start_row = ordered.iloc[start_idx]
        window = ordered.iloc[start_idx : start_idx + max_bars + 1]
        if window.empty:
            continue
        peak_idx = window["high"].idxmax()
        peak_row = ordered.loc[peak_idx]
        pump_return = peak_row["high"] / start_row["low"] - 1
        if not (min_pump <= pump_return <= max_pump):
            continue
        post_peak = ordered.iloc[peak_idx : start_idx + max_bars + 1]
        if post_peak.empty:
            continue
        trough_idx = post_peak["low"].idxmin()
        trough_row = ordered.loc[trough_idx]
        dump_return = 1 - trough_row["low"] / peak_row["high"]
        if dump_return < dump_ratio * pump_return:
            continue
        if last_peak_time is not None and peak_row["open_time"] - last_peak_time < dedupe_gap:
            continue
        last_peak_time = peak_row["open_time"]
        cycle_id = sha1(
            f"{symbol}|{start_row['open_time']}|{peak_row['open_time']}|{trough_row['open_time']}".encode(
                "utf-8"
            )
        ).hexdigest()[:12]
        cycles.append(
            CycleRecord(
                cycle_id=cycle_id,
                symbol=symbol,
                pump_start=start_row["open_time"].to_pydatetime(),
                peak_time=peak_row["open_time"].to_pydatetime(),
                dump_end=trough_row["open_time"].to_pydatetime(),
                pump_return=float(pump_return),
                dump_return=float(dump_return),
                duration_hours=float(
                    (trough_row["open_time"] - start_row["open_time"]).total_seconds() / 3600
                ),
            )
        )
    return cycles

