from __future__ import annotations

from super_crypto.report_api import overview


def test_overview_tolerates_legacy_experiment_metrics_without_net_return(monkeypatch):
    monkeypatch.setattr(
        overview,
        "list_experiments",
        lambda: [
            {
                "experiment_id": "phase1-old",
                "name": "phase1_prediction",
                "strategy": "PHASE1",
                "split": "train_validation",
                "status": "completed",
                "created_at": "2026-07-02T04:21:29Z",
                "metrics": {
                    "f1": 0.66,
                    "auc": 0.66,
                    "sample_count": 4,
                },
            }
        ],
    )
    monkeypatch.setattr(overview, "list_signals", lambda: [])
    monkeypatch.setattr(overview, "list_trades", lambda include_paper=False: [])
    monkeypatch.setattr(overview, "load_paper_trades", lambda: [])
    monkeypatch.setattr(overview, "load_scanner_status", lambda: None)
    monkeypatch.setattr(overview, "list_pipeline_runs", lambda: [])
    monkeypatch.setattr(overview, "latest_pipeline_stage", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(overview, "latest_run_manifest", lambda: None)
    monkeypatch.setattr(overview, "_latest_frozen_config_status", lambda _experiments: {
        "available": False,
        "path": None,
        "source_experiment_id": None,
        "created_at": None,
    })
    monkeypatch.setattr(
        overview,
        "ExperimentStore",
        lambda: type("Store", (), {"holdout_run_count": lambda self: 0})(),
    )

    response = overview.get_overview()
    payload = response["payload"]

    assert payload["validation_best_net_return"] == 0.0
    assert payload["max_drawdown"] == 0.0
    assert payload["latest_research_run"] is None
    assert payload["latest_validation_experiment"] is None
    assert payload["latest_holdout_experiment"] is None
    assert payload["frozen_config"]["available"] is False
    assert payload["holdout_status"]["run_count"] == 0
    assert payload["holdout_status"]["status"] == "not_run"
    assert payload["performance_snapshot"]["split_comparison"] == [
        {
            "split": "train_validation",
            "net_return": 0.0,
            "trade_count": 4,
            "status": "completed",
        }
    ]
