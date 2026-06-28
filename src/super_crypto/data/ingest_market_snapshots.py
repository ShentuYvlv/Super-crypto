from __future__ import annotations

import polars as pl

from super_crypto.common.config import load_yaml
from super_crypto.common.paths import DATA_ROOT, ensure_parent
from super_crypto.common.time import to_iso, utc_now
from super_crypto.data.binance_client import BinanceFuturesClient, ticker_lookup


def run(config_path: str) -> dict:
    config = load_yaml(config_path)
    results = []
    with BinanceFuturesClient() as client:
        exchange_info = client.exchange_info()
        tickers = ticker_lookup(client.all_ticker_24hr())
        exchange_path = ensure_parent(DATA_ROOT / "raw" / "binance" / "exchange_info" / "exchange_info.json")
        exchange_path.write_text(__import__("json").dumps(exchange_info, ensure_ascii=False, indent=2), encoding="utf-8")
        for symbol in config["symbols"]:
            ticker = tickers.get(symbol, {})
            funding = client.current_funding(symbol)
            open_interest = client.open_interest(symbol)
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
    return {"rows": frame.height, "path": str(path)}

