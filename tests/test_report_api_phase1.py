from __future__ import annotations

import pandas as pd

from super_crypto.experiments.experiment_store import ExperimentStore
from super_crypto.report_api import phase1


def test_phase1_api_returns_dashboard_payload(tmp_path, monkeypatch):
    store = ExperimentStore(tmp_path / "experiments.db")
    artifact_dir = tmp_path / "reports" / "phase1-a" / "phase1"
    artifact_dir.mkdir(parents=True)
    dataset_path = artifact_dir / "features.parquet"
    labels_path = artifact_dir / "labels_used.csv"
    windows_path = artifact_dir / "window_diagnostics.csv"
    candidates_path = artifact_dir / "candidates.csv"
    pd.DataFrame(
        [
            {
                "symbol": "RIVERUSDT",
                "split": "train",
                "label": 1,
                "sample_role": "positive",
                "sample_time": "2026-01-01T00:00:00Z",
                "funding_rate": 0.0001,
                "oi_change_1h": 0.0,
                "liq_long_usd": 0.0,
                "liq_short_usd": 0.0,
                "taker_buy_ratio": 0.6,
                "sell_pressure": 0.1,
                "liquidation_data_quality": "missing",
                "orderbook_data_quality": "healthy",
                "onchain_data_quality": "missing",
            },
            {
                "symbol": "RAVEUSDT",
                "split": "holdout",
                "label": 0,
                "sample_role": "negative",
                "sample_time": "2026-01-02T00:00:00Z",
                "funding_rate": 0.0,
                "oi_change_1h": 0.0,
                "liq_long_usd": 0.0,
                "liq_short_usd": 0.0,
                "taker_buy_ratio": 0.45,
                "sell_pressure": -0.05,
                "liquidation_data_quality": "missing",
                "orderbook_data_quality": "missing",
                "onchain_data_quality": "missing",
            },
        ]
    ).to_parquet(dataset_path, index=False)
    pd.DataFrame(
        [
            {
                "event_id": "river",
                "symbol": "RIVERUSDT",
                "event_start": "2026-01-01T04:00:00Z",
                "peak_time": "2026-01-01T08:00:00Z",
                "dump_end": "2026-01-01T12:00:00Z",
                "split": "train",
            }
        ]
    ).to_csv(labels_path, index=False)
    pd.DataFrame(
        [
            {
                "window_id": "river",
                "symbol": "RIVERUSDT",
                "split": "train",
                "window_rows": 10,
                "detected_event_start": "2026-01-01T04:00:00Z",
                "peak_time": "2026-01-01T08:00:00Z",
                "dump_end": "2026-01-01T12:00:00Z",
                "detection_rule": "pump_return_lookback >= 0.15",
                "positive_sample_time": "2026-01-01T00:00:00Z",
                "status": "covered",
            }
        ]
    ).to_csv(windows_path, index=False)
    pd.DataFrame([{"symbol": "RIVERUSDT"}]).to_csv(candidates_path, index=False)
    store.upsert(
        "experiments",
        "experiment_id",
        {
            "experiment_id": "phase1-a",
            "strategy": "PHASE1",
            "status": "completed",
            "created_at": "2026-01-01T00:00:00Z",
            "dataset_path": str(dataset_path),
            "labels_used_path": str(labels_path),
            "window_diagnostics_path": str(windows_path),
            "candidate_path": str(candidates_path),
            "metrics": {
                "label_count": 1,
                "sample_count": 2,
                "positive_sample_count": 1,
                "negative_sample_count": 1,
                "train_sample_count": 1,
                "train_positive_count": 1,
                "holdout_sample_count": 1,
                "holdout_positive_count": 0,
                "train_f1": 1.0,
                "holdout_f1": 0.0,
                "holdout_precision": 0.0,
                "holdout_recall": 0.0,
            },
            "phase1_results": [
                {
                    "experiment": "lightgbm_all_features",
                    "model": "lightgbm",
                    "train_f1": 1.0,
                    "holdout_f1": 0.0,
                    "holdout_precision": 0.0,
                    "holdout_recall": 0.0,
                    "status": "completed",
                }
            ],
        },
    )
    monkeypatch.setattr(phase1, "experiment_store", lambda: store)

    response = phase1.get_phase1_experiment("phase1-a")
    payload = response["payload"]

    assert payload["summary"]["experiment_id"] == "phase1-a"
    assert payload["splits"][0]["symbols"] == ["RIVERUSDT"]
    assert payload["windows"][0]["peak_time"] == "2026-01-01T08:00:00Z"
    assert payload["model_results"][0]["model"] == "lightgbm"
    assert any(item["key"] == "overfit" for item in payload["conclusion_flags"])
    assert any(
        item["key"] == "liquidation" and item["status"] == "missing"
        for item in payload["feature_quality"]
    )


def test_phase1_symbol_api_filters_rows(tmp_path, monkeypatch):
    store = ExperimentStore(tmp_path / "experiments.db")
    artifact_dir = tmp_path / "reports" / "phase1-a" / "phase1"
    artifact_dir.mkdir(parents=True)
    dataset_path = artifact_dir / "features.parquet"
    labels_path = artifact_dir / "labels_used.csv"
    windows_path = artifact_dir / "window_diagnostics.csv"
    pd.DataFrame(
        [
            {"symbol": "RIVERUSDT", "split": "train", "label": 1},
            {"symbol": "RAVEUSDT", "split": "holdout", "label": 0},
        ]
    ).to_parquet(dataset_path, index=False)
    pd.DataFrame(
        [
            {"event_id": "river", "symbol": "RIVERUSDT", "split": "train"},
            {"event_id": "rave", "symbol": "RAVEUSDT", "split": "holdout"},
        ]
    ).to_csv(labels_path, index=False)
    pd.DataFrame(
        [
            {"window_id": "river", "symbol": "RIVERUSDT", "split": "train"},
            {"window_id": "rave", "symbol": "RAVEUSDT", "split": "holdout"},
        ]
    ).to_csv(windows_path, index=False)
    store.upsert(
        "experiments",
        "experiment_id",
        {
            "experiment_id": "phase1-a",
            "strategy": "PHASE1",
            "status": "completed",
            "created_at": "2026-01-01T00:00:00Z",
            "dataset_path": str(dataset_path),
            "labels_used_path": str(labels_path),
            "window_diagnostics_path": str(windows_path),
            "metrics": {},
            "phase1_results": [],
        },
    )
    monkeypatch.setattr(phase1, "experiment_store", lambda: store)

    payload = phase1.get_phase1_symbol("phase1-a", "RIVERUSDT")["payload"]

    assert {item["symbol"] for item in payload["samples"]} == {"RIVERUSDT"}
    assert {item["symbol"] for item in payload["labels"]} == {"RIVERUSDT"}
    assert {item["symbol"] for item in payload["windows"]} == {"RIVERUSDT"}


def test_phase1_api_does_not_read_shared_latest_dataset_for_legacy_experiment(
    tmp_path,
    monkeypatch,
):
    store = ExperimentStore(tmp_path / "experiments.db")
    shared_dataset = tmp_path / "processed" / "phase1" / "features.parquet"
    shared_dataset.parent.mkdir(parents=True)
    pd.DataFrame([{"symbol": "WRONGUSDT", "split": "train", "label": 1}]).to_parquet(
        shared_dataset,
        index=False,
    )
    store.upsert(
        "experiments",
        "experiment_id",
        {
            "experiment_id": "legacy-phase1",
            "strategy": "PHASE1",
            "status": "completed",
            "created_at": "2026-01-01T00:00:00Z",
            "dataset_path": str(shared_dataset),
            "metrics": {"sample_count": 9},
            "window_diagnostics": [
                {
                    "window_id": "legacy",
                    "symbol": "RIVERUSDT",
                    "split": "train",
                    "status": "covered",
                }
            ],
            "phase1_results": [],
        },
    )
    monkeypatch.setattr(phase1, "experiment_store", lambda: store)

    payload = phase1.get_phase1_experiment("legacy-phase1")["payload"]

    assert payload["samples"] == []
    assert payload["sample_count"] == 0
    assert payload["windows"][0]["symbol"] == "RIVERUSDT"
