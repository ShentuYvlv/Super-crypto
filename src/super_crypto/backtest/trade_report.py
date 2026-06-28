from __future__ import annotations

from pathlib import Path

import pandas as pd

from super_crypto.common.paths import ensure_parent


def to_frame(trades: list[dict]) -> pd.DataFrame:
    return pd.DataFrame(trades)


def write_csv(trades: pd.DataFrame, path: Path) -> str:
    ensure_parent(path)
    trades.to_csv(path, index=False)
    return str(path)

