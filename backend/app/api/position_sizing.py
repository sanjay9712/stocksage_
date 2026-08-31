"""Position sizing endpoints.

Computes optimal position sizes using the Kelly Criterion and
alternative methods (fixed-fractional, inverse-volatility).
Uses historical backtest data to estimate win rate and payoff ratio.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from app.api.auth import require_token
from app.api.cache import cached
from app.providers.factory import get_provider
from app.strategies.position_sizing import compute_position_size

router = APIRouter()


class PositionSizingRequest(BaseModel):
    symbol: str
    strategy: str = Field("ema_crossover", pattern="^(ema_crossover|rsi_reversion|bollinger|breakout)$")
    capital: float = Field(100000, ge=1000, le=10000000)
    entry_price: float = Field(..., gt=0)
    stop_price: float = Field(..., gt=0)
    risk_pct: float = Field(2.0, ge=0.5, le=10.0)
    days: int = Field(730, ge=60, le=1095)
    params: dict = Field(default_factory=dict)


@router.post("/position-sizing")
async def position_sizing(req: PositionSizingRequest, _t=Depends(require_token)):
    """Compute optimal position size using Kelly Criterion and alternatives.

    Runs a historical backtest to estimate strategy edge (win rate, payoff
    ratio), then calculates position sizes using full/half/quarter Kelly,
    fixed-fractional risk, and inverse-volatility methods.
    """
    symbol = req.symbol.strip().upper().replace(".NS", "").replace("NSE:", "")

    async def _fetch():
        provider = get_provider()
        df = await provider.get_daily_history(symbol, req.days)

        if df.empty or len(df) < 30:
            return {
                "symbol": symbol,
                "error": "Insufficient historical data for position sizing",
            }

        result = compute_position_size(
            df=df,
            symbol=symbol,
            strategy=req.strategy,
            capital=req.capital,
            entry_price=req.entry_price,
            stop_price=req.stop_price,
            risk_pct=req.risk_pct,
            strategy_params=req.params,
        )

        return {
            "symbol": result.symbol,
            "strategy": result.strategy,
            "capital": result.capital,
            "entry_price": result.entry_price,
            "stop_price": result.stop_price,
            "risk_per_share": round(result.risk_per_share, 4),
            "win_rate": round(result.win_rate, 4),
            "avg_win_pct": round(result.avg_win_pct, 2),
            "avg_loss_pct": round(result.avg_loss_pct, 2),
            "payoff_ratio": round(result.payoff_ratio, 2),
            "kelly_fraction": round(result.kelly_fraction, 4),
            "sizing_methods": {
                "full_kelly_pct": result.full_kelly_pct,
                "half_kelly_pct": result.half_kelly_pct,
                "quarter_kelly_pct": result.quarter_kelly_pct,
                "fixed_fractional_pct": result.fixed_fractional_pct,
                "inverse_volatility_pct": result.inverse_volatility_pct,
            },
            "recommended": {
                "method": result.recommended_method,
                "pct_of_capital": result.recommended_pct,
                "shares": result.recommended_shares,
                "dollar_amount": result.recommended_dollar,
            },
            "risk": {
                "risk_dollar": result.risk_dollar,
                "risk_pct_of_capital": result.risk_pct_of_capital,
            },
            "estimates": {
                "annual_growth_pct": result.est_annual_growth_pct,
                "max_drawdown_pct": result.est_max_drawdown_pct,
            },
            "historical": {
                "trades": result.historical_trades,
                "sharpe": result.historical_sharpe,
                "return_pct": result.historical_return_pct,
                "volatility_pct": result.volatility_pct,
            },
        }

    cache_key = (
        f"position_sizing:{symbol}:{req.strategy}:{req.capital}:"
        f"{req.entry_price}:{req.stop_price}:{req.risk_pct}:{req.days}:"
        f"{str(sorted(req.params.items()))}"
    )
    return await cached(cache_key, 600, _fetch)
