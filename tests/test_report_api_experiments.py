from __future__ import annotations

from super_crypto.experiments.experiment_store import ExperimentStore
from super_crypto.report_api import experiments


def test_delete_experiments_api_cascades_records_and_artifacts(tmp_path, monkeypatch):
    store = ExperimentStore(tmp_path / "experiments.db")
    report_root = tmp_path / "reports"
    report_dir = report_root / "exp-a"
    report_dir.mkdir(parents=True)
    html_path = report_dir / "report.html"
    markdown_path = report_dir / "report.md"
    trades_path = report_dir / "trades.csv"
    html_path.write_text("<html></html>", encoding="utf-8")
    markdown_path.write_text("# report", encoding="utf-8")
    trades_path.write_text("trade_id\ntrade-a\n", encoding="utf-8")
    store.upsert(
        "experiments",
        "experiment_id",
        {
            "experiment_id": "exp-a",
            "created_at": "2026-01-01T00:00:00Z",
            "report_path": str(html_path),
            "markdown_report_path": str(markdown_path),
            "trade_log_path": str(trades_path),
        },
    )
    store.bulk_upsert(
        "trades",
        "trade_id",
        [{"trade_id": "trade-a", "experiment_id": "exp-a", "signal_id": "signal-a"}],
    )
    store.upsert("signals", "signal_id", {"signal_id": "signal-a"})
    monkeypatch.setattr(experiments, "experiment_store", lambda: store)
    monkeypatch.setattr(experiments, "REPORT_ROOT", report_root)

    response = experiments.delete_experiments(
        experiments.DeleteExperimentsRequest(experiment_ids=["exp-a"])
    )

    assert response["payload"]["deleted"] == {
        "experiments": 1,
        "trades": 1,
        "signals": 1,
        "artifact_files": 3,
        "artifact_dirs": 1,
    }
    assert store.get_payload("experiments", "experiment_id", "exp-a") is None
    assert not html_path.exists()
    assert not markdown_path.exists()
    assert not trades_path.exists()
