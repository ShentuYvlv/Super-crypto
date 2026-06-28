from __future__ import annotations

from fastapi import APIRouter, HTTPException

from super_crypto.report_api.deps import envelope, experiment_store
from super_crypto.report_api.loaders import (
    frame_to_records,
    load_paper_trades,
    load_symbol_funding,
    load_symbol_ohlcv,
    load_symbol_open_interest,
    load_symbol_orderbook,
)


router = APIRouter(prefix="/api/signals", tags=["signals"])


@router.get("")
def list_signals():
    payload = sorted(
        experiment_store().list_payloads("signals"),
        key=lambda item: item["signal_time"],
        reverse=True,
    )
    return envelope(payload)


@router.get("/{signal_id}")
def get_signal(signal_id: str):
    signal = experiment_store().get_payload("signals", "signal_id", signal_id)
    if signal is None:
        raise HTTPException(status_code=404, detail="Signal not found")
    symbol = signal["symbol"]
    paper_trade = next(
        (trade for trade in load_paper_trades() if trade.get("signal_id") == signal_id),
        None,
    )
    backtest_trades = [
        trade
        for trade in experiment_store().list_payloads("trades")
        if trade.get("signal_id") == signal_id
    ]
    klines = load_symbol_ohlcv(symbol).tail(200)
    funding = load_symbol_funding(symbol)
    open_interest = load_symbol_open_interest(symbol)
    orderbook = load_symbol_orderbook(symbol)
    latest_orderbook = orderbook.iloc[-1].to_dict() if not orderbook.empty else None
    payload = {
        **signal,
        "paper_trade": paper_trade,
        "backtest_trades": backtest_trades,
        "kline_context": frame_to_records(klines),
        "funding_series": frame_to_records(funding, limit=120),
        "open_interest_series": frame_to_records(open_interest, limit=120),
        "orderbook_snapshot": {
            "snapshot_time": latest_orderbook.get("snapshot_time") if latest_orderbook else None,
            "spread_bps": latest_orderbook.get("spread_bps") if latest_orderbook else None,
            "imbalance": latest_orderbook.get("imbalance") if latest_orderbook else None,
            "slippage_bps_sell": latest_orderbook.get("slippage_bps_sell") if latest_orderbook else {},
        },
        "webhook_payload": {
            "symbol": signal["symbol"],
            "strategy": signal["strategy"],
            "side": signal["side"],
            "signal_time": signal["signal_time"],
            "entry": signal["entry_reference"],
            "stop_loss": signal["stop_loss"],
            "trailing_stop": signal["trailing_stop"],
            "confidence": signal["confidence"],
            "manipulation_score_bucket": signal["manipulation_score_bucket"],
            "reason": signal["reason"],
        },
    }
    return envelope(payload)
