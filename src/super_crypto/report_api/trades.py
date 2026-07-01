from __future__ import annotations

import pandas as pd
from fastapi import APIRouter, HTTPException

from super_crypto.common.config import load_yaml
from super_crypto.report_api.deps import envelope, experiment_store
from super_crypto.report_api.loaders import frame_to_records, load_paper_trades, load_symbol_ohlcv

router = APIRouter(tags=["trades"])


def _trade_marker(payload: dict) -> dict:
    notional = 1000.0
    experiment_id = payload.get("experiment_id")
    experiment = (
        experiment_store().get_payload("experiments", "experiment_id", experiment_id)
        if experiment_id
        else None
    )
    if experiment:
        try:
            experiment_config = load_yaml(experiment.get("config_path", ""))
            backtest_config = experiment_config.get("backtest") or load_yaml(
                experiment.get("backtest_config_path", "")
            )
            notional = float(backtest_config.get("capital_per_trade_usdt", notional))
        except Exception:
            notional = 1000.0
    entry_price = float(payload.get("entry_price") or 0.0)
    exit_price = float(payload.get("exit_price") or 0.0)
    quantity = notional / entry_price if entry_price > 0 else 0.0
    return {
        "trade_id": payload["trade_id"],
        "side": payload["side"],
        "entry_time": payload["entry_time"],
        "exit_time": payload["exit_time"],
        "entry_price": entry_price,
        "exit_price": exit_price,
        "quantity_base": quantity,
        "entry_notional_usdt": quantity * entry_price,
        "exit_notional_usdt": quantity * exit_price,
        "pnl_usdt": notional * float(payload.get("net_return", 0.0)),
        "net_return": float(payload.get("net_return", 0.0)),
        "gross_return": float(payload.get("gross_return", 0.0)),
        "fee_cost": float(payload.get("fee_cost", 0.0)),
        "slippage_cost": float(payload.get("slippage_cost", 0.0)),
        "funding_cost": float(payload.get("funding_cost", 0.0)),
        "notional_usdt": notional,
    }


def _trade_kline_window(klines: pd.DataFrame, payload: dict, *, context_hours: int = 72) -> pd.DataFrame:
    if klines.empty or "open_time" not in klines:
        return klines
    frame = klines.copy()
    frame["open_time"] = pd.to_datetime(frame["open_time"], utc=True)
    frame = frame.sort_values("open_time").reset_index(drop=True)
    entry_time = pd.to_datetime(payload["entry_time"], utc=True)
    exit_time = pd.to_datetime(payload["exit_time"], utc=True)
    start = entry_time - pd.Timedelta(hours=context_hours)
    end = exit_time + pd.Timedelta(hours=context_hours)
    window = frame[(frame["open_time"] >= start) & (frame["open_time"] <= end)]
    if not window.empty:
        return window
    nearest_index = int((frame["open_time"] - entry_time).abs().idxmin())
    start_index = max(0, nearest_index - 100)
    end_index = min(len(frame), nearest_index + 101)
    return frame.iloc[start_index:end_index]


@router.get("/api/trades")
def list_trades(source: str = "backtest"):
    if source == "paper":
        payload = load_paper_trades()
    elif source == "all":
        payload = experiment_store().list_payloads("trades") + load_paper_trades()
    else:
        payload = experiment_store().list_payloads("trades")
    payload = sorted(
        payload,
        key=lambda item: item.get("exit_time") or item.get("entry_time", ""),
        reverse=True,
    )
    return envelope(payload)


@router.get("/api/trades/{trade_id}")
def get_trade(trade_id: str):
    payload = experiment_store().get_payload("trades", "trade_id", trade_id)
    if payload is None:
        payload = experiment_store().get_payload("paper_trades", "trade_id", trade_id)
    if payload is None:
        raise HTTPException(status_code=404, detail="Trade not found")
    signal = experiment_store().get_payload("signals", "signal_id", payload["signal_id"])
    sibling_trades = [
        trade
        for trade in experiment_store().list_payloads("trades")
        if trade.get("experiment_id") == payload.get("experiment_id")
    ]
    sibling_trades.sort(key=lambda item: item["net_return"], reverse=True)
    top_trade_ids = {trade["trade_id"] for trade in sibling_trades[:5]}
    klines = _trade_kline_window(load_symbol_ohlcv(payload["symbol"]), payload)
    payload = {
        **payload,
        "signal": signal,
        "is_top5_trade": payload["trade_id"] in top_trade_ids,
        "kline_context": frame_to_records(klines),
        "trade_marker": _trade_marker(payload),
    }
    return envelope(payload)


@router.get("/api/paper-trades")
def list_paper_trades():
    return envelope(
        sorted(load_paper_trades(), key=lambda item: item.get("entry_time", ""), reverse=True)
    )
