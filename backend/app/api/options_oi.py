"""Options OI-based support/resistance endpoints.

Fetches the option chain for a symbol and identifies:
- Max Pain: the strike where total option writer pain is maximized (price magnet).
- High OI Call strikes = resistance levels.
- High OI Put strikes = support levels.
- Put-Call Ratio (PCR) for sentiment.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, Query

from app.api.auth import require_token
from app.api.cache import cached
from app.providers.factory import get_provider

router = APIRouter()


def _compute_max_pain(calls: list[dict], puts: list[dict], strikes: list[float]) -> float:
    """Max Pain: the strike price at which option writers (sellers) experience
    the minimum total payout. This tends to act as a magnet for the underlying
    price near expiry.
    """
    if not strikes:
        return 0.0

    min_pain = float("inf")
    max_pain_strike = strikes[0]

    for strike in strikes:
        # Total payout for call writers if price settles at `strike`
        call_pain = sum(
            max(0, strike - c["strike"]) * c.get("openInterest", 0)
            for c in calls
            if c["strike"] < strike
        )
        # Total payout for put writers if price settles at `strike`
        put_pain = sum(
            max(0, p["strike"] - strike) * p.get("openInterest", 0)
            for p in puts
            if p["strike"] > strike
        )
        total_pain = call_pain + put_pain
        if total_pain < min_pain:
            min_pain = total_pain
            max_pain_strike = strike

    return round(max_pain_strike, 2)


@router.get("/options-oi/{symbol}")
async def options_oi(
    symbol: str,
    expiry: str | None = Query(None, description="YYYY-MM-DD expiry date, defaults to nearest"),
    _t=Depends(require_token),
):
    """Get options OI analysis for support/resistance levels.

    Returns call/put OI by strike, max pain, PCR, top resistance (high call OI)
    and support (high put OI) levels.
    """
    symbol = symbol.strip().upper().replace(".NS", "").replace("NSE:", "")

    async def _fetch():
        provider = get_provider()

        # Use yfinance directly for option chains (most providers don't support it)
        from app.providers.yfinance_provider import YFinanceProvider
        yf_provider = YFinanceProvider()
        chain = await yf_provider.get_option_chain(symbol, expiry)

        if not chain.get("calls") and not chain.get("puts"):
            return {
                "symbol": symbol,
                "error": "No option chain data available",
                "calls": [],
                "puts": [],
                "expiries": chain.get("expiries", []),
                "expiry": chain.get("expiry"),
                "max_pain": 0.0,
                "pcr": 0.0,
                "total_call_oi": 0,
                "total_put_oi": 0,
                "resistance_levels": [],
                "support_levels": [],
                "current_price": 0.0,
            }

        calls = chain["calls"]
        puts = chain["puts"]

        # Get current price
        try:
            quote = await yf_provider.get_quote(symbol)
            current_price = quote.price
        except Exception:
            current_price = 0.0

        # Aggregate OI by strike
        call_oi = {}
        put_oi = {}
        for c in calls:
            s = round(c.get("strike", 0), 2)
            call_oi[s] = call_oi.get(s, 0) + c.get("openInterest", 0)
        for p in puts:
            s = round(p.get("strike", 0), 2)
            put_oi[s] = put_oi.get(s, 0) + p.get("openInterest", 0)

        all_strikes = sorted(set(list(call_oi.keys()) + list(put_oi.keys())))

        # Max Pain
        max_pain = _compute_max_pain(calls, puts, all_strikes)

        # PCR
        total_call_oi = sum(call_oi.values())
        total_put_oi = sum(put_oi.values())
        pcr = round(total_put_oi / total_call_oi, 3) if total_call_oi > 0 else 0.0

        # Top resistance levels: highest call OI strikes above current price
        call_above = [(s, oi) for s, oi in call_oi.items() if s > current_price and oi > 0]
        call_above.sort(key=lambda x: x[1], reverse=True)
        resistance_levels = [
            {"strike": s, "call_oi": int(oi), "type": "resistance"}
            for s, oi in call_above[:5]
        ]

        # Top support levels: highest put OI strikes below current price
        put_below = [(s, oi) for s, oi in put_oi.items() if s < current_price and oi > 0]
        put_below.sort(key=lambda x: x[1], reverse=True)
        support_levels = [
            {"strike": s, "put_oi": int(oi), "type": "support"}
            for s, oi in put_below[:5]
        ]

        # Build OI profile for charting
        oi_profile = []
        for s in all_strikes:
            oi_profile.append({
                "strike": s,
                "call_oi": int(call_oi.get(s, 0)),
                "put_oi": int(put_oi.get(s, 0)),
                "call_vol": 0,
                "put_vol": 0,
            })

        # Sort by strike
        oi_profile.sort(key=lambda d: d["strike"])

        # Sentiment
        if pcr > 1.5:
            sentiment = "bullish"
        elif pcr > 1.0:
            sentiment = "slightly_bullish"
        elif pcr < 0.5:
            sentiment = "bearish"
        elif pcr < 1.0:
            sentiment = "slightly_bearish"
        else:
            sentiment = "neutral"

        return {
            "symbol": symbol,
            "calls": calls[:20],  # limit payload
            "puts": puts[:20],
            "expiries": chain.get("expiries", [])[:10],
            "expiry": chain.get("expiry"),
            "max_pain": max_pain,
            "pcr": pcr,
            "sentiment": sentiment,
            "total_call_oi": int(total_call_oi),
            "total_put_oi": int(total_put_oi),
            "resistance_levels": resistance_levels,
            "support_levels": support_levels,
            "oi_profile": oi_profile,
            "current_price": round(current_price, 2),
        }

    return await cached(f"options_oi:{symbol}:{expiry or 'auto'}", 300, _fetch)
