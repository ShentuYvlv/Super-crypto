from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from super_crypto.autoresearch.artifacts import (
    delete_cycle_run_artifacts,
    delete_run_artifacts,
    latest_cycle_run_manifest,
    latest_run_manifest,
    list_cycle_run_manifests,
    list_run_manifests,
)
from super_crypto.report_api.deps import envelope, experiment_store

router = APIRouter(prefix="/api/autoresearch", tags=["autoresearch"])


class DeleteAutoResearchRunsRequest(BaseModel):
    run_ids: list[str] = Field(min_length=1, max_length=200)


class DeleteCycleResearchRunsRequest(BaseModel):
    run_ids: list[str] = Field(min_length=1, max_length=200)


@router.get("/runs")
def list_autoresearch_runs():
    return envelope(list_run_manifests(), source="autoresearch_artifacts")


@router.get("/cycle-runs")
def list_cycle_research_runs():
    return envelope(list_cycle_run_manifests(), source="cycle_research_artifacts")


@router.get("/cycle-latest")
def get_latest_cycle_research_run():
    manifest = latest_cycle_run_manifest()
    return envelope(
        manifest,
        source="cycle_research_artifacts",
        data_quality="healthy" if manifest else "empty",
    )


@router.delete("/cycle-runs")
def delete_cycle_research_runs(request: DeleteCycleResearchRunsRequest):
    try:
        deleted = delete_cycle_run_artifacts(request.run_ids)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    if not deleted["deleted_run_ids"]:
        raise HTTPException(status_code=404, detail="No matching CycleResearch runs found")
    return envelope(
        {**deleted, "requested": len(set(request.run_ids))},
        source="cycle_research_artifacts",
    )


@router.delete("/runs")
def delete_autoresearch_runs(request: DeleteAutoResearchRunsRequest):
    manifests_by_run_id = {manifest.get("run_id"): manifest for manifest in list_run_manifests()}
    try:
        deleted = delete_run_artifacts(request.run_ids)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    if not deleted["deleted_run_ids"]:
        raise HTTPException(status_code=404, detail="No matching AutoResearch runs found")
    cycle_run_ids = [
        manifest["cycle_research_result"]["run_id"]
        for run_id in deleted["deleted_run_ids"]
        if (manifest := manifests_by_run_id.get(run_id))
        and isinstance(manifest.get("cycle_research_result"), dict)
        and manifest["cycle_research_result"].get("run_id")
    ]
    deleted_cycle_runs = (
        delete_cycle_run_artifacts(cycle_run_ids)
        if cycle_run_ids
        else {"deleted_run_ids": [], "missing_run_ids": []}
    )
    cleared_experiments = experiment_store().clear_autoresearch_runs(deleted["deleted_run_ids"])
    return envelope(
        {
            **deleted,
            "requested": len(set(request.run_ids)),
            "cleared_experiments": cleared_experiments,
            "deleted_cycle_run_ids": deleted_cycle_runs["deleted_run_ids"],
            "missing_cycle_run_ids": deleted_cycle_runs["missing_run_ids"],
        },
        source="autoresearch_artifacts",
    )


@router.get("/latest")
def get_latest_autoresearch_run():
    manifest = latest_run_manifest()
    return envelope(
        manifest,
        source="autoresearch_artifacts",
        data_quality="healthy" if manifest else "empty",
    )


@router.get("/runs/{run_id}")
def get_autoresearch_run(run_id: str):
    for manifest in list_run_manifests():
        if manifest.get("run_id") == run_id:
            return envelope(manifest, source="autoresearch_artifacts")
    raise HTTPException(status_code=404, detail="AutoResearch run not found")


@router.delete("/runs/{run_id}")
def delete_autoresearch_run(run_id: str):
    return delete_autoresearch_runs(DeleteAutoResearchRunsRequest(run_ids=[run_id]))
