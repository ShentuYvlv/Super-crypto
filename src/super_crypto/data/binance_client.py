from __future__ import annotations

import os
from collections.abc import Iterable
from typing import Any

import httpx


class BinanceFuturesClient:
    def __init__(self, base_url: str | None = None, timeout: float = 20.0) -> None:
        self.base_url = base_url or os.environ.get("BINANCE_BASE_URL", "https://fapi.binance.com")
        self.client = httpx.Client(base_url=self.base_url, timeout=timeout)

    def close(self) -> None:
        self.client.close()

    def __enter__(self) -> "BinanceFuturesClient":
        return self

    def __exit__(self, *_args: Any) -> None:
        self.close()

    def _get(self, path: str, params: dict[str, Any] | None = None) -> Any:
        response = self.client.get(path, params=params or {})
        response.raise_for_status()
        return response.json()

    def exchange_info(self) -> dict[str, Any]:
        return self._get("/fapi/v1/exchangeInfo")

    def all_ticker_24hr(self) -> list[dict[str, Any]]:
        result = self._get("/fapi/v1/ticker/24hr")
        return result if isinstance(result, list) else [result]

    def klines(self, symbol: str, interval: str, limit: int = 1500) -> list[list[Any]]:
        return self._get(
            "/fapi/v1/klines",
            params={"symbol": symbol, "interval": interval, "limit": min(limit, 1500)},
        )

    def funding_rate_history(self, symbol: str, limit: int = 200) -> list[dict[str, Any]]:
        return self._get(
            "/fapi/v1/fundingRate",
            params={"symbol": symbol, "limit": min(limit, 1000)},
        )

    def current_funding(self, symbol: str) -> dict[str, Any]:
        return self._get("/fapi/v1/premiumIndex", params={"symbol": symbol})

    def open_interest(self, symbol: str) -> dict[str, Any]:
        return self._get("/fapi/v1/openInterest", params={"symbol": symbol})

    def orderbook(self, symbol: str, limit: int = 20) -> dict[str, Any]:
        return self._get("/fapi/v1/depth", params={"symbol": symbol, "limit": min(limit, 1000)})


def active_usdt_perpetual_symbols(exchange_info: dict[str, Any]) -> list[str]:
    results: list[str] = []
    for symbol in exchange_info.get("symbols", []):
        if symbol.get("contractType") != "PERPETUAL":
            continue
        if symbol.get("status") != "TRADING":
            continue
        if symbol.get("quoteAsset") != "USDT":
            continue
        results.append(symbol["symbol"])
    return sorted(results)


def ticker_lookup(tickers: Iterable[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    return {ticker["symbol"]: ticker for ticker in tickers}

