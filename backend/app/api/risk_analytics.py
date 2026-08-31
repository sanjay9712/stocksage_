"""Portfolio risk analytics endpoints.

Computes VaR, CVaR, beta, Sharpe, max drawdown, concentration risk,
and per-position risk contributions for the user's holdings.
"""
from __future__ import annotations

import logging

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from app.api.auth import require_token
from app.api.cache import cached
from app.db import User
from app.holdings.factory import get_broker
from app.providers.factory import get_provider
from app.strategies.risk_analytics import compute_risk_metrics

router = APIRouter()
log = logging.getLogger("risk_analytics_api")


class RiskAnalysisRequest(BaseModel):
    benchmark: str = "^NSEI"
    days: int = Field(252, ge=60, le=504)


@router.get("/risk-analytics")
async def risk_analytics(
    benchmark: str = "^NSEI",
    days: int = 252,
    t: User = Depends(require_token),
) -> dict:
    """Compute portfolio risk analytics for the user's holdings.

    Returns VaR, CVaR, beta, Sharpe, max drawdown, concentration risk,
    and per-position risk breakdown.
    """
    days = max(60, min(504, days))

    async def _fetch():
        # Get holdings from broker
        try:
            broker = get_broker()
            holdings_list = await broker.get_holdings()
            holdings = [
                {
                    "symbol": h.symbol,
                    "quantity": h.quantity,
                    "avg_price": h.avg_price,
                }
                for h in holdings_list
            ]
        except RuntimeError as e:
            return {"error": f"Broker not configured: {e}"}

        if not holdings:
            return {"error": "No holdings found. Add positions to your broker account to see risk analytics."}

        provider = get_provider()
        return await compute_risk_metrics(provider, holdings, benchmark, days)

    cache_key = f"risk_analytics:{benchmark}:{days}"
    return await cached(cache_key, 300, _fetch)
