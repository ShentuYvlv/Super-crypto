from __future__ import annotations

from super_crypto.common.config import load_yaml


def forbidden_paths(config_path: str = "configs/protected_files.yaml") -> list[str]:
    return load_yaml(config_path)["forbidden"]

