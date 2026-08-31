"""Portfolio risk analytics.

Computes comprehensive risk metrics for a portfolio:
- VaR (Value at Risk) at 95% and 99% confidence
- CVaR (Conditional VaR / Expected Shortfall)
- Beta vs benchmark (NIFTY 50)
- Portfolio volatility (annualized)
- Sharpe ratio
- Max drawdown
- Concentration risk (Herfindahl-Hirschman Index)
- Diversification ratio
- Sector exposure
"""
from __future__ import annotations

import asyncio
import logging
import math
from typing import Any

import numpy as np
import pandas as pd

from app.providers.base import DataProvider

log = logging.getLogger("risk_analytics")

TRADING_DAYS = 252
RF_ANNUAL = 0.06  # 6% risk-free rate


async def compute_risk_metrics(
    provider: DataProvider,
    holdings: list[dict],
    benchmark_symbol: str = "^NSEI",
    days: int = 252,
) -> dict[str, Any]:
    """Compute portfolio risk metrics from holdings.

    Args:
        provider: Data provider for historical data
        holdings: List of {symbol, quantity, avg_price} dicts
        benchmark_symbol: Benchmark index (^NSEI for NIFTY 50)
        days: Historical period for risk calculation
    """
    if not holdings:
        return {"error": "No holdings to analyze"}

    # Filter out zero-quantity holdings
    holdings = [h for h in holdings if h.get("quantity", 0) > 0]
    if not holdings:
        return {"error": "No active holdings"}

    # Fetch historical data for all holdings + benchmark
    sem = asyncio.Semaphore(8)

    async def _fetch(symbol: str) -> pd.DataFrame | None:
        async with sem:
            try:
                return await provider.get_daily_history(symbol, days)
            except Exception:
                return None

    symbols = [h["symbol"] for h in holdings]
    tasks = [_fetch(s) for s in symbols]
    benchmark_task = _fetch(benchmark_symbol)

    results = await asyncio.gather(*tasks, benchmark_task)
    price_data = dict(zip(symbols, results[:-1]))
    benchmark_df = results[-1]

    # Build aligned returns DataFrame
    returns_dict = {}
    for sym, df in price_data.items():
        if df is not None and not df.empty and len(df) >= 30:
            returns_dict[sym] = df["Close"].pct_change().dropna()

    if not returns_dict:
        return {"error": "Insufficient historical data for risk analysis"}

    returns_df = pd.DataFrame(returns_dict)
    returns_df = returns_df.dropna(how="all").fillna(0)

    if returns_df.empty or len(returns_df) < 20:
        return {"error": "Insufficient data points"}

    # Compute position values
    position_values = {}
    total_value = 0.0
    for h in holdings:
        sym = h["symbol"]
        df = price_data.get(sym)
        if df is not None and not df.empty:
            last_price = float(df["Close"].iloc[-1])
            value = last_price * h["quantity"]
            position_values[sym] = value
            total_value += value

    if total_value <= 0:
        return {"error": "Portfolio has zero value"}

    # Weights
    weights = {sym: val / total_value for sym, val in position_values.items()}
    weight_series = pd.Series(weights)
    weight_series = weight_series.reindex(returns_df.columns).fillna(0)

    # Portfolio returns
    portfolio_returns = (returns_df * weight_series).sum(axis=1)

    # --- Volatility ---
    daily_vol = float(portfolio_returns.std())
    annual_vol = daily_vol * math.sqrt(TRADING_DAYS)

    # --- VaR (historical method) ---
    var_95 = float(np.percentile(portfolio_returns, 5)) * total_value
    var_99 = float(np.percentile(portfolio_returns, 1)) * total_value

    # --- CVaR (Expected Shortfall) ---
    tail_losses = portfolio_returns[portfolio_returns <= np.percentile(portfolio_returns, 5)]
    cvar_95 = float(tail_losses.mean()) * total_value if len(tail_losses) > 0 else var_95

    # --- Sharpe Ratio ---
    avg_daily_return = float(portfolio_returns.mean())
    if daily_vol > 0:
        sharpe = (avg_daily_return * TRADING_DAYS - RF_ANNUAL) / annual_vol
    else:
        sharpe = 0.0

    # --- Max Drawdown ---
    cum_returns = (1 + portfolio_returns).cumprod()
    running_max = cum_returns.cummax()
    drawdown = (cum_returns - running_max) / running_max
    max_dd = float(drawdown.min())

    # --- Beta vs Benchmark ---
    beta = 0.0
    alpha = 0.0
    corr = 0.0
    if benchmark_df is not None and not benchmark_df.empty and len(benchmark_df) >= 30:
        bench_returns = benchmark_df["Close"].pct_change().dropna()
        # Align with portfolio returns
        aligned = pd.DataFrame({"portfolio": portfolio_returns, "benchmark": bench_returns}).dropna()
        if len(aligned) >= 20 and aligned["benchmark"].std() > 0:
            cov_matrix = aligned.cov()
            beta = float(cov_matrix.iloc[0, 1] / cov_matrix.iloc[1, 1])
            bench_mean = float(aligned["benchmark"].mean())
            port_mean = float(aligned["portfolio"].mean())
            alpha = float((port_mean - beta * bench_mean) * TRADING_DAYS)
            corr = float(aligned["portfolio"].corr(aligned["benchmark"]))

    # --- Concentration (Herfindahl-Hirschman Index) ---
    hhi = sum(w ** 2 for w in weights.values())
    effective_positions = 1 / hhi if hhi > 0 else len(holdings)

    # --- Diversification Ratio ---
    # Ratio of weighted avg individual vol to portfolio vol
    individual_vols = {}
    for sym in returns_df.columns:
        vol = float(returns_df[sym].std() * math.sqrt(TRADING_DAYS))
        individual_vols[sym] = vol

    weighted_avg_vol = sum(weight_series.get(sym, 0) * individual_vols.get(sym, 0) for sym in returns_df.columns)
    div_ratio = weighted_avg_vol / annual_vol if annual_vol > 0 else 1.0

    # --- Correlation matrix ---
    corr_matrix = returns_df.corr()
    avg_correlation = float(corr_matrix.where(~np.eye(len(corr_matrix), dtype=bool)).mean().mean())

    # --- Per-position risk ---
    positions_risk = []
    for h in holdings:
        sym = h["symbol"]
        w = weights.get(sym, 0)
        vol = individual_vols.get(sym, 0)
        value = position_values.get(sym, 0)
        marginal_var = w * vol * total_value if vol > 0 else 0
        positions_risk.append({
            "symbol": sym,
            "weight": round(w, 4),
            "value": round(value, 2),
            "volatility": round(vol * 100, 2),
            "marginal_var": round(abs(marginal_var), 2),
            "contribution_to_risk": round(w * vol * 100, 2) if annual_vol > 0 else 0,
        })

    positions_risk.sort(key=lambda x: x["contribution_to_risk"], reverse=True)

    return {
        "total_value": round(total_value, 2),
        "num_positions": len(holdings),
        "volatility_pct": round(annual_vol * 100, 2),
        "var_95": round(abs(var_95), 2),
        "var_99": round(abs(var_99), 2),
        "cvar_95": round(abs(cvar_95), 2),
        "sharpe_ratio": round(sharpe, 2),
        "max_drawdown_pct": round(max_dd * 100, 2),
        "beta": round(beta, 2),
        "alpha_annual": round(alpha * 100, 2),
        "correlation_to_benchmark": round(corr, 2),
        "herfindahl_index": round(hhi, 4),
        "effective_positions": round(effective_positions, 1),
        "diversification_ratio": round(div_ratio, 2),
        "avg_correlation": round(avg_correlation, 2),
        "positions": positions_risk,
    }
