from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pandas as pd

from super_crypto.experiments import phase1_prediction


def _ohlcv() -> pd.DataFrame:
    start = datetime(2026, 1, 1, tzinfo=UTC)
    rows = []
    price = 1.0
    for index in range(80):
        if index == 40:
            price *= 1.35
        elif index == 41:
            price *= 1.08
        else:
            price *= 1.005
        rows.append(
            {
                "symbol": "MMTUSDT",
                "open_time": start + timedelta(hours=index),
                "close_time": start + timedelta(hours=index + 1),
                "open": price * 0.99,
                "high": price * 1.03,
                "low": price * 0.97,
                "close": price,
                "volume": 1000 + index * 10,
                "quote_volume": 1000 + index * 10,
                "trades": 10,
                "taker_buy_base_volume": 400,
                "taker_buy_quote_volume": 400,
            }
        )
    return pd.DataFrame(rows)


def _config() -> dict:
    return {
        "label_source": "data/labels/phase1_events.csv",
        "timeframe": "1h",
        "lead_time_hours": 4,
        "minimum_labels_to_run": 1,
        "allowed_label_quality": ["A", "B"],
        "negative_sample_ratio": 3,
        "negative_gap_hours": 12,
        "candidate_cooldown_hours": 24,
        "candidate_thresholds": {
            "return_4h_min": 0.15,
            "return_24h_min": 0.30,
            "volume_zscore_min": 3.0,
            "range_pct_min": 0.20,
        },
        "experiments": ["fr_baseline", "fr_oi", "all_available_features"],
    }


def test_phase1_generates_label_candidates_and_template(tmp_path, monkeypatch):
    monkeypatch.setattr(phase1_prediction, "DATA_ROOT", tmp_path)
    ohlcv_dir = tmp_path / "processed" / "ohlcv" / "1h"
    ohlcv_dir.mkdir(parents=True)
    _ohlcv().to_parquet(ohlcv_dir / "MMTUSDT.parquet", index=False)

    details = phase1_prediction.generate_label_candidates(_config(), ["MMTUSDT"])

    candidates = pd.read_csv(details["candidate_path"])
    assert details["candidate_count"] >= 1
    assert not candidates["label_event_start"].fillna("").any()
    assert (tmp_path / "labels" / "phase1_events.csv").exists()


def test_phase1_runs_f1_experiment_when_labels_exist(tmp_path, monkeypatch):
    monkeypatch.setattr(phase1_prediction, "DATA_ROOT", tmp_path)
    monkeypatch.setattr(phase1_prediction, "REPORT_ROOT", tmp_path / "reports")
    ohlcv_dir = tmp_path / "processed" / "ohlcv" / "1h"
    ohlcv_dir.mkdir(parents=True)
    _ohlcv().to_parquet(ohlcv_dir / "MMTUSDT.parquet", index=False)
    label_dir = tmp_path / "labels"
    label_dir.mkdir()
    pd.DataFrame(
        [
            {
                "event_id": "mmt_001",
                "symbol": "MMTUSDT",
                "event_start": "2026-01-02T16:00:00Z",
                "peak_time": "2026-01-02T17:00:00Z",
                "dump_end": "2026-01-02T20:00:00Z",
                "split": "train",
                "label_quality": "A",
                "source": "unit",
                "note": "test",
            }
        ]
    ).to_csv(label_dir / "phase1_events.csv", index=False)

    result = phase1_prediction.run(_config(), ["MMTUSDT"], "train_validation")

    experiment = result["experiment"]
    assert experiment["status"] == "completed"
    assert experiment["label_count"] == 1
    assert experiment["sample_count"] >= 2
    assert experiment["phase1_results"]
    assert (tmp_path / "processed" / "phase1" / "features.parquet").exists()
    assert (tmp_path / "reports" / experiment["experiment_id"] / "report.md").exists()
