from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pandas as pd

from super_crypto.report_api import trades


class FakeStore:
    trade = {
        "trade_id": "trade-1",
        "signal_id": "signal-1",
        "experiment_id": "experiment-1",
        "symbol": "VELVETUSDT",
        "strategy": "V4A",
        "split": "validation",
        "source": "backtest",
        "side": "SHORT",
        "entry_time": "2026-06-14T19:00:00+00:00",
        "entry_price": 2.0,
        "exit_time": "2026-06-14T21:00:00+00:00",
        "exit_price": 1.8,
        "gross_return": 0.1,
        "fee_cost": 0.001,
        "slippage_cost": 0.002,
        "funding_cost": 0.0,
        "net_return": 0.097,
        "exit_reason": "max_hold",
        "holding_minutes": 120,
        "mae": -0.02,
        "mfe": 0.08,
        "orderbook_snapshot_status": "healthy",
    }

    def get_payload(self, table: str, key: str, value: str):
        if table == "trades" and key == "trade_id" and value == "trade-1":
            return dict(self.trade)
        if table == "signals":
            return {"signal_id": "signal-1", "symbol": "VELVETUSDT"}
        return None

    def list_payloads(self, table: str):
        return [dict(self.trade)] if table == "trades" else []


def test_trade_detail_includes_chart_marker(monkeypatch):
    start = datetime(2026, 6, 14, 18, tzinfo=UTC)
    klines = pd.DataFrame(
        [
            {
                "open_time": start + timedelta(hours=index),
                "open": 2.1,
                "high": 2.2,
                "low": 1.7,
                "close": 1.9,
            }
            for index in range(6)
        ]
    )
    monkeypatch.setattr(trades, "experiment_store", lambda: FakeStore())
    monkeypatch.setattr(trades, "load_symbol_ohlcv", lambda _symbol: klines)

    response = trades.get_trade("trade-1")
    marker = response["payload"]["trade_marker"]

    assert marker["side"] == "SHORT"
    assert marker["quantity_base"] == 500
    assert marker["entry_notional_usdt"] == 1000
    assert marker["exit_notional_usdt"] == 900
    assert marker["pnl_usdt"] == 97


def test_trade_detail_uses_kline_window_around_trade_not_latest_tail(monkeypatch):
    trade_start = datetime(2026, 6, 14, 0, tzinfo=UTC)
    latest_start = datetime(2026, 6, 25, 0, tzinfo=UTC)
    trade_rows = [
        {
            "open_time": trade_start + timedelta(hours=index),
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
    klines = pd.DataFrame([*trade_rows, *latest_rows])
    monkeypatch.setattr(trades, "experiment_store", lambda: FakeStore())
    monkeypatch.setattr(trades, "load_symbol_ohlcv", lambda _symbol: klines)

    response = trades.get_trade("trade-1")
    context = response["payload"]["kline_context"]

    assert context
    assert any(row["open_time"].startswith("2026-06-14") for row in context)
    assert not all(row["open_time"].startswith("2026-06-25") for row in context)
