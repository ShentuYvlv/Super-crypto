from __future__ import annotations

from datetime import UTC, datetime

from fastapi import APIRouter

from super_crypto.common.paths import DATA_ROOT
from super_crypto.report_api.deps import envelope
from super_crypto.report_api.loaders import latest_pipeline_stage, list_pipeline_runs

router = APIRouter(prefix="/api/data-quality", tags=["data-quality"])


def _freshness_label(latest_mtime: float | None) -> str | None:
    if latest_mtime is None:
        return None
    age_seconds = int(datetime.now(UTC).timestamp() - latest_mtime)
    if age_seconds < 3600:
        return f"{age_seconds // 60}m"
    return f"{age_seconds // 3600}h"


@router.get("")
def get_data_quality():
    sections = [
        ("binance_klines", DATA_ROOT / "processed" / "ohlcv" / "1h"),
        ("binance_funding", DATA_ROOT / "processed" / "derivatives"),
        ("binance_open_interest", DATA_ROOT / "processed" / "derivatives"),
        ("binance_orderbook", DATA_ROOT / "processed" / "orderbook_features"),
        ("coinglass_cache", DATA_ROOT / "processed" / "external_enrichment"),
    ]
    latest_run = next(iter(list_pipeline_runs()), None)
    enrich_stage = latest_pipeline_stage(latest_run["run_id"], "enrich") if latest_run else None
    enrich_details = enrich_stage.get("details", {}) if enrich_stage else {}
    payload = []
    for name, path in sections:
        files = list(path.glob("*.parquet")) if path.exists() else []
        latest_mtime = max((file.stat().st_mtime for file in files), default=None)
        status = "healthy" if files else "partial"
        notes = []
        if name == "coinglass_cache":
            coinglass = enrich_details.get("coinglass", {})
            if coinglass and any(
                value == "request_failed"
                for symbol_info in coinglass.values()
                for value in symbol_info.values()
            ):
                status = "partial"
                notes.append("request_failed")
        payload.append(
            {
                "source_name": name,
                "status": status,
                "file_count": len(files),
                "freshness": _freshness_label(latest_mtime),
                "path": str(path),
                "notes": notes,
            }
        )
    return envelope(payload, source="filesystem")
