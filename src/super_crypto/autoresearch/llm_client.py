from __future__ import annotations

import json
import os
from dataclasses import dataclass
from typing import Any

import httpx


def _extract_json(text: str) -> dict[str, Any]:
    stripped = text.strip()
    if stripped.startswith("```"):
        stripped = stripped.strip("`")
        if stripped.lower().startswith("json"):
            stripped = stripped[4:]
    start = stripped.find("{")
    end = stripped.rfind("}")
    if start == -1 or end == -1 or end < start:
        raise ValueError("LLM response did not contain a JSON object")
    return json.loads(stripped[start : end + 1])


@dataclass
class AutoResearchLLMClient:
    base_url: str
    api_key: str
    model: str
    timeout_sec: float = 60.0

    @classmethod
    def from_env(cls) -> "AutoResearchLLMClient | None":
        base_url = os.environ.get("LLM_BASE_URL", "").rstrip("/")
        api_key = os.environ.get("LLM_API_KEY", "")
        model = os.environ.get("LLM_MODEL", "")
        if not base_url or not api_key or not model:
            return None
        return cls(base_url=base_url, api_key=api_key, model=model)

    def complete_json(self, *, system: str, user: dict[str, Any]) -> dict[str, Any]:
        url = f"{self.base_url}/chat/completions"
        payload = {
            "model": self.model,
            "temperature": 0.2,
            "response_format": {"type": "json_object"},
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": json.dumps(user, ensure_ascii=False, default=str)},
            ],
        }
        headers = {"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"}
        with httpx.Client(timeout=self.timeout_sec) as client:
            response = client.post(url, headers=headers, json=payload)
            response.raise_for_status()
        content = response.json()["choices"][0]["message"]["content"]
        return _extract_json(content)


def llm_status(client: AutoResearchLLMClient | None) -> dict[str, str | bool]:
    if client is None:
        return {
            "enabled": False,
            "mode": "rules_fallback",
            "model": "",
            "reason": "LLM_BASE_URL / LLM_API_KEY / LLM_MODEL not fully configured",
        }
    return {"enabled": True, "mode": "llm", "model": client.model, "reason": "configured"}
