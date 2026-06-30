from __future__ import annotations

from super_crypto.common.paths import DATA_ROOT
from super_crypto.experiments.pipeline_runner import (
    _enrichment_output_paths,
    _ingest_output_paths,
    _stage_enabled,
    _stage_skip_reason,
)


def test_stage_enabled_defaults_to_true():
    assert _stage_enabled({}, "ingest") is True


def test_stage_skip_reason_reports_disabled_stage():
    config = {"stages": {"ingest": {"enabled": False}}}

    assert _stage_skip_reason(config, "ingest", "train_validation") == "disabled"


def test_ingest_outputs_cover_all_timeframes_and_derivatives():
    paths = _ingest_output_paths(["BTCUSDT"], ["1m", "1h"])

    assert paths == [
        DATA_ROOT / "processed" / "ohlcv" / "1m" / "BTCUSDT.parquet",
        DATA_ROOT / "processed" / "ohlcv" / "1h" / "BTCUSDT.parquet",
        DATA_ROOT / "processed" / "derivatives" / "funding_BTCUSDT.parquet",
        DATA_ROOT / "processed" / "derivatives" / "open_interest_BTCUSDT.parquet",
    ]


def test_enrichment_outputs_cover_orderbook_and_coinglass_endpoints():
    paths = _enrichment_output_paths(["BTCUSDT"], ["tickers", "coin_info"])

    assert paths == [
        DATA_ROOT / "processed" / "orderbook_features" / "BTCUSDT.parquet",
        DATA_ROOT / "processed" / "external_enrichment" / "tickers_BTCUSDT.parquet",
        DATA_ROOT / "processed" / "external_enrichment" / "coin_info_BTCUSDT.parquet",
    ]
