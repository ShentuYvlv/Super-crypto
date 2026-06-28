from __future__ import annotations

import os
from typing import Any

import httpx


class CoinGlassClient:
    def __init__(self, api_key: str | None = None, base_url: str | None = None) -> None:
        self.api_key = api_key or os.environ.get("COINGLASS_API_KEY", "")
        self.base_url = base_url or os.environ.get(
            "COINGLASS_BASE_URL", "https://open-api-v4.coinglass.com"
        )
        self.client = httpx.Client(
            base_url=self.base_url,
            timeout=20.0,
            headers={"CG-API-KEY": self.api_key} if self.api_key else {},
        )

    @property
    def enabled(self) -> bool:
        return bool(self.api_key)

    def close(self) -> None:
        self.client.close()

    def __enter__(self) -> "CoinGlassClient":
        return self

    def __exit__(self, *_args: Any) -> None:
        self.close()

    def get(self, path: str, params: dict[str, Any] | None = None) -> Any:
        if not self.enabled:
            return {"data": [], "missing_fields": ["api_key"]}
        response = self.client.get(path, params=params or {})
        response.raise_for_status()
        return response.json()

