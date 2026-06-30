from __future__ import annotations

import pandas as pd


def iter_bars(frame: pd.DataFrame, start_idx: int):
    for idx in range(start_idx, len(frame)):
        yield idx, frame.iloc[idx]
