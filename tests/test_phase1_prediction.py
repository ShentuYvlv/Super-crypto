from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pandas as pd
import pytest

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
        "auto_event_detection": {
            "enabled": True,
            "pump_return_min": 0.15,
            "min_event_gap_hours": 12,
            "peak_search_hours": 48,
            "dump_search_hours": 72,
        },
        "experiments": ["fr_baseline", "fr_oi", "all_available_features", "lightgbm_all_features"],
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


def test_phase1_auto_detects_yaml_windows_and_splits_train_holdout(tmp_path, monkeypatch):
    monkeypatch.setattr(phase1_prediction, "DATA_ROOT", tmp_path)
    monkeypatch.setattr(phase1_prediction, "REPORT_ROOT", tmp_path / "reports")
    ohlcv_dir = tmp_path / "processed" / "ohlcv" / "1h"
    ohlcv_dir.mkdir(parents=True)
    _ohlcv().to_parquet(ohlcv_dir / "MMTUSDT.parquet", index=False)
    config = _config()
    config["minimum_labels_to_run"] = 2
    config["event_windows"] = [
        {
            "window_id": "mmt_train_window",
            "symbol": "MMTUSDT",
            "split": "train",
            "start": "2026-01-01T00:00:00Z",
            "end": "2026-01-02T23:00:00Z",
            "label_quality": "A",
        },
        {
            "window_id": "mmt_holdout_window",
            "symbol": "MMTUSDT",
            "split": "holdout",
            "start": "2026-01-03T00:00:00Z",
            "end": "2026-01-04T07:00:00Z",
            "label_quality": "A",
        },
    ]

    result = phase1_prediction.run(config, ["MMTUSDT"], "train_validation")

    experiment = result["experiment"]
    labels = pd.read_csv(tmp_path / "processed" / "phase1" / "labels_used.csv")
    dataset = pd.read_parquet(tmp_path / "processed" / "phase1" / "features.parquet")
    assert experiment["status"] == "completed"
    assert set(labels["split"]) == {"train", "holdout"}
    assert {"train", "holdout"}.issubset(set(dataset["split"]))
    threshold_results = [
        item
        for item in experiment["phase1_results"]
        if item["experiment"] == "all_available_features"
    ]
    assert threshold_results
    result_row = threshold_results[0]
    assert "train_f1" in result_row
    assert "holdout_f1" in result_row
    assert result_row["train_sample_count"] > 0
    assert result_row["holdout_sample_count"] > 0
    assert isinstance(result_row["threshold"], float)


def test_phase1_uses_event_window_symbols_instead_of_fallback_symbols(tmp_path, monkeypatch):
    monkeypatch.setattr(phase1_prediction, "DATA_ROOT", tmp_path)
    monkeypatch.setattr(phase1_prediction, "REPORT_ROOT", tmp_path / "reports")
    ohlcv_dir = tmp_path / "processed" / "ohlcv" / "1h"
    ohlcv_dir.mkdir(parents=True)
    _ohlcv().to_parquet(ohlcv_dir / "MMTUSDT.parquet", index=False)
    config = _config()
    config["event_windows"] = [
        {
            "window_id": "mmt_window",
            "symbol": "MMTUSDT",
            "split": "train",
            "start": "2026-01-01T00:00:00Z",
            "end": "2026-01-02T23:00:00Z",
            "label_quality": "A",
        },
    ]

    result = phase1_prediction.run(config, ["BTCUSDT"], "train_validation")
    dataset = pd.read_parquet(result["dataset"])

    assert set(dataset["symbol"]) == {"MMTUSDT"}


def test_phase1_event_window_missing_ohlcv_fails_clearly(tmp_path, monkeypatch):
    monkeypatch.setattr(phase1_prediction, "DATA_ROOT", tmp_path)
    config = _config()
    config["event_windows"] = [
        {
            "window_id": "missing_window",
            "symbol": "MISSINGUSDT",
            "split": "train",
            "start": "2026-01-01T00:00:00Z",
            "end": "2026-01-02T23:00:00Z",
            "label_quality": "A",
        },
    ]

    with pytest.raises(FileNotFoundError, match="Missing OHLCV data"):
        phase1_prediction.run(config, [], "train_validation")


def test_phase1_invalid_event_window_date_fails_clearly():
    config = _config()
    config["event_windows"] = [
        {
            "window_id": "bad_date",
            "symbol": "MMTUSDT",
            "split": "train",
            "start": "2026-02-30T00:00:00Z",
            "end": "2026-03-01T00:00:00Z",
            "label_quality": "A",
        },
    ]

    with pytest.raises(ValueError, match="invalid start/end"):
        phase1_prediction.run(config, [], "train_validation")


def test_phase1_merges_real_optional_external_features(tmp_path, monkeypatch):
    monkeypatch.setattr(phase1_prediction, "DATA_ROOT", tmp_path)
    ohlcv_dir = tmp_path / "processed" / "ohlcv" / "1h"
    derivatives_dir = tmp_path / "processed" / "derivatives"
    orderbook_dir = tmp_path / "processed" / "orderbook_features"
    onchain_dir = tmp_path / "processed" / "onchain_features"
    external_dir = tmp_path / "processed" / "external_enrichment"
    for directory in (ohlcv_dir, derivatives_dir, orderbook_dir, onchain_dir, external_dir):
        directory.mkdir(parents=True)
    _ohlcv().to_parquet(ohlcv_dir / "MMTUSDT.parquet", index=False)
    pd.DataFrame(
        [
            {
                "snapshot_time": "2026-01-02T12:00:00Z",
                "long_liquidation_usd": 100.0,
                "short_liquidation_usd": 300.0,
            }
        ]
    ).to_parquet(derivatives_dir / "liquidation_MMTUSDT.parquet", index=False)
    pd.DataFrame(
        [{"snapshot_time": "2026-01-02T12:00:00Z", "long_short_ratio": 1.7}]
    ).to_parquet(external_dir / "long_short_ratio_MMTUSDT.parquet", index=False)
    pd.DataFrame(
        [
            {
                "snapshot_time": "2026-01-02T12:00:00Z",
                "spread_bps": 12.0,
                "imbalance": -0.2,
                "slippage_bps_sell": {"100": 4.0, "500": 9.0, "1000": 14.0},
            }
        ]
    ).to_parquet(orderbook_dir / "MMTUSDT.parquet", index=False)
    pd.DataFrame(
        [
            {
                "transfer_time": "2026-01-02T12:00:00Z",
                "amount_usd": 250000.0,
                "direction": "inflow",
                "is_whale": True,
            }
        ]
    ).to_parquet(onchain_dir / "transfers_MMTUSDT.parquet", index=False)

    frame = phase1_prediction._feature_frame("MMTUSDT", "1h")
    row = frame[frame["open_time"] >= pd.Timestamp("2026-01-02T12:00:00Z")].iloc[0]

    assert row["liq_short_usd"] == 300.0
    assert row["liq_imbalance"] == 0.5
    assert row["long_short_ratio"] == 1.7
    assert row["orderbook_spread_bps"] == 12.0
    assert row["orderbook_slippage_500"] == 9.0
    assert row["cex_inflow_usd"] == 250000.0
    assert row["whale_transfer_count"] == 1.0
