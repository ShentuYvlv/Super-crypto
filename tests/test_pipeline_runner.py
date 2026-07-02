from __future__ import annotations

from super_crypto.common.paths import DATA_ROOT
from super_crypto.experiments import pipeline_runner
from super_crypto.experiments.pipeline_runner import (
    _enrichment_output_paths,
    _ingest_output_paths,
    _stage_enabled,
    _stage_skip_reason,
)


def test_stage_enabled_defaults_to_true():
    assert _stage_enabled({}, "ingest") is True


def test_stage_skip_reason_reports_disabled_stage():
    config = {"stages": {"ingest": {"enabled": False}}}

    assert _stage_skip_reason(config, "ingest", "train_validation") == "disabled"


def test_ingest_outputs_cover_all_timeframes_and_derivatives():
    paths = _ingest_output_paths(["BTCUSDT"], ["1m", "1h"])

    assert paths == [
        DATA_ROOT / "processed" / "ohlcv" / "1m" / "BTCUSDT.parquet",
        DATA_ROOT / "processed" / "ohlcv" / "1h" / "BTCUSDT.parquet",
        DATA_ROOT / "processed" / "derivatives" / "funding_BTCUSDT.parquet",
        DATA_ROOT / "processed" / "derivatives" / "open_interest_BTCUSDT.parquet",
    ]


def test_enrichment_outputs_cover_orderbook_and_coinglass_endpoints():
    paths = _enrichment_output_paths(["BTCUSDT"], ["tickers", "coin_info"])

    assert paths == [
        DATA_ROOT / "processed" / "orderbook_features" / "BTCUSDT.parquet",
        DATA_ROOT / "processed" / "external_enrichment" / "tickers_BTCUSDT.parquet",
        DATA_ROOT / "processed" / "external_enrichment" / "coin_info_BTCUSDT.parquet",
    ]


def test_pipeline_can_run_phase1_stage_without_new_cli(tmp_path, monkeypatch):
    config_path = tmp_path / "pipeline.yaml"
    config_path.write_text(
        """
name: test_pipeline
data:
  symbols: [BTCUSDT]
  timeframes: [1h]
splits:
  train:
    start: "2026-01-01T00:00:00Z"
    end: "2026-01-10T00:00:00Z"
    symbols: [BTCUSDT]
  validation:
    start: "2026-01-11T00:00:00Z"
    end: "2026-01-20T00:00:00Z"
    symbols: [BTCUSDT]
  holdout:
    start: "2026-01-21T00:00:00Z"
    end: "2026-01-30T00:00:00Z"
    symbols: [BTCUSDT]
  holdout_policy:
    require_final_flag: true
    max_manual_runs: 1
  purge_bars: 2
phase1_prediction:
  label_source: data/labels/phase1_events.csv
  timeframe: 1h
  lead_time_hours: 4
  candidate_thresholds:
    return_4h_min: 0.15
    return_24h_min: 0.30
    volume_zscore_min: 3.0
    range_pct_min: 0.20
stages:
  run_phase1_prediction:
    enabled: true
""",
        encoding="utf-8",
    )

    class FakePipelineStore:
        runs: list[dict] = []
        stages: list[dict] = []

        def list_runs(self):
            return self.runs

        def list_stages(self, _run_id):
            return self.stages

        def upsert_run(self, payload):
            self.runs.append(payload)

        def upsert_stage(self, payload):
            self.stages.append(payload)

    class FakeExperimentStore:
        def holdout_run_count(self):
            return 0

    monkeypatch.setattr(pipeline_runner, "PipelineStore", FakePipelineStore)
    monkeypatch.setattr(pipeline_runner, "ExperimentStore", FakeExperimentStore)
    monkeypatch.setattr(pipeline_runner, "holdout_guard", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(
        pipeline_runner,
        "run_phase1_prediction",
        lambda _config, symbols, split: {
            "symbols": symbols,
            "split": split,
            "candidate_count": 1,
        },
    )

    result = pipeline_runner.run_pipeline(
        str(config_path),
        "train_validation",
        only_stage="run_phase1_prediction",
    )

    assert result["stages"]["run_phase1_prediction"]["candidate_count"] == 1


def test_pipeline_phase1_symbols_are_derived_from_event_windows(tmp_path, monkeypatch):
    config_path = tmp_path / "pipeline.yaml"
    config_path.write_text(
        """
name: test_pipeline
data:
  symbols_mode: union
  timeframes: [1h]
splits:
  symbols: [BTCUSDT]
  train:
    start: "2026-01-01T00:00:00Z"
    end: "2026-01-10T00:00:00Z"
  validation:
    start: "2026-01-11T00:00:00Z"
    end: "2026-01-20T00:00:00Z"
  holdout:
    start: "2026-01-21T00:00:00Z"
    end: "2026-01-30T00:00:00Z"
  holdout_policy:
    require_final_flag: true
    max_manual_runs: 1
  purge_bars: 2
phase1_prediction:
  label_source: data/labels/phase1_events.csv
  timeframe: 1h
  lead_time_hours: 4
  event_windows:
    - window_id: river_window
      symbol: RIVERUSDT
      split: train
      start: "2026-01-01T00:00:00Z"
      end: "2026-01-02T00:00:00Z"
  candidate_thresholds:
    return_4h_min: 0.15
    return_24h_min: 0.30
    volume_zscore_min: 3.0
    range_pct_min: 0.20
stages:
  run_phase1_prediction:
    enabled: true
""",
        encoding="utf-8",
    )

    class FakePipelineStore:
        runs: list[dict] = []
        stages: list[dict] = []

        def list_runs(self):
            return self.runs

        def list_stages(self, _run_id):
            return self.stages

        def upsert_run(self, payload):
            self.runs.append(payload)

        def upsert_stage(self, payload):
            self.stages.append(payload)

    class FakeExperimentStore:
        def holdout_run_count(self):
            return 0

    monkeypatch.setattr(pipeline_runner, "PipelineStore", FakePipelineStore)
    monkeypatch.setattr(pipeline_runner, "ExperimentStore", FakeExperimentStore)
    monkeypatch.setattr(
        pipeline_runner,
        "run_phase1_prediction",
        lambda _config, symbols, _split: {"symbols": symbols},
    )

    result = pipeline_runner.run_pipeline(
        str(config_path),
        "train_validation",
        only_stage="run_phase1_prediction",
    )

    assert result["stages"]["run_phase1_prediction"]["symbols"] == ["RIVERUSDT"]


def test_pipeline_ingest_receives_full_config_for_union_symbols(tmp_path, monkeypatch):
    config_path = tmp_path / "pipeline.yaml"
    config_path.write_text(
        """
name: test_pipeline
data:
  symbols_mode: union
  timeframes: [1h]
splits:
  symbols: [BTCUSDT]
  train:
    start: "2026-01-01T00:00:00Z"
    end: "2026-01-10T00:00:00Z"
  validation:
    start: "2026-01-11T00:00:00Z"
    end: "2026-01-20T00:00:00Z"
  holdout:
    start: "2026-01-21T00:00:00Z"
    end: "2026-01-30T00:00:00Z"
  holdout_policy:
    require_final_flag: true
    max_manual_runs: 1
  purge_bars: 2
phase1_prediction:
  event_windows:
    - window_id: river_window
      symbol: RIVERUSDT
      split: train
      start: "2026-01-01T00:00:00Z"
      end: "2026-01-02T00:00:00Z"
stages:
  ingest:
    enabled: true
""",
        encoding="utf-8",
    )
    captured = {}

    class FakePipelineStore:
        runs: list[dict] = []
        stages: list[dict] = []

        def list_runs(self):
            return self.runs

        def list_stages(self, _run_id):
            return self.stages

        def upsert_run(self, payload):
            self.runs.append(payload)

        def upsert_stage(self, payload):
            self.stages.append(payload)

    class FakeExperimentStore:
        def holdout_run_count(self):
            return 0

    def fake_ingest(config):
        captured["symbols_mode"] = config["data"]["symbols_mode"]
        captured["has_splits"] = "splits" in config
        captured["has_phase1"] = "phase1_prediction" in config
        return {}

    monkeypatch.setattr(pipeline_runner, "PipelineStore", FakePipelineStore)
    monkeypatch.setattr(pipeline_runner, "ExperimentStore", FakeExperimentStore)
    monkeypatch.setattr(pipeline_runner, "ingest_market_snapshots", fake_ingest)
    monkeypatch.setattr(pipeline_runner, "ingest_klines", fake_ingest)
    monkeypatch.setattr(pipeline_runner, "ingest_funding", fake_ingest)
    monkeypatch.setattr(pipeline_runner, "ingest_open_interest", fake_ingest)

    pipeline_runner.run_pipeline(str(config_path), "train_validation", only_stage="ingest")

    assert captured == {"symbols_mode": "union", "has_splits": True, "has_phase1": True}


def test_pipeline_injects_top_level_splits_into_experiment_config(tmp_path, monkeypatch):
    config_path = tmp_path / "pipeline.yaml"
    config_path.write_text(
        """
name: test_pipeline
data:
  symbols: [BTCUSDT]
  timeframes: [1h]
splits:
  symbols: [BTCUSDT]
  train:
    start: "2026-01-01T00:00:00Z"
    end: "2026-01-10T00:00:00Z"
  validation:
    start: "2026-01-11T00:00:00Z"
    end: "2026-01-20T00:00:00Z"
  holdout:
    start: "2026-01-21T00:00:00Z"
    end: "2026-01-30T00:00:00Z"
  holdout_policy:
    require_final_flag: true
    max_manual_runs: 1
  purge_bars: 2
experiment:
  name: experiment_v4a
  engine: event_driven
  strategy:
    strategy: V4A
    timeframe: 1h
  backtest: {}
  scores: {}
stages:
  run_experiment:
    enabled: true
""",
        encoding="utf-8",
    )
    captured = {}

    class FakePipelineStore:
        runs: list[dict] = []
        stages: list[dict] = []

        def list_runs(self):
            return self.runs

        def list_stages(self, _run_id):
            return self.stages

        def upsert_run(self, payload):
            self.runs.append(payload)

        def upsert_stage(self, payload):
            self.stages.append(payload)

    class FakeExperimentStore:
        def holdout_run_count(self):
            return 0

    def fake_run_experiment(config, split, final_flag=False):
        captured["config"] = config
        captured["split"] = split
        captured["final_flag"] = final_flag
        return {"html_report": "report.html", "experiment": {}}

    monkeypatch.setattr(pipeline_runner, "PipelineStore", FakePipelineStore)
    monkeypatch.setattr(pipeline_runner, "ExperimentStore", FakeExperimentStore)
    monkeypatch.setattr(pipeline_runner, "run_experiment", fake_run_experiment)

    pipeline_runner.run_pipeline(str(config_path), "train_validation", only_stage="run_experiment")

    assert captured["config"]["splits"]["symbols"] == ["BTCUSDT"]
    assert "symbols" not in captured["config"]["splits"]["train"]
