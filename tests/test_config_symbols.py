from __future__ import annotations

from super_crypto.common.config import load_yaml
from super_crypto.common.config_symbols import (
    data_config_with_resolved_symbols,
    resolve_data_symbols,
)


def test_data_symbols_union_uses_split_and_phase1_window_symbols():
    config = {
        "data": {"symbols_mode": "union"},
        "splits": {
            "symbols": ["MMTUSDT", "VELVETUSDT"],
            "train": {"start": "2026-01-01T00:00:00Z", "end": "2026-01-02T00:00:00Z"},
            "validation": {
                "start": "2026-01-03T00:00:00Z",
                "end": "2026-01-04T00:00:00Z",
            },
            "holdout": {"start": "2026-01-05T00:00:00Z", "end": "2026-01-06T00:00:00Z"},
        },
        "phase1_prediction": {
            "event_windows": [
                {"symbol": "RIVERUSDT", "start": "2026-01-01", "end": "2026-01-02"},
                {"symbol": "MMTUSDT", "start": "2026-01-03", "end": "2026-01-04"},
            ],
        },
    }

    assert resolve_data_symbols(config) == ["MMTUSDT", "VELVETUSDT", "RIVERUSDT"]


def test_pipeline_config_data_symbols_are_derived_not_handwritten():
    config = load_yaml("configs/pipeline_v4a.yaml")
    data = data_config_with_resolved_symbols(config)

    assert config["data"]["symbols_mode"] == "union"
    assert "symbols" not in config["data"]
    assert set(config["splits"]["symbols"]).issubset(set(data["symbols"]))
    assert {window["symbol"] for window in config["phase1_prediction"]["event_windows"]}.issubset(
        set(data["symbols"])
    )
