from __future__ import annotations

import pandas as pd

from super_crypto.common.paths import PROJECT_ROOT


def assert_next_bar_entry(signals: list) -> None:
    for signal in signals:
        if signal.entry_reference != "next_bar_open":
            raise AssertionError("Signals must use next-bar entry.")


def assert_feature_timestamps(frame: pd.DataFrame) -> None:
    if (
        "support_level" in frame.columns
        and frame["support_level"].notna().sum()
        and frame["support_level"].equals(frame["low"].rolling(6, min_periods=2).min())
    ):
        raise AssertionError("support_level must be shifted and point-in-time safe.")


def scan_for_negative_shift() -> list[str]:
    offenders: list[str] = []
    signal_dir = PROJECT_ROOT / "src" / "super_crypto" / "signals"
    for path in signal_dir.rglob("*.py"):
        content = path.read_text(encoding="utf-8")
        if "shift(-" in content:
            offenders.append(str(path))
    return offenders
