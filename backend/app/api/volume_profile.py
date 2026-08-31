"""Volume Profile / POC (Point of Control) endpoints.

Builds a volume-by-price histogram for a symbol, identifying key
support/resistance levels (POC, VAH, VAL, HVN, LVN).
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, Query

from app import indicators as ind
from app.api.auth import require_token
from app.api.cache import cached
from app.config import settings
from app.providers.factory import get_provider

router = APIRouter()


@router.get("/volume-profile/{symbol}")
async def volume_profile(
    symbol: str,
    days: int = Query(5, ge=1, le=30),
    bins: int = Query(50, ge=10, le=200),
    _t=Depends(require_token),
):
    """Build a volume profile for the given symbol over the past N days.

    Returns rows (price bins with volume), POC, VAH, VAL, HVN/LVN levels,
    current price, and VWAP.
    """
    symbol = symbol.strip().upper().replace(".NS", "").replace("NSE:", "")
    provider = get_provider()

    async def _fetch():
        intraday = await provider.get_intraday(symbol, settings.intraday_interval, days)
        daily = await provider.get_daily_history(symbol, max(days + 1, 5))

        if intraday.empty:
            return {
                "symbol": symbol,
                "rows": [],
                "poc_price": 0.0,
                "vah": 0.0,
                "val": 0.0,
                "total_volume": 0.0,
                "hvn": [],
                "lvn": [],
                "current_price": 0.0,
                "vwap": 0.0,
                "prev_close": 0.0,
                "days": days,
            }

        profile = ind.volume_profile(intraday, bins=bins)

        current_price = float(intraday["Close"].iloc[-1])
        vwap_series = ind.vwap(intraday)
        vwap_val = float(vwap_series.iloc[-1]) if not vwap_series.empty else current_price

        prev_close = float(daily["Close"].iloc[-2]) if len(daily) >= 2 else current_price

        return {
            "symbol": symbol,
            "rows": profile["rows"],
            "poc_price": profile["poc_price"],
            "vah": profile["vah"],
            "val": profile["val"],
            "total_volume": profile["total_volume"],
            "hvn": profile["hvn"],
            "lvn": profile["lvn"],
            "current_price": round(current_price, 2),
            "vwap": round(vwap_val, 2),
            "prev_close": round(prev_close, 2),
            "days": days,
        }

    return await cached(f"volume_profile:{symbol}:{days}:{bins}", 120, _fetch)
