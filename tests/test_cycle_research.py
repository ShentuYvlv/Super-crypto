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
    prices = [1.0, 1.02, 1.04, 1.08, 1.15, 1.25, 1.36, 1.30, 1.20, 1.10, 1.0, 0.98]
    for index, close in enumerate(prices):
        rows.append(
            {
                "open_time": start + timedelta(minutes=15 * index),
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
    autoresearch_config_path.write_text(
        yaml.safe_dump({"max_cycle_validation_runs": 2, "max_cycle_research_iterations": 2}),
        encoding="utf-8",
    )

    manifest = run_cycle_research(
        str(config_path),
        autoresearch_config_path=str(autoresearch_config_path),
        use_llm=False,
    )

    assert manifest["status"] == "completed"
    assert manifest["iteration_count"] == 2
    assert manifest["candidate_count"] >= 2
    assert manifest["best_candidate_id"]
    assert manifest["best_quality"]["cycle_count"] >= 1
    assert "control_group_separation" in manifest["best_quality"]
    assert manifest["best_cycles_path"]
    assert manifest["candidate_scores_path"]
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


def test_cycle_research_llm_iterates_from_previous_results(tmp_path, monkeypatch):
    monkeypatch.setattr("super_crypto.autoresearch.cycle_research.DATA_ROOT", tmp_path)
    monkeypatch.setattr(artifacts, "DATA_ROOT", tmp_path)
    ohlcv_dir = tmp_path / "processed" / "ohlcv" / "15m"
    ohlcv_dir.mkdir(parents=True)
    _sample_ohlcv().to_parquet(ohlcv_dir / "MMTUSDT.parquet", index=False)
    _sample_ohlcv().to_parquet(ohlcv_dir / "CTRLUSDT.parquet", index=False)
    config_path = tmp_path / "cycle_discovery.yaml"
    config_path.write_text(
        yaml.safe_dump(
            {
                "name": "cycle_discovery_test",
                "data": {"symbols_mode": "union", "symbols": []},
                "cycle_discovery": {
                    "max_iterations": 2,
                    "candidates_per_iteration": 1,
                    "symbol_groups": {"strong": ["MMTUSDT"], "control": ["CTRLUSDT"]},
                },
                "cycle": {
                    "timeframe": "15m",
                    "pump_threshold_min": 0.2,
                    "pump_threshold_max": 0.8,
                    "dump_return_min": 0.1,
                    "dump_retrace_ratio": 0.4,
                    "max_cycle_hours": 12,
                    "dedupe_gap_hours": 1,
                },
            }
        ),
        encoding="utf-8",
    )
    autoresearch_config_path = tmp_path / "autoresearch.yaml"
    autoresearch_config_path.write_text(
        yaml.safe_dump({"max_cycle_research_iterations": 2}),
        encoding="utf-8",
    )

    calls: list[dict] = []

    class FakeClient:
        model = "fake"

        def complete_json(self, *, system: str, user: dict) -> dict:
            calls.append(user)
            iteration = user["iteration"]
            return {
                "hypothesis": f"第 {iteration} 轮假设",
                "rationale": "根据上一轮结果调整周期定义。",
                "risk": "可能过宽。",
                "candidates": [
                    {
                        "pump_threshold_min": 0.18 if iteration == 1 else 0.22,
                        "pump_threshold_max": 0.8,
                        "dump_return_min": 0.1,
                        "dump_retrace_ratio": 0.4,
                        "max_cycle_hours": 12,
                        "dedupe_gap_hours": 1,
                        "min_peak_distance_from_start_hours": 0,
                        "min_pump_duration_hours": 0,
                        "max_pump_duration_hours": 12,
                    }
                ],
            }

    monkeypatch.setattr(
        "super_crypto.autoresearch.cycle_research.AutoResearchLLMClient.from_env",
        lambda: FakeClient(),
    )

    manifest = run_cycle_research(
        str(config_path),
        autoresearch_config_path=str(autoresearch_config_path),
        use_llm=True,
    )

    assert manifest["model_status"]["mode"] == "llm"
    assert manifest["iteration_count"] == 2
    assert len(calls) == 2
    assert calls[0]["previous_ranked_results"] == []
    assert calls[1]["previous_ranked_results"]
    assert manifest["symbol_groups"]["strong"] == ["MMTUSDT"]


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
