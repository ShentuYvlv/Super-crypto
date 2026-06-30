from __future__ import annotations

import polars as pl

from super_crypto.common.paths import DATA_ROOT, ensure_parent
from super_crypto.data.etherscan_client import EtherscanClient


def run(address: str, symbol: str) -> dict:
    with EtherscanClient() as client:
        payload = client.get(
            {
                "module": "account",
                "action": "tokentx",
                "address": address,
                "sort": "desc",
            }
        )
        rows = payload.get("result", []) if isinstance(payload, dict) else []
        frame = pl.DataFrame(rows if isinstance(rows, list) else [])
        path = ensure_parent(DATA_ROOT / "raw" / "etherscan" / "transfers" / f"{symbol}.parquet")
        frame.write_parquet(path)
        processed = ensure_parent(
            DATA_ROOT / "processed" / "onchain_features" / f"transfers_{symbol}.parquet"
        )
        frame.write_parquet(processed)
        return {"rows": frame.height, "enabled": client.enabled}
