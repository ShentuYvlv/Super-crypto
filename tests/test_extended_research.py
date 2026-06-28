from __future__ import annotations

from datetime import UTC, datetime

import pandas as pd
import pytest

from super_crypto.autoresearch.code_patch_guard import assert_allowed
from super_crypto.backtest.vectorbt_runner import run_vectorbt_benchmark
from super_crypto.features.feature_matrix import build_feature_matrix
from super_crypto.features.lightgbm_filter import score_candidate_filter


def test_extended_research_fields_are_analysis_only(sample_ohlcv):
    liquidation = pd.DataFrame(
        [
            {
                "snapshot_time": datetime(2026, 1, 1, 1, tzinfo=UTC),
                "long_liquidation_usd": 1000.0,
                "short_liquidation_usd": 3000.0,
            }
        ]
    )
    transfers = pd.DataFrame(
        [
            {
                "transfer_time": datetime(2026, 1, 1, 2, tzinfo=UTC),
                "direction": "inflow",
                "amount_usd": 150000.0,
                "is_whale": True,
            }
        ]
    )
    matrix = build_feature_matrix(
        sample_ohlcv,
        liquidation=liquidation,
        onchain_transfers=transfers,
    )
    assert {"liq_imbalance", "cex_inflow_usd", "whale_transfer_count"}.issubset(matrix.columns)
    assert matrix["liquidation_data_quality"].iloc[-1] == "healthy"
    assert matrix["onchain_data_quality"].iloc[-1] == "healthy"


def test_lightgbm_filter_is_optional(sample_ohlcv):
    result = score_candidate_filter(sample_ohlcv)
    assert result.enabled is False
    assert result.reason in {"lightgbm_not_installed", "no_feature_columns", "model_path_required"}


def test_autoresearch_guard_blocks_protected_equivalent_paths():
    with pytest.raises(ValueError):
        assert_allowed(["./configs/splits.yaml"])


def test_vectorbt_benchmark_reports_real_or_unavailable_state(sample_ohlcv):
    result = run_vectorbt_benchmark(
        ohlcv_by_symbol={"BTCUSDT": sample_ohlcv},
        signals=[],
        split="validation",
        backtest_config={
            "capital_per_trade_usdt": 1000,
            "fee_bps": 6,
            "slippage_bps_floor": 25,
            "max_hold_hours": {"v4a": 8},
        },
        strategy_config={"strategy": "V4A"},
    )
    assert result["engine"] == "vectorbt"
    assert result["status"] in {"available", "unavailable"}
    if result["status"] == "available":
        assert result["metrics"]["trade_count"] == 0
