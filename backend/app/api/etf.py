"""ETF invest screener endpoints."""
from __future__ import annotations

import asyncio

from fastapi import APIRouter, Depends

from app.api.auth import require_token
from app.api.cache import cached
from app.market_hours import is_nse_open, screen_cache_ttl
from app.providers.factory import get_provider
from app.strategies import etf_screener as scr
from app.universe import get_etf_universe

router = APIRouter()


async def _run_etf_screen():
    provider = get_provider()
    tasks = [scr.screen_etf(provider, e["symbol"], e["name"], e["category"], e["horizon"]) for e in get_etf_universe()]
    results = await asyncio.gather(*tasks, return_exceptions=True)
    out = [scr.to_dict(s) for s in results if not isinstance(s, Exception)]
    out.sort(key=lambda d: d.get("sharpe", 0), reverse=True)
    return out


@router.get("/etf/screener")
async def etf_screener(_t: str = Depends(require_token)):
    return await cached("etf_screener", screen_cache_ttl(is_nse_open()), _run_etf_screen)


@router.get("/etf/{symbol}/details")
async def etf_details(symbol: str, _t: str = Depends(require_token)):
    """Single ETF detail with all enhanced fields."""
    from app.universe import get_etf_universe
    from app.providers.factory import get_provider
    from app.providers.fundamentals import get_stock_fundamentals

    symbol = symbol.strip().upper().replace(".NS", "")

    async def _fetch():
        etfs = get_etf_universe()
        etf = next((e for e in etfs if e["symbol"].upper() == symbol), None)
        if not etf:
            etf = {"symbol": symbol, "name": symbol, "category": "unknown", "horizon": "long"}
        provider = get_provider()
        result = await scr.screen_etf(provider, etf["symbol"], etf["name"], etf["category"], etf.get("horizon", "long"))
        # Also fetch yfinance fundamentals if available.
        try:
            fundamentals = await get_stock_fundamentals(symbol)
        except Exception:
            fundamentals = {}
        data = scr.to_dict(result)
        data["yf_fundamentals"] = {
            "trailing_pe": fundamentals.get("trailing_pe"),
            "market_cap": fundamentals.get("market_cap"),
            "52w_high": fundamentals.get("52w_high"),
            "52w_low": fundamentals.get("52w_low"),
            "avg_volume": fundamentals.get("avg_volume"),
        }
        return data

    # ETF screen + fundamentals fetch ~1-2s — cache 10 min.
    return await cached(f"etf_detail:{symbol}", 600, _fetch)
