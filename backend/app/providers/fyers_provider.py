"""Fyers-backed DataProvider — gives real-time NSE quotes + intraday bars.

When Fyers credentials are set (APP_FYERS_APP_ID + APP_FYERS_ACCESS_TOKEN),
this provider fetches live data directly from Fyers API v3:
  - get_quote()  → /api/v3/quotes   (real-time last price, OHLC)
  - get_intraday → /api/v3/history  (1/5/15-min candles)

Daily history (60+ days for ATR/pivot EOD math) still falls back to yfinance
because Fyers free history has limited range and yfinance daily EOD is accurate
enough for indicator computation.

If credentials are absent, every call transparently delegates to YFinanceProvider
so the app never breaks — it just uses delayed data.
"""
from __future__ import annotations

import time
from datetime import date, timedelta

import httpx
import pandas as pd

from app.config import settings
from app.models import Quote
from app.providers.base import DataProvider

FYERS_API_BASE = "https://api-t1.fyers.in/api/v3"

# Map our interval strings to Fyers resolution codes.
_RESOLUTION = {"1m": "1", "5m": "5", "15m": "15", "30m": "30", "60m": "60", "1d": "D"}


def _fyers_symbol(symbol: str) -> str:
    """Convert a bare NSE symbol to Fyers format: NSE:RELIANCE-EQ.

    Symbols that already contain ':' or '=' are passed through.
    """
    if ":" in symbol or "=" in symbol:
        return symbol
    return f"NSE:{symbol}-EQ"


class FyersProvider(DataProvider):
    name = "fyers"

    def __init__(self):
        self.app_id = settings.fyers_app_id
        self.token = settings.fyers_access_token
        self._configured = bool(self.app_id and self.token)
        if not self._configured:
            # Graceful fallback — use yfinance for everything.
            from app.providers.yfinance_provider import YFinanceProvider
            self._yf = YFinanceProvider()

    # -- internal helpers --------------------------------------------------

    def _headers(self):
        return {
            "Authorization": f"{self.app_id}:{self.token}",
            "Accept": "application/json",
        }

    async def _fyers_get(self, path: str, params: dict | None = None):
        async with httpx.AsyncClient(timeout=12) as c:
            r = await c.get(f"{FYERS_API_BASE}{path}", params=params, headers=self._headers())
            r.raise_for_status()
            return r.json()

    # -- DataProvider interface --------------------------------------------

    async def get_daily_history(self, symbol: str, days: int = 60) -> pd.DataFrame:
        """Daily EOD bars — use yfinance (Fyers free history range is limited)."""
        if not self._configured:
            return await self._yf.get_daily_history(symbol, days)
        return await self._yf.get_daily_history(symbol, days)

    async def get_intraday(
        self, symbol: str, interval: str = "5m", days: int = 1
    ) -> pd.DataFrame:
        """Intraday candles via Fyers history (real-time when market is open)."""
        if not self._configured:
            return await self._yf.get_intraday(symbol, interval, days)

        resolution = _RESOLUTION.get(interval, "5")
        now = int(time.time())
        # Fyers history range is in seconds; fetch `days` worth ending now.
        frm = now - days * 86400
        try:
            data = await self._fyers_get("/history", {
                "symbol": _fyers_symbol(symbol),
                "resolution": resolution,
                "date_format": "1",
                "range_from": str(frm),
                "range_to": str(now),
                "cont_flag": "1",
            })
        except Exception:
            return await self._yf.get_intraday(symbol, interval, days)

        candles = data.get("candles", [])
        if not candles:
            return await self._yf.get_intraday(symbol, interval, days)

        # Each candle: [epoch, open, high, low, close, volume]
        df = pd.DataFrame(candles, columns=["Datetime", "Open", "High", "Low", "Close", "Volume"])
        df["Datetime"] = pd.to_datetime(df["Datetime"], unit="s", utc=True)
        return df.set_index("Datetime").sort_index()

    async def get_quote(self, symbol: str) -> Quote:
        """Real-time quote via Fyers /quotes."""
        if not self._configured:
            return await self._yf.get_quote(symbol)

        fy_sym = _fyers_symbol(symbol)
        try:
            data = await self._fyers_get("/quotes", {"symbols": fy_sym})
        except Exception:
            return await self._yf.get_quote(symbol)

        quotes = data.get("d", [])
        if not quotes:
            return await self._yf.get_quote(symbol)
        v = quotes[0].get("v", {})
        return Quote(
            symbol=symbol.upper(),
            price=float(v.get("lp", 0)),
            prev_close=float(v.get("pp")) if v.get("pp") else None,
            day_high=float(v.get("fh")) if v.get("fh") else None,
            day_low=float(v.get("fl")) if v.get("fl") else None,
            volume=int(v.get("volume", 0)) if v.get("volume") else None,
        )

    async def get_expiry_calendar(self, symbol: str | None = None) -> list[date]:
        return []
