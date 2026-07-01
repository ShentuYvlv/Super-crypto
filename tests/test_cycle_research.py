from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pandas as pd
import pytest
import yaml

from super_crypto.autoresearch import artifacts
from super_crypto.autoresearch.cycle_research import run_cycle_research


def _sample_ohlcv() -> pd.DataFrame:
    start = datetime(2026, 1, 1, tzinfo=UTC)
    rows = []
    prices = [1.0, 1.08, 1.18, 1.34, 1.28, 1.05, 0.96, 0.98, 1.0, 1.02]
    for index, close in enumerate(prices):
        rows.append(
            {
                "open_time": start + timedelta(hours=index),
                "open": close * 0.98,
                "high": close * 1.02,
                "low": close * 0.96,
                "close": close,
                "volume": 1000.0,
            }
        )
    return pd.DataFrame(rows)


def test_cycle_research_generates_ranked_candidates(tmp_path, monkeypatch):
    monkeypatch.setattr("super_crypto.autoresearch.cycle_research.DATA_ROOT", tmp_path)
    monkeypatch.setattr(artifacts, "DATA_ROOT", tmp_path)
    ohlcv_dir = tmp_path / "processed" / "ohlcv" / "15m"
    ohlcv_dir.mkdir(parents=True)
    _sample_ohlcv().to_parquet(ohlcv_dir / "MMTUSDT.parquet", index=False)
    config_path = tmp_path / "pipeline.yaml"
    config_path.write_text(
        yaml.safe_dump(
            {
                "name": "test_pipeline",
                "data": {"symbols": ["MMTUSDT"]},
                "cycle": {
                    "timeframe": "15m",
                    "pump_threshold_min": 0.2,
                    "pump_threshold_max": 0.6,
                    "dump_retrace_ratio": 0.5,
                    "max_cycle_hours": 12,
                    "dedupe_gap_hours": 1,
                },
                "seed_events": {
                    "version": "test",
                    "manual_seed_events": [],
                    "matching": {"tolerance_hours": 2},
                    "commonality": {"fallback_to_cycle_config": True},
                },
                "experiment": {"strategy": {"timeframe": "15m"}},
            }
        ),
        encoding="utf-8",
    )
    autoresearch_config_path = tmp_path / "autoresearch.yaml"
    autoresearch_config_path.write_text("max_cycle_validation_runs: 2\n", encoding="utf-8")

    manifest = run_cycle_research(
        str(config_path),
        autoresearch_config_path=str(autoresearch_config_path),
        use_llm=False,
    )

    assert manifest["status"] == "completed"
    assert manifest["candidate_count"] == 2
    assert manifest["best_candidate_id"]
    assert manifest["best_quality"]["cycle_count"] >= 1
    assert manifest["best_cycle_config"]["pump_threshold_min"] >= 0.05
    assert (tmp_path / "processed" / "cycle_research" / "runs" / manifest["run_id"]).exists()


def test_cycle_research_apply_best_updates_pipeline_cycle(tmp_path, monkeypatch):
    monkeypatch.setattr("super_crypto.autoresearch.cycle_research.DATA_ROOT", tmp_path)
    monkeypatch.setattr(artifacts, "DATA_ROOT", tmp_path)
    ohlcv_dir = tmp_path / "processed" / "ohlcv" / "15m"
    ohlcv_dir.mkdir(parents=True)
    _sample_ohlcv().to_parquet(ohlcv_dir / "MMTUSDT.parquet", index=False)
    config_path = tmp_path / "pipeline.yaml"
    payload = {
        "name": "test_pipeline",
        "data": {"symbols": ["MMTUSDT"]},
        "cycle": {
            "timeframe": "15m",
            "pump_threshold_min": 0.2,
            "pump_threshold_max": 0.6,
            "dump_retrace_ratio": 0.5,
            "max_cycle_hours": 12,
            "dedupe_gap_hours": 1,
        },
        "seed_events": {
            "manual_seed_events": [],
            "commonality": {"fallback_to_cycle_config": True},
        },
        "experiment": {"strategy": {"timeframe": "15m"}},
    }
    config_path.write_text(yaml.safe_dump(payload), encoding="utf-8")
    autoresearch_config_path = tmp_path / "autoresearch.yaml"
    autoresearch_config_path.write_text("max_cycle_validation_runs: 1\n", encoding="utf-8")

    manifest = run_cycle_research(
        str(config_path),
        autoresearch_config_path=str(autoresearch_config_path),
        use_llm=False,
        apply_best=True,
    )

    updated = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    assert manifest["applied_path"] == str(config_path)
    assert updated["cycle"] == manifest["best_cycle_config"]


def test_cycle_research_rejects_unlisted_pipeline_config(tmp_path):
    config_path = tmp_path / "pipeline.yaml"
    config_path.write_text("name: blocked\ncycle: {}\n", encoding="utf-8")
    autoresearch_config_path = tmp_path / "autoresearch.yaml"
    autoresearch_config_path.write_text(
        yaml.safe_dump({"allowed_pipeline_config_files": ["configs/pipeline_v4a.yaml"]}),
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="not allowed"):
        run_cycle_research(
            str(config_path),
            autoresearch_config_path=str(autoresearch_config_path),
            use_llm=False,
        )
