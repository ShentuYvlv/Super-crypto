from __future__ import annotations

import pandas as pd

from super_crypto.experiments.run_experiment import build_expanded_experiment_config
from super_crypto.experiments.run_experiment import _select_parameters
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
