from __future__ import annotations

from super_crypto.common.config import load_yaml


def plan_next_experiment(config_path: str, hypothesis: str) -> dict:
    config = load_yaml(config_path)
    parameter_grid = dict(config.get("parameter_grid", {}))
    if "trade count" in hypothesis.lower():
        parameter_grid["support_break_threshold"] = sorted(
            set(parameter_grid.get("support_break_threshold", []) + [0.001, 0.002, 0.003])
        )
        parameter_grid["first_sell_pressure_threshold"] = sorted(
            set(parameter_grid.get("first_sell_pressure_threshold", []) + [-0.02, -0.015])
        )
    return {
        "base_config": config_path,
        "hypothesis": hypothesis,
        "suggested_changes": {
            "notes": hypothesis,
            "parameter_grid": parameter_grid,
        },
    }
