from __future__ import annotations

from super_crypto.common.time import utc_now
from super_crypto.experiments.experiment_store import ExperimentStore
from super_crypto.experiments.pipeline_store import PipelineStore


def envelope(
    payload, *, source: str = "sqlite", freshness_sec: int = 0, data_quality: str = "healthy"
):
    return {
        "generated_at": utc_now().isoformat(),
        "source": source,
        "freshness_sec": freshness_sec,
        "data_quality": data_quality,
        "missing_fields": [],
        "stale_fields": [],
        "payload": payload,
    }


def experiment_store() -> ExperimentStore:
    return ExperimentStore()


def pipeline_store() -> PipelineStore:
    return PipelineStore()
