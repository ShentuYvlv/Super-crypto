from __future__ import annotations


def accept(experiment: dict, baseline: dict | None = None, minimum_trade_count: int = 20) -> tuple[bool, str]:
    metrics = experiment["metrics"]
    if metrics["trade_count"] < minimum_trade_count:
        return False, "trade_count_below_threshold"
    if metrics["net_return"] <= 0:
        return False, "non_positive_net_return"
    if baseline and metrics["net_return"] <= baseline["metrics"]["net_return"]:
        return False, "no_validation_improvement"
    return True, "accepted"

