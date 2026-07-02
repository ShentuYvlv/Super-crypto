from __future__ import annotations

import math
from pathlib import Path
from typing import Any

import pandas as pd
import yaml
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


def _json_safe(value: Any) -> Any:
    if isinstance(value, float):
        return value if math.isfinite(value) else None
    if isinstance(value, dict):
        return {key: _json_safe(nested_value) for key, nested_value in value.items()}
    if isinstance(value, list):
        return [_json_safe(item) for item in value]
    return value


def _read_table(path: str | None, *, limit: int = 1000) -> list[dict[str, Any]]:
    if not path:
        return []
    file_path = Path(path)
    if not file_path.exists():
        return []
    frame = pd.read_parquet(file_path) if file_path.suffix == ".parquet" else pd.read_csv(file_path)
    rows = frame.head(limit).astype(object).where(pd.notna(frame), None).to_dict(orient="records")
    return _json_safe(rows)


def _read_yaml(path: str | None) -> dict[str, Any]:
    if not path:
        return {}
    file_path = Path(path)
    if not file_path.exists():
        return {}
    loaded = yaml.safe_load(file_path.read_text(encoding="utf-8")) or {}
    return loaded if isinstance(loaded, dict) else {}


def _cycle_run_detail(manifest: dict[str, Any]) -> dict[str, Any]:
    cycles = _read_table(manifest.get("best_cycles_csv_path"), limit=2000)
    candidate_scores = _read_table(manifest.get("candidate_scores_path"), limit=500)
    best_rule = _read_yaml(manifest.get("best_rule_path"))
    by_symbol: dict[str, dict[str, Any]] = {}
    for row in cycles:
        symbol = str(row.get("symbol") or "")
        if not symbol:
            continue
        current = by_symbol.setdefault(
            symbol,
            {
                "symbol": symbol,
                "cycle_count": 0,
                "median_pump_return": 0.0,
                "median_dump_return": 0.0,
                "median_duration_hours": 0.0,
            },
        )
        current["cycle_count"] += 1
    if cycles:
        frame = pd.DataFrame(cycles)
        for symbol, group in frame.groupby("symbol"):
            by_symbol[str(symbol)] = {
                "symbol": str(symbol),
                "cycle_count": int(len(group)),
                "median_pump_return": float(pd.to_numeric(group["pump_return"]).median()),
                "median_dump_return": float(pd.to_numeric(group["dump_return"]).median()),
                "median_duration_hours": float(pd.to_numeric(group["duration_hours"]).median()),
            }
    return _json_safe(
        {
            **manifest,
            "best_rule": best_rule,
            "cycles": cycles,
            "cycle_count": len(cycles),
            "cycles_by_symbol_summary": sorted(
                by_symbol.values(),
                key=lambda item: item["cycle_count"],
                reverse=True,
            ),
            "candidate_scores": candidate_scores,
        }
    )


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
        _cycle_run_detail(manifest) if manifest else None,
        source="cycle_research_artifacts",
        data_quality="healthy" if manifest else "empty",
    )


@router.get("/cycle-runs/{run_id}")
def get_cycle_research_run(run_id: str):
    for manifest in list_cycle_run_manifests():
        if manifest.get("run_id") == run_id:
            return envelope(_cycle_run_detail(manifest), source="cycle_research_artifacts")
    raise HTTPException(status_code=404, detail="CycleResearch run not found")


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
