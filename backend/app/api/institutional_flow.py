"""Institutional flow endpoints — FII/DII for NSE, institutional holders for US.

NSE:
  GET /api/fii-dii/cash-flow  — today's FII/DII net buy/sell by category

US:
  GET /api/institutional/{symbol} — institutional ownership + top holders
"""
from __future__ import annotations

from fastapi import APIRouter, Depends

from app.api.auth import require_token
from app.api.cache import cached
from app.market_hours import is_nse_open, is_us_open, screen_cache_ttl
from app.providers.institutional_flow import fetch_fii_dii_cashflow, fetch_us_institutional

router = APIRouter()


@router.get("/fii-dii/cash-flow")
async def fii_dii_cash_flow(_t=Depends(require_token)):
    """Today's FII/DII cash flow from NSE.

    Returns net buy/sell values (in crores) by category:
    FII, DII, FPI, etc.
    """
    async def _fetch():
        return await fetch_fii_dii_cashflow()

    return await cached("fii_dii_cashflow", screen_cache_ttl(is_nse_open()), _fetch)


@router.get("/institutional/{symbol}")
async def institutional_holdings(symbol: str, _t=Depends(require_token)):
    """US institutional ownership data for a stock.

    Returns institutional %, insider %, and top 10 institutional holders
    (Vanguard, BlackRock, etc.) with shares, value, pct outstanding.
    """
    sym = symbol.upper()

    async def _fetch():
        return await fetch_us_institutional(sym)

    return await cached(f"institutional_{sym}", screen_cache_ttl(is_us_open()), _fetch)
