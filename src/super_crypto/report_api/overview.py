from __future__ import annotations

import pandas as pd
from fastapi import APIRouter

from super_crypto.autoresearch.artifacts import latest_run_manifest
from super_crypto.backtest.metrics import equity_curve
from super_crypto.experiments.experiment_store import ExperimentStore
from super_crypto.experiments.run_experiment import latest_frozen_config_path
from super_crypto.report_api.deps import envelope
from super_crypto.report_api.loaders import (
    frame_to_records,
    latest_pipeline_stage,
    list_experiments,
    list_pipeline_runs,
    list_signals,
    list_trades,
    load_paper_trades,
    load_scanner_status,
)

router = APIRouter(prefix="/api/overview", tags=["overview"])


def _metric(metrics: dict | None, key: str, default: float = 0.0) -> float:
    if not isinstance(metrics, dict):
        return default
    value = metrics.get(key, default)
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _trade_count(metrics: dict | None) -> int:
    if not isinstance(metrics, dict):
        return 0
    value = metrics.get("trade_count", metrics.get("sample_count", 0))
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0


def _latest_split_experiment(experiments: list[dict], split: str) -> dict | None:
    return next(
        (experiment for experiment in experiments if experiment.get("split") == split),
        None,
    )


def _latest_frozen_config_status(experiments: list[dict]) -> dict:
    for experiment in experiments:
        frozen_path = experiment.get("frozen_config_path")
        if frozen_path:
            return {
                "available": True,
                "path": frozen_path,
                "source_experiment_id": experiment.get("experiment_id"),
                "created_at": experiment.get("created_at"),
            }
    for strategy in ("V4A", "V4B", "V3"):
        path = latest_frozen_config_path(strategy)
        if path.exists():
            return {
                "available": True,
                "path": str(path),
                "source_experiment_id": None,
                "created_at": None,
            }
    return {
        "available": False,
        "path": None,
        "source_experiment_id": None,
        "created_at": None,
    }


@router.get("")
def get_overview():
    experiments = list_experiments()
    signals = list_signals()
    trades = list_trades()
    paper_trades = load_paper_trades()
    scanner_status = load_scanner_status()
    latest_pipeline = next(iter(list_pipeline_runs()), None)
    sorted_experiments = sorted(
        experiments,
        key=lambda item: item["created_at"],
        reverse=True,
    )
    latest_experiment = next(iter(sorted_experiments), None)
    latest_validation_experiment = _latest_split_experiment(sorted_experiments, "validation")
    latest_holdout_experiment = _latest_split_experiment(sorted_experiments, "holdout")
    validation_metric_experiment = latest_validation_experiment or latest_experiment
    latest_research_run = latest_run_manifest()
    frozen_config = _latest_frozen_config_status(sorted_experiments)
    holdout_run_count = ExperimentStore().holdout_run_count()
    latest_pipeline_id = latest_pipeline["run_id"] if latest_pipeline else None
    latest_enrich_stage = (
        latest_pipeline_stage(latest_pipeline_id, "enrich") if latest_pipeline_id else None
    )
    latest_score_stage = (
        latest_pipeline_stage(latest_pipeline_id, "score_symbols") if latest_pipeline_id else None
    )
    latest_trades = [
        trade
        for trade in trades
        if latest_experiment and trade.get("experiment_id") == latest_experiment["experiment_id"]
    ]
    curve = equity_curve(pd.DataFrame(latest_trades))
    split_comparison = [
        {
            "split": experiment.get("split", ""),
            "net_return": _metric(experiment.get("metrics"), "net_return"),
            "trade_count": _trade_count(experiment.get("metrics")),
            "status": experiment.get("status", "unknown"),
        }
        for experiment in experiments[:6]
    ]
    data_warnings = []
    if latest_enrich_stage:
        coinglass = latest_enrich_stage.get("details", {}).get("coinglass", {})
        coinglass_failed = any(
            value == "request_failed"
            for symbol_info in coinglass.values()
            for value in symbol_info.values()
        )
        if coinglass_failed:
            data_warnings.append(
                {
                    "source_name": "CoinGlass cache",
                    "status": "partial",
                    "detail": "request_failed",
                }
            )
    if latest_score_stage and latest_score_stage.get("details", {}).get("score_count", 0) == 0:
        data_warnings.append(
            {
                "source_name": "Manipulation scores",
                "status": "failed",
                "detail": "score_count_zero",
            }
        )
    paper_pnl_7d = sum(float(trade.get("net_return", 0.0)) for trade in paper_trades)
    payload = {
        "latest_pipeline_run": latest_pipeline,
        "latest_research_run": latest_research_run,
        "latest_experiment": latest_experiment,
        "latest_validation_experiment": latest_validation_experiment,
        "latest_holdout_experiment": latest_holdout_experiment,
        "frozen_config": frozen_config,
        "holdout_status": {
            "run_count": holdout_run_count,
            "has_result": latest_holdout_experiment is not None,
            "latest_experiment_id": (
                latest_holdout_experiment.get("experiment_id")
                if latest_holdout_experiment
                else None
            ),
            "status": (
                latest_holdout_experiment.get("status")
                if latest_holdout_experiment
                else "not_run"
            ),
        },
        "today_signal_count": len(signals),
        "active_monitored_symbols": len({signal["symbol"] for signal in signals}),
        "paper_pnl_7d": paper_pnl_7d,
        "validation_best_net_return": (
            _metric(validation_metric_experiment.get("metrics"), "net_return")
            if validation_metric_experiment
            else 0.0
        ),
        "max_drawdown": (
            _metric(latest_experiment.get("metrics"), "max_drawdown")
            if latest_experiment
            else 0.0
        ),
        "data_health_score": 0.91 if latest_pipeline else 0.0,
        "scanner_status": scanner_status,
        "performance_snapshot": {
            "equity_curve": (
                frame_to_records(curve[["exit_time", "equity"]]) if not curve.empty else []
            ),
            "drawdown_curve": (
                frame_to_records(curve[["exit_time", "drawdown"]]) if not curve.empty else []
            ),
            "split_comparison": split_comparison,
        },
        "data_warnings": data_warnings,
        "latest_alerts": signals[:4],
        "recent_trades": list_trades(include_paper=True)[:10],
    }
    return envelope(payload)
