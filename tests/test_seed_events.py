from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pandas as pd
import yaml

from super_crypto.cycles.seed_events import build_event_set


def test_build_event_set_matches_manual_seed_and_expands_cycles(tmp_path):
    cycles_dir = tmp_path / "cycles"
    cycles_dir.mkdir()
    start = datetime(2026, 1, 1, tzinfo=UTC)
    pd.DataFrame(
        [
            {
                "cycle_id": "seed-cycle",
                "symbol": "MMTUSDT",
                "pump_start": start,
                "peak_time": start + timedelta(hours=3),
                "dump_end": start + timedelta(hours=6),
                "pump_return": 0.32,
                "dump_return": 0.21,
                "duration_hours": 6.0,
            },
            {
                "cycle_id": "expanded-cycle",
                "symbol": "TUTUSDT",
                "pump_start": start + timedelta(days=1),
                "peak_time": start + timedelta(days=1, hours=3),
                "dump_end": start + timedelta(days=1, hours=5),
                "pump_return": 0.30,
                "dump_return": 0.19,
                "duration_hours": 5.0,
            },
        ]
    ).to_parquet(cycles_dir / "MMTUSDT.parquet", index=False)

    seed_path = tmp_path / "seed_events.yaml"
    seed_path.write_text(
        yaml.safe_dump(
            {
                "version": "test_seed_events",
                "manual_seed_events": [
                    {
                        "seed_id": "mmt_seed",
                        "symbol": "MMTUSDT",
                        "pump_start": start.isoformat(),
                        "peak_time": (start + timedelta(hours=3)).isoformat(),
                        "dump_end": (start + timedelta(hours=6)).isoformat(),
                    }
                ],
                "matching": {"tolerance_hours": 2},
                "commonality": {"fallback_to_cycle_config": True},
            }
        ),
        encoding="utf-8",
    )
    cycle_path = tmp_path / "cycle.yaml"
    cycle_path.write_text(
        yaml.safe_dump(
            {
                "pump_threshold_min": 0.2,
                "pump_threshold_max": 0.5,
                "dump_retrace_ratio": 0.55,
                "max_cycle_hours": 96,
            }
        ),
        encoding="utf-8",
    )

    manifest = build_event_set(
        str(seed_path),
        str(cycle_path),
        cycles_dir=cycles_dir,
        output_dir=tmp_path / "event_sets",
    )

    assert manifest["matched_seed_event_count"] == 1
    assert manifest["commonality_profile"]["source"] == "matched_seed_events"
    assert manifest["expanded_event_count"] == 2
    assert manifest["event_set_hash"]
