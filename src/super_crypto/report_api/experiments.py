from __future__ import annotations

from pathlib import Path
from typing import Any

import pandas as pd
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from super_crypto.backtest.metrics import equity_curve
from super_crypto.common.paths import REPORT_ROOT
from super_crypto.report_api.deps import envelope, experiment_store
from super_crypto.report_api.loaders import (
    artifact_url,
    frame_to_records,
    list_signals,
    read_csv_if_exists,
    read_yaml_if_exists,
)
from super_crypto.report_api.loaders import (
    list_experiments as load_experiments,
)
from super_crypto.validation.robustness import by_month, by_symbol

router = APIRouter(prefix="/api/experiments", tags=["experiments"])


class DeleteExperimentsRequest(BaseModel):
    experiment_ids: list[str] = Field(min_length=1, max_length=200)
    delete_artifacts: bool = True


def _delete_artifacts(experiments: list[dict[str, Any]]) -> dict[str, int]:
    deleted_files = 0
    deleted_dirs = 0
    report_root = REPORT_ROOT.resolve()
    for experiment in experiments:
        candidates = [
            experiment.get("report_path"),
            experiment.get("markdown_report_path"),
            experiment.get("trade_log_path"),
        ]
        touched_dirs: set[Path] = set()
        for candidate in candidates:
            if not candidate:
                continue
            path = Path(candidate).resolve()
            try:
                path.relative_to(report_root)
            except ValueError:
                continue
            if path.is_file():
                path.unlink()
                deleted_files += 1
                touched_dirs.add(path.parent)
        for directory in sorted(touched_dirs, key=lambda item: len(item.parts), reverse=True):
            try:
                directory.rmdir()
                deleted_dirs += 1
            except OSError:
                pass
    return {"artifact_files": deleted_files, "artifact_dirs": deleted_dirs}


def _vectorbt_diff(experiment: dict) -> dict:
    benchmark = experiment.get("vectorbt_benchmark")
    event_metrics = experiment["metrics"]
    if not benchmark:
        return {
            "event_driven_primary": event_metrics,
            "vectorbt_reference": None,
            "net_return_delta": None,
            "comment": "No persisted vectorbt benchmark found for this experiment.",
        }
    reference_metrics = benchmark.get("metrics") if benchmark.get("status") == "available" else None
    event_return = event_metrics.get("net_return")
    reference_return = reference_metrics.get("net_return") if reference_metrics else None
    return {
        "event_driven_primary": event_metrics,
        "vectorbt_reference": benchmark,
        "net_return_delta": float(event_return - reference_return)
        if event_return is not None and reference_return is not None
        else None,
        "comment": benchmark.get("comment") or benchmark.get("reason"),
    }


def _phase1_diagnostics(experiment: dict) -> dict:
    path = experiment.get("window_diagnostics_path")
    diagnostics = experiment.get("window_diagnostics")
    if diagnostics is None and path:
        diagnostics = frame_to_records(read_csv_if_exists(Path(path)))
    if diagnostics is None:
        diagnostics = []
    return {
        "window_diagnostics": diagnostics,
        "window_diagnostics_path": path,
        "dataset_path": experiment.get("dataset_path"),
        "candidate_path": experiment.get("candidate_path"),
        "label_template_path": experiment.get("label_template_path"),
        "label_count": experiment.get(
            "label_count",
            experiment.get("metrics", {}).get("label_count", 0),
        ),
        "sample_count": experiment.get(
            "sample_count",
            experiment.get("metrics", {}).get("sample_count", 0),
        ),
        "positive_sample_count": experiment.get(
            "positive_sample_count",
            experiment.get("metrics", {}).get("positive_sample_count", 0),
        ),
        "negative_sample_count": experiment.get(
            "negative_sample_count",
            experiment.get("metrics", {}).get("negative_sample_count", 0),
        ),
        "train_positive_count": experiment.get(
            "train_positive_count",
            experiment.get("metrics", {}).get("train_positive_count", 0),
        ),
        "holdout_positive_count": experiment.get(
            "holdout_positive_count",
            experiment.get("metrics", {}).get("holdout_positive_count", 0),
        ),
        "phase1_results": experiment.get("phase1_results", []),
    }


@router.get("")
def list_experiments():
    payload = load_experiments()
    return envelope(payload)


@router.delete("")
def delete_experiments(request: DeleteExperimentsRequest):
    store = experiment_store()
    unique_ids = sorted(set(request.experiment_ids))
    experiments = [
        experiment
        for experiment in store.list_payloads("experiments")
        if experiment.get("experiment_id") in unique_ids
    ]
    if not experiments:
        raise HTTPException(status_code=404, detail="No matching experiments found")
    artifact_counts = (
        _delete_artifacts(experiments)
        if request.delete_artifacts
        else {"artifact_files": 0, "artifact_dirs": 0}
    )
    deleted_counts = store.delete_experiment_bundle(unique_ids)
    return envelope(
        {
            "requested": len(unique_ids),
            "deleted": {**deleted_counts, **artifact_counts},
            "deleted_experiment_ids": [experiment["experiment_id"] for experiment in experiments],
        }
    )


@router.get("/{experiment_id}")
def get_experiment(experiment_id: str):
    experiment = experiment_store().get_payload("experiments", "experiment_id", experiment_id)
    if experiment is None:
        raise HTTPException(status_code=404, detail="Experiment not found")
    trades = [
        trade
        for trade in experiment_store().list_payloads("trades")
        if trade.get("experiment_id") == experiment_id
    ]
    signals = [
        signal
        for signal in list_signals()
        if signal.get("experiment_id") == experiment_id
        or signal["signal_id"] in {trade["signal_id"] for trade in trades}
    ]
    trades_frame = pd.DataFrame(trades)
    curve = equity_curve(trades_frame)
    payload = {
        **experiment,
        "phase1_diagnostics": _phase1_diagnostics(experiment)
        if experiment.get("strategy") == "PHASE1"
        else None,
        "signals": signals,
        "trades": trades,
        "equity_curve": frame_to_records(curve[["exit_time", "equity"]]) if not curve.empty else [],
        "drawdown_curve": frame_to_records(curve[["exit_time", "drawdown"]])
        if not curve.empty
        else [],
        "by_symbol": by_symbol(trades_frame).to_dict(orient="records")
        if not trades_frame.empty
        else [],
        "by_month": by_month(trades_frame).to_dict(orient="records")
        if not trades_frame.empty
        else [],
        "vectorbt_diff": _vectorbt_diff(experiment),
        "config_view": {
            "experiment": read_yaml_if_exists(experiment.get("config_path")),
            "strategy": read_yaml_if_exists(experiment.get("strategy_config_path")),
            "backtest": read_yaml_if_exists(experiment.get("backtest_config_path")),
        },
        "report_urls": {
            "html": artifact_url(experiment.get("report_path")),
            "markdown": artifact_url(experiment.get("markdown_report_path")),
            "trades_csv": artifact_url(experiment.get("trade_log_path")),
        },
    }
    return envelope(payload)


@router.get("/{experiment_id}/trades")
def get_experiment_trades(experiment_id: str):
    trades = [
        trade
        for trade in experiment_store().list_payloads("trades")
        if trade.get("experiment_id") == experiment_id
    ]
    return envelope(trades)


@router.get("/{experiment_id}/metrics")
def get_experiment_metrics(experiment_id: str):
    experiment = experiment_store().get_payload("experiments", "experiment_id", experiment_id)
    if experiment is None:
        raise HTTPException(status_code=404, detail="Experiment not found")
    return envelope(experiment["metrics"])


@router.get("/{experiment_id}/diff")
def get_experiment_diff(experiment_id: str):
    experiment = experiment_store().get_payload("experiments", "experiment_id", experiment_id)
    if experiment is None:
        raise HTTPException(status_code=404, detail="Experiment not found")
    return envelope(_vectorbt_diff(experiment))
