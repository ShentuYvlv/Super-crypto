from __future__ import annotations

import pandas as pd

from super_crypto.features.derivative_features import merge_derivatives
from super_crypto.features.liquidation_features import add_liquidation_analysis_fields
from super_crypto.features.onchain_features import add_onchain_analysis_fields
from super_crypto.features.price_features import add_price_features
from super_crypto.features.taker_features import add_taker_features


def build_feature_matrix(
    ohlcv: pd.DataFrame,
    *,
    funding: pd.DataFrame | None = None,
    open_interest: pd.DataFrame | None = None,
    liquidation: pd.DataFrame | None = None,
    onchain_transfers: pd.DataFrame | None = None,
    lookback_bars: int = 24,
    support_window: int = 6,
    peak_window: int = 12,
) -> pd.DataFrame:
    result = add_price_features(
        ohlcv,
        lookback_bars=lookback_bars,
        support_window=support_window,
        peak_window=peak_window,
    )
    result = merge_derivatives(result, funding=funding, open_interest=open_interest)
    result = add_taker_features(result)
    result = add_liquidation_analysis_fields(result, liquidation=liquidation)
    result = add_onchain_analysis_fields(result, transfers=onchain_transfers)
    return result
