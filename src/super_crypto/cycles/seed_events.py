from __future__ import annotations

from pathlib import Path
from typing import Any

import pandas as pd

from super_crypto.common.config import canonical_json, hash_payload, load_yaml
from super_crypto.common.paths import DATA_ROOT, ensure_directory
from super_crypto.common.time import parse_timestamp, to_iso, utc_now


def _load_cycle_frame(cycles_dir: Path | None = None) -> pd.DataFrame:
    root = cycles_dir or DATA_ROOT / "processed" / "cycles"
    frames = []
    for path in sorted(root.glob("*.parquet")):
        frame = pd.read_parquet(path)
        if frame.empty:
            continue
        frame["pump_start"] = pd.to_datetime(frame["pump_start"], utc=True)
        frame["peak_time"] = pd.to_datetime(frame["peak_time"], utc=True)
        frame["dump_end"] = pd.to_datetime(frame["dump_end"], utc=True)
        frames.append(frame)
    return pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()


def _normalize_seed_event(event: dict[str, Any]) -> dict[str, Any]:
    normalized = dict(event)
    for key in ("pump_start", "peak_time", "dump_end"):
        value = normalized.get(key)
        normalized[key] = to_iso(parse_timestamp(value)) if value else None
    return normalized


def _match_seed_events(
    cycles: pd.DataFrame,
    seed_events: list[dict[str, Any]],
    *,
    tolerance_hours: float,
) -> list[dict[str, Any]]:
    if cycles.empty:
        return []
    tolerance = pd.Timedelta(hours=tolerance_hours)
    matches = []
    for raw_event in seed_events:
        event = _normalize_seed_event(raw_event)
        symbol_cycles = cycles[cycles["symbol"] == event.get("symbol")]
        if symbol_cycles.empty or not event.get("pump_start"):
            continue
        seed_start = parse_timestamp(event["pump_start"])
        candidates = symbol_cycles[
            (symbol_cycles["pump_start"] >= seed_start - tolerance)
            & (symbol_cycles["pump_start"] <= seed_start + tolerance)
        ].copy()
        if candidates.empty:
            continue
        candidates["distance_seconds"] = (
            candidates["pump_start"] - seed_start
        ).abs().dt.total_seconds()
        cycle = candidates.sort_values("distance_seconds").iloc[0].to_dict()
        matches.append(
            {
                "seed_event": event,
                "cycle": {
                    "cycle_id": cycle["cycle_id"],
                    "symbol": cycle["symbol"],
                    "pump_start": to_iso(cycle["pump_start"]),
                    "peak_time": to_iso(cycle["peak_time"]),
                    "dump_end": to_iso(cycle["dump_end"]),
                    "pump_return": float(cycle["pump_return"]),
                    "dump_return": float(cycle["dump_return"]),
                    "duration_hours": float(cycle["duration_hours"]),
                },
                "distance_hours": float(cycle["distance_seconds"] / 3600),
            }
        )
    return matches


def _commonality_profile(
    matched_seed_events: list[dict[str, Any]],
    cycle_config: dict[str, Any],
    *,
    fallback_to_cycle_config: bool,
) -> dict[str, Any]:
    if matched_seed_events:
        matched = pd.DataFrame([item["cycle"] for item in matched_seed_events])
        enough_seed_events = len(matched) >= 3
        return {
            "source": "matched_seed_events",
            "selection_bounds_source": "matched_seed_events"
            if enough_seed_events
            else "cycle_config_fallback_low_seed_count",
            "seed_match_count": int(len(matched)),
            "pump_return_median": float(matched["pump_return"].median()),
            "dump_return_median": float(matched["dump_return"].median()),
            "duration_hours_median": float(matched["duration_hours"].median()),
            "pump_return_min": float(matched["pump_return"].min())
            if enough_seed_events
            else float(cycle_config["pump_threshold_min"]),
            "pump_return_max": float(matched["pump_return"].max())
            if enough_seed_events
            else float(cycle_config["pump_threshold_max"]),
            "duration_hours_max": float(matched["duration_hours"].max())
            if enough_seed_events
            else float(cycle_config["max_cycle_hours"]),
        }
    if not fallback_to_cycle_config:
        return {"source": "none", "seed_match_count": 0}
    return {
        "source": "cycle_config_fallback",
        "seed_match_count": 0,
        "pump_return_min": float(cycle_config["pump_threshold_min"]),
        "pump_return_max": float(cycle_config["pump_threshold_max"]),
        "duration_hours_max": float(cycle_config["max_cycle_hours"]),
        "dump_retrace_ratio": float(cycle_config["dump_retrace_ratio"]),
    }


def build_event_set(
    seed_events_config_path: str,
    cycle_config_path: str,
    *,
    cycles_dir: Path | None = None,
    output_dir: Path | None = None,
) -> dict[str, Any]:
    seed_config = load_yaml(seed_events_config_path)
    cycle_config = load_yaml(cycle_config_path)
    cycles = _load_cycle_frame(cycles_dir)
    seed_events = [_normalize_seed_event(item) for item in seed_config.get("manual_seed_events", [])]
    matched_seed_events = _match_seed_events(
        cycles,
        seed_events,
        tolerance_hours=float(seed_config.get("matching", {}).get("tolerance_hours", 12)),
    )
    commonality = _commonality_profile(
        matched_seed_events,
        cycle_config,
        fallback_to_cycle_config=bool(
            seed_config.get("commonality", {}).get("fallback_to_cycle_config", True)
        ),
    )

    if cycles.empty:
        expanded = cycles
    else:
        expanded = cycles[
            (cycles["pump_return"] >= float(commonality.get("pump_return_min", cycle_config["pump_threshold_min"])))
            & (cycles["pump_return"] <= float(commonality.get("pump_return_max", cycle_config["pump_threshold_max"])))
            & (cycles["duration_hours"] <= float(commonality.get("duration_hours_max", cycle_config["max_cycle_hours"])))
        ].copy()
        expanded["event_set_version"] = seed_config.get("version", "seed_events_v1")
        expanded["commonality_source"] = commonality["source"]

    root = ensure_directory(output_dir or DATA_ROOT / "processed" / "event_sets")
    expanded_path = root / "expanded_cycles.parquet"
    manifest_path = root / "manifest.json"
    if not expanded.empty:
        expanded.to_parquet(expanded_path, index=False)
    else:
        pd.DataFrame().to_parquet(expanded_path, index=False)

    manifest = {
        "version": seed_config.get("version", "seed_events_v1"),
        "created_at": to_iso(utc_now()),
        "seed_event_count": len(seed_events),
        "matched_seed_event_count": len(matched_seed_events),
        "expanded_event_count": int(len(expanded)),
        "expanded_symbols": sorted(expanded["symbol"].unique().tolist()) if not expanded.empty else [],
        "commonality_profile": commonality,
        "manual_seed_events": seed_events,
        "matched_seed_events": matched_seed_events,
        "expanded_cycles_path": str(expanded_path),
    }
    manifest["event_set_hash"] = hash_payload(manifest)
    manifest_path.write_text(canonical_json(manifest), encoding="utf-8")
    manifest["manifest_path"] = str(manifest_path)
    return manifest
