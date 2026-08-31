"""Multi-strategy portfolio simulation endpoints.

Runs multiple strategies on the same symbol with equal capital
allocation and combines the results. Shows diversification benefit
of running strategies together vs any single strategy.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from app.api.auth import require_token
from app.api.cache import cached
from app.providers.factory import get_provider
from app.strategies.portfolio_sim import simulate_portfolio

router = APIRouter()


class StrategyConfig(BaseModel):
    strategy: str = Field(..., pattern="^(ema_crossover|rsi_reversion|bollinger|breakout)$")
    label: str | None = None
    params: dict = Field(default_factory=dict)


class PortfolioSimRequest(BaseModel):
    symbol: str
    strategies: list[StrategyConfig] = Field(..., min_length=2, max_length=6)
    days: int = Field(730, ge=60, le=1095)
    initial_capital: float = Field(100000, ge=1000, le=10000000)


@router.post("/portfolio-sim")
async def portfolio_sim(req: PortfolioSimRequest, _t=Depends(require_token)):
    """Simulate running multiple strategies on one symbol with equal
    capital allocation. Returns per-strategy metrics, combined equity
    curve, and portfolio-level statistics including diversification benefit.
    """
    symbol = req.symbol.strip().upper().replace(".NS", "").replace("NSE:", "")

    async def _fetch():
        provider = get_provider()
        df = await provider.get_daily_history(symbol, req.days)

        if df.empty or len(df) < 30:
            return {
                "symbol": symbol,
                "error": "Insufficient historical data for portfolio simulation",
                "strategies": [],
                "portfolio": {},
            }

        strategies = [
            {
                "strategy": s.strategy,
                "label": s.label or s.strategy,
                "params": s.params,
            }
            for s in req.strategies
        ]

        return simulate_portfolio(
            df=df,
            symbol=symbol,
            strategies=strategies,
            initial_capital=req.initial_capital,
        )

    cache_key = (
        f"portfolio_sim:{symbol}:{req.days}:{req.initial_capital}:"
        f"{str([(s.strategy, sorted(s.params.items())) for s in req.strategies])}"
    )
    return await cached(cache_key, 600, _fetch)
