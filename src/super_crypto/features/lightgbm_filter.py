from __future__ import annotations

from dataclasses import dataclass

import pandas as pd


@dataclass(frozen=True)
class LightGBMFilterResult:
    enabled: bool
    feature_columns: list[str]
    scores: list[float]
    reason: str | None = None


DEFAULT_FEATURE_COLUMNS = [
    "pump_return",
    "dump_return",
    "duration_hours",
    "liq_imbalance",
    "cex_inflow_usd",
    "cex_outflow_usd",
    "whale_transfer_count",
]


def score_candidate_filter(
    frame: pd.DataFrame,
    *,
    feature_columns: list[str] | None = None,
    model_path: str | None = None,
) -> LightGBMFilterResult:
    columns = [
        column for column in (feature_columns or DEFAULT_FEATURE_COLUMNS) if column in frame.columns
    ]
    if not columns:
        return LightGBMFilterResult(
            enabled=False, feature_columns=[], scores=[], reason="no_feature_columns"
        )
    try:
        import lightgbm as lgb  # type: ignore[import-not-found]
    except ImportError:
        return LightGBMFilterResult(
            enabled=False,
            feature_columns=columns,
            scores=[],
            reason="lightgbm_not_installed",
        )
    if not model_path:
        return LightGBMFilterResult(
            enabled=False,
            feature_columns=columns,
            scores=[],
            reason="model_path_required",
        )
    model = lgb.Booster(model_file=model_path)
    matrix = frame[columns].fillna(0.0)
    scores = [float(score) for score in model.predict(matrix)]
    return LightGBMFilterResult(enabled=True, feature_columns=columns, scores=scores)
