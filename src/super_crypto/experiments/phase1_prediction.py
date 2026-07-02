from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pandas as pd

from super_crypto.common.config import hash_payload
from super_crypto.common.paths import DATA_ROOT, REPORT_ROOT, ensure_directory, ensure_parent
from super_crypto.common.time import to_iso, utc_now
from super_crypto.experiments.experiment_store import ExperimentStore

LABEL_COLUMNS = [
    "event_id",
    "symbol",
    "event_start",
    "peak_time",
    "dump_end",
    "split",
    "label_quality",
    "source",
    "note",
]


@dataclass(frozen=True)
class Phase1FeatureSet:
    name: str
    columns: list[str]


FEATURE_SETS = [
    Phase1FeatureSet("fr_baseline", ["funding_rate"]),
    Phase1FeatureSet("fr_oi", ["funding_rate", "oi_change_1h", "oi_change_6h", "oi_change_24h"]),
    Phase1FeatureSet(
        "fr_oi_liquidation",
        [
            "funding_rate",
            "oi_change_1h",
            "oi_change_6h",
            "oi_change_24h",
            "liq_long_usd",
            "liq_short_usd",
            "liq_imbalance",
        ],
    ),
    Phase1FeatureSet(
        "fr_oi_liquidation_taker",
        [
            "funding_rate",
            "oi_change_1h",
            "oi_change_6h",
            "oi_change_24h",
            "liq_long_usd",
            "liq_short_usd",
            "liq_imbalance",
            "taker_buy_ratio",
            "sell_pressure",
        ],
    ),
    Phase1FeatureSet(
        "all_available_features",
        [
            "funding_rate",
            "oi_change_1h",
            "oi_change_6h",
            "oi_change_24h",
            "liq_long_usd",
            "liq_short_usd",
            "liq_imbalance",
            "taker_buy_ratio",
            "sell_pressure",
            "bar_return",
            "return_4h",
            "return_24h",
            "volume_zscore_24h",
            "quote_volume_zscore_24h",
            "range_pct",
            "pump_return_lookback",
            "cex_inflow_usd",
            "cex_outflow_usd",
            "whale_transfer_count",
        ],
    ),
]


def _label_template_path(config: dict[str, Any]) -> Path:
    return DATA_ROOT / "labels" / Path(config["label_source"]).name


def _load_ohlcv(symbol: str, timeframe: str) -> pd.DataFrame:
    path = DATA_ROOT / "processed" / "ohlcv" / timeframe / f"{symbol}.parquet"
    if not path.exists():
        return pd.DataFrame()
    frame = pd.read_parquet(path)
    frame["open_time"] = pd.to_datetime(frame["open_time"], utc=True)
    return frame.sort_values("open_time").reset_index(drop=True)


def _load_optional_parquet(path: Path) -> pd.DataFrame:
    if not path.exists():
        return pd.DataFrame()
    return pd.read_parquet(path)


def _merge_asof(
    frame: pd.DataFrame,
    data: pd.DataFrame,
    *,
    time_column: str,
    columns: list[str],
) -> pd.DataFrame:
    result = frame.copy()
    if data.empty or time_column not in data.columns:
        for column in columns:
            result[column] = 0.0
        return result
    other = data.copy()
    other[time_column] = pd.to_datetime(other[time_column], utc=True, errors="coerce")
    other = other.dropna(subset=[time_column]).sort_values(time_column)
    other = other.rename(columns={time_column: "open_time"})
    for column in columns:
        if column not in other.columns:
            other[column] = 0.0
    return pd.merge_asof(
        result.sort_values("open_time"),
        other[["open_time", *columns]].sort_values("open_time"),
        on="open_time",
        direction="backward",
    )


def _feature_frame(symbol: str, timeframe: str) -> pd.DataFrame:
    frame = _load_ohlcv(symbol, timeframe)
    if frame.empty:
        return frame
    frame["bar_return"] = frame["close"].pct_change().fillna(0.0)
    frame["return_4h"] = frame["close"].pct_change(4, fill_method=None).fillna(0.0)
    frame["return_24h"] = frame["close"].pct_change(24, fill_method=None).fillna(0.0)
    frame["range_pct"] = (frame["high"] / frame["low"].replace(0, pd.NA) - 1).fillna(0.0)
    frame["pump_return_lookback"] = (
        frame["high"].rolling(24, min_periods=2).max()
        / frame["low"].rolling(24, min_periods=2).min()
        - 1
    ).fillna(0.0)
    for column in ("volume", "quote_volume"):
        rolling_mean = frame[column].rolling(24, min_periods=6).mean()
        rolling_std = frame[column].rolling(24, min_periods=6).std().replace(0, pd.NA)
        frame[f"{column}_zscore_24h"] = ((frame[column] - rolling_mean) / rolling_std).fillna(0.0)
    taker_ratio = frame["taker_buy_quote_volume"].replace(0, pd.NA) / frame[
        "quote_volume"
    ].replace(0, pd.NA)
    frame["taker_buy_ratio"] = taker_ratio.fillna(0.5)
    frame["sell_pressure"] = (frame["taker_buy_ratio"] - 0.5).fillna(0.0)

    funding = _load_optional_parquet(
        DATA_ROOT / "processed" / "derivatives" / f"funding_{symbol}.parquet"
    )
    frame = _merge_asof(frame, funding, time_column="funding_time", columns=["funding_rate"])

    oi = _load_optional_parquet(
        DATA_ROOT / "processed" / "derivatives" / f"open_interest_{symbol}.parquet"
    )
    frame = _merge_asof(
        frame,
        oi,
        time_column="snapshot_time",
        columns=["open_interest", "oi_value_usd"],
    )
    frame["oi_level"] = pd.to_numeric(frame.get("open_interest", 0.0), errors="coerce").fillna(0.0)
    for window in (1, 6, 24):
        frame[f"oi_change_{window}h"] = frame["oi_level"].pct_change(
            window,
            fill_method=None,
        ).fillna(0.0)

    for column in ("liq_long_usd", "liq_short_usd", "liq_imbalance"):
        frame[column] = 0.0
    for column in ("cex_inflow_usd", "cex_outflow_usd", "whale_transfer_count"):
        frame[column] = 0.0
    frame["symbol"] = symbol
    return frame


def _candidate_rows(config: dict[str, Any], symbols: list[str]) -> pd.DataFrame:
    thresholds = config["candidate_thresholds"]
    timeframe = config["timeframe"]
    rows: list[dict[str, Any]] = []
    for symbol in symbols:
        frame = _feature_frame(symbol, timeframe)
        if frame.empty:
            continue
        candidates = frame[
            (frame["return_4h"] >= float(thresholds["return_4h_min"]))
            | (frame["return_24h"] >= float(thresholds["return_24h_min"]))
            | (frame["volume_zscore_24h"] >= float(thresholds["volume_zscore_min"]))
            | (frame["range_pct"] >= float(thresholds["range_pct_min"]))
        ].copy()
        if candidates.empty:
            continue
        cooldown = pd.Timedelta(hours=float(config.get("candidate_cooldown_hours", 24)))
        last_time = None
        for _, row in candidates.sort_values("open_time").iterrows():
            open_time = row["open_time"]
            if last_time is not None and open_time - last_time < cooldown:
                continue
            window = frame[
                (frame["open_time"] >= open_time - pd.Timedelta(hours=24))
                & (frame["open_time"] <= open_time + pd.Timedelta(hours=48))
            ]
            if window.empty:
                continue
            peak = window.loc[window["high"].idxmax()]
            rows.append(
                {
                    "event_id": f"{symbol.lower()}_{open_time.strftime('%Y%m%d%H%M')}",
                    "symbol": symbol,
                    "candidate_start": to_iso(open_time.to_pydatetime()),
                    "suggested_peak_time": to_iso(peak["open_time"].to_pydatetime()),
                    "return_4h": float(row["return_4h"]),
                    "return_24h": float(row["return_24h"]),
                    "volume_zscore_24h": float(row["volume_zscore_24h"]),
                    "range_pct": float(row["range_pct"]),
                    "label_event_start": "",
                    "label_peak_time": "",
                    "label_dump_end": "",
                    "label_quality": "",
                    "split": "",
                    "note": "",
                }
            )
            last_time = open_time
    return pd.DataFrame(rows)


def write_label_template(config: dict[str, Any]) -> str:
    path = ensure_parent(_label_template_path(config))
    if not path.exists():
        pd.DataFrame(columns=LABEL_COLUMNS).to_csv(path, index=False)
    return str(path)


def generate_label_candidates(config: dict[str, Any], symbols: list[str]) -> dict[str, Any]:
    candidates = _candidate_rows(config, symbols)
    output_path = ensure_parent(DATA_ROOT / "processed" / "phase1" / "label_candidates.csv")
    candidates.to_csv(output_path, index=False)
    return {
        "candidate_count": int(len(candidates)),
        "candidate_path": str(output_path),
        "label_template_path": write_label_template(config),
    }


def _load_labels(config: dict[str, Any]) -> pd.DataFrame:
    path = _label_template_path(config)
    if not path.exists():
        return pd.DataFrame(columns=LABEL_COLUMNS)
    labels = pd.read_csv(path)
    if labels.empty:
        return labels
    labels = labels[[column for column in LABEL_COLUMNS if column in labels.columns]].copy()
    labels["event_start"] = pd.to_datetime(labels["event_start"], utc=True, errors="coerce")
    labels = labels.dropna(subset=["symbol", "event_start"])
    labels["split"] = labels.get("split", "train").fillna("train")
    labels["label_quality"] = labels.get("label_quality", "").fillna("")
    allowed_quality = set(config.get("allowed_label_quality", ["A", "B"]))
    if allowed_quality:
        labels = labels[labels["label_quality"].isin(allowed_quality)]
    return labels


def _sample_at_or_before(frame: pd.DataFrame, timestamp: pd.Timestamp) -> dict[str, Any] | None:
    eligible = frame[frame["open_time"] <= timestamp]
    if eligible.empty:
        return None
    return eligible.iloc[-1].to_dict()


def _build_dataset(
    config: dict[str, Any],
    symbols: list[str],
    labels: pd.DataFrame,
) -> pd.DataFrame:
    timeframe = config["timeframe"]
    lead_time = pd.Timedelta(hours=float(config["lead_time_hours"]))
    negative_ratio = int(config.get("negative_sample_ratio", 5))
    rows: list[dict[str, Any]] = []
    frames = {symbol: _feature_frame(symbol, timeframe) for symbol in symbols}
    for _, event in labels.iterrows():
        symbol = str(event["symbol"])
        frame = frames.get(symbol)
        if frame is None or frame.empty:
            continue
        sample_time = event["event_start"] - lead_time
        sample = _sample_at_or_before(frame, sample_time)
        if sample:
            sample.update(
                {
                    "sample_id": event.get("event_id") or f"{symbol}_{sample_time.isoformat()}",
                    "label": 1,
                    "event_start": to_iso(event["event_start"].to_pydatetime()),
                    "sample_time": to_iso(pd.Timestamp(sample["open_time"]).to_pydatetime()),
                    "split": event.get("split", "train"),
                }
            )
            rows.append(sample)

        start_gap = pd.Timedelta(hours=float(config.get("negative_gap_hours", 48)))
        blocked_start = event["event_start"] - start_gap
        blocked_end = event["event_start"] + start_gap
        negatives = frame[
            (frame["open_time"] < blocked_start) | (frame["open_time"] > blocked_end)
        ].copy()
        if negatives.empty:
            continue
        picked = negatives.iloc[:: max(len(negatives) // max(negative_ratio, 1), 1)].head(
            negative_ratio
        )
        for index, negative in picked.iterrows():
            row = negative.to_dict()
            row.update(
                {
                    "sample_id": f"neg_{symbol}_{index}_{event.get('event_id', '')}",
                    "label": 0,
                    "event_start": to_iso(event["event_start"].to_pydatetime()),
                    "sample_time": to_iso(pd.Timestamp(negative["open_time"]).to_pydatetime()),
                    "split": event.get("split", "train"),
                }
            )
            rows.append(row)
    return pd.DataFrame(rows)


def _best_threshold(y_true: pd.Series, score: pd.Series) -> tuple[float, dict[str, float]]:
    best_threshold = 0.0
    best = {"precision": 0.0, "recall": 0.0, "f1": 0.0}
    for threshold in sorted(score.dropna().unique()):
        predicted = score >= threshold
        tp = int(((predicted == 1) & (y_true == 1)).sum())
        fp = int(((predicted == 1) & (y_true == 0)).sum())
        fn = int(((predicted == 0) & (y_true == 1)).sum())
        precision = tp / (tp + fp) if tp + fp else 0.0
        recall = tp / (tp + fn) if tp + fn else 0.0
        f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
        if f1 > best["f1"]:
            best_threshold = float(threshold)
            best = {"precision": precision, "recall": recall, "f1": f1}
    return best_threshold, best


def _auc(y_true: pd.Series, score: pd.Series) -> float:
    data = pd.DataFrame({"label": y_true, "score": score}).dropna()
    positives = data[data["label"] == 1]["score"]
    negatives = data[data["label"] == 0]["score"]
    if positives.empty or negatives.empty:
        return 0.0
    wins = 0.0
    total = len(positives) * len(negatives)
    for value in positives:
        wins += float((value > negatives).sum()) + 0.5 * float((value == negatives).sum())
    return wins / total if total else 0.0


def _evaluate_feature_set(dataset: pd.DataFrame, feature_set: Phase1FeatureSet) -> dict[str, Any]:
    available = [column for column in feature_set.columns if column in dataset.columns]
    if not available or dataset["label"].nunique() < 2:
        return {
            "experiment": feature_set.name,
            "status": "insufficient_data",
            "features": available,
            "missing_features": [
                column for column in feature_set.columns if column not in available
            ],
            "precision": 0.0,
            "recall": 0.0,
            "f1": 0.0,
            "auc": 0.0,
            "threshold": 0.0,
        }
    score = dataset[available].apply(pd.to_numeric, errors="coerce").fillna(0.0).abs().sum(axis=1)
    threshold, metrics = _best_threshold(dataset["label"], score)
    return {
        "experiment": feature_set.name,
        "status": "completed",
        "features": available,
        "missing_features": [column for column in feature_set.columns if column not in available],
        "precision": round(metrics["precision"], 6),
        "recall": round(metrics["recall"], 6),
        "f1": round(metrics["f1"], 6),
        "auc": round(_auc(dataset["label"], score), 6),
        "threshold": threshold,
    }


def _write_report(report_dir: Path, payload: dict[str, Any]) -> tuple[str, str]:
    markdown_path = ensure_parent(report_dir / "report.md")
    html_path = ensure_parent(report_dir / "report.html")
    lines = [
        f"# Phase1 Prediction {payload['experiment_id']}",
        "",
        f"- Status: {payload['status']}",
        f"- Label count: {payload['label_count']}",
        f"- Sample count: {payload['sample_count']}",
        f"- Candidate path: {payload['candidate_path']}",
        f"- Label template: {payload['label_template_path']}",
        "",
        "## Experiments",
        "",
        "| Experiment | F1 | Precision | Recall | AUC | Status |",
        "|---|---:|---:|---:|---:|---|",
    ]
    for result in payload["phase1_results"]:
        lines.append(
            (
                "| {experiment} | {f1:.3f} | {precision:.3f} | "
                "{recall:.3f} | {auc:.3f} | {status} |"
            ).format(**result)
        )
    markdown_path.write_text("\n".join(lines), encoding="utf-8")
    html_rows = "\n".join(
        "<tr>"
        f"<td>{result['experiment']}</td>"
        f"<td>{result['f1']:.3f}</td>"
        f"<td>{result['precision']:.3f}</td>"
        f"<td>{result['recall']:.3f}</td>"
        f"<td>{result['auc']:.3f}</td>"
        f"<td>{result['status']}</td>"
        "</tr>"
        for result in payload["phase1_results"]
    )
    html_path.write_text(
        f"""
        <html><head><meta charset="utf-8"><title>Phase1 Prediction</title></head>
        <body>
          <h1>Phase1 Prediction {payload['experiment_id']}</h1>
          <p>Status: {payload['status']}</p>
          <p>Labels: {payload['label_count']} / Samples: {payload['sample_count']}</p>
          <table border="1" cellspacing="0" cellpadding="6">
            <thead><tr><th>Experiment</th><th>F1</th><th>Precision</th><th>Recall</th><th>AUC</th><th>Status</th></tr></thead>
            <tbody>{html_rows}</tbody>
          </table>
        </body></html>
        """,
        encoding="utf-8",
    )
    return str(markdown_path), str(html_path)


def run(config: dict[str, Any], symbols: list[str], split: str) -> dict[str, Any]:
    output_dir = ensure_directory(DATA_ROOT / "processed" / "phase1")
    candidate_details = generate_label_candidates(config, symbols)
    labels = _load_labels(config)
    labels.to_csv(output_dir / "labels_used.csv", index=False)
    dataset = _build_dataset(config, symbols, labels) if not labels.empty else pd.DataFrame()
    dataset_path = output_dir / "features.parquet"
    if not dataset.empty:
        dataset.to_parquet(dataset_path, index=False)
    else:
        pd.DataFrame().to_parquet(dataset_path, index=False)
    results = [
        _evaluate_feature_set(dataset, feature_set)
        for feature_set in FEATURE_SETS
        if feature_set.name in set(config.get("experiments", [item.name for item in FEATURE_SETS]))
    ]
    best = max(results, key=lambda item: item["f1"]) if results else {}
    experiment_id = hash_payload(
        {
            "type": "phase1_prediction",
            "created_at": to_iso(utc_now()),
            "label_count": len(labels),
            "sample_count": len(dataset),
        }
    )[:12]
    status = (
        "completed"
        if len(labels) >= int(config.get("minimum_labels_to_run", 1))
        else "needs_labels"
    )
    report_dir = ensure_directory(REPORT_ROOT / experiment_id)
    payload = {
        "experiment_id": experiment_id,
        "name": "phase1_prediction",
        "strategy": "PHASE1",
        "engine": "classification",
        "split": split,
        "status": status,
        "config_hash": hash_payload(config),
        "split_hash": hash_payload({"split": split}),
        "data_snapshot_hash": hash_payload(candidate_details),
        "git_commit_hash": "unknown",
        "created_at": to_iso(utc_now()),
        "failure_reason": "not_enough_manual_labels" if status == "needs_labels" else None,
        "metrics": {
            "net_return": 0.0,
            "sharpe": 0.0,
            "sortino": 0.0,
            "max_drawdown": 0.0,
            "profit_factor": 0.0,
            "win_rate": 0.0,
            "avg_win": 0.0,
            "avg_loss": 0.0,
            "trade_count": 0,
            "median_holding_minutes": 0.0,
            "fee_cost": 0.0,
            "slippage_cost": 0.0,
            "funding_cost": 0.0,
            "top5_removed_net_return": 0.0,
            "f1": float(best.get("f1", 0.0)),
            "precision": float(best.get("precision", 0.0)),
            "recall": float(best.get("recall", 0.0)),
            "auc": float(best.get("auc", 0.0)),
            "label_count": int(len(labels)),
            "sample_count": int(len(dataset)),
        },
        "phase1_results": results,
        "label_count": int(len(labels)),
        "sample_count": int(len(dataset)),
        "dataset_path": str(dataset_path),
        **candidate_details,
    }
    markdown_path, html_path = _write_report(report_dir, payload)
    payload["markdown_report_path"] = markdown_path
    payload["report_path"] = html_path
    payload["trade_log_path"] = ""
    ExperimentStore().upsert("experiments", "experiment_id", payload)
    return {
        "experiment": payload,
        "markdown_report": markdown_path,
        "html_report": html_path,
        "dataset": str(dataset_path),
        **candidate_details,
    }
