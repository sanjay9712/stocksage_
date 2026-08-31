"""Backtesting engine endpoints.

Runs a backtest of a selected trading strategy on historical data
and returns performance metrics, trade log, and equity curve.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from app.api.auth import require_token
from app.api.cache import cached
from app.providers.factory import get_provider
from app.strategies.backtest import run_backtest

router = APIRouter()


class BacktestRequest(BaseModel):
    symbol: str
    strategy: str = Field("ema_crossover", pattern="^(ema_crossover|rsi_reversion|bollinger|breakout)$")
    days: int = Field(365, ge=60, le=1095)
    initial_capital: float = Field(100000, ge=1000, le=10000000)
    params: dict = Field(default_factory=dict)


@router.post("/backtest")
async def backtest(req: BacktestRequest, _t=Depends(require_token)):
    """Run a backtest for the given symbol and strategy.

    Returns equity curve, trade log, and performance metrics including
    total return, CAGR, max drawdown, Sharpe ratio, and win rate.
    """
    symbol = req.symbol.strip().upper().replace(".NS", "").replace("NSE:", "")

    async def _fetch():
        provider = get_provider()
        df = await provider.get_daily_history(symbol, req.days)

        if df.empty or len(df) < 30:
            return {
                "symbol": symbol,
                "strategy": req.strategy,
                "error": "Insufficient historical data for backtesting",
                "initial_capital": req.initial_capital,
                "final_equity": req.initial_capital,
                "total_return_pct": 0.0,
                "cagr_pct": 0.0,
                "max_drawdown_pct": 0.0,
                "sharpe_ratio": 0.0,
                "volatility_pct": 0.0,
                "win_rate": 0.0,
                "num_trades": 0,
                "avg_trade_pct": 0.0,
                "avg_bars_held": 0.0,
                "trades": [],
                "equity_curve": [],
                "buy_hold_return_pct": 0.0,
                "outperformance_pct": 0.0,
                "params": req.params,
            }

        result = run_backtest(
            df=df,
            strategy=req.strategy,
            symbol=symbol,
            initial_capital=req.initial_capital,
            params=req.params,
        )

        return {
            "symbol": result.symbol,
            "strategy": result.strategy,
            "params": result.params,
            "initial_capital": result.initial_capital,
            "final_equity": result.final_equity,
            "total_return_pct": result.total_return_pct,
            "cagr_pct": result.cagr_pct,
            "max_drawdown_pct": result.max_drawdown_pct,
            "sharpe_ratio": result.sharpe_ratio,
            "volatility_pct": result.volatility_pct,
            "win_rate": result.win_rate,
            "num_trades": result.num_trades,
            "avg_trade_pct": result.avg_trade_pct,
            "avg_bars_held": result.avg_bars_held,
            "trades": result.trades,
            "equity_curve": result.equity_curve,
            "buy_hold_return_pct": result.buy_hold_return_pct,
            "outperformance_pct": result.outperformance_pct,
        }

    cache_key = f"backtest:{symbol}:{req.strategy}:{req.days}:{req.initial_capital}:{str(sorted(req.params.items()))}"
    return await cached(cache_key, 600, _fetch)
