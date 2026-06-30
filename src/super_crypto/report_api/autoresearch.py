from __future__ import annotations

from fastapi import APIRouter, HTTPException

from super_crypto.autoresearch.artifacts import latest_run_manifest, list_run_manifests
from super_crypto.report_api.deps import envelope

router = APIRouter(prefix="/api/autoresearch", tags=["autoresearch"])


@router.get("/runs")
def list_autoresearch_runs():
    return envelope(list_run_manifests(), source="autoresearch_artifacts")


@router.get("/latest")
def get_latest_autoresearch_run():
    manifest = latest_run_manifest()
    return envelope(manifest, source="autoresearch_artifacts", data_quality="healthy" if manifest else "empty")


@router.get("/runs/{run_id}")
def get_autoresearch_run(run_id: str):
    for manifest in list_run_manifests():
        if manifest.get("run_id") == run_id:
            return envelope(manifest, source="autoresearch_artifacts")
    raise HTTPException(status_code=404, detail="AutoResearch run not found")
