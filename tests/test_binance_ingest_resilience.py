from __future__ import annotations

import json
from datetime import UTC, datetime

import httpx
import polars as pl

from super_crypto.data import (
    ingest_funding,
    ingest_klines,
    ingest_market_snapshots,
    ingest_open_interest,
    ingest_orderbook,
)
from super_crypto.data.binance_client import BinanceFuturesClient


def test_binance_client_retries_transient_errors(monkeypatch):
    calls = {"count": 0}

    def fake_get(self, path, params=None):
        calls["count"] += 1
        if calls["count"] == 1:
            raise httpx.ConnectError("reset")
        return httpx.Response(
            200,
            json={"ok": True},
            request=httpx.Request("GET", "https://fapi.binance.com/fapi/v1/test"),
        )

    monkeypatch.setattr(httpx.Client, "get", fake_get)
    monkeypatch.setattr("time.sleep", lambda _seconds: None)

    with BinanceFuturesClient(max_retries=1) as client:
        assert client._get("/fapi/v1/test") == {"ok": True}
    assert calls["count"] == 2


def test_market_snapshot_uses_cached_exchange_and_tickers(tmp_path, monkeypatch):
    monkeypatch.setattr(ingest_market_snapshots, "DATA_ROOT", tmp_path)
    exchange_path = tmp_path / "raw" / "binance" / "exchange_info" / "exchange_info.json"
    ticker_path = tmp_path / "raw" / "binance" / "ticker_24hr" / "latest.json"
    exchange_path.parent.mkdir(parents=True)
    ticker_path.parent.mkdir(parents=True)
    exchange_path.write_text(json.dumps({"symbols": [{"symbol": "BTCUSDT"}]}), encoding="utf-8")
    ticker_path.write_text(
        json.dumps(
            [
                {
                    "symbol": "BTCUSDT",
                    "lastPrice": "100",
                    "priceChangePercent": "2",
                    "quoteVolume": "3000",
                    "count": "12",
                }
            ]
        ),
        encoding="utf-8",
    )
    config_path = tmp_path / "data.yaml"
    config_path.write_text("symbols:\n  - BTCUSDT\n", encoding="utf-8")

    class FailingClient:
        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return None

        def exchange_info(self):
            raise httpx.ConnectError("reset")

        def all_ticker_24hr(self):
            raise httpx.ConnectError("reset")

        def current_funding(self, _symbol):
            raise httpx.ConnectError("reset")

        def open_interest(self, _symbol):
            raise httpx.ConnectError("reset")

    monkeypatch.setattr(ingest_market_snapshots, "BinanceFuturesClient", FailingClient)

    result = ingest_market_snapshots.run(str(config_path))

    assert result["rows"] == 1
    assert result["used_cache"] is True
    assert result["exchange_info_symbols"] == 1
    assert (tmp_path / "processed" / "derivatives" / "market_snapshots.parquet").exists()


def test_klines_ingest_uses_existing_parquet_on_network_failure(tmp_path, monkeypatch):
    monkeypatch.setattr(ingest_klines, "DATA_ROOT", tmp_path)
    processed_path = tmp_path / "processed" / "ohlcv" / "1h" / "BTCUSDT.parquet"
    processed_path.parent.mkdir(parents=True)
    pl.DataFrame(
        [
            {
                "symbol": "BTCUSDT",
                "timeframe": "1h",
                "open_time": datetime(2026, 1, 1, 0, tzinfo=UTC),
                "close_time": datetime(2026, 1, 1, 1, tzinfo=UTC),
                "open": 1.0,
                "high": 1.0,
                "low": 1.0,
                "close": 1.0,
                "volume": 1.0,
                "quote_volume": 1.0,
                "trade_count": 1,
                "taker_buy_base_volume": 1.0,
                "taker_buy_quote_volume": 1.0,
            }
        ]
    ).write_parquet(processed_path)
    config_path = tmp_path / "data.yaml"
    config_path.write_text(
        """
symbols:
  - BTCUSDT
timeframes:
  - 1h
history_days:
  1h: 1
quality:
  max_gap_minutes:
    1h: 180
""",
        encoding="utf-8",
    )

    class FailingClient:
        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return None

        def klines(self, *_args, **_kwargs):
            raise httpx.ConnectError("reset")

    monkeypatch.setattr(ingest_klines, "BinanceFuturesClient", FailingClient)

    result = ingest_klines.run(str(config_path))

    assert result["BTCUSDT"]["1h"]["used_cache"] is True
    assert result["BTCUSDT"]["1h"]["row_count"] == 1


def test_funding_ingest_uses_existing_parquet_on_network_failure(tmp_path, monkeypatch):
    monkeypatch.setattr(ingest_funding, "DATA_ROOT", tmp_path)
    processed_path = tmp_path / "processed" / "derivatives" / "funding_BTCUSDT.parquet"
    processed_path.parent.mkdir(parents=True)
    pl.DataFrame(
        [
            {
                "symbol": "BTCUSDT",
                "funding_time": "2026-01-01T00:00:00Z",
                "funding_rate": 0.01,
            }
        ]
    ).write_parquet(processed_path)
    config_path = tmp_path / "data.yaml"
    config_path.write_text("symbols:\n  - BTCUSDT\n", encoding="utf-8")

    class FailingClient:
        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return None

        def funding_rate_history(self, _symbol):
            raise httpx.ConnectError("reset")

    monkeypatch.setattr(ingest_funding, "BinanceFuturesClient", FailingClient)

    result = ingest_funding.run(str(config_path))

    assert result["BTCUSDT"] == {"rows": 1, "used_cache": True}


def test_open_interest_ingest_uses_existing_parquet_on_network_failure(tmp_path, monkeypatch):
    monkeypatch.setattr(ingest_open_interest, "DATA_ROOT", tmp_path)
    processed_path = tmp_path / "processed" / "derivatives" / "open_interest_BTCUSDT.parquet"
    processed_path.parent.mkdir(parents=True)
    pl.DataFrame(
        [
            {
                "symbol": "BTCUSDT",
                "snapshot_time": "2026-01-01T00:00:00Z",
                "open_interest": 10.0,
                "oi_value_usd": 100.0,
            }
        ]
    ).write_parquet(processed_path)
    config_path = tmp_path / "data.yaml"
    config_path.write_text("symbols:\n  - BTCUSDT\n", encoding="utf-8")

    class FailingClient:
        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return None

        def open_interest(self, _symbol):
            raise httpx.ConnectError("reset")

    monkeypatch.setattr(ingest_open_interest, "BinanceFuturesClient", FailingClient)

    result = ingest_open_interest.run(str(config_path))

    assert result["BTCUSDT"]["used_cache"] is True
    assert result["BTCUSDT"]["rows"] == 1


def test_orderbook_ingest_uses_existing_parquet_on_network_failure(tmp_path, monkeypatch):
    monkeypatch.setattr(ingest_orderbook, "DATA_ROOT", tmp_path)
    processed_path = tmp_path / "processed" / "orderbook_features" / "BTCUSDT.parquet"
    processed_path.parent.mkdir(parents=True)
    pl.DataFrame(
        [
            {
                "symbol": "BTCUSDT",
                "snapshot_time": "2026-01-01T00:00:00Z",
                "spread_bps": 12.0,
                "imbalance": 0.25,
                "slippage_bps_buy": {"100": 3.0, "500": 7.0},
                "slippage_bps_sell": {"100": 4.0, "500": 8.0},
                "bids": [["100", "1"]],
                "asks": [["101", "1"]],
            }
        ]
    ).write_parquet(processed_path)
    config_path = tmp_path / "enrichment.yaml"
    config_path.write_text(
        """
binance_orderbook:
  levels: 20
  notionals_usdt:
    - 100
    - 500
""",
        encoding="utf-8",
    )

    class FailingClient:
        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return None

        def orderbook(self, *_args, **_kwargs):
            raise httpx.ConnectError("reset")

    monkeypatch.setattr(ingest_orderbook, "BinanceFuturesClient", FailingClient)

    result = ingest_orderbook.run(str(config_path), symbols=["BTCUSDT"])

    assert result["BTCUSDT"]["used_cache"] is True
    assert result["BTCUSDT"]["spread_bps"] == 12.0
    assert result["BTCUSDT"]["orderbook_snapshot_status"] == "cached_legacy"


def test_orderbook_ingest_writes_conservative_snapshot_without_cache(tmp_path, monkeypatch):
    monkeypatch.setattr(ingest_orderbook, "DATA_ROOT", tmp_path)
    config_path = tmp_path / "enrichment.yaml"
    config_path.write_text(
        """
binance_orderbook:
  levels: 20
  notionals_usdt:
    - 100
    - 500
""",
        encoding="utf-8",
    )

    class FailingClient:
        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return None

        def orderbook(self, *_args, **_kwargs):
            raise httpx.ConnectError("reset")

    monkeypatch.setattr(ingest_orderbook, "BinanceFuturesClient", FailingClient)

    result = ingest_orderbook.run(str(config_path), symbols=["BTCUSDT"])

    assert result["BTCUSDT"]["used_cache"] is False
    assert result["BTCUSDT"]["orderbook_snapshot_status"] == "unavailable"
    assert result["BTCUSDT"]["slippage_bps_sell"] == {"100": 10000.0, "500": 10000.0}
    assert (tmp_path / "processed" / "orderbook_features" / "BTCUSDT.parquet").exists()
