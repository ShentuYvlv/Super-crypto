from __future__ import annotations

from typing import Any

import pandas as pd


def validate_phase1_event_windows(config: dict[str, Any]) -> None:
    phase1 = config.get("phase1_prediction", config)
    windows = phase1.get("event_windows", [])
    if not windows:
        return
    seen_ids: set[str] = set()
    for index, window in enumerate(windows):
        if not isinstance(window, dict):
            raise ValueError(f"phase1_prediction.event_windows[{index}] must be a mapping")
        window_id = str(window.get("window_id") or window.get("event_id") or f"index_{index}")
        if window_id in seen_ids:
            raise ValueError(f"Duplicate phase1 event window id: {window_id}")
        seen_ids.add(window_id)
        if not window.get("symbol"):
            raise ValueError(f"phase1 event window {window_id} requires symbol")
        start = pd.to_datetime(window.get("start"), utc=True, errors="coerce")
        end = pd.to_datetime(window.get("end"), utc=True, errors="coerce")
        if pd.isna(start) or pd.isna(end):
            raise ValueError(f"phase1 event window {window_id} has invalid start/end")
        if end <= start:
            raise ValueError(f"phase1 event window {window_id} end must be after start")


def validate_split_config(config: dict[str, Any]) -> None:
    splits = config.get("splits", config)
    for split in ("train", "validation", "holdout"):
        if split not in splits:
            raise ValueError(f"splits.{split} is required")
        start = pd.to_datetime(splits[split].get("start"), utc=True, errors="coerce")
        end = pd.to_datetime(splits[split].get("end"), utc=True, errors="coerce")
        if pd.isna(start) or pd.isna(end):
            raise ValueError(f"splits.{split} has invalid start/end")
        if end <= start:
            raise ValueError(f"splits.{split}.end must be after start")
    has_global_symbols = bool(splits.get("symbols"))
    has_split_symbols = any(
        "symbols" in splits[split] for split in ("train", "validation", "holdout")
    )
    has_split_files = bool(splits.get("symbol_split_files"))
    if not (has_global_symbols or has_split_symbols or has_split_files):
        raise ValueError("splits requires symbols, per-split symbols, or symbol_split_files")


def validate_pipeline_config(config: dict[str, Any]) -> None:
    if "splits" in config:
        validate_split_config(config["splits"])
    validate_phase1_event_windows(config)
