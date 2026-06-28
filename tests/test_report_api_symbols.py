from __future__ import annotations

import numpy as np

from super_crypto.report_api.symbols import _build_depth_rows


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
