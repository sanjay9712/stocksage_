"""NSE direct data provider — fetches from nseindia.com public JSON endpoints.

What works from NSE (verified):
  - /api/marketStatus  — live market status (open/closed, NIFTY level)
  - /api/allIndices    — all index values (NIFTY 50, sectoral, etc.)
  - /api/chart-databyindex — intraday chart data (1-min bars) for indices + equities

What NSE BLOCKS (Akamai bot protection, returns 403):
  - /api/quote-equity  — individual stock live quotes
  - /api/equity-stock-icons — Nifty 50 constituent list
  - /api/historical    — historical daily candles

So this provider uses NSE for: market status, index data, intraday index bars.
For individual stock daily/intraday it FALLS BACK to yfinance (which works but
is delayed ~15 min). This is the honest compromise with free data.

For true real-time stock data, a paid feed (GDFL/Truedata) or broker API
(Fyers API) is required.
"""
from __future__ import annotations

import asyncio
import time
from datetime import date, datetime
from zoneinfo import ZoneInfo

import httpx
import pandas as pd

from app.models import Quote
from app.providers.base import DataProvider

NSE_BASE = "https://www.nseindia.com"
BROWSER_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "application/json, text/javascript, */*; q=0.01",
    "Accept-Language": "en-US,en;q=0.9",
    "Referer": "https://www.nseindia.com/",
    "X-Requested-With": "XMLHttpRequest",
}

# In-memory cookie cache; NSE requires a cookie handshake.
_cookie_cache: dict = {"client": None, "ts": 0, "ttl": 300}  # 5 min TTL


class NSEEquityProvider(DataProvider):
    """NSE for indices/market-status, yfinance fallback for stock bars."""

    name = "nse"

    def __init__(self):
        from app.providers.yfinance_provider import YFinanceProvider
        self._yf = YFinanceProvider()

    async def _get_client(self) -> httpx.AsyncClient:
        """Return an httpx client with NSE cookies; refresh on TTL expiry."""
        now = time.time()
        if _cookie_cache["client"] and now - _cookie_cache["ts"] < _cookie_cache["ttl"]:
            return _cookie_cache["client"]
        client = httpx.AsyncClient(timeout=15, follow_redirects=True, http2=False)
        # Cookie handshake.
        try:
            await client.get(NSE_BASE, headers={
                "User-Agent": BROWSER_HEADERS["User-Agent"],
                "Accept": "text/html",
            })
        except Exception:
            pass
        _cookie_cache["client"] = client
        _cookie_cache["ts"] = now
        return client

    async def _nse_get(self, path: str) -> dict | None:
        """GET from NSE API; returns None on failure (403/timeout/etc)."""
        try:
            client = await self._get_client()
            r = await client.get(f"{NSE_BASE}/{path}", headers=BROWSER_HEADERS)
            if r.status_code == 200:
                return r.json()
            return None
        except Exception:
            return None

    # ---- DataProvider interface ----

    async def get_daily_history(self, symbol: str, days: int = 60) -> pd.DataFrame:
        """Stock daily bars — NSE blocks this endpoint, so use yfinance."""
        return await self._yf.get_daily_history(symbol, days)

    async def get_intraday(self, symbol: str, interval: str = "5m", days: int = 1) -> pd.DataFrame:
        """Intraday bars — NSE blocks individual equity quotes, so use yfinance."""
        return await self._yf.get_intraday(symbol, interval, days)

    async def get_quote(self, symbol: str) -> Quote:
        """Stock quote — NSE blocks /api/quote-equity, so use yfinance."""
        return await self._yf.get_quote(symbol)

    # ---- NSE-specific methods (these actually work) ----

    async def get_market_status(self) -> dict:
        """Live NSE market status (open/closed + NIFTY level)."""
        data = await self._nse_get("api/marketStatus")
        if not data:
            return {"market_open": False, "source": "nse (unreachable)"}
        states = data.get("marketState", [])
        cm = next((s for s in states if s.get("market") == "Capital Market"), {})
        return {
            "market_open": cm.get("marketStatus", "").lower() == "open",
            "status_text": cm.get("marketStatusMessage", ""),
            "trade_date": cm.get("tradeDate"),
            "nifty_last": cm.get("last"),
            "nifty_change": cm.get("variation"),
            "nifty_pct_change": cm.get("percentChange"),
            "source": "nse",
        }

    async def get_all_indices(self) -> list[dict]:
        """All NSE index values (NIFTY 50, Bank Nifty, sectoral, etc.)."""
        data = await self._nse_get("api/allIndices")
        if not data:
            return []
        return data.get("data", [])

    async def get_index_intraday(self, index: str = "NIFTY 50") -> pd.DataFrame:
        """Intraday 1-min chart data for an NSE index. Works!"""
        idx = index.replace(" ", "%20")
        data = await self._nse_get(f"api/chart-databyindex?index={idx}")
        if not data:
            return pd.DataFrame()
        raw = data.get("grapthData", [])
        if not raw:
            return pd.DataFrame()
        # grapthData is [[timestamp_ms, price], ...]
        rows = [{"timestamp": r[0], "price": r[1]} for r in raw]
        df = pd.DataFrame(rows)
        df["datetime"] = pd.to_datetime(df["timestamp"], unit="ms")
        df = df.set_index("datetime").drop(columns=["timestamp"])
        df = df.rename(columns={"price": "Close"})
        df["Open"] = df["Close"]
        df["High"] = df["Close"]
        df["Low"] = df["Close"]
        df["Volume"] = 0
        return df
