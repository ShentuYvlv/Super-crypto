from __future__ import annotations

import json
from pathlib import Path

import pytest
import yaml

from super_crypto.autoresearch import agent_loop
from super_crypto.report_api import autoresearch as autoresearch_api


class FakeExperimentStore:
    def __init__(self):
        self.payloads = [
            {
                "experiment_id": "baseline",
                "created_at": "2026-01-01T00:00:00+00:00",
                "status": "rejected",
                "metrics": {
                    "trade_count": 3,
                    "net_return": -0.01,
                    "slippage_cost": 0.0,
                    "max_drawdown": -0.02,
                },
            }
        ]

    def list_payloads(self, table: str):
        assert table == "experiments"
        return self.payloads


def _experiment_payload(experiment_id: str, trade_count: int, net_return: float) -> dict:
    return {
        "experiment": {
            "experiment_id": experiment_id,
            "created_at": "2026-01-01T01:00:00+00:00",
            "status": "completed",
            "minimum_trade_count": 2,
            "metrics": {
                "net_return": net_return,
                "sharpe": 1.2,
                "sortino": 1.3,
                "max_drawdown": -0.03,
                "profit_factor": 1.4,
                "win_rate": 0.55,
                "avg_win": 0.03,
                "avg_loss": -0.02,
                "trade_count": trade_count,
                "median_holding_minutes": 120,
                "fee_cost": 0.001,
                "slippage_cost": 0.001,
                "funding_cost": 0.0,
                "top5_removed_net_return": net_return,
            },
        },
        "trades": [
            {
                "symbol": "BTCUSDT",
                "exit_reason": "trailing_stop",
                "net_return": net_return,
            }
        ],
    }


def test_autoresearch_loop_persists_fallback_recommendation(tmp_path, monkeypatch):
    config_path = tmp_path / "experiment.yaml"
    config_path.write_text(
        yaml.safe_dump(
            {
                "name": "test",
                "parameter_grid": {
                    "support_break_threshold": [0.002],
                    "first_sell_pressure_threshold": [-0.02],
                },
            }
        ),
        encoding="utf-8",
    )
    autoresearch_config_path = tmp_path / "autoresearch.yaml"
    autoresearch_config_path.write_text(
        yaml.safe_dump(
            {
                "max_validation_runs_per_loop": 2,
                "history_window": 5,
                "allowed_config_files": [str(config_path)],
            }
        ),
        encoding="utf-8",
    )
    run_dir = tmp_path / "runs" / "run-a"
    calls = {"count": 0}

    def fake_create_run_dir(_config_path: str):
        (run_dir / "iterations").mkdir(parents=True)
        return "run-a", run_dir

    def fake_run_experiment(_config_path: str, split: str, final_flag: bool):
        calls["count"] += 1
        assert split == "validation"
        assert final_flag is False
        if calls["count"] == 1:
            return _experiment_payload("validation-1", trade_count=1, net_return=-0.02)
        return _experiment_payload("validation-2", trade_count=3, net_return=0.04)

    monkeypatch.setattr(agent_loop, "ExperimentStore", FakeExperimentStore)
    monkeypatch.setattr(agent_loop, "create_run_dir", fake_create_run_dir)
    monkeypatch.setattr(agent_loop, "write_experiment_variant", lambda _base, _plan: str(tmp_path / "variant.yaml"))
    monkeypatch.setattr(agent_loop, "holdout_guard", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(agent_loop, "run_experiment", fake_run_experiment)

    manifest = agent_loop.run_loop(
        str(config_path),
        autoresearch_config_path=str(autoresearch_config_path),
        use_llm=False,
    )

    assert manifest["status"] == "accepted"
    assert manifest["model_status"]["mode"] == "rules_fallback"
    assert len(manifest["iterations"]) == 2
    assert manifest["iterations"][1]["review"]["trade_summary"]["exit_reasons"] == {"trailing_stop": 1}
    assert "recommendation_path" in manifest
    assert Path(manifest["manifest_path"]).exists()
    assert Path(manifest["recommendation_path"]).exists()

    persisted = json.loads(Path(manifest["manifest_path"]).read_text(encoding="utf-8"))
    assert persisted["recommendation_path"] == manifest["recommendation_path"]
    assert (run_dir / "iterations" / "iteration_01.json").exists()
    assert "validation-2" in Path(manifest["recommendation_path"]).read_text(encoding="utf-8")


def test_autoresearch_rejects_unlisted_config(tmp_path):
    config_path = tmp_path / "experiment.yaml"
    config_path.write_text("name: blocked\n", encoding="utf-8")
    autoresearch_config_path = tmp_path / "autoresearch.yaml"
    autoresearch_config_path.write_text(
        yaml.safe_dump({"allowed_config_files": ["configs/experiment_v4a.yaml"]}),
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="not allowed"):
        agent_loop.run_loop(str(config_path), autoresearch_config_path=str(autoresearch_config_path), use_llm=False)


def test_autoresearch_api_returns_latest_manifest(monkeypatch):
    manifest = {"run_id": "run-a", "status": "accepted", "iterations": []}
    monkeypatch.setattr(autoresearch_api, "latest_run_manifest", lambda: manifest)

    response = autoresearch_api.get_latest_autoresearch_run()

    assert response["payload"] == manifest
    assert response["source"] == "autoresearch_artifacts"
