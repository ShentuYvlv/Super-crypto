from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pandas as pd

from super_crypto.common.config import hash_payload
from super_crypto.common.config_validation import validate_phase1_event_windows
from super_crypto.common.paths import DATA_ROOT, REPORT_ROOT, ensure_directory, ensure_parent
from super_crypto.common.time import to_iso, utc_now
from super_crypto.experiments.experiment_store import ExperimentStore

LABEL_COLUMNS = [
    "event_id",
    "symbol",
    "event_start",
    "peak_time",
    "dump_end",
    "split",
    "label_quality",
    "source",
    "note",
]


@dataclass(frozen=True)
class Phase1FeatureSet:
    name: str
    columns: list[str]
    model: str = "threshold"


FEATURE_SETS = [
    Phase1FeatureSet("fr_baseline", ["funding_rate"]),
    Phase1FeatureSet("fr_oi", ["funding_rate", "oi_change_1h", "oi_change_6h", "oi_change_24h"]),
    Phase1FeatureSet(
        "fr_oi_liquidation",
        [
            "funding_rate",
            "oi_change_1h",
            "oi_change_6h",
            "oi_change_24h",
            "liq_long_usd",
            "liq_short_usd",
            "liq_imbalance",
        ],
    ),
    Phase1FeatureSet(
        "fr_oi_liquidation_taker",
        [
            "funding_rate",
            "oi_change_1h",
            "oi_change_6h",
            "oi_change_24h",
            "liq_long_usd",
            "liq_short_usd",
            "liq_imbalance",
            "taker_buy_ratio",
            "sell_pressure",
        ],
    ),
    Phase1FeatureSet(
        "all_available_features",
        [
            "funding_rate",
            "oi_change_1h",
            "oi_change_6h",
            "oi_change_24h",
            "liq_long_usd",
            "liq_short_usd",
            "liq_imbalance",
            "taker_buy_ratio",
            "sell_pressure",
            "bar_return",
            "return_4h",
            "return_24h",
            "volume_zscore_24h",
            "quote_volume_zscore_24h",
            "range_pct",
            "pump_return_lookback",
            "cex_inflow_usd",
            "cex_outflow_usd",
            "whale_transfer_count",
            "long_short_ratio",
            "orderbook_spread_bps",
            "orderbook_imbalance",
            "orderbook_slippage_100",
            "orderbook_slippage_500",
            "orderbook_slippage_1000",
            "orderbook_max_size_under_50bps",
        ],
    ),
    Phase1FeatureSet(
        "lightgbm_all_features",
        [
            "funding_rate",
            "oi_change_1h",
            "oi_change_6h",
            "oi_change_24h",
            "liq_long_usd",
            "liq_short_usd",
            "liq_imbalance",
            "taker_buy_ratio",
            "sell_pressure",
            "bar_return",
            "return_4h",
            "return_24h",
            "volume_zscore_24h",
            "quote_volume_zscore_24h",
            "range_pct",
            "pump_return_lookback",
            "cex_inflow_usd",
            "cex_outflow_usd",
            "whale_transfer_count",
            "long_short_ratio",
            "orderbook_spread_bps",
            "orderbook_imbalance",
            "orderbook_slippage_100",
            "orderbook_slippage_500",
            "orderbook_slippage_1000",
            "orderbook_max_size_under_50bps",
        ],
        model="lightgbm",
    ),
]


def _label_template_path(config: dict[str, Any]) -> Path:
    return DATA_ROOT / "labels" / Path(config.get("label_source", "phase1_events.csv")).name


def _load_ohlcv(symbol: str, timeframe: str) -> pd.DataFrame:
    path = DATA_ROOT / "processed" / "ohlcv" / timeframe / f"{symbol}.parquet"
    if not path.exists():
        return pd.DataFrame()
    frame = pd.read_parquet(path)
    frame["open_time"] = pd.to_datetime(frame["open_time"], utc=True)
    return frame.sort_values("open_time").reset_index(drop=True)


def _load_optional_parquet(path: Path) -> pd.DataFrame:
    if not path.exists():
        return pd.DataFrame()
    return pd.read_parquet(path)


def _load_first_existing(paths: list[Path]) -> pd.DataFrame:
    for path in paths:
        data = _load_optional_parquet(path)
        if not data.empty:
            return data
    return pd.DataFrame()


def _merge_asof(
    frame: pd.DataFrame,
    data: pd.DataFrame,
    *,
    time_column: str,
    columns: list[str],
) -> pd.DataFrame:
    result = frame.copy()
    if data.empty or time_column not in data.columns:
        for column in columns:
            result[column] = 0.0
        return result
    other = data.copy()
    other[time_column] = pd.to_datetime(other[time_column], utc=True, errors="coerce")
    other = other.dropna(subset=[time_column]).sort_values(time_column)
    other = other.rename(columns={time_column: "open_time"})
    for column in columns:
        if column not in other.columns:
            other[column] = 0.0
    return pd.merge_asof(
        result.sort_values("open_time"),
        other[["open_time", *columns]].sort_values("open_time"),
        on="open_time",
        direction="backward",
    )


def _time_column(data: pd.DataFrame, candidates: tuple[str, ...]) -> str | None:
    return next((column for column in candidates if column in data.columns), None)


def _merge_liquidation(frame: pd.DataFrame, symbol: str) -> pd.DataFrame:
    result = frame.copy()
    data = _load_first_existing(
        [
            DATA_ROOT / "processed" / "derivatives" / f"liquidation_{symbol}.parquet",
            DATA_ROOT / "processed" / "derivatives" / f"liquidations_{symbol}.parquet",
            DATA_ROOT / "processed" / "external_enrichment" / f"liquidation_{symbol}.parquet",
            DATA_ROOT / "processed" / "external_enrichment" / f"liquidations_{symbol}.parquet",
        ]
    )
    if data.empty:
        for column in ("liq_long_usd", "liq_short_usd", "liq_imbalance"):
            result[column] = 0.0
        result["liquidation_data_quality"] = "missing"
        return result
    data = data.rename(
        columns={
            "long_liquidation_usd": "liq_long_usd",
            "short_liquidation_usd": "liq_short_usd",
            "longLiquidationUsd": "liq_long_usd",
            "shortLiquidationUsd": "liq_short_usd",
        }
    )
    time_column = _time_column(data, ("open_time", "snapshot_time", "time", "timestamp"))
    if time_column is None:
        for column in ("liq_long_usd", "liq_short_usd", "liq_imbalance"):
            result[column] = 0.0
        result["liquidation_data_quality"] = "missing_time"
        return result
    for column in ("liq_long_usd", "liq_short_usd"):
        if column not in data.columns:
            data[column] = 0.0
    result = _merge_asof(
        result,
        data,
        time_column=time_column,
        columns=["liq_long_usd", "liq_short_usd"],
    )
    total = result["liq_long_usd"] + result["liq_short_usd"]
    result["liq_imbalance"] = (
        (result["liq_short_usd"] - result["liq_long_usd"]) / total.replace(0, pd.NA)
    ).fillna(0.0)
    result["liquidation_data_quality"] = "healthy"
    return result


def _merge_long_short_ratio(frame: pd.DataFrame, symbol: str) -> pd.DataFrame:
    result = frame.copy()
    data = _load_first_existing(
        [
            DATA_ROOT / "processed" / "derivatives" / f"long_short_ratio_{symbol}.parquet",
            DATA_ROOT / "processed" / "external_enrichment" / f"long_short_ratio_{symbol}.parquet",
            DATA_ROOT / "processed" / "external_enrichment" / f"tickers_{symbol}.parquet",
        ]
    )
    if data.empty or "long_short_ratio" not in data.columns:
        result["long_short_ratio"] = 0.0
        result["long_short_data_quality"] = "missing"
        return result
    time_column = _time_column(data, ("open_time", "snapshot_time", "time", "timestamp"))
    if time_column is None:
        result["long_short_ratio"] = 0.0
        result["long_short_data_quality"] = "missing_time"
        return result
    result = _merge_asof(
        result,
        data,
        time_column=time_column,
        columns=["long_short_ratio"],
    )
    result["long_short_data_quality"] = "healthy"
    return result


def _slippage_value(value: Any, notional: str) -> float:
    if isinstance(value, dict):
        return float(value.get(notional, 0.0) or 0.0)
    return 0.0


def _merge_orderbook(frame: pd.DataFrame, symbol: str) -> pd.DataFrame:
    result = frame.copy()
    data = _load_optional_parquet(
        DATA_ROOT / "processed" / "orderbook_features" / f"{symbol}.parquet"
    )
    defaults = {
        "orderbook_spread_bps": 0.0,
        "orderbook_imbalance": 0.0,
        "orderbook_slippage_100": 0.0,
        "orderbook_slippage_500": 0.0,
        "orderbook_slippage_1000": 0.0,
        "orderbook_max_size_under_50bps": 0.0,
    }
    if data.empty:
        for column, value in defaults.items():
            result[column] = value
        result["orderbook_data_quality"] = "missing"
        return result
    time_column = _time_column(data, ("snapshot_time", "open_time", "time", "timestamp"))
    if time_column is None:
        for column, value in defaults.items():
            result[column] = value
        result["orderbook_data_quality"] = "missing_time"
        return result
    data = data.copy()
    data["orderbook_spread_bps"] = pd.to_numeric(data.get("spread_bps", 0.0), errors="coerce")
    data["orderbook_imbalance"] = pd.to_numeric(data.get("imbalance", 0.0), errors="coerce")
    sell_side = data.get("slippage_bps_sell")
    if sell_side is None:
        sell_side = pd.Series([{} for _ in range(len(data))], index=data.index)
    data["orderbook_slippage_100"] = sell_side.apply(lambda value: _slippage_value(value, "100"))
    data["orderbook_slippage_500"] = sell_side.apply(lambda value: _slippage_value(value, "500"))
    data["orderbook_slippage_1000"] = sell_side.apply(lambda value: _slippage_value(value, "1000"))
    data["orderbook_max_size_under_50bps"] = data["orderbook_slippage_1000"].apply(
        lambda value: 1000.0 if float(value or 0.0) <= 50.0 else 500.0
    )
    result = _merge_asof(
        result,
        data,
        time_column=time_column,
        columns=list(defaults),
    )
    result["orderbook_data_quality"] = "healthy"
    return result


def _merge_onchain(frame: pd.DataFrame, symbol: str) -> pd.DataFrame:
    result = frame.copy()
    data = _load_optional_parquet(
        DATA_ROOT / "processed" / "onchain_features" / f"transfers_{symbol}.parquet"
    )
    if data.empty:
        for column in ("cex_inflow_usd", "cex_outflow_usd", "whale_transfer_count"):
            result[column] = 0.0
        result["onchain_data_quality"] = "missing"
        return result
    time_column = _time_column(data, ("transfer_time", "timeStamp", "open_time", "timestamp"))
    if time_column is None:
        for column in ("cex_inflow_usd", "cex_outflow_usd", "whale_transfer_count"):
            result[column] = 0.0
        result["onchain_data_quality"] = "missing_time"
        return result
    data = data.copy()
    data[time_column] = pd.to_datetime(data[time_column], utc=True, errors="coerce")
    data = data.dropna(subset=[time_column])
    if "amount_usd" not in data.columns:
        data["amount_usd"] = pd.to_numeric(data.get("value", 0.0), errors="coerce").fillna(0.0)
    if "direction" not in data.columns:
        data["direction"] = "unknown"
    if "is_whale" not in data.columns:
        data["is_whale"] = pd.to_numeric(data["amount_usd"], errors="coerce").fillna(0.0) > 100000
    data["open_time"] = data[time_column].dt.floor("h")
    grouped = (
        data.assign(
            cex_inflow_usd=lambda item: item["amount_usd"].where(
                item["direction"] == "inflow", 0.0
            ),
            cex_outflow_usd=lambda item: item["amount_usd"].where(
                item["direction"] == "outflow", 0.0
            ),
            whale_transfer_count=lambda item: item["is_whale"].astype(float),
        )
        .groupby("open_time", as_index=False)
        .agg(
            cex_inflow_usd=("cex_inflow_usd", "sum"),
            cex_outflow_usd=("cex_outflow_usd", "sum"),
            whale_transfer_count=("whale_transfer_count", "sum"),
        )
    )
    result = result.merge(grouped, on="open_time", how="left")
    for column in ("cex_inflow_usd", "cex_outflow_usd", "whale_transfer_count"):
        result[column] = result[column].fillna(0.0)
    result["onchain_data_quality"] = "healthy"
    return result


def _feature_frame(symbol: str, timeframe: str) -> pd.DataFrame:
    frame = _load_ohlcv(symbol, timeframe)
    if frame.empty:
        return frame
    frame["bar_return"] = frame["close"].pct_change().fillna(0.0)
    frame["return_4h"] = frame["close"].pct_change(4, fill_method=None).fillna(0.0)
    frame["return_24h"] = frame["close"].pct_change(24, fill_method=None).fillna(0.0)
    frame["range_pct"] = (frame["high"] / frame["low"].replace(0, pd.NA) - 1).fillna(0.0)
    frame["pump_return_lookback"] = (
        frame["high"].rolling(24, min_periods=2).max()
        / frame["low"].rolling(24, min_periods=2).min()
        - 1
    ).fillna(0.0)
    for column in ("volume", "quote_volume"):
        rolling_mean = frame[column].rolling(24, min_periods=6).mean()
        rolling_std = frame[column].rolling(24, min_periods=6).std().replace(0, pd.NA)
        frame[f"{column}_zscore_24h"] = ((frame[column] - rolling_mean) / rolling_std).fillna(0.0)
    taker_ratio = frame["taker_buy_quote_volume"].replace(0, pd.NA) / frame[
        "quote_volume"
    ].replace(0, pd.NA)
    frame["taker_buy_ratio"] = taker_ratio.fillna(0.5)
    frame["sell_pressure"] = (frame["taker_buy_ratio"] - 0.5).fillna(0.0)

    funding = _load_optional_parquet(
        DATA_ROOT / "processed" / "derivatives" / f"funding_{symbol}.parquet"
    )
    frame = _merge_asof(frame, funding, time_column="funding_time", columns=["funding_rate"])

    oi = _load_optional_parquet(
        DATA_ROOT / "processed" / "derivatives" / f"open_interest_{symbol}.parquet"
    )
    frame = _merge_asof(
        frame,
        oi,
        time_column="snapshot_time",
        columns=["open_interest", "oi_value_usd"],
    )
    frame["oi_level"] = pd.to_numeric(frame.get("open_interest", 0.0), errors="coerce").fillna(0.0)
    for window in (1, 6, 24):
        frame[f"oi_change_{window}h"] = frame["oi_level"].pct_change(
            window,
            fill_method=None,
        ).fillna(0.0)

    frame = _merge_liquidation(frame, symbol)
    frame = _merge_long_short_ratio(frame, symbol)
    frame = _merge_orderbook(frame, symbol)
    frame = _merge_onchain(frame, symbol)
    frame["symbol"] = symbol
    return frame


def _candidate_rows(config: dict[str, Any], symbols: list[str]) -> pd.DataFrame:
    thresholds = config["candidate_thresholds"]
    timeframe = config["timeframe"]
    rows: list[dict[str, Any]] = []
    for symbol in symbols:
        frame = _feature_frame(symbol, timeframe)
        if frame.empty:
            continue
        candidates = frame[
            (frame["return_4h"] >= float(thresholds["return_4h_min"]))
            | (frame["return_24h"] >= float(thresholds["return_24h_min"]))
            | (frame["volume_zscore_24h"] >= float(thresholds["volume_zscore_min"]))
            | (frame["range_pct"] >= float(thresholds["range_pct_min"]))
        ].copy()
        if candidates.empty:
            continue
        cooldown = pd.Timedelta(hours=float(config.get("candidate_cooldown_hours", 24)))
        last_time = None
        for _, row in candidates.sort_values("open_time").iterrows():
            open_time = row["open_time"]
            if last_time is not None and open_time - last_time < cooldown:
                continue
            window = frame[
                (frame["open_time"] >= open_time - pd.Timedelta(hours=24))
                & (frame["open_time"] <= open_time + pd.Timedelta(hours=48))
            ]
            if window.empty:
                continue
            peak = window.loc[window["high"].idxmax()]
            rows.append(
                {
                    "event_id": f"{symbol.lower()}_{open_time.strftime('%Y%m%d%H%M')}",
                    "symbol": symbol,
                    "candidate_start": to_iso(open_time.to_pydatetime()),
                    "suggested_peak_time": to_iso(peak["open_time"].to_pydatetime()),
                    "return_4h": float(row["return_4h"]),
                    "return_24h": float(row["return_24h"]),
                    "volume_zscore_24h": float(row["volume_zscore_24h"]),
                    "range_pct": float(row["range_pct"]),
                    "label_event_start": "",
                    "label_peak_time": "",
                    "label_dump_end": "",
                    "label_quality": "",
                    "split": "",
                    "note": "",
                }
            )
            last_time = open_time
    return pd.DataFrame(rows)


def write_label_template(config: dict[str, Any]) -> str:
    path = ensure_parent(_label_template_path(config))
    if not path.exists():
        pd.DataFrame(columns=LABEL_COLUMNS).to_csv(path, index=False)
    return str(path)


def generate_label_candidates(config: dict[str, Any], symbols: list[str]) -> dict[str, Any]:
    candidates = _candidate_rows(config, symbols)
    output_path = ensure_parent(DATA_ROOT / "processed" / "phase1" / "label_candidates.csv")
    candidates.to_csv(output_path, index=False)
    return {
        "candidate_count": int(len(candidates)),
        "candidate_path": str(output_path),
        "label_template_path": write_label_template(config),
    }


def _load_labels(config: dict[str, Any]) -> pd.DataFrame:
    labels = _load_yaml_window_labels(config)
    csv_labels = _load_csv_labels(config)
    if not csv_labels.empty:
        labels = pd.concat([labels, csv_labels], ignore_index=True)
    if labels.empty:
        return pd.DataFrame(columns=LABEL_COLUMNS)
    labels = _normalize_labels(config, labels)
    labels = labels.drop_duplicates(subset=["event_id", "symbol", "event_start"])
    return labels


def _load_csv_labels(config: dict[str, Any]) -> pd.DataFrame:
    path = _label_template_path(config)
    if not path.exists():
        return pd.DataFrame(columns=LABEL_COLUMNS)
    labels = pd.read_csv(path)
    if labels.empty:
        return labels
    return labels


def _normalize_labels(config: dict[str, Any], labels: pd.DataFrame) -> pd.DataFrame:
    labels = labels[[column for column in LABEL_COLUMNS if column in labels.columns]].copy()
    for column in LABEL_COLUMNS:
        if column not in labels.columns:
            labels[column] = ""
    labels["event_start"] = pd.to_datetime(labels["event_start"], utc=True, errors="coerce")
    labels["peak_time"] = pd.to_datetime(labels["peak_time"], utc=True, errors="coerce")
    labels["dump_end"] = pd.to_datetime(labels["dump_end"], utc=True, errors="coerce")
    labels = labels.dropna(subset=["symbol", "event_start"])
    labels["split"] = labels.get("split", "train").fillna("train").replace("", "train")
    labels["label_quality"] = labels.get("label_quality", "").fillna("").replace("", "A")
    allowed_quality = set(config.get("allowed_label_quality", ["A", "B"]))
    if allowed_quality:
        labels = labels[labels["label_quality"].isin(allowed_quality)]
    return labels


def _window_timestamp(window: dict[str, Any], key: str) -> pd.Timestamp:
    value = window.get(key)
    if value is None:
        raise ValueError(f"phase1_prediction.event_windows requires {key}")
    timestamp = pd.to_datetime(value, utc=True, errors="coerce")
    if pd.isna(timestamp):
        raise ValueError(f"invalid phase1_prediction.event_windows {key}: {value}")
    return timestamp


def _auto_detect_event_in_window(
    frame: pd.DataFrame,
    window: dict[str, Any],
    config: dict[str, Any],
) -> dict[str, pd.Timestamp] | None:
    start = _window_timestamp(window, "start")
    end = _window_timestamp(window, "end")
    if end <= start:
        raise ValueError("phase1_prediction.event_windows end must be after start")
    scoped = frame[(frame["open_time"] >= start) & (frame["open_time"] <= end)].copy()
    if scoped.empty:
        return None

    detection = config.get("auto_event_detection", {})
    pump_return_min = float(detection.get("pump_return_min", 0.15))
    threshold_candidates = scoped[scoped["pump_return_lookback"] >= pump_return_min]
    if threshold_candidates.empty:
        thresholds = config.get("candidate_thresholds", {})
        threshold_candidates = scoped[
            (scoped["return_4h"] >= float(thresholds.get("return_4h_min", pump_return_min)))
            | (scoped["return_24h"] >= float(thresholds.get("return_24h_min", pump_return_min)))
            | (
                scoped["volume_zscore_24h"]
                >= float(thresholds.get("volume_zscore_min", 999999.0))
            )
            | (scoped["range_pct"] >= float(thresholds.get("range_pct_min", 999999.0)))
        ]
    if threshold_candidates.empty:
        event_start = scoped.iloc[0]["open_time"]
    else:
        event_start = threshold_candidates.iloc[0]["open_time"]

    after_start = scoped[scoped["open_time"] >= event_start]
    peak_row = (
        after_start.loc[after_start["high"].idxmax()]
        if not after_start.empty
        else scoped.iloc[-1]
    )
    after_peak = scoped[scoped["open_time"] >= peak_row["open_time"]]
    dump_row = after_peak.loc[after_peak["low"].idxmin()] if not after_peak.empty else peak_row
    return {
        "event_start": pd.Timestamp(event_start),
        "peak_time": pd.Timestamp(peak_row["open_time"]),
        "dump_end": pd.Timestamp(dump_row["open_time"]),
    }


def _load_yaml_window_labels(config: dict[str, Any]) -> pd.DataFrame:
    windows = config.get("event_windows", [])
    if not windows:
        return pd.DataFrame(columns=LABEL_COLUMNS)
    rows: list[dict[str, Any]] = []
    timeframe = config["timeframe"]
    for index, window in enumerate(windows):
        symbol = str(window["symbol"])
        frame = _feature_frame(symbol, timeframe)
        if frame.empty:
            raise FileNotFoundError(
                f"Missing OHLCV data for phase1 event window symbol: {symbol} {timeframe}"
            )
        detected = _auto_detect_event_in_window(frame, window, config)
        if detected is None:
            continue
        event_id = window.get("event_id") or window.get("window_id")
        if not event_id:
            event_id = f"{symbol.lower()}_window_{index:03d}"
        rows.append(
            {
                "event_id": event_id,
                "symbol": symbol,
                "event_start": detected["event_start"],
                "peak_time": detected["peak_time"],
                "dump_end": detected["dump_end"],
                "split": window.get("split", "train"),
                "label_quality": window.get("label_quality", "A"),
                "source": window.get("source", "yaml_window_auto_detect"),
                "note": window.get("note", ""),
            }
        )
    return pd.DataFrame(rows, columns=LABEL_COLUMNS)


def _symbols_for_phase1(config: dict[str, Any], symbols: list[str]) -> list[str]:
    window_symbols = [
        str(window["symbol"])
        for window in config.get("event_windows", [])
        if isinstance(window, dict) and window.get("symbol")
    ]
    return list(dict.fromkeys(window_symbols or symbols))


def _sample_at_or_before(frame: pd.DataFrame, timestamp: pd.Timestamp) -> dict[str, Any] | None:
    eligible = frame[frame["open_time"] <= timestamp]
    if eligible.empty:
        return None
    return eligible.iloc[-1].to_dict()


def _build_dataset(
    config: dict[str, Any],
    symbols: list[str],
    labels: pd.DataFrame,
) -> pd.DataFrame:
    timeframe = config["timeframe"]
    lead_time = pd.Timedelta(hours=float(config["lead_time_hours"]))
    negative_ratio = int(config.get("negative_sample_ratio", 5))
    rows: list[dict[str, Any]] = []
    frames = {symbol: _feature_frame(symbol, timeframe) for symbol in symbols}
    for _, event in labels.iterrows():
        symbol = str(event["symbol"])
        frame = frames.get(symbol)
        if frame is None or frame.empty:
            continue
        sample_time = event["event_start"] - lead_time
        sample = _sample_at_or_before(frame, sample_time)
        if sample:
            sample.update(
                {
                    "sample_id": event.get("event_id") or f"{symbol}_{sample_time.isoformat()}",
                    "label": 1,
                    "event_start": to_iso(event["event_start"].to_pydatetime()),
                    "sample_time": to_iso(pd.Timestamp(sample["open_time"]).to_pydatetime()),
                    "split": event.get("split", "train"),
                }
            )
            rows.append(sample)

        start_gap = pd.Timedelta(hours=float(config.get("negative_gap_hours", 48)))
        blocked_start = event["event_start"] - start_gap
        blocked_end = event["event_start"] + start_gap
        negatives = frame[
            (frame["open_time"] < blocked_start) | (frame["open_time"] > blocked_end)
        ].copy()
        if event.get("split"):
            split_windows = [
                window
                for window in config.get("event_windows", [])
                if window.get("split", "train") == event.get("split", "train")
                and window.get("symbol") == symbol
            ]
            if split_windows:
                masks = []
                for window in split_windows:
                    start = _window_timestamp(window, "start")
                    end = _window_timestamp(window, "end")
                    masks.append(
                        (negatives["open_time"] >= start) & (negatives["open_time"] <= end)
                    )
                if masks:
                    mask = masks[0]
                    for item in masks[1:]:
                        mask = mask | item
                    negatives = negatives[mask]
        if negatives.empty:
            continue
        picked = negatives.iloc[:: max(len(negatives) // max(negative_ratio, 1), 1)].head(
            negative_ratio
        )
        for index, negative in picked.iterrows():
            row = negative.to_dict()
            row.update(
                {
                    "sample_id": f"neg_{symbol}_{index}_{event.get('event_id', '')}",
                    "label": 0,
                    "event_start": to_iso(event["event_start"].to_pydatetime()),
                    "sample_time": to_iso(pd.Timestamp(negative["open_time"]).to_pydatetime()),
                    "split": event.get("split", "train"),
                }
            )
            rows.append(row)
    return pd.DataFrame(rows)


def _best_threshold(y_true: pd.Series, score: pd.Series) -> tuple[float, dict[str, float]]:
    best_threshold = 0.0
    best = {"precision": 0.0, "recall": 0.0, "f1": 0.0}
    for threshold in sorted(score.dropna().unique()):
        predicted = score >= threshold
        tp = int(((predicted == 1) & (y_true == 1)).sum())
        fp = int(((predicted == 1) & (y_true == 0)).sum())
        fn = int(((predicted == 0) & (y_true == 1)).sum())
        precision = tp / (tp + fp) if tp + fp else 0.0
        recall = tp / (tp + fn) if tp + fn else 0.0
        f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
        if f1 > best["f1"]:
            best_threshold = float(threshold)
            best = {"precision": precision, "recall": recall, "f1": f1}
    return best_threshold, best


def _metrics_at_threshold(
    y_true: pd.Series,
    score: pd.Series,
    threshold: float,
) -> dict[str, float]:
    data = pd.DataFrame({"label": y_true, "score": score}).dropna()
    if data.empty:
        return {"precision": 0.0, "recall": 0.0, "f1": 0.0}
    predicted = data["score"] >= threshold
    labels = data["label"].astype(int)
    tp = int(((predicted == 1) & (labels == 1)).sum())
    fp = int(((predicted == 1) & (labels == 0)).sum())
    fn = int(((predicted == 0) & (labels == 1)).sum())
    precision = tp / (tp + fp) if tp + fp else 0.0
    recall = tp / (tp + fn) if tp + fn else 0.0
    f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
    return {"precision": precision, "recall": recall, "f1": f1}


def _auc(y_true: pd.Series, score: pd.Series) -> float:
    data = pd.DataFrame({"label": y_true, "score": score}).dropna()
    positives = data[data["label"] == 1]["score"]
    negatives = data[data["label"] == 0]["score"]
    if positives.empty or negatives.empty:
        return 0.0
    wins = 0.0
    total = len(positives) * len(negatives)
    for value in positives:
        wins += float((value > negatives).sum()) + 0.5 * float((value == negatives).sum())
    return wins / total if total else 0.0


def _split_dataset(dataset: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    if dataset.empty or "split" not in dataset.columns:
        return pd.DataFrame(), pd.DataFrame()
    train = dataset[dataset["split"].isin(["train", "validation", "train_validation"])].copy()
    holdout = dataset[dataset["split"] == "holdout"].copy()
    if train.empty and not holdout.empty:
        train = dataset[dataset["split"] != "holdout"].copy()
    return train, holdout


def _empty_result(
    feature_set: Phase1FeatureSet,
    available: list[str],
    status: str,
) -> dict[str, Any]:
    missing = [column for column in feature_set.columns if column not in available]
    return {
        "experiment": feature_set.name,
        "model": feature_set.model,
        "status": status,
        "features": available,
        "missing_features": missing,
        "precision": 0.0,
        "recall": 0.0,
        "f1": 0.0,
        "auc": 0.0,
        "train_precision": 0.0,
        "train_recall": 0.0,
        "train_f1": 0.0,
        "train_auc": 0.0,
        "holdout_precision": 0.0,
        "holdout_recall": 0.0,
        "holdout_f1": 0.0,
        "holdout_auc": 0.0,
        "threshold": 0.0,
        "train_sample_count": 0,
        "holdout_sample_count": 0,
        "train_positive_count": 0,
        "holdout_positive_count": 0,
    }


def _threshold_scores(dataset: pd.DataFrame, available: list[str]) -> pd.Series:
    return dataset[available].apply(pd.to_numeric, errors="coerce").fillna(0.0).abs().sum(axis=1)


def _finalize_result(
    feature_set: Phase1FeatureSet,
    available: list[str],
    train: pd.DataFrame,
    holdout: pd.DataFrame,
    train_score: pd.Series,
    holdout_score: pd.Series,
    threshold: float,
) -> dict[str, Any]:
    train_metrics = _metrics_at_threshold(train["label"], train_score, threshold)
    holdout_metrics = (
        _metrics_at_threshold(holdout["label"], holdout_score, threshold)
        if not holdout.empty
        else {"precision": 0.0, "recall": 0.0, "f1": 0.0}
    )
    return {
        "experiment": feature_set.name,
        "model": feature_set.model,
        "status": "completed" if not holdout.empty else "completed_no_holdout",
        "features": available,
        "missing_features": [column for column in feature_set.columns if column not in available],
        "precision": round(train_metrics["precision"], 6),
        "recall": round(train_metrics["recall"], 6),
        "f1": round(train_metrics["f1"], 6),
        "auc": round(_auc(train["label"], train_score), 6),
        "train_precision": round(train_metrics["precision"], 6),
        "train_recall": round(train_metrics["recall"], 6),
        "train_f1": round(train_metrics["f1"], 6),
        "train_auc": round(_auc(train["label"], train_score), 6),
        "holdout_precision": round(holdout_metrics["precision"], 6),
        "holdout_recall": round(holdout_metrics["recall"], 6),
        "holdout_f1": round(holdout_metrics["f1"], 6),
        "holdout_auc": (
            round(_auc(holdout["label"], holdout_score), 6) if not holdout.empty else 0.0
        ),
        "threshold": float(threshold),
        "train_sample_count": int(len(train)),
        "holdout_sample_count": int(len(holdout)),
        "train_positive_count": int(train["label"].sum()),
        "holdout_positive_count": int(holdout["label"].sum()) if not holdout.empty else 0,
    }


def _evaluate_threshold_feature_set(
    dataset: pd.DataFrame,
    feature_set: Phase1FeatureSet,
    available: list[str],
) -> dict[str, Any]:
    train, holdout = _split_dataset(dataset)
    if train.empty or train["label"].nunique() < 2:
        return _empty_result(feature_set, available, "insufficient_train_data")
    train_score = _threshold_scores(train, available)
    threshold, _metrics = _best_threshold(train["label"], train_score)
    holdout_score = (
        _threshold_scores(holdout, available) if not holdout.empty else pd.Series(dtype=float)
    )
    return _finalize_result(
        feature_set,
        available,
        train,
        holdout,
        train_score,
        holdout_score,
        threshold,
    )


def _evaluate_lightgbm_feature_set(
    dataset: pd.DataFrame,
    feature_set: Phase1FeatureSet,
    available: list[str],
) -> dict[str, Any]:
    train, holdout = _split_dataset(dataset)
    if train.empty or train["label"].nunique() < 2 or len(train) < 4:
        return _empty_result(feature_set, available, "insufficient_train_data")
    try:
        import lightgbm as lgb  # type: ignore[import-not-found]
    except ImportError:
        return _empty_result(feature_set, available, "lightgbm_not_installed")
    train_x = train[available].apply(pd.to_numeric, errors="coerce").fillna(0.0)
    train_y = train["label"].astype(int)
    model = lgb.LGBMClassifier(
        n_estimators=50,
        learning_rate=0.05,
        max_depth=3,
        num_leaves=7,
        min_child_samples=1,
        random_state=42,
        verbose=-1,
    )
    model.fit(train_x, train_y)
    train_score = pd.Series(model.predict_proba(train_x)[:, 1], index=train.index)
    threshold, _metrics = _best_threshold(train_y, train_score)
    if holdout.empty:
        holdout_score = pd.Series(dtype=float)
    else:
        holdout_x = holdout[available].apply(pd.to_numeric, errors="coerce").fillna(0.0)
        holdout_score = pd.Series(model.predict_proba(holdout_x)[:, 1], index=holdout.index)
    return _finalize_result(
        feature_set,
        available,
        train,
        holdout,
        train_score,
        holdout_score,
        threshold,
    )


def _evaluate_feature_set(dataset: pd.DataFrame, feature_set: Phase1FeatureSet) -> dict[str, Any]:
    available = [column for column in feature_set.columns if column in dataset.columns]
    if not available or dataset.empty or dataset["label"].nunique() < 2:
        return _empty_result(feature_set, available, "insufficient_data")
    if feature_set.model == "lightgbm":
        return _evaluate_lightgbm_feature_set(dataset, feature_set, available)
    return _evaluate_threshold_feature_set(dataset, feature_set, available)


def _write_report(report_dir: Path, payload: dict[str, Any]) -> tuple[str, str]:
    markdown_path = ensure_parent(report_dir / "report.md")
    html_path = ensure_parent(report_dir / "report.html")
    lines = [
        f"# Phase1 Prediction {payload['experiment_id']}",
        "",
        f"- Status: {payload['status']}",
        f"- Label count: {payload['label_count']}",
        f"- Sample count: {payload['sample_count']}",
        f"- Candidate path: {payload['candidate_path']}",
        f"- Label template: {payload['label_template_path']}",
        "",
        "## Experiments",
        "",
        (
            "| Experiment | Model | Train F1 | Holdout F1 | Train P/R | "
            "Holdout P/R | Threshold | Status |"
        ),
        "|---|---|---:|---:|---:|---:|---:|---|",
    ]
    for result in payload["phase1_results"]:
        lines.append(
            (
                "| {experiment} | {model} | {train_f1:.3f} | {holdout_f1:.3f} | "
                "{train_precision:.3f}/{train_recall:.3f} | "
                "{holdout_precision:.3f}/{holdout_recall:.3f} | {threshold:.6f} | {status} |"
            ).format(**result)
        )
    markdown_path.write_text("\n".join(lines), encoding="utf-8")
    html_rows = "\n".join(
        "<tr>"
        f"<td>{result['experiment']}</td>"
        f"<td>{result['model']}</td>"
        f"<td>{result['train_f1']:.3f}</td>"
        f"<td>{result['holdout_f1']:.3f}</td>"
        f"<td>{result['train_precision']:.3f}/{result['train_recall']:.3f}</td>"
        f"<td>{result['holdout_precision']:.3f}/{result['holdout_recall']:.3f}</td>"
        f"<td>{result['threshold']:.6f}</td>"
        f"<td>{result['status']}</td>"
        "</tr>"
        for result in payload["phase1_results"]
    )
    html_path.write_text(
        f"""
        <html><head><meta charset="utf-8"><title>Phase1 Prediction</title></head>
        <body>
          <h1>Phase1 Prediction {payload['experiment_id']}</h1>
          <p>Status: {payload['status']}</p>
          <p>Labels: {payload['label_count']} / Samples: {payload['sample_count']}</p>
          <table border="1" cellspacing="0" cellpadding="6">
            <thead><tr>
              <th>Experiment</th><th>Model</th><th>Train F1</th><th>Holdout F1</th>
              <th>Train P/R</th><th>Holdout P/R</th><th>Threshold</th><th>Status</th>
            </tr></thead>
            <tbody>{html_rows}</tbody>
          </table>
        </body></html>
        """,
        encoding="utf-8",
    )
    return str(markdown_path), str(html_path)


def run(config: dict[str, Any], symbols: list[str], split: str) -> dict[str, Any]:
    validate_phase1_event_windows(config)
    symbols = _symbols_for_phase1(config, symbols)
    output_dir = ensure_directory(DATA_ROOT / "processed" / "phase1")
    candidate_details = generate_label_candidates(config, symbols)
    labels = _load_labels(config)
    labels.to_csv(output_dir / "labels_used.csv", index=False)
    dataset = _build_dataset(config, symbols, labels) if not labels.empty else pd.DataFrame()
    dataset_path = output_dir / "features.parquet"
    if not dataset.empty:
        dataset.to_parquet(dataset_path, index=False)
    else:
        pd.DataFrame().to_parquet(dataset_path, index=False)
    results = [
        _evaluate_feature_set(dataset, feature_set)
        for feature_set in FEATURE_SETS
        if feature_set.name in set(config.get("experiments", [item.name for item in FEATURE_SETS]))
    ]
    best = max(results, key=lambda item: item["train_f1"]) if results else {}
    experiment_id = hash_payload(
        {
            "type": "phase1_prediction",
            "created_at": to_iso(utc_now()),
            "label_count": len(labels),
            "sample_count": len(dataset),
        }
    )[:12]
    status = (
        "completed"
        if len(labels) >= int(config.get("minimum_labels_to_run", 1))
        else "needs_labels"
    )
    report_dir = ensure_directory(REPORT_ROOT / experiment_id)
    payload = {
        "experiment_id": experiment_id,
        "name": "phase1_prediction",
        "strategy": "PHASE1",
        "engine": "classification",
        "split": split,
        "status": status,
        "config_hash": hash_payload(config),
        "split_hash": hash_payload({"split": split}),
        "data_snapshot_hash": hash_payload(candidate_details),
        "git_commit_hash": "unknown",
        "created_at": to_iso(utc_now()),
        "failure_reason": "not_enough_manual_labels" if status == "needs_labels" else None,
        "metrics": {
            "net_return": 0.0,
            "sharpe": 0.0,
            "sortino": 0.0,
            "max_drawdown": 0.0,
            "profit_factor": 0.0,
            "win_rate": 0.0,
            "avg_win": 0.0,
            "avg_loss": 0.0,
            "trade_count": 0,
            "median_holding_minutes": 0.0,
            "fee_cost": 0.0,
            "slippage_cost": 0.0,
            "funding_cost": 0.0,
            "top5_removed_net_return": 0.0,
            "f1": float(best.get("train_f1", 0.0)),
            "precision": float(best.get("train_precision", 0.0)),
            "recall": float(best.get("train_recall", 0.0)),
            "auc": float(best.get("train_auc", 0.0)),
            "train_f1": float(best.get("train_f1", 0.0)),
            "train_precision": float(best.get("train_precision", 0.0)),
            "train_recall": float(best.get("train_recall", 0.0)),
            "train_auc": float(best.get("train_auc", 0.0)),
            "holdout_f1": float(best.get("holdout_f1", 0.0)),
            "holdout_precision": float(best.get("holdout_precision", 0.0)),
            "holdout_recall": float(best.get("holdout_recall", 0.0)),
            "holdout_auc": float(best.get("holdout_auc", 0.0)),
            "threshold": float(best.get("threshold", 0.0)),
            "label_count": int(len(labels)),
            "sample_count": int(len(dataset)),
            "train_sample_count": int(best.get("train_sample_count", 0)),
            "holdout_sample_count": int(best.get("holdout_sample_count", 0)),
        },
        "phase1_results": results,
        "label_count": int(len(labels)),
        "sample_count": int(len(dataset)),
        "dataset_path": str(dataset_path),
        **candidate_details,
    }
    markdown_path, html_path = _write_report(report_dir, payload)
    payload["markdown_report_path"] = markdown_path
    payload["report_path"] = html_path
    payload["trade_log_path"] = ""
    ExperimentStore().upsert("experiments", "experiment_id", payload)
    return {
        "experiment": payload,
        "markdown_report": markdown_path,
        "html_report": html_path,
        "dataset": str(dataset_path),
        **candidate_details,
    }
