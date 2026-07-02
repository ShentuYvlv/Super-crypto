from __future__ import annotations

import json
from pathlib import Path
from urllib.parse import quote

import pandas as pd

from super_crypto.common.config import load_yaml
from super_crypto.common.paths import DATA_ROOT, REPORT_ROOT
from super_crypto.experiments.experiment_store import ExperimentStore
from super_crypto.experiments.pipeline_store import PipelineStore


def read_parquet_if_exists(path: Path) -> pd.DataFrame:
    if not path.exists():
        return pd.DataFrame()
    return pd.read_parquet(path)


def read_csv_if_exists(path: Path) -> pd.DataFrame:
    if not path.exists():
        return pd.DataFrame()
    return pd.read_csv(path)


def load_latest_scores() -> pd.DataFrame:
    return read_parquet_if_exists(DATA_ROOT / "processed" / "scores" / "latest.parquet")


def load_symbol_cycles(symbol: str) -> pd.DataFrame:
    return read_parquet_if_exists(DATA_ROOT / "processed" / "cycles" / f"{symbol}.parquet")


def load_symbol_ohlcv(symbol: str, timeframe: str = "1h") -> pd.DataFrame:
    return read_parquet_if_exists(
        DATA_ROOT / "processed" / "ohlcv" / timeframe / f"{symbol}.parquet"
    )


def load_symbol_orderbook(symbol: str) -> pd.DataFrame:
    return read_parquet_if_exists(
        DATA_ROOT / "processed" / "orderbook_features" / f"{symbol}.parquet"
    )


def load_symbol_funding(symbol: str) -> pd.DataFrame:
    return read_parquet_if_exists(
        DATA_ROOT / "processed" / "derivatives" / f"funding_{symbol}.parquet"
    )


def load_symbol_open_interest(symbol: str) -> pd.DataFrame:
    return read_parquet_if_exists(
        DATA_ROOT / "processed" / "derivatives" / f"open_interest_{symbol}.parquet"
    )


def load_scanner_status() -> dict | None:
    path = DATA_ROOT / "cache" / "scanner_status.json"
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def load_paper_trades() -> list[dict]:
    return ExperimentStore().list_payloads("paper_trades")


def list_experiments() -> list[dict]:
    return sorted(
        ExperimentStore().list_payloads("experiments"),
        key=lambda item: item.get("created_at", ""),
        reverse=True,
    )


def list_signals() -> list[dict]:
    return sorted(
        ExperimentStore().list_payloads("signals"),
        key=lambda item: item.get("signal_time", ""),
        reverse=True,
    )


def list_trades(*, include_paper: bool = False) -> list[dict]:
    trades = ExperimentStore().list_payloads("trades")
    if include_paper:
        trades.extend(load_paper_trades())
    return sorted(
        trades,
        key=lambda item: item.get("exit_time") or item.get("entry_time", ""),
        reverse=True,
    )


def list_pipeline_runs() -> list[dict]:
    return sorted(
        PipelineStore().list_runs(),
        key=lambda item: item.get("updated_at", ""),
        reverse=True,
    )


def latest_pipeline_stage(run_id: str, stage_name: str) -> dict | None:
    matches = [
        stage for stage in PipelineStore().list_stages(run_id) if stage.get("stage") == stage_name
    ]
    matches.sort(
        key=lambda item: item.get("completed_at") or item.get("started_at") or "",
        reverse=True,
    )
    return matches[0] if matches else None


def frame_to_records(frame: pd.DataFrame, *, limit: int | None = None) -> list[dict]:
    if frame.empty:
        return []
    normalized = frame.tail(limit) if limit else frame
    return json.loads(normalized.to_json(orient="records", date_format="iso"))


def artifact_url(path: str | Path | None) -> str | None:
    if not path:
        return None
    resolved = Path(path).resolve()
    try:
        relative = resolved.relative_to(REPORT_ROOT.resolve())
    except ValueError:
        return None
    return f"/artifacts/{quote(relative.as_posix(), safe='/')}"


def read_yaml_if_exists(path: str | Path | None) -> dict:
    if not path:
        return {}
    candidate = Path(path)
    if not candidate.exists():
        return {}
    return load_yaml(candidate)
