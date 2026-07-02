from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pandas as pd

from super_crypto.report_api import signals


class FakeStore:
    signal = {
        "signal_id": "signal-1",
        "symbol": "VELVETUSDT",
        "strategy": "V4A",
        "side": "SHORT",
        "signal_time": "2026-06-14T12:00:00+00:00",
        "decision_time": "2026-06-14T12:00:00+00:00",
        "data_cutoff_time": "2026-06-14T12:00:00+00:00",
        "entry_reference": "next_bar_open",
        "stop_loss": 0.08,
        "trailing_stop": 0.05,
        "confidence": 0.8,
        "manipulation_score_bucket": "high",
        "reason": ["pump_context_detected"],
        "data_quality": "healthy",
        "missing_fields": [],
        "stale_fields": [],
        "status": "open",
    }

    def get_payload(self, table: str, key: str, value: str):
        if table == "signals" and key == "signal_id" and value == "signal-1":
            return dict(self.signal)
        return None

    def list_payloads(self, table: str):
        return []


def test_signal_detail_uses_kline_window_around_signal_not_latest_tail(monkeypatch):
    signal_start = datetime(2026, 6, 14, 0, tzinfo=UTC)
    latest_start = datetime(2026, 6, 25, 0, tzinfo=UTC)
    signal_rows = [
        {
            "open_time": signal_start + timedelta(hours=index),
            "open": 2.1,
            "high": 2.2,
            "low": 1.7,
            "close": 1.9,
        }
        for index in range(30)
    ]
    latest_rows = [
        {
            "open_time": latest_start + timedelta(hours=index),
            "open": 9.1,
            "high": 9.2,
            "low": 8.7,
            "close": 8.9,
        }
        for index in range(260)
    ]
    klines = pd.DataFrame([*signal_rows, *latest_rows])
    monkeypatch.setattr(signals, "experiment_store", lambda: FakeStore())
    monkeypatch.setattr(signals, "load_paper_trades", lambda: [])
    monkeypatch.setattr(signals, "load_symbol_ohlcv", lambda _symbol: klines)
    monkeypatch.setattr(signals, "load_symbol_funding", lambda _symbol: pd.DataFrame())
    monkeypatch.setattr(signals, "load_symbol_open_interest", lambda _symbol: pd.DataFrame())
    monkeypatch.setattr(signals, "load_symbol_orderbook", lambda _symbol: pd.DataFrame())

    response = signals.get_signal("signal-1")
    context = response["payload"]["kline_context"]

    assert context
    assert any(row["open_time"].startswith("2026-06-14") for row in context)
    assert not all(row["open_time"].startswith("2026-06-25") for row in context)
