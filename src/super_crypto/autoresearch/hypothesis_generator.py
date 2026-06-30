from __future__ import annotations


def generate_hypotheses(experiments: list[dict]) -> list[str]:
    if not experiments:
        return ["Increase sample quality first; no experiment history available yet."]
    hypotheses = []
    latest = experiments[0]
    metrics = latest["metrics"]
    if metrics["trade_count"] < 20:
        hypotheses.append("Increase trade count by widening support-break threshold search.")
    if metrics["slippage_cost"] > metrics["net_return"]:
        hypotheses.append("Tighten candidate pool toward deeper orderbook symbols.")
    if metrics["max_drawdown"] < -0.12:
        hypotheses.append("Reduce max hold and tighten trailing stop.")
    return hypotheses or ["Retest current best config on fresh validation window."]
