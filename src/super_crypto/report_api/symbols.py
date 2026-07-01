from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pandas as pd
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


def _freshness_label(latest_mtime: float | None) -> str | None:
    if latest_mtime is None:
        return None
    age_seconds = max(0, int(datetime.now(UTC).timestamp() - latest_mtime))
    if age_seconds < 3600:
        return f"{age_seconds // 60}m"
    if age_seconds < 86400:
        return f"{age_seconds // 3600}h"
    return f"{age_seconds // 86400}d"


def _latest_timestamp(frame: pd.DataFrame, columns: tuple[str, ...]) -> str | None:
    if frame.empty:
        return None
    for column in columns:
        if column in frame.columns:
            value = frame[column].dropna().iloc[-1] if frame[column].notna().any() else None
            return str(value) if value is not None else None
    return None


def _source_row(
    *,
    source_name: str,
    path: Path,
    frame: pd.DataFrame | None = None,
    timestamp_columns: tuple[str, ...] = (),
    notes: list[str] | None = None,
) -> dict:
    exists = path.exists()
    file_count = 1 if exists and path.is_file() else len(list(path.glob("*.parquet"))) if exists else 0
    latest_mtime = path.stat().st_mtime if exists and path.is_file() else None
    latest_timestamp = _latest_timestamp(frame if frame is not None else pd.DataFrame(), timestamp_columns)
    status = "healthy" if file_count else "partial"
    row_notes = notes or []
    if frame is not None and frame.empty:
        status = "partial"
        row_notes = [*row_notes, "empty_frame"]
    return {
        "source_name": source_name,
        "status": status,
        "file_count": file_count,
        "freshness": _freshness_label(latest_mtime),
        "latest_timestamp": latest_timestamp,
        "path": str(path),
        "notes": row_notes,
    }


def _coinglass_source_rows(symbol: str) -> list[dict]:
    root = DATA_ROOT / "processed" / "external_enrichment"
    rows = []
    for endpoint in ("tickers", "coin_info", "spot_tickers", "spot_flow", "futures_flow"):
        path = root / f"{endpoint}_{symbol}.parquet"
        frame = pd.read_parquet(path) if path.exists() else pd.DataFrame()
        rows.append(
            _source_row(
                source_name=f"coinglass_{endpoint}",
                path=path,
                frame=frame,
                timestamp_columns=("snapshot_time", "time", "created_at"),
            )
        )
    return rows


def _symbol_data_sources(symbol: str) -> list[dict]:
    rows = []
    for timeframe in ("1m", "5m", "15m", "1h"):
        path = DATA_ROOT / "processed" / "ohlcv" / timeframe / f"{symbol}.parquet"
        frame = pd.read_parquet(path) if path.exists() else pd.DataFrame()
        rows.append(
            _source_row(
                source_name=f"binance_klines_{timeframe}",
                path=path,
                frame=frame,
                timestamp_columns=("open_time", "close_time"),
            )
        )
    funding_path = DATA_ROOT / "processed" / "derivatives" / f"funding_{symbol}.parquet"
    funding = load_symbol_funding(symbol)
    rows.append(
        _source_row(
            source_name="binance_funding",
            path=funding_path,
            frame=funding,
            timestamp_columns=("funding_time", "open_time"),
        )
    )
    oi_path = DATA_ROOT / "processed" / "derivatives" / f"open_interest_{symbol}.parquet"
    open_interest = load_symbol_open_interest(symbol)
    rows.append(
        _source_row(
            source_name="binance_open_interest",
            path=oi_path,
            frame=open_interest,
            timestamp_columns=("snapshot_time", "open_time"),
        )
    )
    orderbook_path = DATA_ROOT / "processed" / "orderbook_features" / f"{symbol}.parquet"
    orderbook = load_symbol_orderbook(symbol)
    rows.append(
        _source_row(
            source_name="binance_orderbook",
            path=orderbook_path,
            frame=orderbook,
            timestamp_columns=("snapshot_time",),
        )
    )
    rows.extend(_coinglass_source_rows(symbol))
    return rows


def _source_summary(rows: list[dict]) -> dict:
    healthy = sum(1 for row in rows if row["status"] == "healthy")
    total = len(rows)
    latest = next(
        (row["latest_timestamp"] for row in rows if row.get("latest_timestamp")),
        None,
    )
    return {
        "healthy_sources": healthy,
        "total_sources": total,
        "coverage": healthy / total if total else 0.0,
        "status": "healthy" if healthy == total else "partial" if healthy else "failed",
        "latest_timestamp": latest,
    }


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
    data_sources = _symbol_data_sources(symbol)
    source_summary = _source_summary(data_sources)
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
        "data_completeness": float(source_summary["coverage"]),
        "data_source_summary": source_summary,
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
        "data_sources": data_sources,
    }


@router.get("")
def list_symbols():
    signal_symbols = {signal["symbol"] for signal in experiment_store().list_payloads("signals")}
    ohlcv_dir = DATA_ROOT / "processed" / "ohlcv" / "1h"
    file_symbols = {path.stem for path in ohlcv_dir.glob("*.parquet")}
    payload = [
        _symbol_score_from_signals(symbol) for symbol in sorted(signal_symbols | file_symbols)
    ]
    return envelope(payload)


@router.get("/{symbol}")
def get_symbol(symbol: str):
    payload = _symbol_score_from_signals(symbol)
    cycles = load_symbol_cycles(symbol)
    funding = load_symbol_funding(symbol)
    open_interest = load_symbol_open_interest(symbol)
    ohlcv = load_symbol_ohlcv(symbol).tail(2000)
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
