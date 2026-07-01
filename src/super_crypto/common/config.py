from __future__ import annotations

import hashlib
import json
import os
from datetime import date, datetime
from pathlib import Path
from typing import Any

import yaml

from super_crypto.common.paths import resolve_project_path


def _expand_env(value: Any) -> Any:
    if isinstance(value, dict):
        return {key: _expand_env(inner) for key, inner in value.items()}
    if isinstance(value, list):
        return [_expand_env(item) for item in value]
    if isinstance(value, str):
        return os.path.expandvars(value)
    return value


def load_yaml(path: str | Path | dict[str, Any]) -> dict[str, Any]:
    if isinstance(path, dict):
        return _expand_env(path)
    file_path = resolve_project_path(path)
    with file_path.open("r", encoding="utf-8") as handle:
        loaded = yaml.safe_load(handle) or {}
    return _expand_env(loaded)


def canonical_json(value: Any) -> str:
    def default_serializer(obj: Any) -> str:
        if isinstance(obj, (datetime, date)):
            return obj.isoformat()
        raise TypeError(f"Object of type {obj.__class__.__name__} is not JSON serializable")

    return json.dumps(
        value,
        sort_keys=True,
        ensure_ascii=False,
        separators=(",", ":"),
        default=default_serializer,
    )


def hash_payload(value: Any) -> str:
    return hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()


def hash_file(path: str | Path) -> str:
    file_path = resolve_project_path(path)
    return hashlib.sha256(file_path.read_bytes()).hexdigest()
