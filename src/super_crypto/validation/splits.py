from __future__ import annotations

import pandas as pd

from super_crypto.common.config import canonical_json, hash_payload, load_yaml
from super_crypto.common.paths import DATA_ROOT, resolve_project_path
from super_crypto.common.time import parse_timestamp


def read_symbol_split_file(path: str) -> list[str]:
    return [
        line.strip()
        for line in resolve_project_path(path).read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def build_split_manifest(config_path: str) -> dict:
    config = load_yaml(config_path)
    manifest = {
        split: {
            "start": config[split]["start"],
            "end": config[split]["end"],
            "symbols": read_symbol_split_file(config["symbol_split_files"][split]),
        }
        for split in ("train", "validation", "holdout")
    }
    manifest["purge_bars"] = config["purge_bars"]
    manifest["split_hash"] = hash_payload(manifest)
    output = DATA_ROOT / "processed" / "split_manifest.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(canonical_json(manifest), encoding="utf-8")
    return manifest


def filter_frame_for_split(frame: pd.DataFrame, config_path: str, split: str) -> pd.DataFrame:
    config = load_yaml(config_path)
    if split == "train_validation":
        train = filter_frame_for_split(frame, config_path, "train")
        validation = filter_frame_for_split(frame, config_path, "validation")
        return pd.concat([train, validation], ignore_index=True)
    start = parse_timestamp(config[split]["start"])
    end = parse_timestamp(config[split]["end"])
    allowed_symbols = set(read_symbol_split_file(config["symbol_split_files"][split]))
    result = frame.copy()
    result["open_time"] = pd.to_datetime(result["open_time"], utc=True)
    return result[
        (result["open_time"] >= start)
        & (result["open_time"] <= end)
        & (result["symbol"].isin(allowed_symbols))
    ].reset_index(drop=True)


def split_hash(config_path: str) -> str:
    manifest_path = DATA_ROOT / "processed" / "split_manifest.json"
    if manifest_path.exists():
        return hash_payload(__import__("json").loads(manifest_path.read_text(encoding="utf-8")))
    return build_split_manifest(config_path)["split_hash"]


def holdout_guard(config_path: str, split: str, final_flag: bool, prior_runs: int = 0) -> None:
    if split != "holdout":
        return
    config = load_yaml(config_path)["holdout_policy"]
    if config["require_final_flag"] and not final_flag:
        raise ValueError("Holdout requires --final.")
    if prior_runs >= int(config["max_manual_runs"]):
        raise ValueError("Holdout manual run limit reached.")
