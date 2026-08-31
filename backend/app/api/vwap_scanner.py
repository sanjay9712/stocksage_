"""VWAP premium/discount scanner endpoints.

Scans NSE and US stock universes for stocks trading at a significant
deviation from their intraday VWAP.
"""
from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Query

from app.api.auth import require_token
from app.api.cache import cached, invalidate
from app.market_hours import is_nse_open, is_us_open, nse_status, screen_cache_ttl, us_status
from app.providers.factory import get_provider
from app.strategies.vwap_scanner import NSE_VWAP_UNIVERSE, US_VWAP_UNIVERSE, scan_all_vwap

router = APIRouter()


@router.get("/vwap-scanner")
async def vwap_scanner(
    market: str = Query("nse", pattern="^(nse|us)$"),
    min_deviation: float = Query(0.5, ge=0, le=10),
    _t=Depends(require_token),
):
    """Scan for stocks trading at a premium or discount to VWAP."""
    provider = get_provider()

    if market == "us":
        async def _fetch():
            return await scan_all_vwap(provider, US_VWAP_UNIVERSE, "us", min_deviation)

        data = await cached("vwap_scanner_us", screen_cache_ttl(is_us_open()), _fetch)
        market_status = us_status()
    else:
        async def _fetch():
            return await scan_all_vwap(provider, NSE_VWAP_UNIVERSE, "in", min_deviation)

        data = await cached("vwap_scanner_nse", screen_cache_ttl(is_nse_open()), _fetch)
        market_status = nse_status()

    premiums = [d for d in data if d["deviation_dir"] == "premium"]
    discounts = [d for d in data if d["deviation_dir"] == "discount"]

    return {
        "market": market,
        "results": data,
        "premiums": premiums,
        "discounts": discounts,
        "total": len(data),
        "refreshed_at": datetime.now(timezone.utc).isoformat(),
        "market_status": market_status,
    }


@router.post("/vwap-scanner/refresh")
async def refresh_vwap_scanner(_t=Depends(require_token)):
    """Force-refresh the VWAP scanner cache for both markets."""
    invalidate("vwap_scanner_nse")
    invalidate("vwap_scanner_us")
    return {"invalidated": True}
