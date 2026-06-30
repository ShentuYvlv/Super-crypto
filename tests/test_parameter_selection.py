from __future__ import annotations

from super_crypto.experiments.run_experiment import _select_parameters


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
