from __future__ import annotations

from hashlib import sha1

import pandas as pd

from super_crypto.common.time import parse_timestamp
from super_crypto.common.types import SignalRecord


def build_signal(
    *,
    symbol: str,
    strategy: str,
    bar: pd.Series,
    stop_loss: float,
    trailing_stop: float,
    confidence: float,
    bucket: str,
    reason: list[str],
    orderbook_slippage_bps: float | None = None,
    data_quality: str = "healthy",
    missing_fields: list[str] | None = None,
    stale_fields: list[str] | None = None,
) -> SignalRecord:
    decision_time = parse_timestamp(bar["open_time"]).to_pydatetime()
    signal_id = sha1(f"{symbol}|{strategy}|{decision_time.isoformat()}".encode("utf-8")).hexdigest()[:12]
    return SignalRecord(
        signal_id=signal_id,
        symbol=symbol,
        strategy=strategy,  # type: ignore[arg-type]
        side="SHORT",
        signal_time=decision_time,
        decision_time=decision_time,
        data_cutoff_time=decision_time,
        entry_reference="next_bar_open",
        stop_loss=stop_loss,
        trailing_stop=trailing_stop,
        confidence=max(0.0, min(1.0, confidence)),
        manipulation_score_bucket=bucket,  # type: ignore[arg-type]
        reason=reason,
        data_quality=data_quality,  # type: ignore[arg-type]
        missing_fields=missing_fields or [],
        stale_fields=stale_fields or [],
        orderbook_slippage_bps=orderbook_slippage_bps,
    )

