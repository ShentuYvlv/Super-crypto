from __future__ import annotations

import json
import shutil
from pathlib import Path
from typing import Any

from super_crypto.common.config import canonical_json, hash_payload
from super_crypto.common.paths import DATA_ROOT, ensure_directory, ensure_parent
from super_crypto.common.time import to_iso, utc_now

USER_TEXT_TRANSLATIONS = {
    "Increase signal coverage before judging profitability.": "先提高信号覆盖率，再判断盈利能力。",
    "No validation run completed.": "没有完成验证实验。",
    "No recommendation generated.": "没有生成建议。",
}


def _autoresearch_root() -> Path:
    return DATA_ROOT / "processed" / "autoresearch" / "runs"


def cycle_research_root() -> Path:
    return DATA_ROOT / "processed" / "cycle_research" / "runs"


def _looks_english(text: str) -> bool:
    letters = [char for char in text if char.isalpha()]
    if not letters:
        return False
    ascii_letters = [char for char in letters if char.isascii()]
    has_chinese = any("\u4e00" <= char <= "\u9fff" for char in text)
    return not has_chinese and len(ascii_letters) / max(len(letters), 1) > 0.7


def localize_user_text(value: Any) -> Any:
    if not isinstance(value, str) or not value.strip():
        return value
    stripped = value.strip()
    if stripped in USER_TEXT_TRANSLATIONS:
        return USER_TEXT_TRANSLATIONS[stripped]
    if stripped.startswith("Relax entry constraints further to increase trade count."):
        return (
            "进一步放宽入场约束以提高交易数量。可以把支撑跌破阈值扩大到 0.015-0.02，"
            "把首次卖压阈值扩大到 -0.04 附近，或切换到最高价/最低价支撑类型；"
            "同时增加标的数量、拉长回看窗口，提高信号多样性。"
        )
    if _looks_english(stripped):
        return "模型返回了英文内容，已隐藏原文；请重新运行研究循环生成中文建议。"
    return value


def localize_manifest(manifest: dict[str, Any]) -> dict[str, Any]:
    manifest["recommendation"] = localize_user_text(manifest.get("recommendation"))
    for iteration in manifest.get("iterations", []):
        hypothesis = iteration.get("hypothesis") or {}
        for key in ("hypothesis", "rationale", "risk"):
            hypothesis[key] = localize_user_text(hypothesis.get(key))
        plan = iteration.get("plan") or {}
        suggested_changes = plan.get("suggested_changes") or {}
        suggested_changes["notes"] = localize_user_text(suggested_changes.get("notes"))
        review = iteration.get("review") or {}
        for key in ("decision", "recommendation"):
            review[key] = localize_user_text(review.get(key))
        if isinstance(review.get("evidence"), list):
            review["evidence"] = [localize_user_text(item) for item in review["evidence"]]
    return manifest


def create_run_dir(config_path: str) -> tuple[str, Path]:
    run_id = hash_payload({"config_path": config_path, "created_at": to_iso(utc_now())})[:12]
    run_dir = ensure_directory(_autoresearch_root() / run_id)
    ensure_directory(run_dir / "iterations")
    return run_id, run_dir


def create_cycle_run_dir(config_path: str) -> tuple[str, Path]:
    run_id = hash_payload({"cycle_config_path": config_path, "created_at": to_iso(utc_now())})[:12]
    run_dir = ensure_directory(cycle_research_root() / run_id)
    ensure_directory(run_dir / "candidates")
    return run_id, run_dir


def write_json(path: Path, payload: dict[str, Any]) -> str:
    ensure_parent(path)
    path.write_text(canonical_json(payload), encoding="utf-8")
    return str(path)


def write_markdown(path: Path, payload: dict[str, Any]) -> str:
    ensure_parent(path)
    cycle_research = payload.get("cycle_research_result") or {}
    cycle_quality = cycle_research.get("best_quality") or {}
    lines = [
        f"# 自动研究建议 {payload['run_id']}",
        "",
        f"- 状态: {payload['status']}",
        f"- 模型模式: {payload['model_status']['mode']}",
        f"- 轮数: {len(payload['iterations'])}",
    ]
    if cycle_research:
        lines.extend(
            [
                f"- 周期定义研究: {cycle_research.get('run_id', '-')}",
                f"- 最佳周期质量分: {cycle_quality.get('score', '-')}",
                f"- 最佳周期数量: {cycle_quality.get('cycle_count', '-')}",
            ]
        )
    lines.extend(
        [
            "",
            "## 最新建议",
            "",
            localize_user_text(payload.get("recommendation", "No recommendation generated.")),
            "",
            "## 周期定义研究",
            "",
        ]
    )
    if cycle_research:
        lines.extend(
            [
                f"- 候选数: {cycle_research.get('candidate_count', '-')}",
                f"- 最佳候选: {cycle_research.get('best_candidate_id', '-')}",
                f"- 最佳定义: {cycle_research.get('best_cycle_config', {})}",
                "",
            ]
        )
    else:
        lines.extend(["未启用或未完成周期定义研究。", ""])
    lines.append("## 策略验证轮次")
    for iteration in payload["iterations"]:
        acceptance = iteration["validation_acceptance"]
        experiment = iteration["validation_result"]["experiment"]
        lines.extend(
            [
                "",
                f"### 第 {iteration['iteration']} 轮",
                "",
                f"- 假设: {localize_user_text(iteration['hypothesis'].get('hypothesis'))}",
                f"- 实验: {experiment['experiment_id']}",
                f"- 状态: {experiment['status']}",
                f"- 交易数: {experiment['metrics']['trade_count']}",
                f"- 净收益: {experiment['metrics']['net_return']:.4f}",
                f"- 结论: {acceptance['reason']}",
            ]
        )
    path.write_text("\n".join(lines), encoding="utf-8")
    return str(path)


def latest_run_manifest() -> dict[str, Any] | None:
    root = _autoresearch_root()
    if not root.exists():
        return None
    manifests = sorted(
        root.glob("*/manifest.json"),
        key=lambda path: path.stat().st_mtime,
        reverse=True,
    )
    if not manifests:
        return None
    return localize_manifest(json.loads(manifests[0].read_text(encoding="utf-8")))


def list_run_manifests() -> list[dict[str, Any]]:
    root = _autoresearch_root()
    if not root.exists():
        return []
    manifests = sorted(
        root.glob("*/manifest.json"),
        key=lambda path: path.stat().st_mtime,
        reverse=True,
    )
    return [localize_manifest(json.loads(path.read_text(encoding="utf-8"))) for path in manifests]


def delete_run_artifacts(run_ids: list[str]) -> dict[str, Any]:
    root = _autoresearch_root().resolve()
    deleted: list[str] = []
    missing: list[str] = []
    for run_id in sorted(set(run_ids)):
        run_dir = (root / run_id).resolve()
        try:
            run_dir.relative_to(root)
        except ValueError as exc:
            raise ValueError(f"Invalid AutoResearch run id: {run_id}") from exc
        if not (run_dir / "manifest.json").exists():
            missing.append(run_id)
            continue
        shutil.rmtree(run_dir)
        deleted.append(run_id)
    return {"deleted_run_ids": deleted, "missing_run_ids": missing}


def latest_cycle_run_manifest() -> dict[str, Any] | None:
    root = cycle_research_root()
    if not root.exists():
        return None
    manifests = sorted(
        root.glob("*/manifest.json"),
        key=lambda path: path.stat().st_mtime,
        reverse=True,
    )
    if not manifests:
        return None
    return json.loads(manifests[0].read_text(encoding="utf-8"))


def list_cycle_run_manifests() -> list[dict[str, Any]]:
    root = cycle_research_root()
    if not root.exists():
        return []
    manifests = sorted(
        root.glob("*/manifest.json"),
        key=lambda path: path.stat().st_mtime,
        reverse=True,
    )
    return [json.loads(path.read_text(encoding="utf-8")) for path in manifests]


def delete_cycle_run_artifacts(run_ids: list[str]) -> dict[str, Any]:
    root = cycle_research_root().resolve()
    deleted: list[str] = []
    missing: list[str] = []
    for run_id in sorted(set(run_ids)):
        run_dir = (root / run_id).resolve()
        try:
            run_dir.relative_to(root)
        except ValueError as exc:
            raise ValueError(f"Invalid CycleResearch run id: {run_id}") from exc
        if not (run_dir / "manifest.json").exists():
            missing.append(run_id)
            continue
        shutil.rmtree(run_dir)
        deleted.append(run_id)
    return {"deleted_run_ids": deleted, "missing_run_ids": missing}
