from __future__ import annotations

import yaml

from super_crypto.autoresearch.code_patch_guard import assert_allowed
from super_crypto.common.config import hash_payload, load_yaml
from super_crypto.common.paths import DATA_ROOT, ensure_directory, resolve_project_path


def apply_patch_to_config(config_path: str, updates: dict) -> dict:
    assert_allowed([config_path])
    payload = load_yaml(config_path)
    payload.update(updates)
    path = resolve_project_path(config_path)
    path.write_text(yaml.safe_dump(payload, sort_keys=False, allow_unicode=True), encoding="utf-8")
    return payload


def write_experiment_variant(base_config_path: str, plan: dict) -> str:
    base_config = load_yaml(base_config_path)
    variant = {
        **base_config,
        "name": f"{base_config.get('name', 'experiment')}_autoresearch",
        "parameter_grid": plan.get("suggested_changes", {}).get(
            "parameter_grid", base_config.get("parameter_grid", {})
        ),
        "autoresearch": {
            "base_config": base_config_path,
            "hypothesis": plan["hypothesis"],
            "notes": plan.get("suggested_changes", {}).get("notes"),
        },
    }
    output_dir = ensure_directory(DATA_ROOT / "processed" / "autoresearch" / "configs")
    output_path = output_dir / f"experiment_{hash_payload(variant)[:12]}.yaml"
    assert_allowed([str(output_path)])
    output_path.write_text(
        yaml.safe_dump(variant, sort_keys=False, allow_unicode=True),
        encoding="utf-8",
    )
    return str(output_path)
