from __future__ import annotations

import json
from pathlib import Path

import pytest
import yaml
from fastapi.testclient import TestClient

from super_crypto.autoresearch import agent_loop
from super_crypto.autoresearch import artifacts as autoresearch_artifacts
from super_crypto.report_api import autoresearch as autoresearch_api
from super_crypto.reports import report_server


class FakeExperimentStore:
    upserted: list[dict] = []

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

    def upsert(self, table: str, key: str, payload: dict):
        assert table == "experiments"
        assert key == "experiment_id"
        self.upserted.append(payload)


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
    FakeExperimentStore.upserted = []
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
                "cycle_research_enabled": False,
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
    monkeypatch.setattr(
        agent_loop,
        "write_experiment_variant",
        lambda _base, _plan: str(tmp_path / "variant.yaml"),
    )
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
    assert manifest["iterations"][1]["started_at"]
    assert manifest["iterations"][1]["completed_at"]
    assert FakeExperimentStore.upserted[-1]["autoresearch_run_id"] == "run-a"
    assert FakeExperimentStore.upserted[-1]["autoresearch_iteration"] == 2
    assert manifest["iterations"][1]["review"]["trade_summary"]["exit_reasons"] == {
        "trailing_stop": 1
    }
    assert "recommendation_path" in manifest
    assert Path(manifest["manifest_path"]).exists()
    assert Path(manifest["recommendation_path"]).exists()

    persisted = json.loads(Path(manifest["manifest_path"]).read_text(encoding="utf-8"))
    assert persisted["recommendation_path"] == manifest["recommendation_path"]
    assert (run_dir / "iterations" / "iteration_01.json").exists()
    assert "validation-2" in Path(manifest["recommendation_path"]).read_text(encoding="utf-8")


def test_autoresearch_loop_runs_cycle_research_before_strategy(tmp_path, monkeypatch):
    FakeExperimentStore.upserted = []
    config_path = tmp_path / "experiment.yaml"
    config_path.write_text(
        yaml.safe_dump(
            {
                "name": "test",
                "engine": "event_driven",
                "minimum_trade_count": 2,
                "parameter_grid": {"support_break_threshold": [0.003]},
            }
        ),
        encoding="utf-8",
    )
    pipeline_config_path = tmp_path / "pipeline.yaml"
    pipeline_config_path.write_text("name: pipeline\n", encoding="utf-8")
    autoresearch_config_path = tmp_path / "autoresearch.yaml"
    autoresearch_config_path.write_text(
        yaml.safe_dump(
            {
                "max_validation_runs_per_loop": 1,
                "max_cycle_validation_runs": 2,
                "cycle_research_enabled": True,
                "pipeline_config_path": str(pipeline_config_path),
                "history_window": 5,
                "allowed_config_files": [str(config_path)],
            }
        ),
        encoding="utf-8",
    )
    run_dir = tmp_path / "runs" / "run-cycle"
    cycle_calls: list[dict] = []

    def fake_create_run_dir(_config_path: str):
        (run_dir / "iterations").mkdir(parents=True)
        return "run-cycle", run_dir

    def fake_cycle_research(*args, **kwargs):
        cycle_calls.append({"args": args, "kwargs": kwargs})
        return {
            "run_id": "cycle-a",
            "status": "completed",
            "pipeline_config_path": str(pipeline_config_path),
            "timeframe": "15m",
            "candidate_count": 2,
            "best_candidate_id": "cycle_01",
            "best_cycle_config": {
                "pump_threshold_min": 0.16,
                "pump_threshold_max": 0.45,
                "dump_retrace_ratio": 0.45,
                "max_cycle_hours": 48,
                "dedupe_gap_hours": 4,
            },
            "best_quality": {"score": 0.7, "cycle_count": 12, "covered_symbols": 3},
            "hypothesis": {"hypothesis": "测试周期定义。"},
        }

    monkeypatch.setattr(agent_loop, "ExperimentStore", FakeExperimentStore)
    monkeypatch.setattr(agent_loop, "create_run_dir", fake_create_run_dir)
    monkeypatch.setattr(agent_loop, "run_cycle_research", fake_cycle_research)
    monkeypatch.setattr(
        agent_loop,
        "write_experiment_variant",
        lambda _base, _plan: str(tmp_path / "variant.yaml"),
    )
    monkeypatch.setattr(agent_loop, "holdout_guard", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(
        agent_loop,
        "run_experiment",
        lambda _config_path, _split, final_flag: _experiment_payload(
            "validation-cycle",
            trade_count=3,
            net_return=0.04,
        ),
    )

    manifest = agent_loop.run_loop(
        str(config_path),
        autoresearch_config_path=str(autoresearch_config_path),
        use_llm=False,
    )

    assert len(cycle_calls) == 1
    assert cycle_calls[0]["args"][0] == str(pipeline_config_path)
    assert cycle_calls[0]["kwargs"]["max_runs"] == 2
    assert cycle_calls[0]["kwargs"]["apply_best"] is False
    assert manifest["cycle_research_result"]["run_id"] == "cycle-a"
    assert manifest["iterations"][0]["hypothesis"]["rationale"].startswith(
        "CycleResearch 最佳周期质量分"
    )
    persisted = json.loads(Path(manifest["manifest_path"]).read_text(encoding="utf-8"))
    assert persisted["cycle_research_result"]["best_candidate_id"] == "cycle_01"


def test_autoresearch_rejects_unlisted_config(tmp_path):
    config_path = tmp_path / "experiment.yaml"
    config_path.write_text("name: blocked\n", encoding="utf-8")
    autoresearch_config_path = tmp_path / "autoresearch.yaml"
    autoresearch_config_path.write_text(
        yaml.safe_dump({"allowed_config_files": ["configs/experiment_v4a.yaml"]}),
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="not allowed"):
        agent_loop.run_loop(
            str(config_path),
            autoresearch_config_path=str(autoresearch_config_path),
            use_llm=False,
        )


def test_autoresearch_api_returns_latest_manifest(monkeypatch):
    manifest = {"run_id": "run-a", "status": "accepted", "iterations": []}
    monkeypatch.setattr(autoresearch_api, "latest_run_manifest", lambda: manifest)

    response = autoresearch_api.get_latest_autoresearch_run()

    assert response["payload"] == manifest
    assert response["source"] == "autoresearch_artifacts"


def test_autoresearch_api_returns_cycle_research_detail(tmp_path, monkeypatch):
    monkeypatch.setattr(autoresearch_artifacts, "DATA_ROOT", tmp_path)
    run_dir = tmp_path / "processed" / "cycle_research" / "runs" / "cycle-a"
    final_dir = run_dir / "final"
    final_dir.mkdir(parents=True)
    best_rule_path = final_dir / "best_rule.yaml"
    cycles_path = final_dir / "cycles.csv"
    scores_path = run_dir / "candidate_scores.csv"
    best_rule_path.write_text(
        yaml.safe_dump(
            {
                "timeframe": "1h",
                "pump_threshold_min": 0.2,
                "dump_return_min": 0.12,
            }
        ),
        encoding="utf-8",
    )
    cycles_path.write_text(
        "\n".join(
            [
                "cycle_id,symbol,pump_return,dump_return,duration_hours",
                "RIVERUSDT_1,RIVERUSDT,0.35,-0.18,24",
                "RIVERUSDT_2,RIVERUSDT,0.25,-0.14,18",
                "STOUSDT_1,STOUSDT,0.22,-0.16,30",
            ]
        ),
        encoding="utf-8",
    )
    scores_path.write_text(
        "candidate_id,score,cycle_count,rejection_reason\ncycle_01,0.82,3,\n",
        encoding="utf-8",
    )
    (run_dir / "manifest.json").write_text(
        json.dumps(
            {
                "run_id": "cycle-a",
                "status": "completed",
                "best_rule_path": str(best_rule_path),
                "best_cycles_csv_path": str(cycles_path),
                "candidate_scores_path": str(scores_path),
            }
        ),
        encoding="utf-8",
    )

    response = autoresearch_api.get_cycle_research_run("cycle-a")
    payload = response["payload"]

    assert payload["best_rule"]["timeframe"] == "1h"
    assert payload["cycle_count"] == 3
    assert payload["cycles"][0]["symbol"] == "RIVERUSDT"
    assert payload["candidate_scores"][0]["candidate_id"] == "cycle_01"
    assert payload["candidate_scores"][0]["rejection_reason"] is None
    assert payload["cycles_by_symbol_summary"][0]["symbol"] == "RIVERUSDT"
    assert payload["cycles_by_symbol_summary"][0]["cycle_count"] == 2

    monkeypatch.setattr(report_server, "ensure_dashboard_built", lambda: None)
    monkeypatch.setattr(report_server, "DASHBOARD_OUT", tmp_path)
    monkeypatch.setattr(report_server, "REPORT_ROOT", tmp_path)
    http_response = TestClient(report_server.create_server_app()).get(
        "/api/autoresearch/cycle-runs/cycle-a"
    )

    assert http_response.status_code == 200
    assert http_response.json()["payload"]["candidate_scores"][0]["rejection_reason"] is None


def test_autoresearch_artifacts_localize_english_recommendations(tmp_path, monkeypatch):
    monkeypatch.setattr(autoresearch_artifacts, "DATA_ROOT", tmp_path)
    run_dir = tmp_path / "processed" / "autoresearch" / "runs" / "run-a"
    run_dir.mkdir(parents=True)
    (run_dir / "manifest.json").write_text(
        json.dumps(
            {
                "run_id": "run-a",
                "created_at": "2026-01-01T00:00:00Z",
                "status": "rejected",
                "recommendation": "Increase signal coverage before judging profitability.",
                "iterations": [
                    {
                        "hypothesis": {
                            "hypothesis": "Increase signal coverage before judging profitability.",
                            "rationale": (
                                "Generated by rules fallback from recent experiment metrics."
                            ),
                            "risk": "May miss regime changes.",
                        },
                        "plan": {
                            "suggested_changes": {
                                "notes": "Increase signal coverage before judging profitability."
                            }
                        },
                        "review": {
                            "decision": "Increase signal coverage before judging profitability.",
                            "recommendation": (
                                "Increase signal coverage before judging profitability."
                            ),
                            "evidence": ["Increase signal coverage before judging profitability."],
                        },
                    }
                ],
            }
        ),
        encoding="utf-8",
    )

    manifest = autoresearch_artifacts.latest_run_manifest()

    assert manifest is not None
    assert manifest["recommendation"] == "先提高信号覆盖率，再判断盈利能力。"
    assert (
        manifest["iterations"][0]["review"]["recommendation"]
        == "先提高信号覆盖率，再判断盈利能力。"
    )
    assert manifest["iterations"][0]["hypothesis"]["rationale"].startswith("模型返回了英文内容")


def test_delete_autoresearch_runs_removes_artifacts_and_clears_experiment_links(
    tmp_path,
    monkeypatch,
):
    class FakeStore:
        cleared: list[str] = []

        def clear_autoresearch_runs(self, run_ids: list[str]) -> int:
            self.cleared.extend(run_ids)
            return len(run_ids)

    store = FakeStore()
    monkeypatch.setattr(autoresearch_artifacts, "DATA_ROOT", tmp_path)
    monkeypatch.setattr(autoresearch_api, "experiment_store", lambda: store)
    run_dir = tmp_path / "processed" / "autoresearch" / "runs" / "run-a"
    run_dir.mkdir(parents=True)
    cycle_dir = tmp_path / "processed" / "cycle_research" / "runs" / "cycle-a"
    cycle_dir.mkdir(parents=True)
    (cycle_dir / "manifest.json").write_text("{}", encoding="utf-8")
    (run_dir / "manifest.json").write_text(
        json.dumps({"run_id": "run-a", "cycle_research_result": {"run_id": "cycle-a"}}),
        encoding="utf-8",
    )

    response = autoresearch_api.delete_autoresearch_runs(
        autoresearch_api.DeleteAutoResearchRunsRequest(run_ids=["run-a"])
    )

    assert response["payload"]["deleted_run_ids"] == ["run-a"]
    assert response["payload"]["cleared_experiments"] == 1
    assert response["payload"]["deleted_cycle_run_ids"] == ["cycle-a"]
    assert store.cleared == ["run-a"]
    assert not run_dir.exists()
    assert not cycle_dir.exists()


def test_report_server_allows_autoresearch_delete_before_static_mount(tmp_path, monkeypatch):
    class FakeStore:
        def clear_autoresearch_runs(self, run_ids: list[str]) -> int:
            return len(run_ids)

    dashboard_out = tmp_path / "dashboard"
    dashboard_out.mkdir()
    (dashboard_out / "index.html").write_text("<html></html>", encoding="utf-8")
    report_root = tmp_path / "reports"
    report_root.mkdir()
    run_dir = tmp_path / "processed" / "autoresearch" / "runs" / "run-a"
    run_dir.mkdir(parents=True)
    (run_dir / "manifest.json").write_text("{}", encoding="utf-8")
    monkeypatch.setattr(report_server, "ensure_dashboard_built", lambda: None)
    monkeypatch.setattr(report_server, "DASHBOARD_OUT", dashboard_out)
    monkeypatch.setattr(report_server, "REPORT_ROOT", report_root)
    monkeypatch.setattr(autoresearch_artifacts, "DATA_ROOT", tmp_path)
    monkeypatch.setattr(autoresearch_api, "experiment_store", lambda: FakeStore())

    response = TestClient(report_server.create_server_app()).request(
        "DELETE",
        "/api/autoresearch/runs",
        json={"run_ids": ["run-a"]},
    )

    assert response.status_code == 200
    assert response.json()["payload"]["deleted_run_ids"] == ["run-a"]
