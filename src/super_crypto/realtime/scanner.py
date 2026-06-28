from __future__ import annotations

import json
import time
from urllib.parse import urlparse

import httpx
import pandas as pd

from super_crypto.common.config import load_yaml
from super_crypto.common.paths import DATA_ROOT, ensure_parent
from super_crypto.common.time import to_iso, utc_now
from super_crypto.experiments.experiment_store import ExperimentStore
from super_crypto.features.orderbook_features import latest_orderbook_metrics
from super_crypto.signals.v4a_early_short import generate as generate_v4a
from super_crypto.signals.v4b_confirmed_short import generate as generate_v4b


def _send_webhook(url: str, payload: dict) -> None:
    if not url:
        return
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"}:
        return
    with httpx.Client(timeout=10.0) as client:
        client.post(url, json=payload)


def _write_heartbeat(payload: dict) -> None:
    path = ensure_parent(DATA_ROOT / "cache" / "scanner_status.json")
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _load_frame(symbol: str) -> pd.DataFrame:
    path = DATA_ROOT / "processed" / "ohlcv" / "1h" / f"{symbol}.parquet"
    if not path.exists():
        return pd.DataFrame()
    frame = pd.read_parquet(path)
    frame["open_time"] = pd.to_datetime(frame["open_time"], utc=True)
    return frame.tail(200)


def run(config_path: str, *, once: bool = False) -> dict:
    config = load_yaml(config_path)
    store = ExperimentStore()
    generated = []
    while True:
        for strategy_config_path in config["strategy_configs"]:
            strategy_config = load_yaml(strategy_config_path)
            for symbol in config["symbols"]:
                ohlcv = _load_frame(symbol)
                if ohlcv.empty:
                    continue
                funding_path = (
                    DATA_ROOT / "processed" / "derivatives" / f"funding_{symbol}.parquet"
                )
                oi_path = (
                    DATA_ROOT / "processed" / "derivatives" / f"open_interest_{symbol}.parquet"
                )
                orderbook_path = (
                    DATA_ROOT / "processed" / "orderbook_features" / f"{symbol}.parquet"
                )
                funding = pd.read_parquet(funding_path) if funding_path.exists() else pd.DataFrame()
                open_interest = pd.read_parquet(oi_path) if oi_path.exists() else pd.DataFrame()
                orderbook = (
                    pd.read_parquet(orderbook_path)
                    if orderbook_path.exists()
                    else pd.DataFrame()
                )
                orderbook_metrics = latest_orderbook_metrics(orderbook)
                if strategy_config["strategy"] == "V4A":
                    signals = generate_v4a(
                        ohlcv,
                        symbol,
                        strategy_config,
                        funding=funding,
                        open_interest=open_interest,
                        manipulation_bucket="high",
                        orderbook_slippage_bps=orderbook_metrics["slippage_500"],
                    )
                else:
                    signals = generate_v4b(
                        ohlcv,
                        symbol,
                        strategy_config,
                        funding=funding,
                        open_interest=open_interest,
                        manipulation_bucket="high",
                        orderbook_slippage_bps=orderbook_metrics["slippage_500"],
                    )
                for signal in signals[-1:]:
                    if store.get_payload("signals", "signal_id", signal.signal_id):
                        continue
                    recent_duplicates = [
                        existing
                        for existing in store.list_payloads("signals")
                        if existing["symbol"] == signal.symbol
                        and existing["strategy"] == signal.strategy
                        and pd.Timestamp(existing["signal_time"])
                        >= pd.Timestamp(signal.signal_time)
                        - pd.Timedelta(minutes=config["dedupe_window_minutes"])
                    ]
                    if recent_duplicates:
                        continue
                    payload = signal.model_dump(mode="json")
                    store.upsert("signals", "signal_id", payload)
                    generated.append(payload)
                    store.upsert(
                        "paper_trades",
                        "trade_id",
                        {
                            "trade_id": f"paper-{signal.signal_id}",
                            "signal_id": signal.signal_id,
                            "experiment_id": None,
                            "symbol": signal.symbol,
                            "strategy": signal.strategy,
                            "split": "train_validation",
                            "source": "paper",
                            "side": "SHORT",
                            "entry_time": payload["signal_time"],
                            "entry_price": float(ohlcv.iloc[-1]["close"]),
                            "exit_time": payload["signal_time"],
                            "exit_price": float(ohlcv.iloc[-1]["close"]),
                            "gross_return": 0.0,
                            "fee_cost": 0.0,
                            "slippage_cost": 0.0,
                            "funding_cost": 0.0,
                            "net_return": 0.0,
                            "exit_reason": "open",
                            "holding_minutes": 0.0,
                            "mae": 0.0,
                            "mfe": 0.0,
                            "orderbook_snapshot_status": (
                                "healthy" if orderbook_metrics["spread_bps"] else "partial"
                            ),
                        },
                    )
                    webhook_payload = {
                        "symbol": signal.symbol,
                        "strategy": signal.strategy,
                        "side": signal.side,
                        "signal_time": payload["signal_time"],
                        "entry": signal.entry_reference,
                        "stop_loss": signal.stop_loss,
                        "trailing_stop": signal.trailing_stop,
                        "confidence": signal.confidence,
                        "manipulation_score_bucket": signal.manipulation_score_bucket,
                        "reason": signal.reason,
                    }
                    for url in config.get("webhooks", {}).values():
                        if url:
                            _send_webhook(url, webhook_payload)
        heartbeat = {
            "scanner_status": "running",
            "generated_at": to_iso(utc_now()),
            "generated_signals": len(generated),
            "tracked_symbols": len(config["symbols"]),
            "webhook_targets": [
                name
                for name, url in config.get("webhooks", {}).items()
                if urlparse(url).scheme in {"http", "https"}
            ],
        }
        _write_heartbeat(heartbeat)
        if once:
            return heartbeat
        time.sleep(int(config["poll_interval_sec"]))
