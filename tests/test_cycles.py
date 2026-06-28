from __future__ import annotations

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

