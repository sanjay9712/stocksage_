"""Pre-market gap scanner endpoints.

Scans NSE and US stock universes for significant opening gaps, with
volume ratio, ATR-based expected move, and strategy suggestions.
"""
from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Query

from app.api.auth import require_token
from app.api.cache import cached, invalidate
from app.market_hours import is_nse_open, is_us_open, nse_status, screen_cache_ttl, us_status
from app.providers.factory import get_provider
from app.strategies.gap_scanner import NSE_GAP_UNIVERSE, US_GAP_UNIVERSE, scan_all_gaps

router = APIRouter()


@router.get("/gap-scanner")
async def gap_scanner(
    market: str = Query("nse", pattern="^(nse|us)$"),
    min_gap_pct: float = Query(0.5, ge=0, le=20),
    _t=Depends(require_token),
):
    """Scan for stocks with significant gaps from previous close.

    Returns a sorted list of gap candidates with gap %, direction, volume
    ratio, ATR, expected move, and strategy suggestion.
    """
    provider = get_provider()

    if market == "us":
        async def _fetch():
            return await scan_all_gaps(provider, US_GAP_UNIVERSE, "us", min_gap_pct)

        data = await cached(
            "gap_scanner_us",
            screen_cache_ttl(is_us_open()),
            _fetch,
        )
        market_status = us_status()
    else:
        async def _fetch():
            return await scan_all_gaps(provider, NSE_GAP_UNIVERSE, "in", min_gap_pct)

        data = await cached(
            "gap_scanner_nse",
            screen_cache_ttl(is_nse_open()),
            _fetch,
        )
        market_status = nse_status()

    # Split into gap-ups and gap-downs.
    gap_ups = [d for d in data if d["gap_dir"] == "up"]
    gap_downs = [d for d in data if d["gap_dir"] == "down"]

    return {
        "market": market,
        "gaps": data,
        "gap_ups": gap_ups,
        "gap_downs": gap_downs,
        "total": len(data),
        "refreshed_at": datetime.now(timezone.utc).isoformat(),
        "market_status": market_status,
    }


@router.post("/gap-scanner/refresh")
async def refresh_gap_scanner(
    _t=Depends(require_token),
):
    """Force-refresh the gap scanner cache for both markets."""
    invalidate("gap_scanner_nse")
    invalidate("gap_scanner_us")
    return {"invalidated": True}
