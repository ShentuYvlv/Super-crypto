from __future__ import annotations

import json

import httpx
import polars as pl

from super_crypto.common.config import load_yaml
from super_crypto.common.http import binance_offline_cache_enabled
from super_crypto.common.paths import DATA_ROOT, ensure_parent
from super_crypto.common.time import to_iso, utc_now
from super_crypto.data.binance_client import BinanceFuturesClient, ticker_lookup


def _exchange_info_cache_path():
    return DATA_ROOT / "raw" / "binance" / "exchange_info" / "exchange_info.json"


def _tickers_cache_path():
    return DATA_ROOT / "raw" / "binance" / "ticker_24hr" / "latest.json"


def _load_json_cache(path):
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def run(config_path: str) -> dict:
    config = load_yaml(config_path)
    results = []
    used_cache = False
    offline_cache = binance_offline_cache_enabled()
    with BinanceFuturesClient() as client:
        try:
            if offline_cache:
                raise httpx.ConnectError("offline cache mode")
            exchange_info = client.exchange_info()
            exchange_path = ensure_parent(_exchange_info_cache_path())
            exchange_path.write_text(
                json.dumps(exchange_info, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
        except httpx.HTTPError:
            exchange_info = _load_json_cache(_exchange_info_cache_path()) or {"symbols": []}
            used_cache = True

        try:
            if offline_cache:
                raise httpx.ConnectError("offline cache mode")
            ticker_rows = client.all_ticker_24hr()
            ticker_path = ensure_parent(_tickers_cache_path())
            ticker_path.write_text(
                json.dumps(ticker_rows, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
        except httpx.HTTPError:
            ticker_rows = _load_json_cache(_tickers_cache_path()) or []
            used_cache = True
        tickers = ticker_lookup(ticker_rows)

        for symbol in config["symbols"]:
            ticker = tickers.get(symbol, {})
            try:
                if offline_cache:
                    raise httpx.ConnectError("offline cache mode")
                funding = client.current_funding(symbol)
            except httpx.HTTPError:
                funding = {}
                used_cache = True
            try:
                if offline_cache:
                    raise httpx.ConnectError("offline cache mode")
                open_interest = client.open_interest(symbol)
            except httpx.HTTPError:
                open_interest = {}
                used_cache = True
            results.append(
                {
                    "symbol": symbol,
                    "snapshot_time": to_iso(utc_now()),
                    "price": float(ticker.get("lastPrice", 0.0)),
                    "price_change_percent": float(ticker.get("priceChangePercent", 0.0)) / 100.0,
                    "quote_volume": float(ticker.get("quoteVolume", 0.0)),
                    "trade_count": int(float(ticker.get("count", 0))),
                    "funding_rate": float(funding.get("lastFundingRate", 0.0)),
                    "open_interest": float(open_interest.get("openInterest", 0.0)),
                }
            )
    frame = pl.DataFrame(results)
    path = ensure_parent(DATA_ROOT / "processed" / "derivatives" / "market_snapshots.parquet")
    frame.write_parquet(path)
    return {
        "rows": frame.height,
        "path": str(path),
        "used_cache": used_cache,
        "exchange_info_symbols": len(exchange_info.get("symbols", [])),
    }
