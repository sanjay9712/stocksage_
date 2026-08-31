"""Fetches and caches the full NSE listed stocks list with company names.

Uses the public NSE archive CSV (EQUITY_L.csv) which contains ~2000 stocks
with their company names. Cached for 24 hours — the list changes rarely.
"""
from __future__ import annotations

import csv
import io
import time
from typing import Any

import httpx

_CSV_URL = "https://archives.nseindia.com/content/equities/EQUITY_L.csv"

# Cache: (timestamp, list of {symbol, name})
_cache: tuple[float, list[dict[str, str]]] | None = None
_TTL = 86400  # 24 hours


async def get_nse_stocks() -> list[dict[str, str]]:
    """Return list of {symbol, name} for all NSE-listed EQ stocks. Cached 24h."""
    global _cache
    now = time.time()
    if _cache and (now - _cache[0]) < _TTL:
        return _cache[1]

    try:
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.get(_CSV_URL, headers={"User-Agent": "Mozilla/5.0"})
            resp.raise_for_status()
        reader = csv.DictReader(io.StringIO(resp.text))
        stocks = []
        for row in reader:
            sym = (row.get("SYMBOL") or "").strip()
            name = (row.get("NAME OF COMPANY") or "").strip()
            series = (row.get(" SERIES") or row.get("SERIES") or "").strip()
            if sym and series == "EQ":
                stocks.append({"symbol": sym, "name": name})
        if stocks:
            _cache = (now, stocks)
            return stocks
    except Exception:
        pass

    # Fallback to cached data even if stale, or empty list.
    return _cache[1] if _cache else []


def search_stocks(query: str, stocks: list[dict[str, str]], limit: int = 12) -> list[dict[str, str]]:
    """Case-insensitive search by symbol OR company name. Returns top matches."""
    q = query.strip().upper()
    if not q:
        return []
    # Priority: symbol starts with query > symbol contains query > name contains query
    symbol_starts = []
    symbol_contains = []
    name_contains = []
    for s in stocks:
        sym = s["symbol"]
        name = s["name"].upper()
        if sym.startswith(q):
            symbol_starts.append(s)
        elif q in sym:
            symbol_contains.append(s)
        elif q in name:
            name_contains.append(s)
    result = symbol_starts + symbol_contains + name_contains
    return result[:limit]
