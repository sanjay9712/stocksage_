"""Opening Range Breakout scanner endpoints.

Scans NSE and US stock universes for OR-5, OR-15, OR-30 breakouts.
"""
from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Query

from app.api.auth import require_token
from app.api.cache import cached, invalidate
from app.market_hours import is_nse_open, is_us_open, nse_status, screen_cache_ttl, us_status
from app.providers.factory import get_provider
from app.strategies.opening_range_scanner import (
    NSE_OR_UNIVERSE,
    US_OR_UNIVERSE,
    scan_all_opening_range,
)

router = APIRouter()


@router.get("/or-scanner")
async def or_scanner(
    market: str = Query("nse", pattern="^(nse|us)$"),
    or_minutes: int = Query(15, ge=5, le=30),
    _t=Depends(require_token),
):
    """Scan for opening range breakouts.

    Returns stocks that broke out of their opening range (first N minutes)
    on above-average volume, with entry/stop/target levels.
    """
    provider = get_provider()

    if market == "us":
        async def _fetch():
            return await scan_all_opening_range(provider, US_OR_UNIVERSE, "us", or_minutes)

        data = await cached(
            f"or_scanner_us_{or_minutes}",
            screen_cache_ttl(is_us_open()),
            _fetch,
        )
        market_status = us_status()
    else:
        async def _fetch():
            return await scan_all_opening_range(provider, NSE_OR_UNIVERSE, "in", or_minutes)

        data = await cached(
            f"or_scanner_nse_{or_minutes}",
            screen_cache_ttl(is_nse_open()),
            _fetch,
        )
        market_status = nse_status()

    longs = [d for d in data if d["side"] == "long"]
    shorts = [d for d in data if d["side"] == "short"]

    return {
        "market": market,
        "or_minutes": or_minutes,
        "signals": data,
        "longs": longs,
        "shorts": shorts,
        "total": len(data),
        "refreshed_at": datetime.now(timezone.utc).isoformat(),
        "market_status": market_status,
    }


@router.post("/or-scanner/refresh")
async def refresh_or_scanner(_t=Depends(require_token)):
    """Force-refresh the OR scanner cache."""
    for mkt in ["nse", "us"]:
        for mins in [5, 15, 30]:
            invalidate(f"or_scanner_{mkt}_{mins}")
    return {"invalidated": True}
