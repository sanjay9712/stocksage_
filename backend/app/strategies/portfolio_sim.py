"""Multi-strategy portfolio simulation.

Simulates running multiple trading strategies simultaneously with equal
capital allocation. Shows how combining strategies affects risk/return
— diversified strategy portfolios typically have smoother equity curves
and better Sharpe ratios than any single strategy.
"""
from __future__ import annotations

import logging
from typing import Any

import numpy as np
import pandas as pd

from app import indicators as ind
from app.strategies.backtest import run_backtest

log = logging.getLogger("portfolio_sim")

TRADING_DAYS = 252


def simulate_portfolio(
    df: pd.DataFrame,
    symbol: str,
    strategies: list[dict],
    initial_capital: float = 100000,
) -> dict[str, Any]:
    """Run multiple strategies on the same symbol and combine results.

    Each strategy gets an equal share of capital. Returns combined equity
    curve, per-strategy metrics, and portfolio-level statistics.
    """
    df = df.dropna(subset=["Close"]).sort_index()

    if len(df) < 30:
        return {
            "symbol": symbol,
            "error": "Insufficient data",
            "strategies": [],
            "portfolio": {},
        }

    allocation = initial_capital / len(strategies)
    all_equity: dict[str, list[float]] = {}
    strategy_results: list[dict] = []

    for strat in strategies:
        result = run_backtest(
            df=df,
            strategy=strat["strategy"],
            symbol=symbol,
            initial_capital=allocation,
            params=strat.get("params", {}),
        )

        equity = [e["equity"] for e in result.equity_curve]
        all_equity[strat["strategy"]] = equity

        strategy_results.append({
            "strategy": strat["strategy"],
            "label": strat.get("label", strat["strategy"]),
            "params": strat.get("params", {}),
            "initial_capital": allocation,
            "final_equity": result.final_equity,
            "total_return_pct": result.total_return_pct,
            "cagr_pct": result.cagr_pct,
            "max_drawdown_pct": result.max_drawdown_pct,
            "sharpe_ratio": result.sharpe_ratio,
            "win_rate": result.win_rate,
            "num_trades": result.num_trades,
        })

    # Combine equity curves (all same length since same df)
    n = len(df)
    portfolio_equity = []
    for i in range(n):
        total = sum(all_equity[s][i] for s in all_equity if i < len(all_equity[s]))
        portfolio_equity.append(total)

    final_equity = portfolio_equity[-1] if portfolio_equity else initial_capital
    total_return = (final_equity - initial_capital) / initial_capital * 100

    # Portfolio metrics
    eq_series = pd.Series(portfolio_equity)
    returns = eq_series.pct_change().dropna()
    volatility = float(returns.std() * np.sqrt(TRADING_DAYS) * 100) if len(returns) > 1 else 0.0

    n_years = len(df) / TRADING_DAYS
    if n_years > 0 and final_equity > 0:
        cagr = ((final_equity / initial_capital) ** (1 / n_years) - 1) * 100
    else:
        cagr = 0.0

    running_max = eq_series.cummax()
    drawdown = (eq_series - running_max) / running_max
    max_dd = float(drawdown.min() * 100) if len(drawdown) > 0 else 0.0

    if len(returns) > 1 and returns.std() > 0:
        sharpe = float(returns.mean() / returns.std() * np.sqrt(TRADING_DAYS))
    else:
        sharpe = 0.0

    # Buy & hold benchmark
    close = df["Close"]
    bh_return = (close.iloc[-1] / close.iloc[0] - 1) * 100 if len(close) > 1 else 0.0

    equity_curve = [
        {"date": str(df.index[i].date()) if hasattr(df.index[i], "date") else str(df.index[i]),
         "equity": round(eq, 2)}
        for i, eq in enumerate(portfolio_equity)
    ]

    # Diversification benefit: portfolio Sharpe vs avg strategy Sharpe
    avg_strat_sharpe = np.mean([s["sharpe_ratio"] for s in strategy_results]) if strategy_results else 0.0
    div_benefit = sharpe - avg_strat_sharpe

    return {
        "symbol": symbol,
        "initial_capital": initial_capital,
        "final_equity": round(final_equity, 2),
        "total_return_pct": round(total_return, 2),
        "cagr_pct": round(cagr, 2),
        "max_drawdown_pct": round(max_dd, 2),
        "sharpe_ratio": round(sharpe, 2),
        "volatility_pct": round(volatility, 2),
        "buy_hold_return_pct": round(bh_return, 2),
        "outperformance_pct": round(total_return - bh_return, 2),
        "diversification_benefit": round(float(div_benefit), 2),
        "num_strategies": len(strategies),
        "strategies": strategy_results,
        "equity_curve": equity_curve,
    }
