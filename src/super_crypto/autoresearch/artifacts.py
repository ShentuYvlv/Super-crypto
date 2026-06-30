from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from super_crypto.common.config import canonical_json, hash_payload
from super_crypto.common.paths import DATA_ROOT, ensure_directory, ensure_parent
from super_crypto.common.time import to_iso, utc_now


def create_run_dir(config_path: str) -> tuple[str, Path]:
    run_id = hash_payload({"config_path": config_path, "created_at": to_iso(utc_now())})[:12]
    run_dir = ensure_directory(DATA_ROOT / "processed" / "autoresearch" / "runs" / run_id)
    ensure_directory(run_dir / "iterations")
    return run_id, run_dir


def write_json(path: Path, payload: dict[str, Any]) -> str:
    ensure_parent(path)
    path.write_text(canonical_json(payload), encoding="utf-8")
    return str(path)


def write_markdown(path: Path, payload: dict[str, Any]) -> str:
    ensure_parent(path)
    lines = [
        f"# AutoResearch Recommendation {payload['run_id']}",
        "",
        f"- Status: {payload['status']}",
        f"- Model mode: {payload['model_status']['mode']}",
        f"- Iterations: {len(payload['iterations'])}",
        "",
        "## Latest Recommendation",
        "",
        payload.get("recommendation", "No recommendation generated."),
        "",
        "## Iterations",
    ]
    for iteration in payload["iterations"]:
        acceptance = iteration["validation_acceptance"]
        experiment = iteration["validation_result"]["experiment"]
        lines.extend(
            [
                "",
                f"### Iteration {iteration['iteration']}",
                "",
                f"- Hypothesis: {iteration['hypothesis'].get('hypothesis')}",
                f"- Experiment: {experiment['experiment_id']}",
                f"- Status: {experiment['status']}",
                f"- Trades: {experiment['metrics']['trade_count']}",
                f"- Net return: {experiment['metrics']['net_return']:.4f}",
                f"- Decision: {acceptance['reason']}",
            ]
        )
    path.write_text("\n".join(lines), encoding="utf-8")
    return str(path)


def latest_run_manifest() -> dict[str, Any] | None:
    root = DATA_ROOT / "processed" / "autoresearch" / "runs"
    if not root.exists():
        return None
    manifests = sorted(root.glob("*/manifest.json"), key=lambda path: path.stat().st_mtime, reverse=True)
    if not manifests:
        return None
    return json.loads(manifests[0].read_text(encoding="utf-8"))


def list_run_manifests() -> list[dict[str, Any]]:
    root = DATA_ROOT / "processed" / "autoresearch" / "runs"
    if not root.exists():
        return []
    manifests = sorted(root.glob("*/manifest.json"), key=lambda path: path.stat().st_mtime, reverse=True)
    return [json.loads(path.read_text(encoding="utf-8")) for path in manifests]
