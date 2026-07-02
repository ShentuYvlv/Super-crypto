from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path
from statistics import median
from typing import Any

import pandas as pd
import yaml

from super_crypto.autoresearch.artifacts import create_cycle_run_dir, write_json
from super_crypto.autoresearch.llm_client import AutoResearchLLMClient, llm_status
from super_crypto.common.config import hash_payload, load_yaml
from super_crypto.common.config_symbols import data_config_with_resolved_symbols
from super_crypto.common.paths import DATA_ROOT, resolve_project_path
from super_crypto.common.time import to_iso, utc_now
from super_crypto.cycles.detect_pump_dump import detect_cycles
from super_crypto.cycles.seed_events import build_event_set

SYSTEM_PROMPT = """You are a CycleResearch assistant for crypto manipulation-cycle research.
Return compact JSON only. Do not propose trading entries, execution, holdout access,
or production changes.
Your task is to propose testable definitions of pump-dump manipulation cycles.
Use Simplified Chinese for hypothesis, rationale, risk, and notes."""


DEFAULT_CYCLE_GRID = [
    {
        "pump_threshold_min": 0.16,
        "pump_threshold_max": 0.45,
        "dump_retrace_ratio": 0.45,
        "max_cycle_hours": 48,
        "dedupe_gap_hours": 4,
    },
    {
        "pump_threshold_min": 0.20,
        "pump_threshold_max": 0.50,
        "dump_retrace_ratio": 0.55,
        "max_cycle_hours": 96,
        "dedupe_gap_hours": 6,
    },
    {
        "pump_threshold_min": 0.25,
        "pump_threshold_max": 0.75,
        "dump_retrace_ratio": 0.50,
        "max_cycle_hours": 72,
        "dedupe_gap_hours": 8,
    },
]


PARAM_BOUNDS = {
    "pump_threshold_min": (0.05, 1.5),
    "pump_threshold_max": (0.08, 3.0),
    "dump_retrace_ratio": (0.2, 1.2),
    "max_cycle_hours": (4.0, 240.0),
    "dedupe_gap_hours": (0.0, 72.0),
}


def _candidate_from_base(base_cycle: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    candidate = deepcopy(base_cycle)
    candidate.update(override)
    for key, (minimum, maximum) in PARAM_BOUNDS.items():
        value = float(candidate[key])
        candidate[key] = max(minimum, min(maximum, value))
    if candidate["pump_threshold_max"] <= candidate["pump_threshold_min"]:
        candidate["pump_threshold_max"] = min(
            PARAM_BOUNDS["pump_threshold_max"][1],
            float(candidate["pump_threshold_min"]) * 1.8,
        )
    candidate["max_cycle_hours"] = int(round(float(candidate["max_cycle_hours"])))
    candidate["dedupe_gap_hours"] = int(round(float(candidate["dedupe_gap_hours"])))
    return candidate


def _fallback_candidates(base_cycle: dict[str, Any], limit: int) -> list[dict[str, Any]]:
    variants = [_candidate_from_base(base_cycle, item) for item in DEFAULT_CYCLE_GRID]
    variants.append(
        _candidate_from_base(
            base_cycle,
            {
                "pump_threshold_min": float(base_cycle["pump_threshold_min"]) * 0.8,
                "pump_threshold_max": float(base_cycle["pump_threshold_max"]) * 1.2,
                "dump_retrace_ratio": float(base_cycle["dump_retrace_ratio"]) * 0.9,
            },
        )
    )
    deduped: list[dict[str, Any]] = []
    seen: set[str] = set()
    for candidate in variants:
        key = hash_payload(candidate)
        if key in seen:
            continue
        seen.add(key)
        deduped.append(candidate)
    return deduped[:limit]


def _llm_candidates(
    client: AutoResearchLLMClient | None,
    *,
    base_cycle: dict[str, Any],
    symbols: list[str],
    run_limit: int,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    fallback = _fallback_candidates(base_cycle, run_limit)
    if client is None:
        return fallback, {
            "mode": "rules_fallback",
            "hypothesis": "用宽松、基准、偏严格三组周期定义搜索操盘周期边界。",
            "rationale": "未配置大模型，使用规则候选覆盖不同拉盘幅度、回撤比例和周期时长。",
            "risk": "规则候选不能理解文章语义或人工体感，只能提供参数空间基线。",
        }
    try:
        payload = client.complete_json(
            system=SYSTEM_PROMPT,
            user={
                "task": "propose_cycle_definition_candidates",
                "base_cycle_config": base_cycle,
                "symbols": symbols,
                "candidate_count": run_limit,
                "allowed_parameters": list(PARAM_BOUNDS),
                "required_schema": {
                    "hypothesis": "testable cycle-definition hypothesis in Chinese",
                    "rationale": "why these candidates cover manipulation-cycle boundaries",
                    "risk": "main false-positive or false-negative risk",
                    "candidates": [
                        {
                            "pump_threshold_min": "float",
                            "pump_threshold_max": "float",
                            "dump_retrace_ratio": "float",
                            "max_cycle_hours": "int",
                            "dedupe_gap_hours": "int",
                            "notes": "Chinese note",
                        }
                    ],
                },
            },
        )
        raw_candidates = payload.get("candidates")
        if not isinstance(raw_candidates, list):
            return fallback, {
                **payload,
                "mode": "rules_fallback",
                "llm_error": "missing candidates",
            }
        candidates = [
            _candidate_from_base(base_cycle, item)
            for item in raw_candidates
            if isinstance(item, dict)
        ]
        if not candidates:
            return fallback, {**payload, "mode": "rules_fallback", "llm_error": "empty candidates"}
        return candidates[:run_limit], {
            "mode": "llm",
            "hypothesis": str(payload.get("hypothesis") or "大模型提出周期定义候选。"),
            "rationale": str(payload.get("rationale") or ""),
            "risk": str(payload.get("risk") or ""),
        }
    except Exception as exc:
        return fallback, {
            "mode": "rules_fallback",
            "hypothesis": "大模型不可用，回退到规则候选。",
            "rationale": "CycleResearch 必须可离线运行，不能因为模型失败阻塞周期定义评估。",
            "risk": "fallback 参数空间有限。",
            "llm_error": f"{type(exc).__name__}: {exc}",
        }


def _load_ohlcv(symbol: str, timeframe: str) -> pd.DataFrame:
    path = DATA_ROOT / "processed" / "ohlcv" / timeframe / f"{symbol}.parquet"
    if not path.exists():
        return pd.DataFrame()
    frame = pd.read_parquet(path)
    if "open_time" in frame:
        frame["open_time"] = pd.to_datetime(frame["open_time"], utc=True)
    return frame


def _write_candidate_cycles(
    *,
    candidate_dir: Path,
    candidate_config: dict[str, Any],
    symbols: list[str],
    timeframe: str,
) -> tuple[pd.DataFrame, dict[str, int]]:
    cycles_by_symbol: dict[str, int] = {}
    frames: list[pd.DataFrame] = []
    cycles_dir = candidate_dir / "cycles"
    cycles_dir.mkdir(parents=True, exist_ok=True)
    for symbol in symbols:
        ohlcv = _load_ohlcv(symbol, timeframe)
        cycles = [] if ohlcv.empty else detect_cycles(ohlcv, symbol, candidate_config)
        records = []
        for cycle in cycles:
            record = cycle.model_dump(mode="json")
            record["score_context"] = json.dumps(
                record.get("score_context", {}),
                ensure_ascii=False,
            )
            records.append(record)
        frame = pd.DataFrame(records)
        frame.to_parquet(cycles_dir / f"{symbol}.parquet", index=False)
        cycles_by_symbol[symbol] = int(len(frame))
        if not frame.empty:
            frames.append(frame)
    return (pd.concat(frames, ignore_index=True) if frames else pd.DataFrame(), cycles_by_symbol)


def _cycle_quality_score(
    cycles: pd.DataFrame,
    cycles_by_symbol: dict[str, int],
    seed_manifest: dict[str, Any],
) -> dict[str, Any]:
    cycle_count = int(len(cycles))
    covered_symbols = sum(1 for value in cycles_by_symbol.values() if value > 0)
    symbol_count = max(len(cycles_by_symbol), 1)
    coverage_ratio = covered_symbols / symbol_count
    if cycles.empty:
        return {
            "score": 0.0,
            "cycle_count": 0,
            "covered_symbols": covered_symbols,
            "coverage_ratio": coverage_ratio,
            "median_pump_return": 0.0,
            "median_dump_return": 0.0,
            "median_duration_hours": 0.0,
            "matched_seed_event_count": int(seed_manifest.get("matched_seed_event_count", 0)),
            "expanded_event_count": int(seed_manifest.get("expanded_event_count", 0)),
            "rejection_reason": "no_cycles",
        }
    counts = list(cycles_by_symbol.values())
    density_penalty = 0.0
    if cycle_count < max(5, symbol_count):
        density_penalty += 0.25
    if cycle_count > symbol_count * 250:
        density_penalty += 0.25
    concentration_penalty = 0.0
    if sum(counts) > 0 and max(counts) / sum(counts) > 0.45:
        concentration_penalty = 0.2
    seed_bonus = min(int(seed_manifest.get("matched_seed_event_count", 0)) / 3, 1.0) * 0.2
    expanded_count = int(seed_manifest.get("expanded_event_count", 0))
    expanded_bonus = min(expanded_count / max(symbol_count * 4, 1), 1.0) * 0.15
    score = (
        coverage_ratio * 0.35
        + min(cycle_count / max(symbol_count * 12, 1), 1.0) * 0.25
        + seed_bonus
        + expanded_bonus
        - density_penalty
        - concentration_penalty
    )
    return {
        "score": max(0.0, round(score, 6)),
        "cycle_count": cycle_count,
        "covered_symbols": covered_symbols,
        "coverage_ratio": round(coverage_ratio, 6),
        "median_pump_return": float(cycles["pump_return"].median()),
        "median_dump_return": float(cycles["dump_return"].median()),
        "median_duration_hours": float(cycles["duration_hours"].median()),
        "cycles_per_symbol_median": float(median(counts)) if counts else 0.0,
        "matched_seed_event_count": int(seed_manifest.get("matched_seed_event_count", 0)),
        "expanded_event_count": expanded_count,
        "rejection_reason": "",
    }


def _evaluate_candidate(
    *,
    run_dir: Path,
    index: int,
    candidate_config: dict[str, Any],
    seed_events_config: dict[str, Any],
    symbols: list[str],
    timeframe: str,
) -> dict[str, Any]:
    candidate_id = f"cycle_{index:02d}_{hash_payload(candidate_config)[:8]}"
    candidate_dir = run_dir / "candidates" / candidate_id
    candidate_dir.mkdir(parents=True, exist_ok=True)
    cycle_config_path = candidate_dir / "cycle.yaml"
    seed_config_path = candidate_dir / "seed_events.yaml"
    cycle_config_path.write_text(
        yaml.safe_dump(candidate_config, sort_keys=False, allow_unicode=True),
        encoding="utf-8",
    )
    seed_config_path.write_text(
        yaml.safe_dump(seed_events_config, sort_keys=False, allow_unicode=True),
        encoding="utf-8",
    )
    cycles, cycles_by_symbol = _write_candidate_cycles(
        candidate_dir=candidate_dir,
        candidate_config=candidate_config,
        symbols=symbols,
        timeframe=timeframe,
    )
    event_manifest = build_event_set(
        str(seed_config_path),
        str(cycle_config_path),
        cycles_dir=candidate_dir / "cycles",
        output_dir=candidate_dir / "event_sets",
    )
    quality = _cycle_quality_score(cycles, cycles_by_symbol, event_manifest)
    result = {
        "candidate_id": candidate_id,
        "cycle_config": candidate_config,
        "quality": quality,
        "cycles_by_symbol": cycles_by_symbol,
        "event_set_manifest": event_manifest,
        "cycle_config_path": str(cycle_config_path),
        "seed_events_config_path": str(seed_config_path),
    }
    write_json(candidate_dir / "result.json", result)
    return result


def _apply_best_cycle_config(pipeline_config_path: str, best_config: dict[str, Any]) -> str:
    path = resolve_project_path(pipeline_config_path)
    payload = load_yaml(path)
    payload["cycle"] = best_config
    if isinstance(payload.get("experiment"), dict):
        payload["experiment"]["cycle"] = best_config
    path.write_text(yaml.safe_dump(payload, sort_keys=False, allow_unicode=True), encoding="utf-8")
    return str(path)


def _allowed_pipeline_config(
    pipeline_config_path: str,
    autoresearch_config: dict[str, Any],
) -> bool:
    allowed = autoresearch_config.get("allowed_pipeline_config_files", [])
    if not allowed:
        return True
    requested = resolve_project_path(pipeline_config_path).resolve()
    allowed_paths = {resolve_project_path(path).resolve() for path in allowed}
    return requested in allowed_paths


def run_cycle_research(
    pipeline_config_path: str = "configs/pipeline_v4a.yaml",
    autoresearch_config_path: str = "configs/autoresearch.yaml",
    *,
    max_runs: int | None = None,
    use_llm: bool = True,
    apply_best: bool = False,
) -> dict[str, Any]:
    pipeline_config = load_yaml(pipeline_config_path)
    autoresearch_config = load_yaml(autoresearch_config_path)
    if not _allowed_pipeline_config(pipeline_config_path, autoresearch_config):
        raise ValueError(f"CycleResearch pipeline config is not allowed: {pipeline_config_path}")
    run_limit = int(max_runs or autoresearch_config.get("max_cycle_validation_runs", 3))
    run_limit = max(1, min(run_limit, 20))
    base_cycle = pipeline_config["cycle"]
    data_config = data_config_with_resolved_symbols(pipeline_config)
    seed_events_config = pipeline_config["seed_events"]
    symbols = list(data_config["symbols"])
    timeframe = str(
        base_cycle.get("timeframe")
        or pipeline_config["experiment"]["strategy"]["timeframe"]
    )
    client = AutoResearchLLMClient.from_env() if use_llm else None
    run_id, run_dir = create_cycle_run_dir(pipeline_config_path)
    candidates, hypothesis = _llm_candidates(
        client,
        base_cycle=base_cycle,
        symbols=symbols,
        run_limit=run_limit,
    )
    started_at = to_iso(utc_now())
    candidate_results = [
        _evaluate_candidate(
            run_dir=run_dir,
            index=index,
            candidate_config=candidate,
            seed_events_config=seed_events_config,
            symbols=symbols,
            timeframe=timeframe,
        )
        for index, candidate in enumerate(candidates, start=1)
    ]
    ranked = sorted(candidate_results, key=lambda item: item["quality"]["score"], reverse=True)
    best = ranked[0] if ranked else None
    applied_path = (
        _apply_best_cycle_config(pipeline_config_path, best["cycle_config"])
        if apply_best and best
        else None
    )
    manifest = {
        "run_id": run_id,
        "created_at": started_at,
        "completed_at": to_iso(utc_now()),
        "status": "completed" if best else "failed",
        "pipeline_config_path": pipeline_config_path,
        "autoresearch_config_path": autoresearch_config_path,
        "model_status": llm_status(client),
        "hypothesis": hypothesis,
        "base_cycle_config": base_cycle,
        "timeframe": timeframe,
        "symbols": symbols,
        "candidate_count": len(candidate_results),
        "best_candidate_id": best["candidate_id"] if best else None,
        "best_cycle_config": best["cycle_config"] if best else None,
        "best_quality": best["quality"] if best else None,
        "applied_path": applied_path,
        "candidates": candidate_results,
    }
    manifest["manifest_path"] = write_json(run_dir / "manifest.json", manifest)
    return manifest
