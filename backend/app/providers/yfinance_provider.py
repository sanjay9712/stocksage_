"""Free data provider backed by yfinance (Yahoo Finance).

Covers NSE (.NS) and BSE (.BO) symbols. Intraday bars are available but are
delayed ~15 minutes - fine for screening levels, NOT for tick scalping.

IMPORTANT: yfinance uses synchronous `requests` under the hood. We wrap all
calls in asyncio.to_thread() so they run in a thread pool and don't block
the FastAPI event loop. Without this, every yfinance call freezes ALL
concurrent API requests.

Per-symbol caching: quotes cached 30s, history/intraday cached 60s.
This eliminates redundant yfinance calls when multiple endpoints (strategy
scan, stock screen, scalp) fetch the same symbols within the same window.
"""
from __future__ import annotations

import asyncio
import time
from datetime import date

import pandas as pd
import yfinance as yf

from app.models import Quote
from app.providers.base import DataProvider
from app.universe import is_us_symbol

# Per-symbol caches: {key: (expiry_timestamp, value)}
_quote_cache: dict[str, tuple[float, Quote]] = {}
_daily_cache: dict[str, tuple[float, pd.DataFrame]] = {}
_intraday_cache: dict[str, tuple[float, pd.DataFrame]] = {}
_option_cache: dict[str, tuple[float, dict]] = {}

_QUOTE_TTL = 1     # 1 second — minimum possible cache
_DATA_TTL = 300   # 5 minutes — yfinance data is ~15 min delayed anyway
_OPTION_TTL = 300  # 5 minutes


def _suffix(symbol: str) -> str:
    """Normalize a symbol for yfinance.

    Bare equity tickers (e.g. RELIANCE) get .NS appended for NSE.
    Futures (GC=F), indices (^NSEI), and already-suffixed symbols (RELIANCE.NS)
    are passed through unchanged. US tickers (AAPL, MSFT) need no suffix.
    """
    if any(ch in symbol for ch in (".", "=", "^")):
        return symbol
    if is_us_symbol(symbol):
        return symbol  # US tickers need no suffix on yfinance
    return f"{symbol}.NS"


def _fetch_daily_sync(symbol: str, days: int) -> pd.DataFrame:
    """Synchronous yfinance call — runs in thread pool via to_thread."""
    ticker = yf.Ticker(_suffix(symbol))
    df = ticker.history(period=f"{days + 10}d", interval="1d")
    if df.empty:
        return df
    df = df.dropna(subset=["Close"]).sort_index()
    return df.tail(days)


def _fetch_intraday_sync(symbol: str, interval: str, days: int) -> pd.DataFrame:
    """Synchronous yfinance call — runs in thread pool via to_thread."""
    ticker = yf.Ticker(_suffix(symbol))
    period = "1d" if days <= 1 else f"{days}d"
    df = ticker.history(period=period, interval=interval)
    if df.empty:
        return df
    return df.sort_index()


def _fetch_quote_sync(symbol: str) -> Quote:
    """Synchronous yfinance call — runs in thread pool via to_thread."""
    ticker = yf.Ticker(_suffix(symbol))
    info = ticker.fast_info
    return Quote(
        symbol=symbol.upper(),
        price=float(info.last_price),
        prev_close=float(info.previous_close) if info.previous_close else None,
        day_high=float(info.day_high) if info.day_high else None,
        day_low=float(info.day_low) if info.day_low else None,
    )


def _fetch_option_chain_sync(symbol: str, expiry: str | None) -> dict:
    """Synchronous yfinance option chain fetch — runs in thread pool."""
    ticker = yf.Ticker(_suffix(symbol))
    expiries = ticker.options
    if not expiries:
        return {"calls": [], "puts": [], "expiries": [], "expiry": None}

    if expiry is None:
        expiry = expiries[0]  # nearest expiry
    elif expiry not in expiries:
        expiry = expiries[0]

    chain = ticker.option_chain(expiry)

    def _clean(df: pd.DataFrame) -> list[dict]:
        if df.empty:
            return []
        cols = ["strike", "lastPrice", "bid", "ask", "volume", "openInterest",
                "impliedVolatility", "inTheMoney", "change"]
        available = [c for c in cols if c in df.columns]
        return df[available].fillna(0).to_dict(orient="records")

    return {
        "calls": _clean(chain.calls),
        "puts": _clean(chain.puts),
        "expiries": list(expiries),
        "expiry": expiry,
    }


class YFinanceProvider(DataProvider):
    name = "yfinance"

    async def get_daily_history(self, symbol: str, days: int = 60) -> pd.DataFrame:
        key = f"{symbol}:{days}"
        now = time.monotonic()
        cached = _daily_cache.get(key)
        if cached and cached[0] > now:
            return cached[1].copy()
        df = await asyncio.to_thread(_fetch_daily_sync, symbol, days)
        if not df.empty:
            _daily_cache[key] = (now + _DATA_TTL, df)
        return df

    async def get_intraday(
        self, symbol: str, interval: str = "5m", days: int = 1
    ) -> pd.DataFrame:
        key = f"{symbol}:{interval}:{days}"
        now = time.monotonic()
        cached = _intraday_cache.get(key)
        if cached and cached[0] > now:
            return cached[1].copy()
        df = await asyncio.to_thread(_fetch_intraday_sync, symbol, interval, days)
        if not df.empty:
            _intraday_cache[key] = (now + _DATA_TTL, df)
        return df

    async def get_quote(self, symbol: str) -> Quote:
        key = symbol.upper()
        now = time.monotonic()
        cached = _quote_cache.get(key)
        if cached and cached[0] > now:
            return cached[1]
        quote = await asyncio.to_thread(_fetch_quote_sync, symbol)
        _quote_cache[key] = (now + _QUOTE_TTL, quote)
        return quote

    async def get_expiry_calendar(self, symbol: str | None = None) -> list[date]:
        # yfinance does not expose NSE F&O expiry reliably; defer to NSE provider.
        return []

    async def get_option_chain(self, symbol: str, expiry: str | None = None) -> dict:
        """Fetch option chain for a symbol. Returns dict with calls, puts,
        expiries, and the selected expiry date."""
        key = f"{symbol}:{expiry or 'auto'}"
        now = time.monotonic()
        cached = _option_cache.get(key)
        if cached and cached[0] > now:
            return cached[1]
        chain = await asyncio.to_thread(_fetch_option_chain_sync, symbol, expiry)
        if chain["calls"] or chain["puts"]:
            _option_cache[key] = (now + _OPTION_TTL, chain)
        return chain
