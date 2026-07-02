from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pandas as pd

from super_crypto.cycles.detect_pump_dump import detect_cycles


def test_detect_cycles_finds_pump_dump(sample_ohlcv):
    cycles = detect_cycles(
        sample_ohlcv,
        "MMTUSDT",
        {
            "pump_threshold_min": 0.2,
            "pump_threshold_max": 0.6,
            "dump_retrace_ratio": 0.5,
            "max_cycle_hours": 12,
            "dedupe_gap_hours": 1,
        },
    )
    assert cycles
    assert cycles[0].pump_return >= 0.2
    assert cycles[0].dump_return > 0


def test_detect_cycles_converts_hours_to_bars_for_15m_timeframe():
    start = datetime(2026, 1, 1, tzinfo=UTC)
    rows = []
    for index in range(33):
        if index < 20:
            close = 1.0 + index * 0.01
        elif index == 20:
            close = 1.45
        elif index < 30:
            close = 1.45 - (index - 20) * 0.04
        else:
            close = 1.05
        rows.append(
            {
                "open_time": start + timedelta(minutes=15 * index),
                "open": close * 0.99,
                "high": close * 1.02,
                "low": close * 0.98,
                "close": close,
                "volume": 1000.0,
            }
        )
    frame = pd.DataFrame(rows)

    cycles = detect_cycles(
        frame,
        "MMTUSDT",
        {
            "timeframe": "15m",
            "pump_threshold_min": 0.2,
            "pump_threshold_max": 0.8,
            "dump_return_min": 0.1,
            "dump_retrace_ratio": 0.35,
            "max_cycle_hours": 4,
            "dedupe_gap_hours": 1,
        },
    )
    enough_hours = detect_cycles(
        frame,
        "MMTUSDT",
        {
            "timeframe": "15m",
            "pump_threshold_min": 0.2,
            "pump_threshold_max": 0.8,
            "dump_return_min": 0.1,
            "dump_retrace_ratio": 0.35,
            "max_cycle_hours": 8,
            "dedupe_gap_hours": 1,
        },
    )

    assert cycles
    assert cycles[0].score_context["max_cycle_bars"] == 16
    assert enough_hours
    assert enough_hours[0].score_context["max_cycle_bars"] == 32
    assert enough_hours[0].duration_hours > 4
    assert enough_hours[0].timeframe == "15m"
    assert enough_hours[0].rule_id
