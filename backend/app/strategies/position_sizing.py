"""Risk-adjusted position sizing using Kelly Criterion.

Computes optimal position sizes based on historical trade statistics
and risk parameters. Supports full Kelly, half-Kelly, and fractional Kelly,
plus volatility-based sizing (inverse volatility) and fixed-fractional
methods for comparison.

Kelly fraction = W - (1 - W) / R
where W = win rate, R = avg_win / avg_loss

For real-world use, half-Kelly is recommended (cuts drawdowns significantly
while keeping most of the return). The module also computes the theoretical
growth rate and drawdown estimates for each sizing method.
"""
from __future__ import annotations

import logging
import math
from dataclasses import dataclass
from typing import Any

import numpy as np
import pandas as pd

from app import indicators as ind
from app.strategies.backtest import run_backtest

log = logging.getLogger("position_sizing")

TRADING_DAYS = 252


@dataclass
class PositionSizeResult:
    symbol: str
    strategy: str
    capital: float
    entry_price: float
    stop_price: float
    risk_per_share: float
    # Kelly stats from historical backtest
    win_rate: float
    avg_win_pct: float
    avg_loss_pct: float
    payoff_ratio: float
    kelly_fraction: float
    # Position sizing methods
    full_kelly_pct: float
    half_kelly_pct: float
    quarter_kelly_pct: float
    fixed_fractional_pct: float
    inverse_volatility_pct: float
    # Recommended position
    recommended_method: str
    recommended_pct: float
    recommended_shares: int
    recommended_dollar: float
    # Risk metrics
    risk_dollar: float
    risk_pct_of_capital: float
    # Theoretical estimates (for recommended method)
    est_annual_growth_pct: float
    est_max_drawdown_pct: float
    # Historical reference
    historical_trades: int
    historical_sharpe: float
    historical_return_pct: float
    volatility_pct: float


def _kelly_fraction(win_rate: float, payoff_ratio: float) -> float:
    """Compute the Kelly fraction.

    Kelly = W - (1 - W) / R
    where W = win rate, R = avg_win / avg_loss

    Returns a fraction (0 to 1+). Negative means no edge.
    """
    if payoff_ratio <= 0:
        return 0.0
    kelly = win_rate - (1 - win_rate) / payoff_ratio
    return max(0.0, kelly)


def _theoretical_growth(kelly: float, win_rate: float, payoff_ratio: float, trades_per_year: float) -> float:
    """Estimate the annualized geometric growth rate for a given Kelly fraction.

    Uses the log-growth formula:
    G_per_trade = p * ln(1 + kelly * R) + q * ln(1 - kelly)
    Annualized by multiplying by actual trades_per_year.
    """
    if kelly <= 0 or trades_per_year <= 0:
        return 0.0
    p = win_rate
    q = 1 - p
    try:
        g_per_trade = p * math.log(1 + kelly * payoff_ratio) + q * math.log(1 - kelly)
        return g_per_trade * trades_per_year * 100  # annualized, as percentage
    except (ValueError, ZeroDivisionError):
        return 0.0


def _estimate_max_drawdown(kelly: float, volatility: float) -> float:
    """Rough max drawdown estimate for a Kelly fraction.

    Thorp-style approximation: DD ≈ kelly / (kelly + sigma^2)
    Capped at 90% for safety.
    """
    if kelly <= 0 or volatility <= 0:
        return 0.0
    sigma = volatility / 100.0
    # Diversified estimate: drawdown scales with leverage
    dd = min(0.90, kelly * 0.8 + sigma * 2)
    return dd * 100


def compute_position_size(
    df: pd.DataFrame,
    symbol: str,
    strategy: str,
    capital: float,
    entry_price: float,
    stop_price: float,
    risk_pct: float = 2.0,
    strategy_params: dict | None = None,
) -> PositionSizeResult:
    """Compute optimal position size using Kelly and alternative methods.

    Runs a historical backtest to estimate win rate and payoff ratio,
    then calculates Kelly-based sizing plus fixed-fractional and inverse-volatility
    methods.

    Args:
        df: Historical daily OHLCV data
        symbol: Ticker symbol
        strategy: Strategy name (ema_crossover, rsi_reversion, bollinger, breakout)
        capital: Total account capital
        entry_price: Planned entry price
        stop_price: Planned stop-loss price
        risk_pct: Risk per trade as % of capital (default 2%)
        strategy_params: Strategy parameters for backtest
    """
    strategy_params = strategy_params or {}
    df = df.dropna(subset=["Close"]).sort_index()

    # Run backtest to get historical trade statistics
    bt = run_backtest(
        df=df,
        strategy=strategy,
        symbol=symbol,
        initial_capital=capital,
        params=strategy_params,
    )

    # Extract trade statistics
    trades = bt.trades
    num_trades = len(trades)
    wins = [t for t in trades if t["pnl"] > 0]
    losses = [t for t in trades if t["pnl"] <= 0]

    win_rate = len(wins) / num_trades if num_trades > 0 else 0.0
    avg_win_pct = np.mean([t["pnl_pct"] for t in wins]) if wins else 0.0
    avg_loss_pct = abs(np.mean([t["pnl_pct"] for t in losses])) if losses else 0.0
    payoff_ratio = avg_win_pct / avg_loss_pct if avg_loss_pct > 0 else 0.0

    kelly = _kelly_fraction(win_rate, payoff_ratio)

    # Clamp Kelly to reasonable range
    kelly_clamped = min(kelly, 1.0)

    # Position sizing methods (% of capital)
    full_kelly_pct = kelly_clamped * 100
    half_kelly_pct = kelly_clamped * 50
    quarter_kelly_pct = kelly_clamped * 25
    fixed_fractional_pct = risk_pct  # e.g., 2%

    # Inverse volatility sizing: allocate inversely proportional to volatility
    # Lower volatility → larger position
    vol = bt.volatility_pct
    if vol > 0:
        # Target 15% annual volatility for the position
        target_vol = 15.0
        inverse_volatility_pct = min(100.0, (target_vol / vol) * 100)
    else:
        inverse_volatility_pct = 0.0

    # Risk-based shares: how many shares can we buy given entry/stop and risk budget
    risk_per_share = abs(entry_price - stop_price)
    risk_dollar = capital * (risk_pct / 100)
    if risk_per_share > 0:
        max_shares_by_risk = int(risk_dollar / risk_per_share)
    else:
        max_shares_by_risk = 0

    # Determine recommended method
    if kelly > 0.1:
        recommended_method = "half_kelly"
        recommended_pct = half_kelly_pct
    elif vol > 0:
        recommended_method = "inverse_volatility"
        recommended_pct = inverse_volatility_pct
    else:
        recommended_method = "fixed_fractional"
        recommended_pct = fixed_fractional_pct

    # Cap at 100%
    recommended_pct = min(recommended_pct, 100.0)

    # Compute recommended shares and dollar amount
    recommended_dollar = capital * (recommended_pct / 100)
    if entry_price > 0:
        recommended_shares = int(recommended_dollar / entry_price)
    else:
        recommended_shares = 0

    # Trades per year from historical backtest
    n_years = len(df) / TRADING_DAYS
    trades_per_year = num_trades / n_years if n_years > 0 else 0.0

    # Theoretical estimates
    est_growth = _theoretical_growth(
        kelly_clamped * 0.5 if recommended_method == "half_kelly" else kelly_clamped * 0.25,
        win_rate, payoff_ratio, trades_per_year
    )
    est_dd = _estimate_max_drawdown(recommended_pct / 100, vol)

    return PositionSizeResult(
        symbol=symbol,
        strategy=strategy,
        capital=capital,
        entry_price=entry_price,
        stop_price=stop_price,
        risk_per_share=risk_per_share,
        win_rate=win_rate,
        avg_win_pct=float(avg_win_pct),
        avg_loss_pct=float(avg_loss_pct),
        payoff_ratio=payoff_ratio,
        kelly_fraction=kelly,
        full_kelly_pct=round(full_kelly_pct, 2),
        half_kelly_pct=round(half_kelly_pct, 2),
        quarter_kelly_pct=round(quarter_kelly_pct, 2),
        fixed_fractional_pct=fixed_fractional_pct,
        inverse_volatility_pct=round(inverse_volatility_pct, 2),
        recommended_method=recommended_method,
        recommended_pct=round(recommended_pct, 2),
        recommended_shares=recommended_shares,
        recommended_dollar=round(recommended_dollar, 2),
        risk_dollar=round(risk_dollar, 2),
        risk_pct_of_capital=risk_pct,
        est_annual_growth_pct=round(est_growth, 2),
        est_max_drawdown_pct=round(est_dd, 2),
        historical_trades=num_trades,
        historical_sharpe=bt.sharpe_ratio,
        historical_return_pct=bt.total_return_pct,
        volatility_pct=vol,
    )
