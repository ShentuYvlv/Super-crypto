from __future__ import annotations

from pathlib import Path
from typing import Annotated, Any

import pandas as pd
from fastapi import APIRouter, HTTPException, Query

from super_crypto.report_api.deps import envelope, experiment_store
from super_crypto.report_api.loaders import artifact_url, frame_to_records, read_csv_if_exists

router = APIRouter(prefix="/api/phase1", tags=["phase1"])

FEATURE_GROUPS = [
    {
        "key": "funding",
        "label": "FR 资金费率",
        "columns": ["funding_rate"],
        "quality_column": None,
    },
    {
        "key": "open_interest",
        "label": "OI 持仓量",
        "columns": ["oi_change_1h", "oi_change_6h", "oi_change_24h", "oi_level"],
        "quality_column": None,
    },
    {
        "key": "liquidation",
        "label": "爆仓",
        "columns": ["liq_long_usd", "liq_short_usd", "liq_imbalance"],
        "quality_column": "liquidation_data_quality",
    },
    {
        "key": "taker",
        "label": "主动买卖",
        "columns": ["taker_buy_ratio", "sell_pressure"],
        "quality_column": None,
    },
    {
        "key": "orderbook",
        "label": "盘口",
        "columns": [
            "orderbook_spread_bps",
            "orderbook_imbalance",
            "orderbook_slippage_100",
            "orderbook_slippage_500",
            "orderbook_slippage_1000",
        ],
        "quality_column": "orderbook_data_quality",
    },
    {
        "key": "onchain",
        "label": "链上",
        "columns": ["cex_inflow_usd", "cex_outflow_usd", "whale_transfer_count"],
        "quality_column": "onchain_data_quality",
    },
    {
        "key": "long_short",
        "label": "多空比",
        "columns": ["long_short_ratio"],
        "quality_column": "long_short_data_quality",
    },
]


def _phase1_experiments() -> list[dict[str, Any]]:
    return [
        experiment
        for experiment in experiment_store().list_payloads("experiments")
        if experiment.get("strategy") == "PHASE1"
    ]


def _phase1_experiment(experiment_id: str) -> dict[str, Any]:
    experiment = experiment_store().get_payload("experiments", "experiment_id", experiment_id)
    if experiment is None or experiment.get("strategy") != "PHASE1":
        raise HTTPException(status_code=404, detail="Phase1 experiment not found")
    return experiment


def _trusted_phase1_artifact_path(experiment: dict[str, Any], path: str | None) -> Path | None:
    if not path:
        return None
    candidate = Path(path)
    experiment_id = str(experiment.get("experiment_id") or "")
    if (
        candidate.parent.name == "phase1"
        and candidate.parent.parent.name == experiment_id
        and candidate.exists()
    ):
        return candidate
    return None


def _read_dataset(experiment: dict[str, Any]) -> pd.DataFrame:
    candidate = _trusted_phase1_artifact_path(experiment, experiment.get("dataset_path"))
    if candidate is None:
        return pd.DataFrame()
    return pd.read_parquet(candidate)


def _read_labels(experiment: dict[str, Any]) -> pd.DataFrame:
    candidate = _trusted_phase1_artifact_path(experiment, experiment.get("labels_used_path"))
    return read_csv_if_exists(candidate) if candidate else pd.DataFrame()


def _read_windows(experiment: dict[str, Any]) -> pd.DataFrame:
    diagnostics = experiment.get("window_diagnostics")
    if diagnostics is not None:
        return pd.DataFrame(diagnostics)
    candidate = _trusted_phase1_artifact_path(
        experiment,
        experiment.get("window_diagnostics_path"),
    )
    return read_csv_if_exists(candidate) if candidate else pd.DataFrame()


def _read_candidates(experiment: dict[str, Any]) -> pd.DataFrame:
    candidate = _trusted_phase1_artifact_path(experiment, experiment.get("candidate_path"))
    return read_csv_if_exists(candidate) if candidate else pd.DataFrame()


def _labels_from_windows(windows: pd.DataFrame) -> pd.DataFrame:
    if windows.empty or "detected_event_start" not in windows.columns:
        return pd.DataFrame()
    rows = []
    for _, window in windows.iterrows():
        event_start = window.get("detected_event_start")
        if pd.isna(event_start) or not event_start:
            continue
        rows.append(
            {
                "event_id": window.get("window_id") or f"{window.get('symbol', '')}_{event_start}",
                "symbol": window.get("symbol", ""),
                "event_start": event_start,
                "peak_time": window.get("peak_time"),
                "dump_end": window.get("dump_end"),
                "split": window.get("split", "train"),
                "label_quality": window.get("label_quality", ""),
                "source": "window_diagnostics_compat",
                "note": "从旧实验窗口诊断兼容生成",
            }
        )
    return pd.DataFrame(rows)


def _split_summary(dataset: pd.DataFrame, labels: pd.DataFrame) -> list[dict[str, Any]]:
    split_order = ["train", "validation", "holdout"]
    splits = sorted(
        {
            *dataset.get("split", pd.Series(dtype=str)).dropna().astype(str).unique().tolist(),
            *labels.get("split", pd.Series(dtype=str)).dropna().astype(str).unique().tolist(),
        },
        key=lambda item: split_order.index(item) if item in split_order else len(split_order),
    )
    rows = []
    for split in splits:
        split_dataset = (
            dataset[dataset["split"].astype(str) == split]
            if "split" in dataset
            else pd.DataFrame()
        )
        split_labels = (
            labels[labels["split"].astype(str) == split]
            if "split" in labels
            else pd.DataFrame()
        )
        label_series = split_dataset.get("label", pd.Series(dtype=int))
        symbols = sorted(
            {
                *split_dataset.get("symbol", pd.Series(dtype=str)).dropna().astype(str).unique(),
                *split_labels.get("symbol", pd.Series(dtype=str)).dropna().astype(str).unique(),
            }
        )
        rows.append(
            {
                "split": split,
                "symbols": symbols,
                "symbol_count": len(symbols),
                "label_count": int(len(split_labels)),
                "sample_count": int(len(split_dataset)),
                "positive_sample_count": int(label_series.sum()) if not split_dataset.empty else 0,
                "negative_sample_count": int((label_series == 0).sum())
                if not split_dataset.empty
                else 0,
            }
        )
    return rows


def _feature_quality(dataset: pd.DataFrame) -> list[dict[str, Any]]:
    if dataset.empty:
        return [
            {
                "key": group["key"],
                "label": group["label"],
                "status": "unknown",
                "available_columns": [],
                "nonzero_sample_count": 0,
                "sample_count": 0,
                "missing_ratio": 1.0,
                "quality_counts": {},
            }
            for group in FEATURE_GROUPS
        ]
    rows = []
    sample_count = int(len(dataset))
    for group in FEATURE_GROUPS:
        columns = [column for column in group["columns"] if column in dataset.columns]
        nonzero_sample_count = 0
        if columns:
            values = dataset[columns].apply(pd.to_numeric, errors="coerce").fillna(0.0).abs()
            nonzero_sample_count = int((values.sum(axis=1) != 0).sum())
        quality_column = group["quality_column"]
        quality_counts = (
            dataset[quality_column].fillna("unknown").astype(str).value_counts().to_dict()
            if quality_column and quality_column in dataset.columns
            else {}
        )
        missing_rows = quality_counts.get("missing", 0) + quality_counts.get("missing_time", 0)
        if quality_counts:
            if missing_rows == 0:
                status = "healthy"
            elif missing_rows < sample_count:
                status = "partial"
            else:
                status = "missing"
        else:
            status = "healthy" if columns and nonzero_sample_count > 0 else "missing"
        rows.append(
            {
                "key": group["key"],
                "label": group["label"],
                "status": status,
                "available_columns": columns,
                "nonzero_sample_count": nonzero_sample_count,
                "sample_count": sample_count,
                "missing_ratio": missing_rows / sample_count if sample_count else 1.0,
                "quality_counts": quality_counts,
            }
        )
    return rows


def _model_results(experiment: dict[str, Any]) -> list[dict[str, Any]]:
    return sorted(
        experiment.get("phase1_results", []),
        key=lambda item: (
            0 if item.get("model") == "lightgbm" else 1,
            -float(item.get("holdout_f1", 0.0) or 0.0),
        ),
    )


def _conclusion_flags(
    experiment: dict[str, Any],
    feature_quality: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    metrics = experiment.get("metrics", {})
    results = experiment.get("phase1_results", [])
    flags = []
    if int(metrics.get("sample_count", 0) or 0) > 0 and not experiment.get("phase1_artifact_dir"):
        flags.append(
            {
                "key": "legacy_artifacts",
                "severity": "warning",
                "label": "旧实验缺少独立样本快照",
                "detail": (
                    "该实验生成于快照隔离改造前，窗口和模型结果可信，"
                    "样本明细不再回读公共最新文件。"
                ),
            }
        )
    if int(metrics.get("holdout_positive_count", 0) or 0) < 5:
        flags.append(
            {
                "key": "small_holdout",
                "severity": "warning",
                "label": "留出集正样本过少",
                "detail": "留出集正样本少于 5 个，结论只能阶段性参考。",
            }
        )
    if float(metrics.get("holdout_precision", 0.0) or 0.0) < 0.3:
        flags.append(
            {
                "key": "low_holdout_precision",
                "severity": "danger",
                "label": "留出集误报偏高",
                "detail": "precision 低于 0.30，当前信号不适合直接用于实盘前兆预测。",
            }
        )
    overfit = [
        item
        for item in results
        if float(item.get("train_f1", 0.0) or 0.0) >= 0.7
        and float(item.get("holdout_f1", 0.0) or 0.0) < 0.2
    ]
    if overfit:
        flags.append(
            {
                "key": "overfit",
                "severity": "danger",
                "label": "训练集过拟合",
                "detail": "训练 F1 很高但 holdout 失效，优先按过拟合处理。",
                "experiments": [item.get("experiment") for item in overfit],
            }
        )
    missing_features = [
        item["label"] for item in feature_quality if item["status"] == "missing"
    ]
    if missing_features:
        flags.append(
            {
                "key": "missing_features",
                "severity": "warning",
                "label": "部分特征没有真实数据",
                "detail": "缺失特征：" + "、".join(missing_features),
            }
        )
    return flags


def _summary(experiment: dict[str, Any]) -> dict[str, Any]:
    metrics = experiment.get("metrics", {})
    results = experiment.get("phase1_results", [])
    best_train = max(
        results,
        key=lambda item: float(item.get("train_f1", 0.0) or 0.0),
        default={},
    )
    best_holdout = max(
        results,
        key=lambda item: float(item.get("holdout_f1", 0.0) or 0.0),
        default={},
    )
    lightgbm = next(
        (
            item
            for item in results
            if item.get("model") == "lightgbm"
        ),
        None,
    )
    return {
        "experiment_id": experiment.get("experiment_id"),
        "status": experiment.get("status"),
        "created_at": experiment.get("created_at"),
        "label_count": int(metrics.get("label_count", experiment.get("label_count", 0)) or 0),
        "sample_count": int(metrics.get("sample_count", experiment.get("sample_count", 0)) or 0),
        "positive_sample_count": int(metrics.get("positive_sample_count", 0) or 0),
        "negative_sample_count": int(metrics.get("negative_sample_count", 0) or 0),
        "train_sample_count": int(metrics.get("train_sample_count", 0) or 0),
        "train_positive_count": int(metrics.get("train_positive_count", 0) or 0),
        "holdout_sample_count": int(metrics.get("holdout_sample_count", 0) or 0),
        "holdout_positive_count": int(metrics.get("holdout_positive_count", 0) or 0),
        "train_f1": float(best_train.get("train_f1", metrics.get("train_f1", 0.0)) or 0.0),
        "holdout_f1": float(best_holdout.get("holdout_f1", metrics.get("holdout_f1", 0.0)) or 0.0),
        "holdout_precision": float(
            best_holdout.get("holdout_precision", metrics.get("holdout_precision", 0.0)) or 0.0
        ),
        "holdout_recall": float(
            best_holdout.get("holdout_recall", metrics.get("holdout_recall", 0.0)) or 0.0
        ),
        "best_train_experiment": best_train.get("experiment"),
        "best_holdout_experiment": best_holdout.get("experiment"),
        "lightgbm_holdout_f1": float(lightgbm.get("holdout_f1", 0.0) or 0.0)
        if lightgbm
        else None,
    }


def _detail_payload(experiment: dict[str, Any], *, sample_limit: int = 500) -> dict[str, Any]:
    dataset = _read_dataset(experiment)
    windows = _read_windows(experiment)
    labels = _read_labels(experiment)
    if labels.empty:
        labels = _labels_from_windows(windows)
    candidates = _read_candidates(experiment)
    feature_quality = _feature_quality(dataset)
    return {
        "experiment": experiment,
        "summary": _summary(experiment),
        "splits": _split_summary(dataset, labels),
        "windows": frame_to_records(windows),
        "labels": frame_to_records(labels),
        "samples": frame_to_records(dataset.head(sample_limit)),
        "sample_limit": sample_limit,
        "sample_count": int(len(dataset)),
        "candidates": frame_to_records(candidates.head(sample_limit)),
        "feature_quality": feature_quality,
        "model_results": _model_results(experiment),
        "conclusion_flags": _conclusion_flags(experiment, feature_quality),
        "report_urls": {
            "html": artifact_url(experiment.get("report_path")),
            "markdown": artifact_url(experiment.get("markdown_report_path")),
        },
        "artifact_paths": {
            "dataset": experiment.get("dataset_path"),
            "labels": experiment.get("labels_used_path"),
            "windows": experiment.get("window_diagnostics_path"),
            "candidates": experiment.get("candidate_path"),
        },
    }


@router.get("/experiments")
def list_phase1_experiments():
    experiments = sorted(
        _phase1_experiments(),
        key=lambda item: item.get("created_at", ""),
        reverse=True,
    )
    return envelope([_summary(experiment) for experiment in experiments])


@router.get("/experiments/{experiment_id}")
def get_phase1_experiment(
    experiment_id: str,
    sample_limit: Annotated[int, Query(ge=1, le=5000)] = 500,
):
    limit = int(sample_limit)
    return envelope(_detail_payload(_phase1_experiment(experiment_id), sample_limit=limit))


@router.get("/experiments/{experiment_id}/symbols/{symbol}")
def get_phase1_symbol(
    experiment_id: str,
    symbol: str,
    sample_limit: Annotated[int, Query(ge=1, le=5000)] = 500,
):
    limit = int(sample_limit)
    detail = _detail_payload(_phase1_experiment(experiment_id), sample_limit=5000)
    target = symbol.upper()
    detail["windows"] = [
        item for item in detail["windows"] if str(item.get("symbol", "")).upper() == target
    ]
    detail["labels"] = [
        item for item in detail["labels"] if str(item.get("symbol", "")).upper() == target
    ]
    detail["samples"] = [
        item for item in detail["samples"] if str(item.get("symbol", "")).upper() == target
    ][:limit]
    detail["sample_limit"] = limit
    return envelope(detail)
