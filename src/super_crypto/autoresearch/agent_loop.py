from __future__ import annotations

from super_crypto.autoresearch.accept_reject_policy import accept
from super_crypto.autoresearch.config_mutator import write_experiment_variant
from super_crypto.autoresearch.experiment_planner import plan_next_experiment
from super_crypto.autoresearch.hypothesis_generator import generate_hypotheses
from super_crypto.common.config import load_yaml
from super_crypto.experiments.experiment_store import ExperimentStore
from super_crypto.experiments.run_experiment import run as run_experiment
from super_crypto.validation.splits import holdout_guard


def run_loop(config_path: str, autoresearch_config_path: str = "configs/autoresearch.yaml") -> dict:
    autoresearch_config = load_yaml(autoresearch_config_path)
    experiments = sorted(
        ExperimentStore().list_payloads("experiments"),
        key=lambda item: item["created_at"],
        reverse=True,
    )[: int(autoresearch_config.get("history_window", 20))]
    hypotheses = generate_hypotheses(experiments)
    plan = plan_next_experiment(config_path, hypotheses[0])
    latest = experiments[0] if experiments else None
    accepted, reason = accept(latest, baseline=experiments[1] if len(experiments) > 1 else None) if latest else (False, "no_experiment")
    validation_config_path = write_experiment_variant(config_path, plan)
    validation_split = "validation"
    holdout_guard("configs/splits.yaml", validation_split, final_flag=False)
    validation_result = run_experiment(validation_config_path, validation_split, final_flag=False)
    validation_experiment = validation_result["experiment"]
    validation_accepted, validation_reason = accept(
        validation_experiment,
        baseline=latest,
        minimum_trade_count=int(validation_experiment.get("minimum_trade_count", 20))
        if "minimum_trade_count" in validation_experiment
        else 20,
    )
    return {
        "hypotheses": hypotheses,
        "plan": plan,
        "generated_config": validation_config_path,
        "validation_result": validation_result,
        "validation_acceptance": {
            "accepted": validation_accepted,
            "reason": validation_reason,
        },
        "latest_acceptance": {"accepted": accepted, "reason": reason},
    }
