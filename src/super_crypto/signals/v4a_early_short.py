from __future__ import annotations

import pandas as pd

from super_crypto.features.feature_matrix import build_feature_matrix
from super_crypto.signals.base import build_signal
from super_crypto.signals.naked_k import pump_context


def generate(
    ohlcv: pd.DataFrame,
    symbol: str,
    config: dict,
    *,
    funding: pd.DataFrame | None = None,
    open_interest: pd.DataFrame | None = None,
    manipulation_bucket: str = "high",
    orderbook_slippage_bps: float | None = None,
) -> list:
    frame = build_feature_matrix(
        ohlcv,
        funding=funding,
        open_interest=open_interest,
        lookback_bars=int(config["lookback_bars"]),
        support_window=int(config["support_window"]),
        peak_window=int(config["peak_window"]),
    )
    frame["pump_context"] = pump_context(frame)
    frame["first_sell"] = frame["sell_pressure"] <= float(config["first_sell_pressure_threshold"])
    frame["support_break"] = frame["close"] <= frame["support_level"] * (
        1 - float(config["support_break_threshold"])
    )
    frame["trigger"] = frame["pump_context"] & frame["first_sell"] & frame["support_break"]
    signals = []
    for _, row in frame[frame["trigger"]].iterrows():
        confidence = (
            min(row["pump_return_lookback"] / 0.5, 1.0) * 0.32
            + min(abs(row["sell_pressure"]) / 0.1, 1.0) * 0.24
            + min(abs(row["drawdown_from_peak"]) / 0.1, 1.0) * 0.21
            + 0.16
            + (0.07 if orderbook_slippage_bps is not None and orderbook_slippage_bps < 50 else 0.0)
        )
        signals.append(
            build_signal(
                symbol=symbol,
                strategy="V4A",
                bar=row,
                stop_loss=float(config["stop_loss_pct"]),
                trailing_stop=float(config["trailing_stop_pct"]),
                confidence=confidence,
                bucket=manipulation_bucket,
                reason=["pump_context_detected", "first_sell_pressure", "support_break"],
                orderbook_slippage_bps=orderbook_slippage_bps,
            )
        )
    return signals

