from __future__ import annotations

import json

import pandas as pd
import polars as pl

from super_crypto.common.config import load_yaml
from super_crypto.common.paths import DATA_ROOT, ensure_parent
from super_crypto.cycles.detect_pump_dump import detect_cycles


def _empty_cycle_frame() -> pl.DataFrame:
    return pl.DataFrame(
        schema={
            "cycle_id": pl.String,
            "symbol": pl.String,
            "pump_start": pl.Datetime(time_zone="UTC"),
            "peak_time": pl.Datetime(time_zone="UTC"),
            "dump_end": pl.Datetime(time_zone="UTC"),
            "pump_return": pl.Float64,
            "dump_return": pl.Float64,
            "duration_hours": pl.Float64,
            "score_context": pl.String,
        }
    )


def run(config_path: str, symbols: list[str], timeframe: str = "1h") -> dict:
    config = load_yaml(config_path)
    results: dict[str, int] = {}
    for symbol in symbols:
        ohlcv_path = DATA_ROOT / "processed" / "ohlcv" / timeframe / f"{symbol}.parquet"
        if not ohlcv_path.exists():
            results[symbol] = 0
            continue
        frame = pd.read_parquet(ohlcv_path)
        frame["open_time"] = pd.to_datetime(frame["open_time"], utc=True)
        cycles = detect_cycles(frame, symbol, config)
        if cycles:
            records = []
            for cycle in cycles:
                record = cycle.model_dump(mode="json")
                record["score_context"] = json.dumps(
                    record.get("score_context", {}), ensure_ascii=False
                )
                records.append(record)
            output_frame = pl.DataFrame(records)
        else:
            output_frame = _empty_cycle_frame()
        path = ensure_parent(DATA_ROOT / "processed" / "cycles" / f"{symbol}.parquet")
        output_frame.write_parquet(path)
        results[symbol] = len(cycles)
    return results
