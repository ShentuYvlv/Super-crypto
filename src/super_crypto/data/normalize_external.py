from __future__ import annotations

import json
import math
from typing import Any

import polars as pl


def _as_list(value: Any) -> list[Any]:
    if isinstance(value, list):
        return value
    if isinstance(value, dict):
        for key in ("list", "data", "items", "rows"):
            nested = value.get(key)
            result = _as_list(nested)
            if result:
                return result
        return [value]
    return []


def _number(value: Any) -> float | None:
    if isinstance(value, int | float):
        number = float(value)
        return number if math.isfinite(number) else None
    if isinstance(value, str):
        try:
            number = float(value.strip().replace(",", ""))
        except ValueError:
            return None
        return number if math.isfinite(number) else None
    return None


def _first_number(mapping: dict[str, Any], *keys: str) -> float | None:
    for key in keys:
        value = _number(mapping.get(key))
        if value is not None:
            return value
    return None


def _first_string(mapping: dict[str, Any], *keys: str) -> str:
    for key in keys:
        value = mapping.get(key)
        if value is not None:
            text = str(value).strip()
            if text:
                return text
    return ""


def _bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, int | float):
        return value != 0
    if isinstance(value, str):
        return value.lower() in {"true", "1", "yes"}
    return False


def _raw_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"), default=str)


def _base_row(symbol: str, endpoint: str, raw: Any) -> dict[str, Any]:
    return {
        "symbol": symbol,
        "endpoint": endpoint,
        "raw_json": _raw_json(raw),
    }


def _normalize_coin_info(symbol: str, endpoint: str, raw: Any) -> list[dict[str, Any]]:
    mapping = raw if isinstance(raw, dict) else {}
    row = _base_row(symbol, endpoint, raw)
    row.update(
        {
            "market_cap": _first_number(mapping, "marketCap", "market_cap", "mcap"),
            "circulating_supply": _first_number(
                mapping,
                "circulatingSupply",
                "circulating_supply",
            ),
            "total_supply": _first_number(mapping, "totalSupply", "total_supply"),
            "max_supply": _first_number(mapping, "maxSupply", "max_supply"),
            "cross_exchange_oi": _first_number(
                mapping,
                "openInterest",
                "open_interest",
                "openInterestUsd",
            ),
            "contract_volume_24h": _first_number(
                mapping,
                "futuresVolUsd",
                "futures_vol_usd",
                "contractVolume24h",
            ),
            "spot_volume_24h": _first_number(mapping, "volUsd", "spotVolUsd", "volume24h"),
            "binance_has_perp": _bool(mapping.get("futures")),
        }
    )
    return [row]


def _market_type(mapping: dict[str, Any]) -> str:
    value = _first_string(
        mapping,
        "marketType",
        "market_type",
        "type",
        "instrumentType",
        "contractType",
        "category",
    ).lower()
    if "spot" in value:
        return "spot"
    if any(part in value for part in ("future", "swap", "perp", "contract")):
        return "contract"
    if _bool(mapping.get("spot")) or _bool(mapping.get("isSpot")):
        return "spot"
    return "contract"


def _normalize_tickers(symbol: str, endpoint: str, raw: Any) -> list[dict[str, Any]]:
    rows = []
    items = _as_list(raw)
    for item in items:
        if not isinstance(item, dict):
            continue
        exchange = _first_string(
            item,
            "exchangeName",
            "exchange",
            "exchange_name",
            "exName",
            "name",
        )
        market_type = _market_type(item)
        row = _base_row(symbol, endpoint, item)
        row.update(
            {
                "exchange": exchange,
                "pair": _first_string(
                    item,
                    "symbol",
                    "originalSymbol",
                    "instrumentId",
                    "pair",
                    "baseQuote",
                    "instId",
                ),
                "market_type": market_type,
                "price": _first_number(item, "price", "lastPrice", "close", "last"),
                "price_change_24h": _first_number(
                    item,
                    "priceChangePercent24h",
                    "h24PriceChangePercent",
                    "priceChange24h",
                    "change24h",
                    "changePercent24h",
                ),
                "volume_24h": _first_number(
                    item,
                    "volumeUsd",
                    "volUsd",
                    "volume",
                    "turnover24h",
                    "futuresVolUsd",
                    "spotVolumeUsd",
                    "spotVolUsd",
                    "spotVolume",
                ),
                "open_interest": _first_number(
                    item,
                    "openInterest",
                    "open_interest",
                    "openInterestUsd",
                    "oi",
                ),
                "oi_change_24h": _first_number(
                    item,
                    "openInterestChange24h",
                    "h24OiChangePercent",
                    "oiChange24h",
                    "open_interest_change_24h",
                ),
                "long_short_ratio": _first_number(
                    item,
                    "longShortRatio",
                    "long_short_ratio",
                    "lsRatio",
                    "longShort",
                ),
                "binance_has_perp": "binance" in exchange.lower() and market_type != "spot",
            }
        )
        rows.append(row)
    return rows


def _walk(value: Any, path: str = "") -> list[tuple[str, Any]]:
    values = [(path, value)]
    if isinstance(value, dict):
        for key, child in value.items():
            child_path = f"{path}.{key}" if path else key
            values.extend(_walk(child, child_path))
    elif isinstance(value, list):
        for index, child in enumerate(value):
            child_path = f"{path}.{index}" if path else str(index)
            values.extend(_walk(child, child_path))
    return values


def _find_period_number(value: Any, period: str, *keys: str) -> float | None:
    normalized_keys = [key.lower().replace("_", "") for key in keys]
    period_aliases = {
        "1h": ("1h", "h1"),
        "4h": ("4h", "h4"),
        "24h": ("24h", "h24"),
    }.get(period, (period,))
    for path, item in _walk(value):
        normalized_path = path.lower().replace("_", "")
        if not any(alias in normalized_path for alias in period_aliases):
            continue
        if any(key in normalized_path for key in normalized_keys):
            number = _number(item)
            if number is not None:
                return number
    return None


def _normalize_money_flow(
    symbol: str,
    endpoint: str,
    raw: Any,
    prefix: str,
) -> list[dict[str, Any]]:
    row = _base_row(symbol, endpoint, raw)
    for period in ("1h", "4h", "24h"):
        inflow = _find_period_number(raw, period, "inflow", "inflowUsd", "inFlow", "in")
        outflow = _find_period_number(raw, period, "outflow", "outflowUsd", "outFlow", "out")
        netflow = _find_period_number(raw, period, "netflow", "netFlow", "netflowUsd", "net")
        if netflow is None and (inflow is not None or outflow is not None):
            netflow = (inflow or 0.0) - (outflow or 0.0)
        row[f"{prefix}_inflow_{period}"] = inflow
        row[f"{prefix}_outflow_{period}"] = outflow
        row[f"{prefix}_netflow_{period}"] = netflow
    return [row]


def normalize_records(symbol: str, endpoint: str, raw: Any) -> pl.DataFrame:
    if endpoint == "coin_info":
        rows = _normalize_coin_info(symbol, endpoint, raw)
    elif endpoint in {"tickers", "spot_tickers"}:
        rows = _normalize_tickers(symbol, endpoint, raw)
    elif endpoint == "futures_flow":
        rows = _normalize_money_flow(symbol, endpoint, raw, "futures")
    elif endpoint == "spot_flow":
        rows = _normalize_money_flow(symbol, endpoint, raw, "spot")
    else:
        rows = [_base_row(symbol, endpoint, raw)]

    if not rows:
        return pl.DataFrame(schema={"symbol": pl.String, "endpoint": pl.String})
    return pl.DataFrame(rows)
