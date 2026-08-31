"""Portfolio rebalancing endpoints.

Suggests buy/sell trades to rebalance the user's portfolio against
a target allocation. Supports equal-weight, custom, and risk-parity methods.
"""
from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field

from app.api.auth import require_token
from app.api.cache import cached
from app.db import User
from app.holdings.factory import get_broker
from app.providers.factory import get_provider
from app.strategies.rebalancing import compute_rebalancing

router = APIRouter()
log = logging.getLogger("rebalancing_api")


class RebalancingRequest(BaseModel):
    method: str = Field("equal_weight", pattern="^(equal_weight|custom|risk_parity)$")
    target_allocation: dict[str, float] | None = None
    threshold_pct: float = Field(5.0, ge=1.0, le=20.0)


@router.post("/rebalancing")
async def rebalancing(req: RebalancingRequest, t: User = Depends(require_token)) -> dict:
    """Compute rebalancing suggestions for the user's portfolio.

    Analyzes current holdings vs target allocation and generates
    buy/sell trade suggestions to bring the portfolio back to target.
    """
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
            return {"error": "No holdings found. Add positions to your broker account to get rebalancing suggestions."}

        provider = get_provider()
        return await compute_rebalancing(
            provider,
            holdings,
            target_allocation=req.target_allocation,
            method=req.method,
            threshold_pct=req.threshold_pct,
        )

    cache_key = f"rebalancing:{req.method}:{req.threshold_pct}:{str(sorted((req.target_allocation or {}).items()))}"
    return await cached(cache_key, 300, _fetch)
