from __future__ import annotations

import json
from typing import Any

from fastapi import APIRouter, HTTPException

from super_crypto.common.paths import DATA_ROOT
from super_crypto.report_api.deps import envelope, experiment_store
from super_crypto.report_api.loaders import (
    frame_to_records,
    load_latest_scores,
    load_symbol_cycles,
    load_symbol_funding,
    load_symbol_ohlcv,
    load_symbol_open_interest,
    load_symbol_orderbook,
)

router = APIRouter(prefix="/api/symbols", tags=["symbols"])


def _depth_levels(value: Any) -> list[list[float]]:
    if value is None:
        return []
    if isinstance(value, str):
        try:
            value = json.loads(value)
        except json.JSONDecodeError:
            return []
    if hasattr(value, "tolist"):
        value = value.tolist()
    if not isinstance(value, list):
        return []

    levels = []
    for level in value:
        if hasattr(level, "tolist"):
            level = level.tolist()
        if isinstance(level, dict):
            price_raw = level.get("price")
            size_raw = level.get("size") or level.get("qty") or level.get("quantity")
        elif isinstance(level, list | tuple) and len(level) >= 2:
            price_raw = level[0]
            size_raw = level[1]
        else:
            continue
        try:
            levels.append([float(price_raw), float(size_raw)])
        except (TypeError, ValueError):
            continue
    return levels


def _build_depth_rows(snapshot: dict | None) -> list[dict]:
    if snapshot is None:
        return []
    bids = _depth_levels(snapshot.get("bids"))
    asks = _depth_levels(snapshot.get("asks"))
    rows = []
    levels = max(len(bids), len(asks))
    for index in range(levels):
        bid_price, bid_size = bids[index] if index < len(bids) else [0.0, 0.0]
        ask_price, ask_size = asks[index] if index < len(asks) else [0.0, 0.0]
        rows.append(
            {
                "price": bid_price or ask_price,
                "bid": bid_size,
                "ask": ask_size,
            }
        )
    return rows


def _symbol_score_from_signals(symbol: str) -> dict:
    store = experiment_store()
    signals = [signal for signal in store.list_payloads("signals") if signal["symbol"] == symbol]
    paper_trades = [
        trade for trade in store.list_payloads("paper_trades") if trade["symbol"] == symbol
    ]
    trades = [trade for trade in store.list_payloads("trades") if trade["symbol"] == symbol]
    scores = load_latest_scores()
    score_row = scores[scores["symbol"] == symbol].to_dict(orient="records")
    score_row = score_row[0] if score_row else {}
    cycles = load_symbol_cycles(symbol)
    funding = load_symbol_funding(symbol)
    open_interest = load_symbol_open_interest(symbol)
    ohlcv = load_symbol_ohlcv(symbol)
    orderbook = load_symbol_orderbook(symbol)
    latest_signal = signals[0] if signals else None
    latest_orderbook = orderbook.iloc[-1].to_dict() if not orderbook.empty else None
    avg_pump_return = cycles["pump_return"].mean() if not cycles.empty else 0.0
    avg_dump_return = cycles["dump_return"].mean() if not cycles.empty else 0.0
    median_duration_hours = cycles["duration_hours"].median() if not cycles.empty else 0.0
    return {
        "symbol": symbol,
        "manipulation_score": float(score_row.get("score", len(signals) * 10 + len(trades) * 5)),
        "score_bucket": score_row.get("bucket", "medium"),
        "cycle_count": int(score_row.get("cycle_count", len(cycles))),
        "avg_pump_return": float(score_row.get("avg_pump_return", avg_pump_return)),
        "avg_dump_return": float(score_row.get("avg_dump_return", avg_dump_return)),
        "median_duration_hours": float(median_duration_hours),
        "latest_funding": float(funding["funding_rate"].iloc[-1]) if not funding.empty else 0.0,
        "oi_change_1h": (
            float(open_interest["open_interest"].pct_change(1).fillna(0.0).iloc[-1])
            if not open_interest.empty and len(open_interest) > 1
            else 0.0
        ),
        "oi_change_6h": (
            float(open_interest["open_interest"].pct_change(6).fillna(0.0).iloc[-1])
            if not open_interest.empty and len(open_interest) > 6
            else 0.0
        ),
        "oi_change_24h": (
            float(open_interest["open_interest"].pct_change(24).fillna(0.0).iloc[-1])
            if not open_interest.empty and len(open_interest) > 24
            else 0.0
        ),
        "quote_volume_24h": float(ohlcv["quote_volume"].tail(24).sum()) if not ohlcv.empty else 0.0,
        "data_completeness": 1.0 if not orderbook.empty and not funding.empty else 0.8,
        "orderbook_depth_status": "healthy" if not orderbook.empty else "partial",
        "latest_signal": latest_signal,
        "latest_signal_label": (
            f"{latest_signal['strategy']} · {latest_signal['signal_time'][:16]}"
            if latest_signal
            else "none"
        ),
        "trade_count": len(trades),
        "paper_trade_count": len(paper_trades),
        "point_in_time_cutoff": score_row.get("point_in_time_cutoff"),
        "latest_orderbook": {
            "snapshot_time": latest_orderbook.get("snapshot_time") if latest_orderbook else None,
            "spread_bps": latest_orderbook.get("spread_bps") if latest_orderbook else None,
            "imbalance": latest_orderbook.get("imbalance") if latest_orderbook else None,
            "slippage_bps_sell": (
                latest_orderbook.get("slippage_bps_sell") if latest_orderbook else {}
            ),
        },
    }


@router.get("")
def list_symbols():
    signal_symbols = {signal["symbol"] for signal in experiment_store().list_payloads("signals")}
    ohlcv_dir = DATA_ROOT / "processed" / "ohlcv" / "1h"
    file_symbols = {path.stem for path in ohlcv_dir.glob("*.parquet")}
    payload = [
        _symbol_score_from_signals(symbol)
        for symbol in sorted(signal_symbols | file_symbols)
    ]
    return envelope(payload)


@router.get("/{symbol}")
def get_symbol(symbol: str):
    payload = _symbol_score_from_signals(symbol)
    cycles = load_symbol_cycles(symbol)
    funding = load_symbol_funding(symbol)
    open_interest = load_symbol_open_interest(symbol)
    ohlcv = load_symbol_ohlcv(symbol).tail(240)
    orderbook = load_symbol_orderbook(symbol)
    latest_orderbook = orderbook.iloc[-1].to_dict() if not orderbook.empty else None
    payload = {
        **payload,
        "klines": frame_to_records(ohlcv),
        "cycles": frame_to_records(cycles),
        "funding_series": frame_to_records(funding, limit=120),
        "open_interest_series": frame_to_records(open_interest, limit=120),
        "signals": [
            signal
            for signal in experiment_store().list_payloads("signals")
            if signal["symbol"] == symbol
        ][:20],
        "trades": [
            trade
            for trade in experiment_store().list_payloads("trades")
            if trade["symbol"] == symbol
        ][:20],
        "paper_trades": [
            trade
            for trade in experiment_store().list_payloads("paper_trades")
            if trade["symbol"] == symbol
        ][:20],
        "orderbook_depth": _build_depth_rows(latest_orderbook),
    }
    return envelope(payload)


@router.get("/{symbol}/klines")
def get_symbol_klines(symbol: str):
    frame = load_symbol_ohlcv(symbol)
    if frame.empty:
        raise HTTPException(status_code=404, detail="Symbol klines not found")
    frame = frame.tail(200)
    return envelope(frame_to_records(frame), source="parquet")


@router.get("/{symbol}/orderbook")
def get_symbol_orderbook(symbol: str):
    frame = load_symbol_orderbook(symbol)
    if frame.empty:
        raise HTTPException(status_code=404, detail="Orderbook snapshot not found")
    latest_snapshot = frame.iloc[-1].to_dict()
    payload = {
        "summary": {
            "snapshot_time": latest_snapshot.get("snapshot_time"),
            "spread_bps": latest_snapshot.get("spread_bps"),
            "imbalance": latest_snapshot.get("imbalance"),
            "slippage_bps_sell": latest_snapshot.get("slippage_bps_sell"),
            "slippage_bps_buy": latest_snapshot.get("slippage_bps_buy"),
        },
        "depth_rows": _build_depth_rows(latest_snapshot),
        "history": frame_to_records(frame),
    }
    return envelope(payload, source="parquet")
