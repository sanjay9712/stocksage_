"""IPO endpoints — current, recent, upcoming IPOs with GMP and selection scores.

  GET /api/ipo/current   — current + recent IPOs (mainboard + SME), scored
  GET /api/ipo/upcoming  — upcoming IPOs (mainboard + SME), scored
  GET /api/ipo/all       — combined current + recent + upcoming, scored
  GET /api/ipo/{symbol}  — single IPO detail by symbol
"""
from __future__ import annotations

from fastapi import APIRouter, Depends

from app.api.auth import require_token
from app.api.cache import cached
from app.db import User
from app.market_hours import is_nse_open, screen_cache_ttl
from app.providers.ipo_provider import fetch_all_ipos, fetch_current_recent_ipos, fetch_upcoming_ipos
from app.strategies.ipo_analyzer import annotate_ipos

router = APIRouter()


@router.get("/ipo/current")
async def ipo_current(_t: User = Depends(require_token)):
    """Current + recent IPOs (mainboard + SME), with GMP and scores."""
    async def _fetch():
        data = await fetch_current_recent_ipos()
        annotate_ipos(data)
        return data

    return await cached("ipo:current", screen_cache_ttl(is_nse_open()), _fetch)


@router.get("/ipo/upcoming")
async def ipo_upcoming(_t: User = Depends(require_token)):
    """Upcoming IPOs (mainboard + SME), with GMP and scores."""
    async def _fetch():
        data = await fetch_upcoming_ipos()
        annotate_ipos(data)
        return data

    return await cached("ipo:upcoming", screen_cache_ttl(is_nse_open()), _fetch)


@router.get("/ipo/all")
async def ipo_all(_t: User = Depends(require_token)):
    """Combined current + recent + upcoming IPOs (mainboard + SME), scored."""
    async def _fetch():
        data = await fetch_all_ipos()
        annotate_ipos(data)
        return data

    return await cached("ipo:all", screen_cache_ttl(is_nse_open()), _fetch)


@router.get("/ipo/{symbol}")
async def ipo_detail(symbol: str, _t: User = Depends(require_token)):
    """Single IPO detail by symbol — searches across all boards/statuses."""
    async def _fetch():
        data = await fetch_all_ipos()
        annotate_ipos(data)
        sym_upper = symbol.strip().upper()
        for board_key in ("mainboard", "sme"):
            board = data.get(board_key, {})
            for section in ("current", "recent", "upcoming"):
                for ipo in board.get(section, []):
                    if ipo.get("symbol", "").upper() == sym_upper:
                        return ipo
                    if ipo.get("company_name", "").upper() == sym_upper:
                        return ipo
        return None

    return await cached(f"ipo:detail:{symbol}", 300, _fetch)
