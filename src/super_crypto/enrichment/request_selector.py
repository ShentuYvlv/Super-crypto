from __future__ import annotations

from super_crypto.common.config import load_yaml


def select_candidates(scores: list[dict], config_path: str) -> list[str]:
    config = load_yaml(config_path)["candidate_selection"]
    top_n = int(config["top_n_by_score"])
    allowed_buckets = {"ultra_high", "high", "medium"} if config["min_bucket"] == "medium" else {"ultra_high", "high"}
    return [
        item["symbol"]
        for item in sorted(scores, key=lambda row: row["score"], reverse=True)
        if item["bucket"] in allowed_buckets
    ][:top_n]

