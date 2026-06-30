from __future__ import annotations

import pandas as pd

from super_crypto.signals.base import build_signal


def generate(frame: pd.DataFrame, symbol: str, config: dict, bucket: str = "medium") -> list:
    threshold = float(config["drop_threshold"])
    consecutive = int(config["consecutive_bars"])
    bars = frame.copy()
    bars["bearish"] = ((bars["close"] / bars["open"]) - 1) <= -threshold
    bars["trigger"] = (
        bars["bearish"].rolling(consecutive, min_periods=consecutive).sum() == consecutive
    )
    signals = []
    for _, row in bars[bars["trigger"]].iterrows():
        signals.append(
            build_signal(
                symbol=symbol,
                strategy="V3",
                bar=row,
                stop_loss=float(config["stop_loss_pct"]),
                trailing_stop=float(config["trailing_stop_pct"]),
                confidence=0.55,
                bucket=bucket,
                reason=["abandon_point", "two_bar_break"],
            )
        )
    return signals
