"""Market hours helpers — determine if NSE or US markets are currently open.

Used by stock screeners to decide cache TTL: when market is open, cache is
very short (60s) so data is live; when closed, cache is long (1h) since
data doesn't change.
"""
from __future__ import annotations

from datetime import date, datetime, timezone
from zoneinfo import ZoneInfo

_IST = ZoneInfo("Asia/Kolkata")


def today_ist() -> date:
    """Today's calendar date in IST.

    NSE trading days are defined in IST, so pick storage/lookups must key on the
    IST date — not the server's local timezone (which may be UTC/ET and would
    otherwise shift the day boundary and surface picks on the wrong date,
    including on weekends).
    """
    return datetime.now(_IST).date()


def is_nse_open(now: datetime | None = None) -> bool:
    """NSE is open 09:15–15:30 IST, Monday–Friday."""
    ist = ZoneInfo("Asia/Kolkata")
    now = now or datetime.now(ist)
    now = now.astimezone(ist)
    if now.weekday() >= 5:  # Sat=5, Sun=6
        return False
    market_open = now.replace(hour=9, minute=15, second=0, microsecond=0)
    market_close = now.replace(hour=15, minute=30, second=0, microsecond=0)
    return market_open <= now <= market_close


def is_us_open(now: datetime | None = None) -> bool:
    """US markets are open 09:30–16:00 ET, Monday–Friday."""
    et = ZoneInfo("America/New_York")
    now = now or datetime.now(et)
    now = now.astimezone(et)
    if now.weekday() >= 5:
        return False
    market_open = now.replace(hour=9, minute=30, second=0, microsecond=0)
    market_close = now.replace(hour=16, minute=0, second=0, microsecond=0)
    return market_open <= now <= market_close


def nse_status() -> dict:
    """Return NSE market status dict for API responses."""
    ist = ZoneInfo("Asia/Kolkata")
    now = datetime.now(ist)
    open_ = is_nse_open(now)
    if open_:
        status = "OPEN · live data"
    elif now.weekday() >= 5:
        status = "Closed (weekend)"
    else:
        status = "Closed · last session data"
    return {
        "market_open": open_,
        "market_status": status,
        "exchange": "NSE",
        "timezone": "Asia/Kolkata",
    }


def us_status() -> dict:
    """Return US market status dict for API responses."""
    et = ZoneInfo("America/New_York")
    now = datetime.now(et)
    open_ = is_us_open(now)
    if open_:
        status = "OPEN · live data"
    elif now.weekday() >= 5:
        status = "Closed (weekend)"
    else:
        status = "Closed · last session data"
    return {
        "market_open": open_,
        "market_status": status,
        "exchange": "NYSE/NASDAQ",
        "timezone": "America/New_York",
    }


# Cache TTLs: short when market is open (live data), long when closed.
# yfinance data is already ~15 min delayed, so 5 min cache during market hours is fine.
LIVE_TTL = 3      # 3 seconds — near-live when market is open
CLOSED_TTL = 3600   # 1 hour — data doesn't change after hours


def screen_cache_ttl(market_open: bool) -> int:
    return LIVE_TTL if market_open else CLOSED_TTL
