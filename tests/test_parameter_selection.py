from __future__ import annotations

from datetime import UTC, datetime

import pandas as pd
import pytest
import yaml

from super_crypto.common.types import TradeRecord
from super_crypto.experiments import run_experiment
from super_crypto.experiments.run_experiment import (
    _load_holdout_frozen_config,
    _select_parameters,
    build_expanded_experiment_config,
    freeze_selected_experiment_config,
)
from super_crypto.validation.splits import filter_frame_for_split


def test_select_parameters_prefers_accepted_grid_candidate():
    params, source, reason = _select_parameters(
        [
            {
                "params": {"support_break_threshold": 0.001},
                "metrics": {
                    "trade_count": 25,
                    "net_return": 0.08,
                    "max_drawdown": -0.03,
                },
            }
        ],
        {"trade_count": 10, "net_return": 0.02, "max_drawdown": -0.02},
        minimum_trade_count=20,
        allow_selection=True,
    )

    assert params == {"support_break_threshold": 0.001}
    assert source == "parameter_grid"
    assert reason == "accepted"


def test_select_parameters_is_disabled_for_holdout():
    params, source, _reason = _select_parameters(
        [
            {
                "params": {"support_break_threshold": 0.001},
                "metrics": {
                    "trade_count": 25,
                    "net_return": 0.08,
                    "max_drawdown": -0.03,
                },
            }
        ],
        {"trade_count": 10, "net_return": 0.02, "max_drawdown": -0.02},
        minimum_trade_count=20,
        allow_selection=False,
    )

    assert params == {}
    assert source == "base_strategy_config"


def test_build_expanded_experiment_config_inlines_referenced_configs():
    expanded = build_expanded_experiment_config("configs/experiment_v4a_full.yaml")

    assert "strategy_config" not in expanded
    assert "backtest_config" not in expanded
    assert "scores_config" not in expanded
    assert expanded["strategy"]["strategy"] == "V4A"
    assert expanded["backtest"]["capital_per_trade_usdt"] == 1000
    assert expanded["scores"]["weights"]["cycle_frequency"] == 0.5
    assert expanded["splits"]["validation"]["symbols"]
    assert "symbol_split_files" not in expanded["splits"]


def test_inline_split_symbols_filter_frame():
    frame = pd.DataFrame(
        [
            {"symbol": "BTCUSDT", "open_time": "2026-01-02T00:00:00Z", "close": 1},
            {"symbol": "ETHUSDT", "open_time": "2026-01-02T00:00:00Z", "close": 2},
            {"symbol": "BTCUSDT", "open_time": "2026-02-01T00:00:00Z", "close": 3},
        ]
    )
    split_config = {
        "train": {
            "start": "2026-01-01T00:00:00Z",
            "end": "2026-01-31T23:59:59Z",
            "symbols": ["BTCUSDT"],
        },
        "validation": {
            "start": "2026-02-01T00:00:00Z",
            "end": "2026-02-28T23:59:59Z",
            "symbols": ["ETHUSDT"],
        },
        "holdout": {
            "start": "2026-03-01T00:00:00Z",
            "end": "2026-03-31T23:59:59Z",
            "symbols": ["BTCUSDT"],
        },
        "purge_bars": 2,
    }

    filtered = filter_frame_for_split(frame, split_config, "train")

    assert filtered["close"].tolist() == [1]


def test_split_symbols_are_inherited_by_each_split():
    frame = pd.DataFrame(
        [
            {"symbol": "BTCUSDT", "open_time": "2026-01-02T00:00:00Z", "close": 1},
            {"symbol": "ETHUSDT", "open_time": "2026-01-02T00:00:00Z", "close": 2},
        ]
    )
    split_config = {
        "symbols": ["ETHUSDT"],
        "train": {
            "start": "2026-01-01T00:00:00Z",
            "end": "2026-01-31T23:59:59Z",
        },
        "validation": {
            "start": "2026-02-01T00:00:00Z",
            "end": "2026-02-28T23:59:59Z",
        },
        "holdout": {
            "start": "2026-03-01T00:00:00Z",
            "end": "2026-03-31T23:59:59Z",
        },
        "purge_bars": 2,
    }

    filtered = filter_frame_for_split(frame, split_config, "train")

    assert filtered["symbol"].tolist() == ["ETHUSDT"]


def _split_config() -> dict:
    return {
        "train": {
            "start": "2026-01-01T00:00:00Z",
            "end": "2026-01-31T23:59:59Z",
            "symbols": ["BTCUSDT"],
        },
        "validation": {
            "start": "2026-02-01T00:00:00Z",
            "end": "2026-02-28T23:59:59Z",
            "symbols": ["BTCUSDT"],
        },
        "holdout": {
            "start": "2026-03-01T00:00:00Z",
            "end": "2026-03-31T23:59:59Z",
            "symbols": ["BTCUSDT"],
        },
        "purge_bars": 2,
        "holdout_policy": {
            "require_final_flag": True,
            "max_manual_runs": 1,
        },
    }


def test_freeze_selected_experiment_config_writes_selected_strategy(tmp_path, monkeypatch):
    monkeypatch.setattr(run_experiment, "DATA_ROOT", tmp_path)

    path = freeze_selected_experiment_config(
        experiment_config={
            "name": "v4a_research",
            "engine": "event_driven",
            "parameter_grid": {"support_break_threshold": [0.001, 0.002]},
        },
        strategy_config={
            "strategy": "V4A",
            "timeframe": "1h",
            "support_break_threshold": 0.001,
            "max_hold_bars": 8,
        },
        backtest_config={"capital_per_trade_usdt": 1000},
        scores_config={"weights": {"cycle_frequency": 0.5}},
        splits_config=_split_config(),
        selected_parameters={"support_break_threshold": 0.002},
        source_experiment_id="exp-1",
        source_config_hash="config-hash",
        source_split_hash="split-hash",
        created_at="2026-07-01T00:00:00Z",
    )

    frozen_path = tmp_path / "processed" / "frozen_configs" / "v4a_selected.yaml"
    frozen = yaml.safe_load(frozen_path.read_text())

    assert path.endswith("v4a_selected.yaml")
    assert frozen["name"] == "v4a_research_frozen"
    assert frozen["strategy"]["support_break_threshold"] == 0.002
    assert frozen["parameter_grid"] == {}
    assert frozen["frozen_from"]["experiment_id"] == "exp-1"
    assert frozen["frozen_from"]["selected_parameters"] == {"support_break_threshold": 0.002}
    assert "symbol_split_files" not in frozen["splits"]


def test_load_holdout_frozen_config_reports_missing_default_path(tmp_path, monkeypatch):
    monkeypatch.setattr(run_experiment, "DATA_ROOT", tmp_path)

    frozen, missing_path = _load_holdout_frozen_config({}, "V4A")

    assert frozen is None
    assert missing_path == str(tmp_path / "processed" / "frozen_configs" / "v4a_selected.yaml")


def test_holdout_requires_frozen_config_before_loading_market_data(tmp_path, monkeypatch):
    monkeypatch.setattr(run_experiment, "DATA_ROOT", tmp_path)

    with pytest.raises(ValueError, match="Holdout requires a frozen config"):
        run_experiment.run(
            {
                "name": "v4a_research",
                "engine": "event_driven",
                "strategy": {"strategy": "V4A", "timeframe": "1h"},
                "backtest": {},
                "scores": {},
                "splits": _split_config(),
            },
            split="holdout",
            final_flag=True,
        )


def test_rejected_train_validation_does_not_freeze_selected_config(tmp_path, monkeypatch):
    monkeypatch.setattr(run_experiment, "DATA_ROOT", tmp_path)
    monkeypatch.setattr(run_experiment, "REPORT_ROOT", tmp_path / "reports")
    monkeypatch.setattr(run_experiment, "_git_commit_hash", lambda: "git-hash")
    monkeypatch.setattr(run_experiment, "_data_snapshot_hash", lambda _paths: "data-hash")
    monkeypatch.setattr(run_experiment, "_load_scores", lambda *_args, **_kwargs: [])
    monkeypatch.setattr(
        run_experiment,
        "latest_orderbook_metrics",
        lambda _orderbook: {"slippage_500": 0},
    )
    monkeypatch.setattr(run_experiment, "render_markdown_report", lambda path, _ctx: str(path))
    monkeypatch.setattr(run_experiment, "render_html_report", lambda path, _ctx: str(path))
    monkeypatch.setattr(
        run_experiment,
        "run_vectorbt_benchmark",
        lambda **_kwargs: {"status": "skipped"},
    )
    monkeypatch.setattr(run_experiment, "split_hash", lambda _config: "split-hash")

    ohlcv_dir = tmp_path / "processed" / "ohlcv" / "1h"
    ohlcv_dir.mkdir(parents=True)
    pd.DataFrame(
        [
            {
                "symbol": "BTCUSDT",
                "open_time": "2026-01-02T00:00:00Z",
                "close_time": "2026-01-02T01:00:00Z",
                "open": 100,
                "high": 101,
                "low": 99,
                "close": 100,
                "volume": 1,
            }
        ]
    ).to_parquet(ohlcv_dir / "BTCUSDT.parquet")

    def fake_strategy(*_args, **_kwargs):
        return []

    def fake_parameter_scan(**_kwargs):
        return [
            {
                "params": {"support_break_threshold": 0.002},
                "signal_count": 1,
                "metrics": {
                    "trade_count": 30,
                    "net_return": 0.2,
                    "max_drawdown": -0.01,
                },
            }
        ]

    def fake_run_strategy(**_kwargs):
        trade = TradeRecord(
            trade_id="trade-1",
            signal_id="signal-1",
            symbol="BTCUSDT",
            strategy="V4A",
            split="train_validation",
            source="backtest",
            side="SHORT",
            entry_time=datetime(2026, 1, 2, tzinfo=UTC),
            entry_price=100,
            exit_time=datetime(2026, 1, 2, 1, tzinfo=UTC),
            exit_price=101,
            gross_return=-0.01,
            fee_cost=0,
            slippage_cost=0,
            funding_cost=0,
            net_return=-0.01,
            exit_reason="max_hold",
            holding_minutes=60,
            mae=-0.01,
            mfe=0,
            orderbook_snapshot_status="partial",
        )
        return [], [trade.model_dump(mode="json")]

    class FakeStore:
        def upsert(self, *_args, **_kwargs):
            return None

        def bulk_upsert(self, *_args, **_kwargs):
            return None

    monkeypatch.setitem(run_experiment.GENERATOR_MAP, "V4A", fake_strategy)
    monkeypatch.setattr(run_experiment, "_parameter_scan", fake_parameter_scan)
    monkeypatch.setattr(run_experiment, "_run_strategy_for_config", fake_run_strategy)
    monkeypatch.setattr(run_experiment, "ExperimentStore", lambda: FakeStore())

    result = run_experiment.run(
        {
            "name": "v4a_research",
            "engine": "event_driven",
            "minimum_trade_count": 20,
            "strategy": {
                "strategy": "V4A",
                "timeframe": "1h",
                "max_hold_bars": 8,
            },
            "backtest": {
                "capital_per_trade_usdt": 1000,
                "fee_bps": 5,
                "slippage_bps_floor": 1,
                "max_hold_hours": {"v4a": 8},
            },
            "scores": {},
            "splits": _split_config(),
            "parameter_grid": {"support_break_threshold": [0.002]},
        },
        split="train_validation",
    )

    assert result["experiment"]["status"] == "rejected"
    assert result["experiment"]["frozen_config_path"] is None
    assert not (tmp_path / "processed" / "frozen_configs" / "v4a_selected.yaml").exists()
