from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pandas as pd
import pytest


@pytest.fixture()
def sample_ohlcv() -> pd.DataFrame:
    start = datetime(2026, 1, 1, tzinfo=UTC)
    rows = []
    closes = [1.0, 1.08, 1.2, 1.34, 1.48, 1.55, 1.42, 1.3, 1.18, 1.08, 1.02, 0.98]
    for index, close in enumerate(closes):
        open_price = closes[index - 1] if index else close * 0.98
        high = max(open_price, close) * 1.04
        low = min(open_price, close) * 0.97
        rows.append(
            {
                "symbol": "MMTUSDT",
                "timeframe": "1h",
                "open_time": start + timedelta(hours=index),
                "close_time": start + timedelta(hours=index + 1),
                "open": open_price,
                "high": high,
                "low": low,
                "close": close,
                "volume": 1000 + index * 10,
                "quote_volume": 1500 + index * 15,
                "trade_count": 200 + index,
                "taker_buy_base_volume": 480 + index * 6,
                "taker_buy_quote_volume": 620 + index * 8,
            }
        )
    frame = pd.DataFrame(rows)
    frame.loc[5, "taker_buy_quote_volume"] = 450
    frame.loc[6, "taker_buy_quote_volume"] = 380
    return frame

