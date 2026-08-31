"""Sector rotation heatmap endpoints.

Returns multi-timeframe performance metrics for sector ETFs across both
NSE and US markets, with rotation detection (accelerating/strengthening/
weakening/decelerating/bearish).
"""
from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends

from app.api.auth import require_token
from app.api.cache import cached, invalidate
from app.market_hours import is_nse_open, is_us_open, nse_status, screen_cache_ttl, us_status
from app.providers.factory import get_provider
from app.strategies.sector_rotation import NSE_SECTORS, US_SECTORS, screen_all_sectors

router = APIRouter()


@router.get("/sector-rotation")
async def sector_rotation(_t=Depends(require_token)):
    """Get sector rotation heatmap data for both NSE and US markets.

    Returns multi-timeframe returns (1d/1w/1m/3m), RSI, trend, Sharpe,
    rotation verdict, and momentum score for each sector ETF.
    """
    provider = get_provider()

    async def _fetch_nse():
        return await screen_all_sectors(provider, NSE_SECTORS)

    async def _fetch_us():
        return await screen_all_sectors(provider, US_SECTORS)

    # Separate cache keys per market — different TTLs based on market hours.
    nse_data = await cached(
        "sector_rotation_nse",
        screen_cache_ttl(is_nse_open()),
        _fetch_nse,
    )
    us_data = await cached(
        "sector_rotation_us",
        screen_cache_ttl(is_us_open()),
        _fetch_us,
    )

    return {
        "nse": nse_data,
        "us": us_data,
        "refreshed_at": datetime.now(timezone.utc).isoformat(),
        "nse_market": nse_status(),
        "us_market": us_status(),
    }


@router.post("/sector-rotation/refresh")
async def refresh_sector_rotation(_t=Depends(require_token)):
    """Force-refresh the sector rotation cache for both markets."""
    invalidate("sector_rotation_nse")
    invalidate("sector_rotation_us")
    return {"invalidated": True}
