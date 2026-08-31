"""Momentum rotation strategy endpoints (Jegadeesh-Titman 12-1).

Returns ranked momentum screen for NSE and US stocks/ETFs, classifying
each into Strong Buy / Accumulate / Hold / Reduce / Avoid based on 12-month
momentum (excluding the most recent month).
"""
from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends

from app.api.auth import require_token
from app.api.cache import cached, invalidate
from app.market_hours import is_nse_open, is_us_open, nse_status, screen_cache_ttl, us_status
from app.providers.factory import get_provider
from app.strategies.momentum_rotation import (
    NSE_MOMENTUM_UNIVERSE,
    US_MOMENTUM_UNIVERSE,
    screen_all_momentum,
)

router = APIRouter()


@router.get("/momentum-rotation")
async def momentum_rotation(_t=Depends(require_token)):
    """Get 12-1 month momentum rotation screen for both NSE and US markets.

    Returns ranked stocks/ETFs with momentum score, multi-timeframe returns,
    RSI, Sharpe, volatility, trend, signal, and tier classification.
    """
    provider = get_provider()

    async def _fetch_nse():
        return await screen_all_momentum(provider, NSE_MOMENTUM_UNIVERSE)

    async def _fetch_us():
        return await screen_all_momentum(provider, US_MOMENTUM_UNIVERSE)

    nse_data = await cached(
        "momentum_rotation_nse",
        screen_cache_ttl(is_nse_open()),
        _fetch_nse,
    )
    us_data = await cached(
        "momentum_rotation_us",
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


@router.post("/momentum-rotation/refresh")
async def refresh_momentum_rotation(_t=Depends(require_token)):
    """Force-refresh the momentum rotation cache for both markets."""
    invalidate("momentum_rotation_nse")
    invalidate("momentum_rotation_us")
    return {"invalidated": True}
