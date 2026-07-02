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
        "dump_return_min": 0.10,
        "dump_retrace_ratio": 0.45,
        "max_cycle_hours": 48,
        "dedupe_gap_hours": 12,
        "min_peak_distance_from_start_hours": 1,
        "min_pump_duration_hours": 1,
        "max_pump_duration_hours": 24,
    },
    {
        "pump_threshold_min": 0.20,
        "pump_threshold_max": 0.50,
        "dump_return_min": 0.15,
        "dump_retrace_ratio": 0.55,
        "max_cycle_hours": 96,
        "dedupe_gap_hours": 24,
        "min_peak_distance_from_start_hours": 2,
        "min_pump_duration_hours": 2,
        "max_pump_duration_hours": 48,
    },
    {
        "pump_threshold_min": 0.25,
        "pump_threshold_max": 0.75,
        "dump_return_min": 0.20,
        "dump_retrace_ratio": 0.50,
        "max_cycle_hours": 72,
        "dedupe_gap_hours": 24,
        "min_peak_distance_from_start_hours": 2,
        "min_pump_duration_hours": 1,
        "max_pump_duration_hours": 24,
    },
]


PARAM_BOUNDS = {
    "pump_threshold_min": (0.05, 1.5),
    "pump_threshold_max": (0.08, 3.0),
    "dump_return_min": (0.0, 1.5),
    "dump_retrace_ratio": (0.2, 1.2),
    "max_cycle_hours": (4.0, 240.0),
    "dedupe_gap_hours": (0.0, 72.0),
    "min_peak_distance_from_start_hours": (0.0, 48.0),
    "min_pump_duration_hours": (0.0, 72.0),
    "max_pump_duration_hours": (1.0, 168.0),
}


CYCLE_COLUMNS = [
    "cycle_id",
    "symbol",
    "timeframe",
    "pump_start",
    "peak_time",
    "dump_end",
    "pump_return",
    "dump_return",
    "pump_duration_hours",
    "dump_duration_hours",
    "duration_hours",
    "rule_id",
    "quality_score",
    "detection_rule",
    "score_context",
]


def _candidate_from_base(base_cycle: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    candidate = deepcopy(base_cycle)
    candidate.update(override)
    candidate.setdefault("dump_return_min", 0.0)
    candidate.setdefault("dedupe_gap_hours", 24)
    candidate.setdefault("min_peak_distance_from_start_hours", 0)
    candidate.setdefault("min_pump_duration_hours", 0)
    candidate.setdefault("max_pump_duration_hours", candidate.get("max_cycle_hours", 96))
    for key, (minimum, maximum) in PARAM_BOUNDS.items():
        value = float(candidate[key])
        candidate[key] = max(minimum, min(maximum, value))
    if candidate["pump_threshold_max"] <= candidate["pump_threshold_min"]:
        candidate["pump_threshold_max"] = min(
            PARAM_BOUNDS["pump_threshold_max"][1],
            float(candidate["pump_threshold_min"]) * 1.8,
        )
    if candidate["max_pump_duration_hours"] < candidate["min_pump_duration_hours"]:
        candidate["max_pump_duration_hours"] = candidate["min_pump_duration_hours"]
    if candidate["max_pump_duration_hours"] > candidate["max_cycle_hours"]:
        candidate["max_pump_duration_hours"] = candidate["max_cycle_hours"]
    candidate["max_cycle_hours"] = int(round(float(candidate["max_cycle_hours"])))
    candidate["dedupe_gap_hours"] = int(round(float(candidate["dedupe_gap_hours"])))
    candidate["rule_id"] = str(
        candidate.get("rule_id")
        or (
            f"rule_p{float(candidate['pump_threshold_min']):g}"
            f"_d{float(candidate.get('dump_return_min', 0.0)):g}"
            f"_r{float(candidate['dump_retrace_ratio']):g}"
            f"_h{int(candidate['max_cycle_hours'])}"
        )
    )
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


def _fallback_iteration_candidates(
    *,
    base_cycle: dict[str, Any],
    iteration: int,
    limit: int,
    previous_results: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    if iteration <= 1 or not previous_results:
        return _fallback_candidates(base_cycle, limit), {
            "mode": "rules_fallback",
            "hypothesis": "第一轮用宽松、基准、偏严格三类周期定义探索操盘周期边界。",
            "rationale": "未配置大模型时，使用固定候选覆盖不同拉盘幅度、回撤比例和周期时长。",
            "risk": "规则候选不能理解人工体感，只能作为可复现基线。",
        }
    best = max(previous_results, key=lambda item: item["quality"]["score"])
    best_config = best["cycle_config"]
    variants = [
        _candidate_from_base(
            best_config,
            {
                "pump_threshold_min": float(best_config["pump_threshold_min"]) * 0.9,
                "dump_return_min": float(best_config.get("dump_return_min", 0.0)) * 0.9,
            },
        ),
        _candidate_from_base(
            best_config,
            {
                "pump_threshold_min": float(best_config["pump_threshold_min"]) * 1.1,
                "dump_return_min": float(best_config.get("dump_return_min", 0.0)) * 1.1,
            },
        ),
        _candidate_from_base(
            best_config,
            {
                "max_cycle_hours": float(best_config["max_cycle_hours"]) * 0.75,
                "dedupe_gap_hours": max(float(best_config["dedupe_gap_hours"]), 24),
            },
        ),
        _candidate_from_base(
            best_config,
            {
                "max_cycle_hours": float(best_config["max_cycle_hours"]) * 1.25,
                "min_peak_distance_from_start_hours": float(
                    best_config.get("min_peak_distance_from_start_hours", 0.0)
                )
                + 1,
            },
        ),
    ]
    deduped: list[dict[str, Any]] = []
    seen: set[str] = set()
    for candidate in variants:
        key = hash_payload(candidate)
        if key in seen:
            continue
        seen.add(key)
        deduped.append(candidate)
    return deduped[:limit], {
        "mode": "rules_fallback",
        "hypothesis": f"第 {iteration} 轮围绕上一轮最佳定义做局部扰动，验证稳定性。",
        "rationale": "通过放宽/收紧 pump、dump 和周期时长，观察核心周期是否稳定。",
        "risk": "fallback 只能局部搜索，可能错过不同形态的慢磨型操盘周期。",
        "previous_best_candidate_id": best["candidate_id"],
    }


def _llm_candidates(
    client: AutoResearchLLMClient | None,
    *,
    base_cycle: dict[str, Any],
    symbols: list[str],
    symbol_groups: dict[str, list[str]],
    previous_results: list[dict[str, Any]],
    iteration: int,
    run_limit: int,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    fallback, fallback_hypothesis = _fallback_iteration_candidates(
        base_cycle=base_cycle,
        iteration=iteration,
        limit=run_limit,
        previous_results=previous_results,
    )
    if client is None:
        return fallback, fallback_hypothesis
    try:
        payload = client.complete_json(
            system=SYSTEM_PROMPT,
            user={
                "task": "propose_cycle_definition_candidates",
                "iteration": iteration,
                "base_cycle_config": base_cycle,
                "symbols": symbols,
                "symbol_groups": symbol_groups,
                "previous_ranked_results": [
                    {
                        "candidate_id": item["candidate_id"],
                        "cycle_config": item["cycle_config"],
                        "quality": item["quality"],
                        "cycles_by_symbol": item["cycles_by_symbol"],
                    }
                    for item in sorted(
                        previous_results,
                        key=lambda previous: previous["quality"]["score"],
                        reverse=True,
                    )[:8]
                ],
                "candidate_count": run_limit,
                "allowed_parameters": list(PARAM_BOUNDS),
                "required_schema": {
                    "hypothesis": "testable cycle-definition hypothesis in Chinese",
                    "rationale": "why these candidates improve on previous results",
                    "risk": "main false-positive or false-negative risk",
                    "candidates": [
                        {
                            "pump_threshold_min": "float",
                            "pump_threshold_max": "float",
                            "dump_return_min": "float",
                            "dump_retrace_ratio": "float",
                            "max_cycle_hours": "int",
                            "dedupe_gap_hours": "int",
                            "min_peak_distance_from_start_hours": "float",
                            "min_pump_duration_hours": "float",
                            "max_pump_duration_hours": "float",
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
            "iteration": iteration,
            "hypothesis": str(payload.get("hypothesis") or "大模型提出周期定义候选。"),
            "rationale": str(payload.get("rationale") or ""),
            "risk": str(payload.get("risk") or ""),
        }
    except Exception as exc:
        return fallback, {
            **fallback_hypothesis,
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


def _empty_cycles_frame() -> pd.DataFrame:
    return pd.DataFrame(columns=CYCLE_COLUMNS)


def _symbol_groups(config: dict[str, Any], fallback_symbols: list[str]) -> dict[str, list[str]]:
    discovery = config.get("cycle_discovery", {})
    raw_groups = discovery.get("symbol_groups") or config.get("symbol_groups") or {}
    groups = {
        "strong": [str(symbol) for symbol in raw_groups.get("strong", [])],
        "volatile": [str(symbol) for symbol in raw_groups.get("volatile", [])],
        "control": [str(symbol) for symbol in raw_groups.get("control", [])],
    }
    if not any(groups.values()):
        groups["strong"] = list(fallback_symbols)
    return groups


def _symbols_from_groups(groups: dict[str, list[str]], fallback_symbols: list[str]) -> list[str]:
    symbols: list[str] = []
    for key in ("strong", "volatile", "control"):
        symbols.extend(groups.get(key, []))
    symbols.extend(fallback_symbols)
    return list(dict.fromkeys(symbols))


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
        frame = pd.DataFrame(records, columns=CYCLE_COLUMNS)
        frame.to_parquet(cycles_dir / f"{symbol}.parquet", index=False)
        cycles_by_symbol[symbol] = int(len(frame))
        if not frame.empty:
            frames.append(frame)
    cycles = pd.concat(frames, ignore_index=True) if frames else _empty_cycles_frame()
    return cycles, cycles_by_symbol


def _cycle_signature_set(cycles: pd.DataFrame) -> set[tuple[str, str]]:
    if cycles.empty:
        return set()
    signatures = set()
    for _, row in cycles.iterrows():
        peak_time = pd.Timestamp(row["peak_time"]).floor("h").isoformat()
        signatures.add((str(row["symbol"]), peak_time))
    return signatures


def _stability_score(cycles: pd.DataFrame, previous_results: list[dict[str, Any]]) -> float:
    if not previous_results or cycles.empty:
        return 0.0
    best = max(previous_results, key=lambda item: item["quality"]["score"])
    previous_path = Path(best.get("combined_cycles_path", ""))
    if not previous_path.exists():
        return 0.0
    previous_cycles = pd.read_parquet(previous_path)
    current = _cycle_signature_set(cycles)
    previous = _cycle_signature_set(previous_cycles)
    if not current or not previous:
        return 0.0
    return len(current & previous) / len(current | previous)


def _cycle_quality_score(
    cycles: pd.DataFrame,
    cycles_by_symbol: dict[str, int],
    seed_manifest: dict[str, Any],
    *,
    symbol_groups: dict[str, list[str]],
    scoring_config: dict[str, Any],
    stability_score: float = 0.0,
) -> dict[str, Any]:
    cycle_count = int(len(cycles))
    covered_symbols = sum(1 for value in cycles_by_symbol.values() if value > 0)
    symbol_count = max(len(cycles_by_symbol), 1)
    coverage_ratio = covered_symbols / symbol_count
    weights = {
        "coverage": 0.25,
        "strength": 0.25,
        "duration": 0.20,
        "stability": 0.15,
        "control_group_separation": 0.15,
        **scoring_config.get("weights", {}),
    }
    target_cycles_per_symbol = float(scoring_config.get("target_cycles_per_symbol", 12))
    max_cycles_per_symbol = float(scoring_config.get("max_cycles_per_symbol", 80))
    target_pump_median = float(scoring_config.get("target_pump_median", 0.20))
    target_dump_median = float(scoring_config.get("target_dump_median", 0.15))
    ideal_duration_hours = float(scoring_config.get("ideal_duration_hours", 24))
    max_acceptable_duration_hours = float(scoring_config.get("max_acceptable_duration_hours", 96))

    def group_rate(group: str) -> float:
        symbols = symbol_groups.get(group, [])
        if not symbols:
            return 0.0
        return sum(cycles_by_symbol.get(symbol, 0) for symbol in symbols) / max(len(symbols), 1)

    strong_rate = group_rate("strong")
    volatile_rate = group_rate("volatile")
    control_rate = group_rate("control")
    separation_denominator = max(strong_rate, volatile_rate, control_rate, 1.0)
    control_group_separation = max(
        0.0,
        min(1.0, (strong_rate - control_rate) / separation_denominator),
    )
    if cycles.empty:
        return {
            "score": 0.0,
            "cycle_count": 0,
            "covered_symbols": covered_symbols,
            "coverage_ratio": coverage_ratio,
            "coverage_score": 0.0,
            "strength_score": 0.0,
            "duration_score": 0.0,
            "stability_score": round(stability_score, 6),
            "control_group_separation": round(control_group_separation, 6),
            "over_detection_penalty": 0.0,
            "duplicate_penalty": 0.0,
            "concentration_penalty": 0.0,
            "median_pump_return": 0.0,
            "median_dump_return": 0.0,
            "median_duration_hours": 0.0,
            "strong_cycles_per_symbol": round(strong_rate, 6),
            "volatile_cycles_per_symbol": round(volatile_rate, 6),
            "control_cycles_per_symbol": round(control_rate, 6),
            "matched_seed_event_count": int(seed_manifest.get("matched_seed_event_count", 0)),
            "expanded_event_count": int(seed_manifest.get("expanded_event_count", 0)),
            "rejection_reason": "no_cycles",
        }
    counts = list(cycles_by_symbol.values())
    cycles_per_symbol = cycle_count / symbol_count
    coverage_score = min(coverage_ratio, 1.0) * min(
        cycles_per_symbol / target_cycles_per_symbol,
        1.0,
    )
    median_pump = float(cycles["pump_return"].median())
    median_dump = float(cycles["dump_return"].median())
    strength_score = min(
        1.0,
        0.5 * min(median_pump / max(target_pump_median, 0.000001), 1.0)
        + 0.5 * min(median_dump / max(target_dump_median, 0.000001), 1.0),
    )
    median_duration = float(cycles["duration_hours"].median())
    if median_duration <= ideal_duration_hours:
        duration_score = 1.0
    elif median_duration >= max_acceptable_duration_hours:
        duration_score = 0.0
    else:
        duration_score = 1 - (
            (median_duration - ideal_duration_hours)
            / max(max_acceptable_duration_hours - ideal_duration_hours, 1.0)
        )
    over_detection_penalty = 0.0
    if cycle_count < max(5, symbol_count):
        over_detection_penalty += 0.20
    if cycles_per_symbol > max_cycles_per_symbol:
        over_detection_penalty += min(
            0.35,
            (cycles_per_symbol - max_cycles_per_symbol) / max_cycles_per_symbol,
        )
    concentration_penalty = 0.0
    if sum(counts) > 0 and max(counts) / sum(counts) > 0.45:
        concentration_penalty = 0.2
    duplicate_penalty = 0.0
    if "peak_time" in cycles.columns:
        duplicate_count = int(
            cycles.duplicated(subset=["symbol", "peak_time"], keep=False).sum()
        )
        duplicate_penalty = min(0.2, duplicate_count / max(cycle_count, 1))
    seed_bonus = min(int(seed_manifest.get("matched_seed_event_count", 0)) / 3, 1.0) * 0.2
    expanded_count = int(seed_manifest.get("expanded_event_count", 0))
    expanded_bonus = min(expanded_count / max(symbol_count * 4, 1), 1.0) * 0.05
    score = (
        coverage_score * float(weights["coverage"])
        + strength_score * float(weights["strength"])
        + duration_score * float(weights["duration"])
        + stability_score * float(weights["stability"])
        + control_group_separation * float(weights["control_group_separation"])
        + seed_bonus
        + expanded_bonus
        - over_detection_penalty
        - concentration_penalty
        - duplicate_penalty
    )
    return {
        "score": max(0.0, round(score, 6)),
        "cycle_count": cycle_count,
        "covered_symbols": covered_symbols,
        "coverage_ratio": round(coverage_ratio, 6),
        "coverage_score": round(coverage_score, 6),
        "strength_score": round(strength_score, 6),
        "duration_score": round(duration_score, 6),
        "stability_score": round(stability_score, 6),
        "control_group_separation": round(control_group_separation, 6),
        "over_detection_penalty": round(over_detection_penalty, 6),
        "duplicate_penalty": round(duplicate_penalty, 6),
        "concentration_penalty": round(concentration_penalty, 6),
        "median_pump_return": median_pump,
        "median_dump_return": median_dump,
        "median_duration_hours": median_duration,
        "cycles_per_symbol_median": float(median(counts)) if counts else 0.0,
        "cycles_per_symbol_mean": round(cycles_per_symbol, 6),
        "strong_cycles_per_symbol": round(strong_rate, 6),
        "volatile_cycles_per_symbol": round(volatile_rate, 6),
        "control_cycles_per_symbol": round(control_rate, 6),
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
    symbol_groups: dict[str, list[str]],
    scoring_config: dict[str, Any],
    previous_results: list[dict[str, Any]],
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
    combined_cycles_path = candidate_dir / "cycles.parquet"
    cycles_csv_path = candidate_dir / "cycles.csv"
    cycles.to_parquet(combined_cycles_path, index=False)
    cycles.to_csv(cycles_csv_path, index=False)
    event_manifest = build_event_set(
        str(seed_config_path),
        str(cycle_config_path),
        cycles_dir=candidate_dir / "cycles",
        output_dir=candidate_dir / "event_sets",
    )
    stability = _stability_score(cycles, previous_results)
    quality = _cycle_quality_score(
        cycles,
        cycles_by_symbol,
        event_manifest,
        symbol_groups=symbol_groups,
        scoring_config=scoring_config,
        stability_score=stability,
    )
    cycles_by_symbol_path = candidate_dir / "cycles_by_symbol.csv"
    pd.DataFrame(
        [
            {
                "symbol": symbol,
                "group": next(
                    (
                        group
                        for group, group_symbols in symbol_groups.items()
                        if symbol in group_symbols
                    ),
                    "unassigned",
                ),
                "cycle_count": count,
            }
            for symbol, count in cycles_by_symbol.items()
        ]
    ).to_csv(cycles_by_symbol_path, index=False)
    result = {
        "candidate_id": candidate_id,
        "cycle_config": candidate_config,
        "quality": quality,
        "cycles_by_symbol": cycles_by_symbol,
        "event_set_manifest": event_manifest,
        "cycle_config_path": str(cycle_config_path),
        "seed_events_config_path": str(seed_config_path),
        "combined_cycles_path": str(combined_cycles_path),
        "cycles_csv_path": str(cycles_csv_path),
        "cycles_by_symbol_path": str(cycles_by_symbol_path),
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
    discovery_config = pipeline_config.get("cycle_discovery", {})
    run_limit = int(
        max_runs
        or discovery_config.get("candidates_per_iteration")
        or autoresearch_config.get("max_cycle_validation_runs", 3)
    )
    run_limit = max(1, min(run_limit, 20))
    iteration_count = int(
        discovery_config.get(
            "max_iterations",
            autoresearch_config.get("max_cycle_research_iterations", 2),
        )
    )
    iteration_count = max(1, min(iteration_count, 10))
    base_cycle = _candidate_from_base(pipeline_config["cycle"], {})
    data_config = data_config_with_resolved_symbols(pipeline_config)
    seed_events_config = pipeline_config.get(
        "seed_events",
        {
            "version": "cycle_discovery_auto",
            "manual_seed_events": [],
            "matching": {"tolerance_hours": 12},
            "commonality": {"fallback_to_cycle_config": True},
        },
    )
    symbol_groups = _symbol_groups(pipeline_config, list(data_config["symbols"]))
    symbols = _symbols_from_groups(symbol_groups, list(data_config["symbols"]))
    timeframe = str(
        base_cycle.get("timeframe")
        or discovery_config.get("timeframe")
        or pipeline_config.get("experiment", {}).get("strategy", {}).get("timeframe")
        or "1h"
    )
    client = AutoResearchLLMClient.from_env() if use_llm else None
    run_id, run_dir = create_cycle_run_dir(pipeline_config_path)
    started_at = to_iso(utc_now())
    candidate_results: list[dict[str, Any]] = []
    iterations: list[dict[str, Any]] = []
    seen_configs: set[str] = set()
    scoring_config = discovery_config.get("scoring", {})
    for iteration in range(1, iteration_count + 1):
        candidates, hypothesis = _llm_candidates(
            client,
            base_cycle=base_cycle,
            symbols=symbols,
            symbol_groups=symbol_groups,
            previous_results=candidate_results,
            iteration=iteration,
            run_limit=run_limit,
        )
        iteration_dir = run_dir / "iterations" / f"{iteration:02d}"
        iteration_dir.mkdir(parents=True, exist_ok=True)
        iteration_results = []
        for candidate in candidates:
            candidate_key = hash_payload(candidate)
            if candidate_key in seen_configs:
                continue
            seen_configs.add(candidate_key)
            result = _evaluate_candidate(
                run_dir=iteration_dir,
                index=len(candidate_results) + 1,
                candidate_config=candidate,
                seed_events_config=seed_events_config,
                symbols=symbols,
                timeframe=timeframe,
                symbol_groups=symbol_groups,
                scoring_config=scoring_config,
                previous_results=candidate_results,
            )
            candidate_results.append(result)
            iteration_results.append(result)
        ranked_iteration = sorted(
            iteration_results,
            key=lambda item: item["quality"]["score"],
            reverse=True,
        )
        iteration_manifest = {
            "iteration": iteration,
            "hypothesis": hypothesis,
            "candidate_count": len(iteration_results),
            "best_candidate_id": ranked_iteration[0]["candidate_id"]
            if ranked_iteration
            else None,
            "best_quality": ranked_iteration[0]["quality"] if ranked_iteration else None,
            "candidates": iteration_results,
        }
        iteration_manifest["manifest_path"] = write_json(
            iteration_dir / "iteration_manifest.json",
            iteration_manifest,
        )
        iterations.append(iteration_manifest)
    ranked = sorted(candidate_results, key=lambda item: item["quality"]["score"], reverse=True)
    best = ranked[0] if ranked else None
    applied_path = (
        _apply_best_cycle_config(pipeline_config_path, best["cycle_config"])
        if apply_best and best
        else None
    )
    if best:
        final_dir = run_dir / "final"
        final_dir.mkdir(parents=True, exist_ok=True)
        best_rule_path = final_dir / "best_rule.yaml"
        best_rule_path.write_text(
            yaml.safe_dump(best["cycle_config"], sort_keys=False, allow_unicode=True),
            encoding="utf-8",
        )
        best_cycles = pd.read_parquet(best["combined_cycles_path"])
        best_cycles_path = final_dir / "cycles.parquet"
        best_cycles_csv_path = final_dir / "cycles.csv"
        best_cycles.to_parquet(best_cycles_path, index=False)
        best_cycles.to_csv(best_cycles_csv_path, index=False)
    else:
        best_rule_path = None
        best_cycles_path = None
        best_cycles_csv_path = None
    candidate_scores_path = run_dir / "candidate_scores.csv"
    pd.DataFrame(
        [
            {
                "candidate_id": item["candidate_id"],
                **item["quality"],
                **{
                    f"config_{key}": value
                    for key, value in item["cycle_config"].items()
                    if key in PARAM_BOUNDS or key in {"rule_id", "timeframe"}
                },
            }
            for item in ranked
        ]
    ).to_csv(candidate_scores_path, index=False)
    manifest = {
        "run_id": run_id,
        "created_at": started_at,
        "completed_at": to_iso(utc_now()),
        "status": "completed" if best else "failed",
        "pipeline_config_path": pipeline_config_path,
        "autoresearch_config_path": autoresearch_config_path,
        "model_status": llm_status(client),
        "hypothesis": iterations[-1]["hypothesis"] if iterations else {},
        "base_cycle_config": base_cycle,
        "timeframe": timeframe,
        "symbols": symbols,
        "symbol_groups": symbol_groups,
        "iteration_count": len(iterations),
        "candidate_count": len(candidate_results),
        "best_candidate_id": best["candidate_id"] if best else None,
        "best_cycle_config": best["cycle_config"] if best else None,
        "best_quality": best["quality"] if best else None,
        "best_rule_path": str(best_rule_path) if best_rule_path else None,
        "best_cycles_path": str(best_cycles_path) if best_cycles_path else None,
        "best_cycles_csv_path": str(best_cycles_csv_path) if best_cycles_csv_path else None,
        "candidate_scores_path": str(candidate_scores_path),
        "applied_path": applied_path,
        "iterations": iterations,
        "candidates": candidate_results,
    }
    manifest["manifest_path"] = write_json(run_dir / "manifest.json", manifest)
    return manifest
