from __future__ import annotations


def build_quality_flags(*, missing_fields: list[str], stale_fields: list[str]) -> dict:
    if missing_fields:
        state = "partial"
    elif stale_fields:
        state = "stale"
    else:
        state = "healthy"
    return {
        "data_quality": state,
        "missing_fields": missing_fields,
        "stale_fields": stale_fields,
    }
