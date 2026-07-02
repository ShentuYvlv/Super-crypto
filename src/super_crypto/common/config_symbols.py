from __future__ import annotations

from typing import Any

from super_crypto.common.config import load_yaml


def unique_symbols(symbols: list[str]) -> list[str]:
    return list(dict.fromkeys(str(symbol) for symbol in symbols if symbol))


def phase1_event_symbols(config: dict[str, Any]) -> list[str]:
    phase1 = config.get("phase1_prediction", config)
    return unique_symbols(
        [
            str(window["symbol"])
            for window in phase1.get("event_windows", [])
            if isinstance(window, dict) and window.get("symbol")
        ]
    )


def split_symbols(config: dict[str, Any]) -> list[str]:
    splits = config.get("splits", config)
    symbols = list(splits.get("symbols", []))
    for split in ("train", "validation", "holdout"):
        section = splits.get(split, {})
        if isinstance(section, dict):
            symbols.extend(section.get("symbols", []))
    return unique_symbols(symbols)


def resolve_data_symbols(config: dict[str, Any]) -> list[str]:
    data = config.get("data", config)
    mode = data.get("symbols_mode", "explicit")
    explicit = list(data.get("symbols", []))
    if mode == "explicit":
        return unique_symbols(explicit)
    if mode != "union":
        raise ValueError(f"Unknown data.symbols_mode: {mode}")
    return unique_symbols([*explicit, *split_symbols(config), *phase1_event_symbols(config)])


def data_config_with_resolved_symbols(config: str | dict[str, Any]) -> dict[str, Any]:
    loaded = load_yaml(config)
    data = loaded.get("data", loaded)
    return {**data, "symbols": resolve_data_symbols(loaded)}
