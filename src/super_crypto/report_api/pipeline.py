from __future__ import annotations

from fastapi import APIRouter, HTTPException

from super_crypto.report_api.deps import envelope, pipeline_store
from super_crypto.report_api.loaders import list_pipeline_runs

router = APIRouter(prefix="/api/pipeline", tags=["pipeline"])


@router.get("/runs")
def list_runs():
    return envelope(list_pipeline_runs())


@router.get("/runs/{run_id}")
def get_run(run_id: str):
    runs = {run["run_id"]: run for run in list_pipeline_runs()}
    run = runs.get(run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="Pipeline run not found")
    run["stages"] = sorted(
        pipeline_store().list_stages(run_id),
        key=lambda item: item.get("started_at", ""),
    )
    return envelope(run)
