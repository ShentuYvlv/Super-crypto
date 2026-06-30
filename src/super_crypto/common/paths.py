from __future__ import annotations

import os
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[3]
SRC_ROOT = PROJECT_ROOT / "src"
DATA_ROOT = PROJECT_ROOT / os.environ.get("SUPER_CRYPTO_DATA_DIR", "data")
DB_PATH = PROJECT_ROOT / os.environ.get("SUPER_CRYPTO_DB_PATH", "data/super_crypto.db")
REPORT_ROOT = PROJECT_ROOT / os.environ.get("SUPER_CRYPTO_REPORT_DIR", "data/processed/reports")
DASHBOARD_ROOT = PROJECT_ROOT / "dashboard"
DASHBOARD_OUT = DASHBOARD_ROOT / "out"


def ensure_directory(path: Path) -> Path:
    path.mkdir(parents=True, exist_ok=True)
    return path


def ensure_parent(path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


def resolve_project_path(path: str | Path) -> Path:
    resolved = Path(path)
    if resolved.is_absolute():
        return resolved
    return PROJECT_ROOT / resolved
