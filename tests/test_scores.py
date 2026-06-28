from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pandas as pd

from super_crypto.universe.manipulation_score import score_symbols


def test_manipulation_score_point_in_time():
    cutoff = datetime(2026, 2, 1, tzinfo=UTC)
    cycles = pd.DataFrame(
        [
            {
                "symbol": "MMTUSDT",
                "pump_start": cutoff - timedelta(days=3),
                "pump_return": 0.31,
                "dump_return": 0.22,
            },
            {
                "symbol": "MMTUSDT",
                "pump_start": cutoff + timedelta(days=1),
                "pump_return": 0.45,
                "dump_return": 0.31,
            },
        ]
    )
    scores = score_symbols(
        cycles,
        cutoff_time=cutoff,
        config={
            "lookback_days": 30,
            "weights": {
                "cycle_frequency": 0.5,
                "avg_pump_return": 0.15,
                "avg_dump_return": 0.15,
                "oi_momentum": 0.1,
                "funding_extremes": 0.05,
                "data_completeness": 0.05,
            },
            "buckets": {"ultra_high": 85, "high": 70, "medium": 55, "low": 0},
        },
    )
    assert len(scores) == 1
    assert scores[0].cycle_count == 1
    assert scores[0].point_in_time_cutoff == cutoff

