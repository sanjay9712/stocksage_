"""Commodities screener endpoints."""
from __future__ import annotations

import asyncio

from fastapi import APIRouter, Depends

from app.api.auth import require_token
from app.api.cache import cached
from app.market_hours import is_nse_open, screen_cache_ttl
from app.providers.factory import get_provider
from app.strategies import commodity_breakout as strat
from app.universe import get_commodities
from app.explain import commodity_explainer as explainer

router = APIRouter()


async def _screen_one(provider, c):
    try:
        daily = await provider.get_daily_history(c["symbol"], 60)
        intraday = await provider.get_intraday(c["symbol"], "5m", 1)
    except Exception:
        return None
    ctx = strat.CommodityContext(name=c["name"], symbol=c["symbol"], daily=daily, intraday=intraday)
    res = strat.evaluate(ctx)
    return {
        "name": res.name, "symbol": res.symbol, "side": res.side,
        "entry": res.entry, "stop_loss": res.stop_loss,
        "target1": res.target1, "target2": res.target2,
        "confidence": res.confidence, "atr": res.atr_value,
        "pdh": res.pdh, "pdl": res.pdl,
        "explanation": explainer.build(res),
    }


async def _run_commodities_screen():
    provider = get_provider()
    sem = asyncio.Semaphore(7)
    async def _bounded(c):
        async with sem:
            return await _screen_one(provider, c)
    results = await asyncio.gather(*[_bounded(c) for c in get_commodities()])
    return [r for r in results if r is not None]


@router.get("/commodities/today")
async def commodities_today(_t: str = Depends(require_token)):
    return await cached("commodities", screen_cache_ttl(is_nse_open()), _run_commodities_screen)
