from __future__ import annotations

import os
from typing import Any

import httpx


class EtherscanClient:
    def __init__(self, api_key: str | None = None, base_url: str | None = None) -> None:
        self.api_key = api_key or os.environ.get("ETHERSCAN_API_KEY", "")
        self.base_url = base_url or os.environ.get(
            "ETHERSCAN_BASE_URL", "https://api.etherscan.io/v2/api"
        )
        self.client = httpx.Client(base_url=self.base_url, timeout=20.0)

    @property
    def enabled(self) -> bool:
        return bool(self.api_key)

    def close(self) -> None:
        self.client.close()

    def __enter__(self) -> "EtherscanClient":
        return self

    def __exit__(self, *_args: Any) -> None:
        self.close()

    def get(self, params: dict[str, Any]) -> Any:
        if not self.enabled:
            return {"result": [], "missing_fields": ["api_key"]}
        payload = {"apikey": self.api_key, **params}
        response = self.client.get("", params=payload)
        response.raise_for_status()
        return response.json()

