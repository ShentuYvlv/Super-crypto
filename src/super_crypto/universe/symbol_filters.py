from __future__ import annotations

from collections.abc import Iterable


def apply_symbol_filters(
    symbols: Iterable[str],
    *,
    exclude_keywords: list[str] | None = None,
    manual_watchlist: list[str] | None = None,
) -> list[str]:
    exclude_keywords = exclude_keywords or []
    manual_watchlist = manual_watchlist or []
    results = []
    for symbol in sorted(set(symbols) | set(manual_watchlist)):
        if any(keyword in symbol for keyword in exclude_keywords):
            continue
        results.append(symbol)
    return results

