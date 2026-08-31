"""Dividend calendar endpoints — upcoming ex-dividend dates, income screening.

NSE:
  GET /api/dividends/nse  — dividend screen for NSE stocks + ETFs

US:
  GET /api/dividends/us   — dividend screen for US stocks + ETFs

  GET /api/dividends/{symbol} — single symbol dividend detail
"""
from __future__ import annotations

from fastapi import APIRouter, Depends

from app.api.auth import require_token
from app.api.cache import cached
from app.market_hours import is_nse_open, is_us_open, screen_cache_ttl
from app.providers.dividend_data import fetch_dividend_data, fetch_dividend_calendar
from app.universe import NIFTY_50, US_STOCKS, US_ETF_UNIVERSE, ETF_UNIVERSE, get_us_stocks

router = APIRouter()


@router.get("/dividends/nse")
async def nse_dividends(_t=Depends(require_token)):
    """Dividend screen for NSE — Nifty 50 stocks + ETFs, sorted by yield."""
    # Combine stock + ETF symbols
    etf_symbols = [e["symbol"] for e in ETF_UNIVERSE]
    symbols = list(NIFTY_50[:30]) + etf_symbols  # top 30 stocks + ETFs to keep it fast

    async def _fetch():
        return await fetch_dividend_calendar(symbols)

    return await cached("nse_dividends", screen_cache_ttl(is_nse_open()), _fetch)


@router.get("/dividends/us")
async def us_dividends(_t=Depends(require_token)):
    """Dividend screen for US — stocks + ETFs, sorted by yield."""
    etf_symbols = [e["symbol"] for e in US_ETF_UNIVERSE]
    symbols = list(get_us_stocks()[:30]) + etf_symbols

    async def _fetch():
        return await fetch_dividend_calendar(symbols)

    return await cached("us_dividends", screen_cache_ttl(is_us_open()), _fetch)


@router.get("/dividends/{symbol}")
async def dividend_detail(symbol: str, _t=Depends(require_token)):
    """Single symbol dividend detail — yield, rate, ex-date, history."""
    sym = symbol.upper()

    async def _fetch():
        return await fetch_dividend_data(sym)

    return await cached(f"dividend_{sym}", screen_cache_ttl(is_us_open()), _fetch)
