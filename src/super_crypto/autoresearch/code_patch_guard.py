from __future__ import annotations

from super_crypto.autoresearch.protected_files import forbidden_paths
from super_crypto.common.paths import resolve_project_path


def assert_allowed(paths: list[str]) -> None:
    forbidden = [resolve_project_path(path).resolve() for path in forbidden_paths()]
    for path in paths:
        resolved = resolve_project_path(path).resolve()
        if any(resolved == blocked or blocked in resolved.parents for blocked in forbidden):
            raise ValueError(f"AutoResearch cannot touch protected path: {path}")
