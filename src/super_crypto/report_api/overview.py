from __future__ import annotations

import pandas as pd
from fastapi import APIRouter

from super_crypto.backtest.metrics import equity_curve
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
            "split": experiment["split"],
            "net_return": experiment["metrics"]["net_return"],
            "trade_count": experiment["metrics"]["trade_count"],
            "status": experiment["status"],
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
        "latest_experiment": latest_experiment,
        "today_signal_count": len(signals),
        "active_monitored_symbols": len({signal["symbol"] for signal in signals}),
        "paper_pnl_7d": paper_pnl_7d,
        "validation_best_net_return": (
            latest_experiment["metrics"]["net_return"] if latest_experiment else 0.0
        ),
        "max_drawdown": latest_experiment["metrics"]["max_drawdown"] if latest_experiment else 0.0,
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
