from __future__ import annotations

import os
import time
from collections.abc import Iterable
from typing import Any

import httpx

from super_crypto.common.http import http_trust_env


class BinanceFuturesClient:
    def __init__(
        self,
        base_url: str | None = None,
        timeout: float = 20.0,
        max_retries: int | None = None,
        retry_backoff_sec: float | None = None,
    ) -> None:
        self.base_url = base_url or os.environ.get("BINANCE_BASE_URL", "https://fapi.binance.com")
        self.max_retries = max_retries if max_retries is not None else int(
            os.environ.get("BINANCE_MAX_RETRIES", "3")
        )
        self.retry_backoff_sec = (
            retry_backoff_sec
            if retry_backoff_sec is not None
            else float(os.environ.get("BINANCE_RETRY_BACKOFF_SEC", "0.5"))
        )
        self.client = httpx.Client(
            base_url=self.base_url,
            timeout=timeout,
            trust_env=http_trust_env("BINANCE"),
        )

    def close(self) -> None:
        self.client.close()

    def __enter__(self) -> BinanceFuturesClient:
        return self

    def __exit__(self, *_args: Any) -> None:
        self.close()

    def _get(self, path: str, params: dict[str, Any] | None = None) -> Any:
        last_error: Exception | None = None
        attempts = max(self.max_retries, 0) + 1
        for attempt in range(attempts):
            try:
                response = self.client.get(path, params=params or {})
                response.raise_for_status()
                return response.json()
            except (
                httpx.ConnectError,
                httpx.ConnectTimeout,
                httpx.ReadError,
                httpx.ReadTimeout,
            ) as exc:
                last_error = exc
            except httpx.HTTPStatusError as exc:
                if exc.response.status_code not in {408, 425, 429, 500, 502, 503, 504}:
                    raise
                last_error = exc

            if attempt < attempts - 1:
                time.sleep(self.retry_backoff_sec * (2**attempt))

        if last_error is not None:
            raise last_error
        raise RuntimeError(f"Binance request failed without exception: {path}")

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
