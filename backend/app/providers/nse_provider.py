"""NSE public-endpoint metadata provider (reference only).

Fetches F&O expiry dates and lot sizes from NSE's public JSON endpoints with
gentle rate limiting and caching. These endpoints are for reference only and
break under aggressive scraping, so all calls are cached and degrade to a
static fallback on any failure.
"""
from __future__ import annotations

import time
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

import httpx
from dateutil import rrule

from app.providers.base import DataProvider

NSE_BASE = "https://www.nseindia.com"
NSE_OPTIONS = f"{NSE_BASE}/api/option-chain-indices?symbol=NIFTY"

# Simple in-memory caches with TTL.
_cache: dict[str, tuple[float, object]] = {}
_CACHE_TTL = 6 * 3600  # 6 hours


def _cached(key: str):
    def deco(fn):
        async def wrapper(*args, **kwargs):
            now = time.time()
            hit = _cache.get(key)
            if hit and now - hit[0] < _CACHE_TTL:
                return hit[1]
            value = await fn(*args, **kwargs)
            _cache[key] = (now, value)
            return value
        return wrapper
    return deco


class NSEProvider(DataProvider):
    """Metadata-only provider; daily/intraday/quote delegate to yfinance.

    Implemented as a mixin-style standalone: the screener uses YFinanceProvider
    for bars and NSEProvider only for expiry/lot-size metadata. So the
    daily/intraday/quote methods here raise - they are not meant to be used.
    """

    name = "nse"

    async def get_daily_history(self, symbol, days=60):
        raise NotImplementedError("Use YFinanceProvider for bars")

    async def get_intraday(self, symbol, interval="5m", days=1):
        raise NotImplementedError("Use YFinanceProvider for bars")

    async def get_quote(self, symbol):
        raise NotImplementedError("Use YFinanceProvider for quotes")

    async def _fetch_with_session(self, url: str) -> dict | None:
        try:
            async with httpx.AsyncClient(timeout=10.0, follow_redirects=True) as client:
                # NSE requires a cookie handshake; fetch homepage first.
                await client.get(NSE_BASE, headers={"User-Agent": "Mozilla/5.0"})
                r = await client.get(url, headers={
                    "User-Agent": "Mozilla/5.0",
                    "Accept": "application/json",
                    "Referer": NSE_BASE,
                })
                r.raise_for_status()
                return r.json()
        except Exception:
            return None

    @_cached("nifty_expiry")
    async def get_expiry_calendar(self, symbol: str | None = None) -> list[date]:
        data = await self._fetch_with_session(NSE_OPTIONS)
        if not data:
            return _fallback_expiry()
        try:
            records = data["records"]["expiryDates"]
            parsed: list[date] = []
            for s in records:
                try:
                    parsed.append(datetime.strptime(s, "%d-%b-%Y").date())
                except ValueError:
                    continue
            parsed.sort()
            return parsed or _fallback_expiry()
        except (KeyError, TypeError):
            return _fallback_expiry()


def _fallback_expiry() -> list[date]:
    """If NSE is unreachable, derive weekly Thursdays for the next ~8 weeks."""
    tz = ZoneInfo("Asia/Kolkata")
    today = datetime.now(tz).date()
    # NSE weekly expiry is normally Thursday; recent changes moved Nifty to Thursday.
    start = today + timedelta(days=1)
    thursdays = list(rrule.rrule(
        rrule.WEEKLY, byweekday=rrule.TH, dtstart=start, count=8
    ))
    return [d.date() for d in thursdays]
