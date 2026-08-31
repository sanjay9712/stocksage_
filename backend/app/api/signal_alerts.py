"""Signal alerts endpoints.

Scans the stock universe for technical signal alerts (RSI, EMA crossover,
volume spike, breakout, etc.) and returns matching signals with entry/stop/target.
"""
from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel

from app.api.auth import require_token
from app.api.cache import cached
from app.market_hours import is_nse_open, is_us_open, screen_cache_ttl
from app.providers.factory import get_provider
from app.strategies.signal_alerts import (
    NSE_SIGNAL_UNIVERSE,
    US_SIGNAL_UNIVERSE,
    SIGNAL_TYPES,
    scan_all_signals,
)
from app.universe import US_STOCK_NAMES

router = APIRouter()

log = logging.getLogger("signal_alerts_api")


class SignalAlertsResponse(BaseModel):
    market: str
    signals: list[dict]
    total: int
    refreshed_at: str
    market_status: dict


@router.get("/signal-alerts")
async def signal_alerts(
    market: str = Query("nse", pattern="^(nse|us)$"),
    signal_types: str | None = Query(None, description="Comma-separated signal types to filter"),
    _t=Depends(require_token),
) -> dict:
    """Scan for technical signal alerts.

    Scans the NSE or US stock universe for configured signal types and
    returns all matching signals with entry/stop/target/confidence.
    """
    import asyncio
    from datetime import datetime

    mkt = "in" if market == "nse" else "us"
    is_open = is_nse_open() if market == "nse" else is_us_open()

    # Parse signal types filter
    types_filter = None
    if signal_types:
        types_filter = [t.strip() for t in signal_types.split(",") if t.strip() in SIGNAL_TYPES]

    async def _scan():
        provider = get_provider()
        if market == "nse":
            symbols = [(s, s) for s in NSE_SIGNAL_UNIVERSE]
        else:
            symbols = [(s, US_STOCK_NAMES.get(s, s)) for s in US_SIGNAL_UNIVERSE]

        signals = await scan_all_signals(provider, symbols, mkt, types_filter)
        return {
            "market": market,
            "signals": signals,
            "total": len(signals),
            "refreshed_at": datetime.utcnow().isoformat() + "Z",
            "market_status": {
                "market_open": is_open,
                "market": market,
            },
        }

    cache_key = f"signal_alerts:{market}:{signal_types or 'all'}"
    ttl = screen_cache_ttl(is_open)
    return await cached(cache_key, ttl, _scan)


@router.post("/signal-alerts/refresh")
async def refresh_signal_alerts(
    market: str = Query("nse", pattern="^(nse|us)$"),
    _t=Depends(require_token),
) -> dict:
    """Invalidate signal alerts cache for a market."""
    from app.api.cache import _cache

    keys_to_remove = [k for k in _cache if k.startswith(f"signal_alerts:{market}:")]
    for k in keys_to_remove:
        _cache.pop(k, None)
    return {"invalidated": True, "market": market, "keys_cleared": len(keys_to_remove)}
