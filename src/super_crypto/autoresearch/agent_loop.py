from __future__ import annotations

from typing import Any

from super_crypto.autoresearch.accept_reject_policy import accept
from super_crypto.autoresearch.artifacts import create_run_dir, write_json, write_markdown
from super_crypto.autoresearch.config_mutator import write_experiment_variant
from super_crypto.autoresearch.experiment_planner import plan_next_experiment
from super_crypto.autoresearch.hypothesis_generator import generate_hypotheses
from super_crypto.autoresearch.llm_client import AutoResearchLLMClient, llm_status
from super_crypto.autoresearch.result_interpreter import review_result
from super_crypto.common.config import load_yaml
from super_crypto.common.paths import resolve_project_path
from super_crypto.common.time import to_iso, utc_now
from super_crypto.experiments.experiment_store import ExperimentStore
from super_crypto.experiments.run_experiment import run as run_experiment
from super_crypto.validation.splits import holdout_guard


SYSTEM_PROMPT = """You are an AutoResearch assistant for a crypto signal research system.
Return compact JSON only. Do not suggest touching holdout data, protected files, or production execution paths.
Focus on testable parameter changes, evidence, and validation risk.
Use Simplified Chinese for all user-facing hypothesis, rationale, risk, decision, recommendation, notes, and evidence values."""


def _experiment_history(limit: int) -> list[dict]:
    return sorted(
        ExperimentStore().list_payloads("experiments"),
        key=lambda item: item["created_at"],
        reverse=True,
    )[:limit]


def _fallback_hypothesis(experiments: list[dict]) -> dict:
    hypothesis = generate_hypotheses(experiments)[0]
    return {
        "hypothesis": hypothesis,
        "rationale": "根据最近实验指标由规则 fallback 生成。",
        "risk": "规则只能看结构化指标，可能漏掉需要人工/LLM 解释的行情 regime 变化。",
    }


def _llm_hypothesis(
    client: AutoResearchLLMClient | None,
    *,
    experiments: list[dict],
    previous_iterations: list[dict],
) -> dict:
    if client is None:
        return _fallback_hypothesis(experiments)
    try:
        payload = client.complete_json(
            system=SYSTEM_PROMPT,
            user={
                "task": "propose_next_hypothesis",
                "recent_experiments": experiments[:8],
                "previous_iterations": previous_iterations,
                "required_schema": {
                    "hypothesis": "short testable statement",
                    "rationale": "brief evidence summary",
                    "risk": "main validation risk",
                },
            },
        )
        return {
            "hypothesis": str(payload.get("hypothesis") or _fallback_hypothesis(experiments)["hypothesis"]),
            "rationale": str(payload.get("rationale") or "LLM did not provide rationale."),
            "risk": str(payload.get("risk") or "unspecified"),
        }
    except Exception as exc:
        fallback = _fallback_hypothesis(experiments)
        fallback["llm_error"] = f"{type(exc).__name__}: {exc}"
        return fallback


def _llm_plan(
    client: AutoResearchLLMClient | None,
    *,
    config_path: str,
    hypothesis: dict,
    fallback_plan: dict,
) -> dict:
    if client is None:
        return fallback_plan
    try:
        payload = client.complete_json(
            system=SYSTEM_PROMPT,
            user={
                "task": "plan_validation_experiment",
                "base_config_path": config_path,
                "hypothesis": hypothesis,
                "base_plan": fallback_plan,
                "allowed_change_surface": ["parameter_grid"],
                "required_schema": {
                    "suggested_changes": {"parameter_grid": "dict of parameter names to arrays"},
                    "notes": "brief plan summary",
                },
            },
        )
        suggested = payload.get("suggested_changes", {})
        parameter_grid = suggested.get("parameter_grid") if isinstance(suggested, dict) else None
        if not isinstance(parameter_grid, dict):
            return fallback_plan
        return {
            **fallback_plan,
            "suggested_changes": {
                **fallback_plan.get("suggested_changes", {}),
                "parameter_grid": parameter_grid,
                "notes": str(payload.get("notes") or hypothesis["hypothesis"]),
            },
        }
    except Exception as exc:
        return {**fallback_plan, "llm_error": f"{type(exc).__name__}: {exc}"}


def _llm_review(
    client: AutoResearchLLMClient | None,
    *,
    experiment: dict,
    acceptance: dict,
    baseline: dict | None,
    validation_result: dict,
) -> dict:
    fallback = review_result(experiment, acceptance, baseline=baseline, validation_result=validation_result)
    if client is None:
        return fallback
    try:
        payload = client.complete_json(
            system=SYSTEM_PROMPT,
            user={
                "task": "review_validation_result",
                "experiment": experiment,
                "acceptance": acceptance,
                "baseline": baseline,
                "trade_summary": fallback.get("trade_summary"),
                "required_schema": {
                    "decision": "accepted/rejected reason",
                    "recommendation": "next action",
                    "evidence": ["metric evidence"],
                },
            },
        )
        return {
            **fallback,
            "decision": str(payload.get("decision") or fallback["decision"]),
            "recommendation": str(payload.get("recommendation") or fallback["recommendation"]),
            "evidence": payload.get("evidence") if isinstance(payload.get("evidence"), list) else fallback["evidence"],
        }
    except Exception as exc:
        return {**fallback, "llm_error": f"{type(exc).__name__}: {exc}"}


def _allowed_config(config_path: str, autoresearch_config: dict[str, Any]) -> bool:
    allowed = autoresearch_config.get("allowed_config_files", [])
    if not allowed:
        return True
    requested = resolve_project_path(config_path).resolve()
    allowed_paths = {resolve_project_path(path).resolve() for path in allowed}
    return requested in allowed_paths


def run_loop(
    config_path: str,
    autoresearch_config_path: str = "configs/autoresearch.yaml",
    *,
    max_runs: int | None = None,
    use_llm: bool = True,
) -> dict:
    autoresearch_config = load_yaml(autoresearch_config_path)
    if not _allowed_config(config_path, autoresearch_config):
        raise ValueError(f"AutoResearch config is not allowed: {config_path}")
    run_limit = int(max_runs or autoresearch_config.get("max_validation_runs_per_loop", 1))
    history_window = int(autoresearch_config.get("history_window", 20))
    run_started_at = to_iso(utc_now())
    run_id, run_dir = create_run_dir(config_path)
    client = AutoResearchLLMClient.from_env() if use_llm else None
    model_status = llm_status(client)
    experiments = _experiment_history(history_window)
    latest = experiments[0] if experiments else None
    accepted, reason = (
        accept(latest, baseline=experiments[1] if len(experiments) > 1 else None)
        if latest
        else (False, "no_experiment")
    )
    iterations = []
    status = "rejected"
    recommendation = "No validation run completed."
    for index in range(1, run_limit + 1):
        iteration_started_at = to_iso(utc_now())
        experiments = _experiment_history(history_window)
        hypothesis = _llm_hypothesis(client, experiments=experiments, previous_iterations=iterations)
        fallback_plan = plan_next_experiment(config_path, hypothesis["hypothesis"])
        plan = _llm_plan(client, config_path=config_path, hypothesis=hypothesis, fallback_plan=fallback_plan)
        validation_config_path = write_experiment_variant(config_path, plan)
        validation_split = "validation"
        holdout_guard("configs/splits.yaml", validation_split, final_flag=False)
        validation_result = run_experiment(validation_config_path, validation_split, final_flag=False)
        validation_experiment = validation_result["experiment"]
        validation_experiment.update(
            {
                "autoresearch_run_id": run_id,
                "autoresearch_iteration": index,
                "autoresearch_started_at": iteration_started_at,
                "autoresearch_parent_config": config_path,
                "autoresearch_generated_config": validation_config_path,
                "autoresearch_hypothesis": hypothesis["hypothesis"],
            }
        )
        validation_accepted, validation_reason = accept(
            validation_experiment,
            baseline=latest,
            minimum_trade_count=int(validation_experiment.get("minimum_trade_count", 20))
            if "minimum_trade_count" in validation_experiment
            else 20,
        )
        acceptance = {"accepted": validation_accepted, "reason": validation_reason}
        review = _llm_review(
            client,
            experiment=validation_experiment,
            acceptance=acceptance,
            baseline=latest,
            validation_result=validation_result,
        )
        validation_experiment.update(
            {
                "autoresearch_completed_at": to_iso(utc_now()),
                "autoresearch_decision": review["decision"],
                "autoresearch_recommendation": review["recommendation"],
            }
        )
        ExperimentStore().upsert("experiments", "experiment_id", validation_experiment)
        recommendation = review["recommendation"]
        iteration_payload = {
            "iteration": index,
            "started_at": iteration_started_at,
            "completed_at": validation_experiment["autoresearch_completed_at"],
            "hypothesis": hypothesis,
            "plan": plan,
            "generated_config": validation_config_path,
            "validation_result": validation_result,
            "validation_acceptance": acceptance,
            "review": review,
        }
        write_json(run_dir / "iterations" / f"iteration_{index:02d}.json", iteration_payload)
        iterations.append(iteration_payload)
        if validation_accepted:
            status = "accepted"
            break
    manifest = {
        "run_id": run_id,
        "created_at": run_started_at,
        "completed_at": to_iso(utc_now()),
        "status": status,
        "config_path": config_path,
        "autoresearch_config_path": autoresearch_config_path,
        "model_status": model_status,
        "latest_acceptance": {"accepted": accepted, "reason": reason},
        "iterations": iterations,
        "recommendation": recommendation,
    }
    manifest["recommendation_path"] = write_markdown(run_dir / "recommendation.md", manifest)
    manifest["manifest_path"] = write_json(run_dir / "manifest.json", manifest)
    return manifest
