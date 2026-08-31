"""Dividend data — upcoming ex-dividend dates, dividend yields, history.

Uses yfinance's ticker.dividends (historical) and ticker.info (dividend_yield,
dividend_rate, ex_dividend_date) to build a dividend calendar for screening
income-focused stocks/ETFs.
"""
from __future__ import annotations

import asyncio
import logging
from datetime import date, datetime, timedelta
from typing import Any

from app.universe import (
    NIFTY_50,
    US_STOCKS,
    US_ETF_UNIVERSE,
    ETF_UNIVERSE,
    is_us_symbol,
)

log = logging.getLogger("dividend_data")


def _suffix(symbol: str) -> str:
    if any(ch in symbol for ch in (".", "=", "^")):
        return symbol
    if is_us_symbol(symbol):
        return symbol
    return f"{symbol}.NS"


def _fetch_dividend_sync(symbol: str) -> dict[str, Any]:
    """Synchronous yfinance call — runs in thread pool via to_thread."""
    import yfinance as yf
    import pandas as pd

    ticker = yf.Ticker(_suffix(symbol))
    info = ticker.info

    result: dict[str, Any] = {
        "symbol": symbol,
        "dividend_yield": None,
        "dividend_rate": None,
        "payout_ratio": None,
        "ex_dividend_date": None,
        "next_dividend_date": None,
        "dividend_history": [],
    }

    # Dividend yield and rate from info.
    # Priority: dividendRate/price > trailingAnnualDividendRate/price >
    # dividendYield (already a %) > trailingAnnualDividendYield*100
    dr = info.get("dividendRate")
    if dr is not None:
        result["dividend_rate"] = round(float(dr), 2)
    else:
        tdr = info.get("trailingAnnualDividendRate")
        if tdr is not None:
            result["dividend_rate"] = round(float(tdr), 2)

    price = info.get("currentPrice") or info.get("regularMarketPrice")
    rate = dr or info.get("trailingAnnualDividendRate")
    if rate is not None and price and float(price) > 0:
        result["dividend_yield"] = round((float(rate) / float(price)) * 100, 2)
    else:
        dy = info.get("dividendYield")
        if dy is not None:
            result["dividend_yield"] = round(float(dy), 2)
        else:
            tady = info.get("trailingAnnualDividendYield")
            if tady is not None:
                result["dividend_yield"] = round(float(tady) * 100, 2)
    pr = info.get("payoutRatio")
    if pr is not None:
        result["payout_ratio"] = round(float(pr) * 100, 1)

    # Ex-dividend date
    ex_date = info.get("exDividendDate")
    if ex_date:
        try:
            dt = datetime.fromtimestamp(ex_date)
            result["ex_dividend_date"] = dt.strftime("%Y-%m-%d")
        except Exception:
            pass

    # Dividend history (last 5 years)
    try:
        divs = ticker.dividends
        if divs is not None and not divs.empty:
            # Last 3 years of dividends
            recent = divs.tail(12)  # ~quarterly, so 12 = 3 years
            history = []
            for idx, val in recent.items():
                if hasattr(idx, "strftime"):
                    history.append({
                        "date": idx.strftime("%Y-%m-%d"),
                        "amount": round(float(val), 4),
                    })
            result["dividend_history"] = history[::-1]  # most recent first
    except Exception:
        pass

    return result


async def fetch_dividend_data(symbol: str) -> dict[str, Any]:
    """Fetch dividend data for a single symbol."""
    return await asyncio.to_thread(_fetch_dividend_sync, symbol)


async def fetch_dividend_calendar(symbols: list[str]) -> list[dict[str, Any]]:
    """Fetch dividend data for multiple symbols in parallel."""
    sem = asyncio.Semaphore(8)

    async def _fetch(sym: str) -> dict[str, Any] | None:
        async with sem:
            try:
                return await fetch_dividend_data(sym)
            except Exception as e:
                log.warning("Failed to fetch dividend data for %s: %s", sym, e)
                return None

    results = await asyncio.gather(*[_fetch(s) for s in symbols])
    # Filter out symbols with no dividend data, sort by yield descending
    out = [r for r in results if r and (r.get("dividend_yield") or r.get("dividend_rate"))]
    out.sort(key=lambda d: d.get("dividend_yield") or 0, reverse=True)
    return out
