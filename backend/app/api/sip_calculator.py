"""SIP/STP calculator — lump sum vs SIP entry timing based on volatility regime.

Helps investors decide whether to deploy lump sum or stagger via SIP based on
current market volatility. In high-volatility regimes, SIP/STP reduces timing
risk; in low-volatility regimes, lump sum captures more upside.
"""
from __future__ import annotations

import math
from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from app.api.auth import require_token
from app.api.cache import cached
from app.providers.factory import get_provider
from app import indicators as ind

router = APIRouter()


class SIPRequest(BaseModel):
    symbol: str = Field(..., description="Stock/ETF/MF symbol")
    amount: float = Field(..., gt=0, description="Total investment amount")
    months: int = Field(36, ge=1, le=120, description="SIP duration in months")


@router.post("/sip/calculate")
async def calculate_sip(req: SIPRequest, _t=Depends(require_token)):
    """Calculate SIP vs lump sum recommendation based on volatility regime.

    Fetches daily history for the symbol, computes volatility and CAGR,
    then recommends a strategy:
    - Low vol (< 15%): Lump sum preferred — captures more upside
    - Moderate vol (15-25%): 50-50 split — balance timing risk and opportunity
    - High vol (> 25%): STP over 6-12 months — reduces timing risk

    Also simulates: if you had invested lump sum vs SIP over the past
    `months` years, what would the P&L difference be?
    """
    async def _fetch():
        provider = get_provider()
        daily = await provider.get_daily_history(req.symbol, 504)  # ~2 years

        if daily.empty or len(daily) < 60:
            return {
                "symbol": req.symbol,
                "error": "Insufficient data for analysis",
            }

        close = daily["Close"]
        metrics = ind.risk_metrics(close, rf_annual=0.06)
        vol = metrics["volatility"]
        cagr_val = metrics["cagr"]
        max_dd = metrics["max_drawdown"]

        # Volatility regime classification
        if vol < 0.15:
            regime = "low"
            recommendation = "Lump sum preferred"
            rationale = f"Low volatility ({vol*100:.1f}%) suggests stable trend. Lump sum captures more upside in calm markets."
            lump_sum_pct = 100
            sip_months = 1
        elif vol < 0.25:
            regime = "moderate"
            recommendation = "50-50 split (lump sum + STP over 6 months)"
            rationale = f"Moderate volatility ({vol*100:.1f}%) — balance timing risk with opportunity. Deploy 50% now, stagger rest over 6 months."
            lump_sum_pct = 50
            sip_months = 6
        else:
            regime = "high"
            recommendation = "STP over 12 months"
            rationale = f"High volatility ({vol*100:.1f}%) with max drawdown of {max_dd*100:.1f}%. Staggering entry via STP reduces timing risk."
            lump_sum_pct = 0
            sip_months = 12

        # Backtest: lump sum vs SIP over the past N months
        trading_days_per_month = 21
        total_days = min(req.months * trading_days_per_month, len(close) - 1)

        if total_days < trading_days_per_month:
            total_days = min(len(close) - 1, 126)  # fallback to 6 months

        end_price = float(close.iloc[-1])

        # Lump sum: buy all at start price
        start_price = float(close.iloc[-total_days - 1])
        units_lump = req.amount / start_price
        lump_value = units_lump * end_price
        lump_pnl_pct = ((lump_value - req.amount) / req.amount) * 100

        # SIP: equal installments every month
        monthly_amount = req.amount / req.months
        total_units = 0.0
        for m in range(req.months):
            day_idx = -total_days + int(m * total_days / req.months)
            if abs(day_idx) > len(close):
                day_idx = -1
            price = float(close.iloc[day_idx])
            total_units += monthly_amount / price

        sip_value = total_units * end_price
        sip_pnl_pct = ((sip_value - req.amount) / req.amount) * 100

        # Better strategy
        better = "lump_sum" if lump_pnl_pct >= sip_pnl_pct else "sip"
        advantage = abs(lump_pnl_pct - sip_pnl_pct)

        return {
            "symbol": req.symbol,
            "amount": req.amount,
            "months": req.months,
            "volatility": round(vol, 4),
            "cagr": round(cagr_val, 4),
            "max_drawdown": round(max_dd, 4),
            "regime": regime,
            "recommendation": recommendation,
            "rationale": rationale,
            "lump_sum_pct": lump_sum_pct,
            "sip_months": sip_months,
            "backtest": {
                "lump_sum_pnl_pct": round(lump_pnl_pct, 2),
                "sip_pnl_pct": round(sip_pnl_pct, 2),
                "better": better,
                "advantage_pct": round(advantage, 2),
                "period_months": req.months,
            },
        }

    return await cached(f"sip:{req.symbol}:{req.amount}:{req.months}", 3600, _fetch)
