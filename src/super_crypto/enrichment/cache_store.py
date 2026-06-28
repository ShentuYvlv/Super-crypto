from __future__ import annotations

import json
from pathlib import Path

from super_crypto.common.paths import DATA_ROOT, ensure_parent


def write_cache_status(name: str, payload: dict) -> str:
    path = ensure_parent(DATA_ROOT / "cache" / f"{name}.json")
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return str(path)


def read_cache_status(name: str) -> dict | None:
    path = DATA_ROOT / "cache" / f"{name}.json"
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))

