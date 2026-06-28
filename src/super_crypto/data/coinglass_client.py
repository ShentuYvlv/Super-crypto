from __future__ import annotations

import os
from typing import Any

import httpx


class CoinGlassClient:
    def __init__(self, base_url: str | None = None) -> None:
        self.base_url = base_url or os.environ.get(
            "COINGLASS_BASE_URL", "https://www.coinglass.com"
        )
        self.client = httpx.Client(
            base_url=self.base_url,
            timeout=20.0,
            headers={
                "accept": "application/json, text/plain, */*",
                "user-agent": "Mozilla/5.0 SuperCryptoResearch/0.1",
            },
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

    def get(self, path: str, params: dict[str, Any] | None = None) -> Any:
        response = self.client.get(path, params=params or {})
        response.raise_for_status()
        return response.json()
