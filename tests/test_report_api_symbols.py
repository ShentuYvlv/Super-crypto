from __future__ import annotations

import numpy as np
import pandas as pd

from super_crypto.report_api.symbols import _build_depth_rows, _source_summary


def test_build_depth_rows_accepts_numpy_orderbook_levels():
    rows = _build_depth_rows(
        {
            "bids": np.array([["1.0", "10"], ["0.9", "8"]]),
            "asks": np.array([["1.1", "7"]]),
        }
    )

    assert rows == [
        {"price": 1.0, "bid": 10.0, "ask": 7.0},
        {"price": 0.9, "bid": 8.0, "ask": 0.0},
    ]


def test_build_depth_rows_accepts_json_encoded_levels():
    rows = _build_depth_rows(
        {
            "bids": '[["1.0", "10"]]',
            "asks": '[["1.1", "7"]]',
        }
    )

    assert rows == [{"price": 1.0, "bid": 10.0, "ask": 7.0}]


def test_source_summary_reports_coverage_and_latest_timestamp():
    rows = [
        {
            "source_name": "binance_klines_1h",
            "status": "healthy",
            "file_count": 1,
            "latest_timestamp": pd.Timestamp("2026-01-01T00:00:00Z"),
        },
        {
            "source_name": "binance_funding",
            "status": "partial",
            "file_count": 0,
            "latest_timestamp": None,
        },
    ]

    summary = _source_summary(rows)

    assert summary["healthy_sources"] == 1
    assert summary["total_sources"] == 2
    assert summary["coverage"] == 0.5
    assert summary["status"] == "partial"
