from __future__ import annotations

from super_crypto.common.types import QualityState


def classify_freshness(
    freshness_sec: int,
    stale_after_sec: int,
    blocked_after_sec: int | None = None,
) -> QualityState:
    if freshness_sec <= stale_after_sec:
        return "healthy"
    if blocked_after_sec is not None and freshness_sec > blocked_after_sec:
        return "blocked"
    return "stale"
