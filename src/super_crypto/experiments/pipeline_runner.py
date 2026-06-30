from __future__ import annotations

import json
import subprocess
from hashlib import sha256
from pathlib import Path
from typing import Any

import pandas as pd

from super_crypto.common.config import hash_file, load_yaml
from super_crypto.common.paths import DATA_ROOT
from super_crypto.common.time import to_iso, utc_now
from super_crypto.cycles.label_cycles import run as label_cycles
from super_crypto.data.ingest_coinglass import run as ingest_coinglass
from super_crypto.data.ingest_funding import run as ingest_funding
from super_crypto.data.ingest_klines import run as ingest_klines
from super_crypto.data.ingest_market_snapshots import run as ingest_market_snapshots
from super_crypto.data.ingest_open_interest import run as ingest_open_interest
from super_crypto.data.ingest_orderbook import run as ingest_orderbook
from super_crypto.experiments.experiment_store import ExperimentStore
from super_crypto.experiments.pipeline_store import PipelineStore
from super_crypto.experiments.run_experiment import run as run_experiment
from super_crypto.universe.manipulation_score import score_symbols, write_scores
from super_crypto.validation.splits import build_split_manifest, holdout_guard, split_hash


def _git_commit_hash() -> str:
    try:
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            capture_output=True,
            text=True,
            check=True,
        )
        return result.stdout.strip()
    except Exception:
        return "unknown"


def _snapshot_hash() -> str:
    payload = []
    for path in sorted((DATA_ROOT / "processed").rglob("*.parquet")):
        payload.append(
            {
                "path": str(path),
                "mtime": path.stat().st_mtime_ns,
                "size": path.stat().st_size,
            }
        )
    if not payload:
        return hash_file("configs/pipeline_v4a.yaml")
    snapshot = json.dumps(payload, sort_keys=True, ensure_ascii=False)
    return sha256(snapshot.encode()).hexdigest()


PIPELINE_STAGES = [
    "ingest",
    "build_splits",
    "detect_cycles",
    "score_symbols",
    "enrich",
    "run_experiment",
    "report",
]


def _stage_config(pipeline_config: dict[str, Any], stage: str) -> dict[str, Any]:
    stages = pipeline_config.get("stages", {})
    if not isinstance(stages, dict):
        return {}
    config = stages.get(stage, {})
    return config if isinstance(config, dict) else {}


def _stage_enabled(pipeline_config: dict[str, Any], stage: str) -> bool:
    return bool(_stage_config(pipeline_config, stage).get("enabled", True))


def _is_stage_fresh(output_paths: list[Path], freshness_seconds: int) -> bool:
    if not output_paths or not all(path.exists() for path in output_paths):
        return False
    oldest_output = min(path.stat().st_mtime for path in output_paths)
    return utc_now().timestamp() - oldest_output <= freshness_seconds


def _has_existing_outputs(output_paths: list[Path]) -> bool:
    return bool(output_paths) and all(path.exists() for path in output_paths)


def _ingest_output_paths(symbols: list[str], timeframes: list[str]) -> list[Path]:
    paths: list[Path] = []
    for symbol in symbols:
        paths.extend(
            [
                DATA_ROOT / "processed" / "ohlcv" / timeframe / f"{symbol}.parquet"
                for timeframe in timeframes
            ]
        )
        paths.extend(
            [
                DATA_ROOT / "processed" / "derivatives" / f"funding_{symbol}.parquet",
                DATA_ROOT / "processed" / "derivatives" / f"open_interest_{symbol}.parquet",
            ]
        )
    return paths


def _enrichment_output_paths(symbols: list[str], endpoints: list[str]) -> list[Path]:
    paths: list[Path] = []
    for symbol in symbols:
        paths.append(DATA_ROOT / "processed" / "orderbook_features" / f"{symbol}.parquet")
        paths.extend(
            [
                DATA_ROOT / "processed" / "external_enrichment" / f"{endpoint}_{symbol}.parquet"
                for endpoint in endpoints
            ]
        )
    return paths


def _stage_skip_reason(pipeline_config: dict[str, Any], stage: str, split: str) -> str | None:
    config = _stage_config(pipeline_config, stage)
    if not _stage_enabled(pipeline_config, stage):
        return "disabled"

    data_config_path = pipeline_config.get("data_config", "configs/data.yaml")
    try:
        data_config = load_yaml(data_config_path)
    except Exception:
        data_config = {}
    symbols = data_config.get("symbols", [])
    timeframes = data_config.get("timeframes", [])

    if stage == "ingest" and config.get("skip_if_fresh"):
        freshness_seconds = int(float(config.get("freshness_hours", 0)) * 3600)
        outputs = _ingest_output_paths(symbols, timeframes)
        if freshness_seconds > 0 and _is_stage_fresh(outputs, freshness_seconds):
            return "fresh_outputs"

    if (
        stage == "build_splits"
        and config.get("skip_if_exists")
        and (DATA_ROOT / "processed" / "split_manifest.json").exists()
    ):
        return "existing_split_manifest"

    if stage == "detect_cycles" and not config.get("rebuild", True):
        outputs = [DATA_ROOT / "processed" / "cycles" / f"{symbol}.parquet" for symbol in symbols]
        if _has_existing_outputs(outputs):
            return "existing_cycle_outputs"

    if stage == "enrich" and config.get("skip_if_fresh"):
        freshness_seconds = int(float(config.get("freshness_minutes", 0)) * 60)
        try:
            enrichment_config = load_yaml(pipeline_config.get("enrichment_config", ""))
        except Exception:
            enrichment_config = {}
        endpoints = enrichment_config.get("coinglass", {}).get("endpoints", [])
        top_n = int(enrichment_config.get("candidate_selection", {}).get("top_n_by_score", 0))
        selected_symbols = symbols[:top_n] if top_n > 0 else symbols
        outputs = _enrichment_output_paths(selected_symbols, endpoints)
        if freshness_seconds > 0 and _is_stage_fresh(outputs, freshness_seconds):
            return "fresh_outputs"

    return None


def run_pipeline(
    config_path: str,
    split: str,
    *,
    from_stage: str | None = None,
    only_stage: str | None = None,
    resume: bool = False,
    final_flag: bool = False,
) -> dict:
    pipeline_config = load_yaml(config_path)
    run_id = hash_file(config_path)[:12] + "-" + split
    store = PipelineStore()
    experiment_store = ExperimentStore()
    holdout_guard("configs/splits.yaml", split, final_flag, experiment_store.holdout_run_count())
    previous_run = next((run for run in store.list_runs() if run.get("run_id") == run_id), {})
    pipeline_run = {
        "run_id": run_id,
        "name": pipeline_config["name"],
        "split": split,
        "status": "running",
        "config_hash": hash_file(config_path),
        "split_hash": split_hash("configs/splits.yaml"),
        "data_snapshot_hash": previous_run.get("data_snapshot_hash", ""),
        "git_commit_hash": _git_commit_hash(),
        "report_path": previous_run.get("report_path"),
        "created_at": previous_run.get("created_at", to_iso(utc_now())),
        "updated_at": to_iso(utc_now()),
    }
    store.upsert_run(pipeline_run)
    stage_results: dict[str, dict] = {}
    completed_on_resume = set()
    if resume:
        completed_on_resume = {
            stage["stage"]
            for stage in store.list_stages(run_id)
            if stage.get("status") == "completed"
        }
    should_execute = from_stage is None
    for stage in PIPELINE_STAGES:
        if only_stage and stage != only_stage:
            continue
        if resume and stage in completed_on_resume and only_stage is None and from_stage is None:
            continue
        if not should_execute and stage == from_stage:
            should_execute = True
        if not should_execute:
            continue
        skip_reason = _stage_skip_reason(pipeline_config, stage, split)
        if skip_reason and not only_stage:
            skipped_payload = {
                "run_id": run_id,
                "stage": stage,
                "status": "skipped",
                "started_at": to_iso(utc_now()),
                "completed_at": to_iso(utc_now()),
                "details": {"reason": skip_reason},
            }
            store.upsert_stage(skipped_payload)
            stage_results[stage] = skipped_payload["details"]
            continue
        stage_payload = {
            "run_id": run_id,
            "stage": stage,
            "status": "running",
            "started_at": to_iso(utc_now()),
            "completed_at": None,
            "details": {},
        }
        store.upsert_stage(stage_payload)
        try:
            if stage == "ingest":
                details = {
                    "market_snapshots": ingest_market_snapshots(pipeline_config["data_config"]),
                    "klines": ingest_klines(pipeline_config["data_config"]),
                    "funding": ingest_funding(pipeline_config["data_config"]),
                    "open_interest": ingest_open_interest(pipeline_config["data_config"]),
                }
            elif stage == "build_splits":
                details = build_split_manifest(pipeline_config["splits_config"])
            elif stage == "detect_cycles":
                data_config = load_yaml(pipeline_config["data_config"])
                details = label_cycles(
                    pipeline_config["cycle_config"], data_config["symbols"], timeframe="1h"
                )
            elif stage == "score_symbols":
                cycle_frames = []
                derivatives = {}
                for cycle_path in (DATA_ROOT / "processed" / "cycles").glob("*.parquet"):
                    frame = pd.read_parquet(cycle_path)
                    frame["pump_start"] = pd.to_datetime(frame["pump_start"], utc=True)
                    cycle_frames.append(frame)
                    symbol = cycle_path.stem
                    oi_path = (
                        DATA_ROOT
                        / "processed"
                        / "derivatives"
                        / f"open_interest_{symbol}.parquet"
                    )
                    if oi_path.exists():
                        derivatives[symbol] = pd.read_parquet(oi_path)
                cycles = (
                    pd.concat(cycle_frames, ignore_index=True)
                    if cycle_frames
                    else pd.DataFrame()
                )
                scores = score_symbols(
                    cycles,
                    cutoff_time=utc_now(),
                    config=load_yaml(pipeline_config["scores_config"]),
                    derivatives_by_symbol=derivatives,
                )
                path = write_scores(
                    str(DATA_ROOT / "processed" / "scores" / "latest.parquet"),
                    scores,
                )
                details = {"score_count": len(scores), "path": path}
            elif stage == "enrich":
                enrichment_config = load_yaml(pipeline_config["enrichment_config"])
                symbols = load_yaml(pipeline_config["data_config"])["symbols"][
                    : enrichment_config["candidate_selection"]["top_n_by_score"]
                ]
                details = {
                    "coinglass": ingest_coinglass(
                        pipeline_config["enrichment_config"],
                        symbols=symbols,
                    ),
                    "orderbook": ingest_orderbook(
                        pipeline_config["enrichment_config"],
                        symbols=symbols,
                    ),
                }
            elif stage == "run_experiment":
                details = run_experiment(
                    pipeline_config["experiment_config"],
                    split,
                    final_flag=final_flag,
                )
                pipeline_run["report_path"] = details["html_report"]
            else:
                details = {"report_path": pipeline_run["report_path"]}
        except Exception as exc:
            stage_payload["status"] = "failed"
            stage_payload["completed_at"] = to_iso(utc_now())
            stage_payload["details"] = {"error": str(exc)}
            store.upsert_stage(stage_payload)
            pipeline_run["status"] = "failed"
            pipeline_run["data_snapshot_hash"] = _snapshot_hash()
            pipeline_run["updated_at"] = to_iso(utc_now())
            store.upsert_run(pipeline_run)
            raise
        stage_payload["status"] = "completed"
        stage_payload["completed_at"] = to_iso(utc_now())
        stage_payload["details"] = details
        store.upsert_stage(stage_payload)
        stage_results[stage] = details
    pipeline_run["status"] = "completed"
    pipeline_run["data_snapshot_hash"] = _snapshot_hash()
    pipeline_run["updated_at"] = to_iso(utc_now())
    store.upsert_run(pipeline_run)
    return {"pipeline_run": pipeline_run, "stages": stage_results}
