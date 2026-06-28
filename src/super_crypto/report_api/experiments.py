from __future__ import annotations

import pandas as pd
from fastapi import APIRouter, HTTPException

from super_crypto.backtest.metrics import equity_curve
from super_crypto.report_api.deps import envelope, experiment_store
from super_crypto.report_api.loaders import (
    artifact_url,
    frame_to_records,
    list_experiments as load_experiments,
    list_signals,
    read_yaml_if_exists,
)
from super_crypto.validation.robustness import by_month, by_symbol


router = APIRouter(prefix="/api/experiments", tags=["experiments"])


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


@router.get("")
def list_experiments():
    payload = load_experiments()
    return envelope(payload)


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
        if signal["signal_id"] in {trade["signal_id"] for trade in trades}
    ]
    trades_frame = pd.DataFrame(trades)
    curve = equity_curve(trades_frame)
    payload = {
        **experiment,
        "signals": signals,
        "trades": trades,
        "equity_curve": frame_to_records(curve[["exit_time", "equity"]]) if not curve.empty else [],
        "drawdown_curve": frame_to_records(curve[["exit_time", "drawdown"]]) if not curve.empty else [],
        "by_symbol": by_symbol(trades_frame).to_dict(orient="records") if not trades_frame.empty else [],
        "by_month": by_month(trades_frame).to_dict(orient="records") if not trades_frame.empty else [],
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
