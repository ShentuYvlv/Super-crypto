from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter

from super_crypto.report_api.deps import envelope
from super_crypto.report_api.loaders import artifact_url, list_experiments
from super_crypto.reports.report_store import list_reports


router = APIRouter(prefix="/api/reports", tags=["reports"])


@router.get("")
def get_reports():
    experiments = {experiment["experiment_id"]: experiment for experiment in list_experiments()}
    payload = []
    for report in list_reports():
        report_path = Path(report["path"])
        experiment_id = report_path.parent.name if report_path.parent != report_path else None
        experiment = experiments.get(experiment_id or "")
        payload.append(
            {
                **report,
                "experiment_id": experiment_id,
                "strategy": experiment.get("strategy") if experiment else None,
                "split": experiment.get("split") if experiment else None,
                "url": artifact_url(report["path"]),
            }
        )
    return envelope(payload, source="filesystem")
