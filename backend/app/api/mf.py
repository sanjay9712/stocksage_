"""Mutual fund screener endpoints (free AMFI NAV data)."""
from __future__ import annotations

import asyncio

from fastapi import APIRouter, Depends

from app.api.auth import require_user
from app.api.cache import cached
from app.strategies import mf_screener as scr
from app.universe import get_mutual_funds

router = APIRouter()


async def _run_mf_screen():
    funds = get_mutual_funds()
    tasks = [scr.screen_mf(m["code"], m["name"], m["category"], m["horizon"]) for m in funds]
    results = await asyncio.gather(*tasks, return_exceptions=True)
    out = [scr.to_dict(s) for s in results if not isinstance(s, Exception)]
    out.sort(key=lambda d: d.get("sharpe", 0), reverse=True)
    return out


@router.get("/mf/screener")
async def mf_screener(_t = Depends(require_user)):
    return await cached("mf_screener", 600, _run_mf_screen)


@router.get("/mf/{code}/details")
async def mf_details(code: str, _t = Depends(require_user)):
    """Single MF detail with all enhanced fields."""
    from app.universe import get_mutual_funds

    code = code.strip()

    async def _fetch():
        funds = get_mutual_funds()
        fund = next((f for f in funds if f["code"] == code), None)
        if not fund:
            fund = {"code": code, "name": code, "category": "unknown", "horizon": "long"}
        result = await scr.screen_mf(fund["code"], fund["name"], fund["category"], fund.get("horizon", "long"))
        return scr.to_dict(result)

    # MF NAV history fetch takes ~60s — cache for 10 min with background refresh.
    return await cached(f"mf_detail:{code}", 600, _fetch)
