from __future__ import annotations

import os
import time
from dataclasses import dataclass, field
from typing import Any
from urllib.parse import urljoin

import httpx

from super_crypto.common.http import http_trust_env
from super_crypto.data.coinglass_crypto import decrypt_response_data

DEFAULT_USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/149.0.0.0 Safari/537.36"
)


@dataclass(frozen=True)
class CoinGlassEndpoint:
    url: str
    params: dict[str, str] = field(default_factory=dict)


ENDPOINTS = {
    "tickers": CoinGlassEndpoint("capi:/api/coin/tickers"),
    "spot_tickers": CoinGlassEndpoint("capi:/api/spot/coin/symbol"),
    "coin_info": CoinGlassEndpoint("fapi:/api/coin/v2/info"),
    "futures_flow": CoinGlassEndpoint(
        "fapi:/api/moneyFlow/coin",
        {"type": "FUTURES"},
    ),
    "spot_flow": CoinGlassEndpoint(
        "fapi:/api/moneyFlow/coin",
        {"type": "SPOT"},
    ),
}


class CoinGlassClient:
    def __init__(
        self,
        *,
        timeout: float = 20.0,
        language: str | None = None,
        user_agent: str | None = None,
        obe: str | None = None,
    ) -> None:
        self.language = language or os.environ.get("COINGLASS_LANGUAGE", "zh")
        self.user_agent = user_agent or os.environ.get("COINGLASS_USER_AGENT", DEFAULT_USER_AGENT)
        self.obe = obe if obe is not None else os.environ.get("COINGLASS_OBE", "")
        self.capi_base_url = os.environ.get("COINGLASS_CAPI_BASE_URL", "https://capi.coinglass.com")
        self.fapi_base_url = os.environ.get("COINGLASS_FAPI_BASE_URL", "https://fapi.coinglass.com")
        self.client = httpx.Client(
            timeout=timeout,
            follow_redirects=True,
            trust_env=http_trust_env("COINGLASS"),
        )

    @property
    def enabled(self) -> bool:
        return True

    def close(self) -> None:
        self.client.close()

    def __enter__(self) -> CoinGlassClient:
        return self

    def __exit__(self, *_args: Any) -> None:
        self.close()

    def _headers(self, cache_ts_v2: str) -> dict[str, str]:
        accept_language = "zh-CN,zh;q=0.9" if self.language == "zh" else self.language
        headers = {
            "accept": "application/json",
            "accept-language": accept_language,
            "cache-ts-v2": cache_ts_v2,
            "encryption": "true",
            "language": self.language,
            "origin": "https://www.coinglass.com",
            "referer": "https://www.coinglass.com/",
            "user-agent": self.user_agent,
        }
        if self.obe:
            headers["obe"] = self.obe
        return headers

    def fetch(self, data_type: str, symbol: str) -> Any:
        if data_type not in ENDPOINTS:
            raise ValueError(f"unsupported CoinGlass data type: {data_type}")

        endpoint = ENDPOINTS[data_type]
        params = {"symbol": symbol.upper().strip(), **endpoint.params}
        cache_ts_v2 = str(int(time.time() * 1000))
        response = self.client.get(
            self._resolve_url(endpoint.url),
            params=params,
            headers=self._headers(cache_ts_v2),
        )
        response.raise_for_status()
        envelope = response.json()
        if not isinstance(envelope, dict):
            raise ValueError("CoinGlass response JSON must be an object")

        data = envelope.get("data")
        encrypted = response.headers.get("encryption") == "true"
        user_header = response.headers.get("user", "")
        v_header = response.headers.get("v", "")
        if encrypted and user_header and v_header and isinstance(data, str) and data:
            return decrypt_response_data(
                data_cipher=data,
                user_header=user_header,
                v_header=v_header,
                url=str(response.url),
                cache_ts_v2=cache_ts_v2,
                time_header=response.headers.get("time", ""),
            )
        return data

    def _resolve_url(self, url: str) -> str:
        if url.startswith("capi:"):
            return urljoin(self.capi_base_url.rstrip("/") + "/", url.removeprefix("capi:/"))
        if url.startswith("fapi:"):
            return urljoin(self.fapi_base_url.rstrip("/") + "/", url.removeprefix("fapi:/"))
        return url

    def get(self, path: str, params: dict[str, Any] | None = None) -> Any:
        response = self.client.get(path, params=params or {})
        response.raise_for_status()
        return response.json()
