from __future__ import annotations

from fastapi import APIRouter, HTTPException

from super_crypto.report_api.deps import envelope, experiment_store
from super_crypto.report_api.loaders import frame_to_records, load_paper_trades, load_symbol_ohlcv

router = APIRouter(tags=["trades"])


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
    klines = load_symbol_ohlcv(payload["symbol"]).tail(200)
    payload = {
        **payload,
        "signal": signal,
        "is_top5_trade": payload["trade_id"] in top_trade_ids,
        "kline_context": frame_to_records(klines),
    }
    return envelope(payload)


@router.get("/api/paper-trades")
def list_paper_trades():
    return envelope(
        sorted(load_paper_trades(), key=lambda item: item.get("entry_time", ""), reverse=True)
    )
