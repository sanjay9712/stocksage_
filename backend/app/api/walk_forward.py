"""Walk-forward optimization endpoints."""
from __future__ import annotations

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from app.api.auth import require_token
from app.api.cache import cached
from app.providers.factory import get_provider
from app.strategies.walk_forward import run_walk_forward

router = APIRouter()


class WalkForwardRequest(BaseModel):
    symbol: str
    strategy: str = Field("ema_crossover", pattern="^(ema_crossover|rsi_reversion|bollinger|breakout)$")
    days: int = Field(730, ge=180, le=1095)
    in_sample_pct: float = Field(0.7, ge=0.5, le=0.9)
    num_windows: int = Field(5, ge=3, le=10)
    initial_capital: float = Field(100000, ge=1000, le=10000000)


@router.post("/walk-forward")
async def walk_forward(req: WalkForwardRequest, _t=Depends(require_token)):
    """Run walk-forward optimization for a strategy.

    Splits historical data into rolling windows, optimizes parameters
    in-sample, and validates out-of-sample. Returns per-window results
    and overall robustness metrics.
    """
    symbol = req.symbol.strip().upper().replace(".NS", "").replace("NSE:", "")

    async def _fetch():
        provider = get_provider()
        df = await provider.get_daily_history(symbol, req.days)

        if df.empty or len(df) < 60:
            return {
                "symbol": symbol,
                "strategy": req.strategy,
                "error": "Insufficient historical data for walk-forward analysis",
                "windows": [],
                "summary": {},
            }

        result = run_walk_forward(
            df=df,
            strategy=req.strategy,
            symbol=symbol,
            in_sample_pct=req.in_sample_pct,
            num_windows=req.num_windows,
            initial_capital=req.initial_capital,
        )
        return result

    cache_key = f"walk_forward:{symbol}:{req.strategy}:{req.days}:{req.in_sample_pct}:{req.num_windows}"
    return await cached(cache_key, 600, _fetch)
