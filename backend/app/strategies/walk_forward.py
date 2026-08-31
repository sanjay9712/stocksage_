"""Walk-forward optimization.

Splits historical data into rolling windows: optimize strategy parameters
on the in-sample window, then test on the out-of-sample window. This
detects overfitting — if a strategy performs well in-sample but poorly
out-of-sample, it's likely curve-fit.

Walk-forward efficiency (WFE) = out-of-sample return / in-sample return.
A WFE > 50% suggests a robust strategy; < 25% suggests overfitting.
"""
from __future__ import annotations

import logging
from typing import Any

import pandas as pd

from app import indicators as ind
from app.strategies.backtest import run_backtest

log = logging.getLogger("walk_forward")

TRADING_DAYS = 252


def _param_grid(strategy: str) -> list[dict]:
    """Generate parameter combinations to test for each strategy."""
    if strategy == "ema_crossover":
        grid = []
        for fast in [5, 9, 12, 20]:
            for slow in [21, 26, 50]:
                if fast < slow:
                    grid.append({"fast_period": fast, "slow_period": slow})
        return grid
    elif strategy == "rsi_reversion":
        grid = []
        for period in [7, 14]:
            for os in [25, 30, 35]:
                for ob in [65, 70, 75]:
                    if os < ob:
                        grid.append({"rsi_period": period, "oversold": os, "overbought": ob})
        return grid
    elif strategy == "bollinger":
        grid = []
        for period in [15, 20, 30]:
            for std in [1.5, 2.0, 2.5]:
                grid.append({"bb_period": period, "bb_std": std})
        return grid
    elif strategy == "breakout":
        grid = []
        for lookback in [10, 15, 20, 30, 55]:
            grid.append({"lookback": lookback})
        return grid
    return [{}]


def _run_optimization(
    df: pd.DataFrame, strategy: str, symbol: str, params: dict, capital: float
) -> dict:
    """Run a single backtest and return summary metrics."""
    result = run_backtest(
        df=df, strategy=strategy, symbol=symbol,
        initial_capital=capital, params=params,
    )
    return {
        "params": params,
        "total_return_pct": result.total_return_pct,
        "sharpe_ratio": result.sharpe_ratio,
        "max_drawdown_pct": result.max_drawdown_pct,
        "win_rate": result.win_rate,
        "num_trades": result.num_trades,
        "final_equity": result.final_equity,
    }


def run_walk_forward(
    df: pd.DataFrame,
    strategy: str,
    symbol: str,
    in_sample_pct: float = 0.7,
    num_windows: int = 5,
    initial_capital: float = 100000,
) -> dict[str, Any]:
    """Run walk-forward optimization.

    Splits data into `num_windows` rolling windows. Each window has an
    in-sample portion (for optimization) and an out-of-sample portion
    (for validation). Returns the best params per window, OOS performance,
    and overall walk-forward efficiency.
    """
    df = df.dropna(subset=["Close"]).sort_index()
    n = len(df)

    if n < 60:
        return {
            "symbol": symbol,
            "strategy": strategy,
            "error": "Insufficient data for walk-forward analysis",
            "windows": [],
            "summary": {},
        }

    param_grid = _param_grid(strategy)
    window_size = n // num_windows
    in_sample_size = int(window_size * in_sample_pct)

    windows: list[dict] = []
    all_oos_returns: list[float] = []
    all_is_returns: list[float] = []

    for w in range(num_windows):
        start = w * window_size
        end = min(start + window_size, n)
        if end - start < 30:
            break

        is_start = start
        is_end = start + in_sample_size
        oos_start = is_end
        oos_end = end

        if oos_end - oos_start < 10:
            break

        is_df = df.iloc[is_start:is_end]
        oos_df = df.iloc[oos_start:oos_end]

        if len(is_df) < 20 or len(oos_df) < 5:
            break

        # Optimize on in-sample
        best_params = param_grid[0]
        best_is_result = None
        best_is_return = float("-inf")

        for params in param_grid:
            try:
                result = _run_optimization(is_df, strategy, symbol, params, initial_capital)
                if result["total_return_pct"] > best_is_return:
                    best_is_return = result["total_return_pct"]
                    best_params = params
                    best_is_result = result
            except Exception:
                continue

        # Test best params on out-of-sample
        oos_result = _run_optimization(oos_df, strategy, symbol, best_params, initial_capital)

        is_return = best_is_result["total_return_pct"] if best_is_result else 0.0
        oos_return = oos_result["total_return_pct"]

        all_is_returns.append(is_return)
        all_oos_returns.append(oos_return)

        windows.append({
            "window": w + 1,
            "in_sample_start": str(is_df.index[0].date()) if hasattr(is_df.index[0], "date") else str(is_df.index[0]),
            "in_sample_end": str(is_df.index[-1].date()) if hasattr(is_df.index[-1], "date") else str(is_df.index[-1]),
            "out_of_sample_start": str(oos_df.index[0].date()) if hasattr(oos_df.index[0], "date") else str(oos_df.index[0]),
            "out_of_sample_end": str(oos_df.index[-1].date()) if hasattr(oos_df.index[-1], "date") else str(oos_df.index[-1]),
            "best_params": best_params,
            "in_sample_return": round(is_return, 2),
            "in_sample_sharpe": round(best_is_result["sharpe_ratio"], 2) if best_is_result else 0.0,
            "in_sample_trades": best_is_result["num_trades"] if best_is_result else 0,
            "out_of_sample_return": round(oos_return, 2),
            "out_of_sample_sharpe": round(oos_result["sharpe_ratio"], 2),
            "out_of_sample_trades": oos_result["num_trades"],
            "out_of_sample_max_dd": round(oos_result["max_drawdown_pct"], 2),
        })

    # Summary
    avg_is = sum(all_is_returns) / len(all_is_returns) if all_is_returns else 0.0
    avg_oos = sum(all_oos_returns) / len(all_oos_returns) if all_oos_returns else 0.0
    wfe = (avg_oos / avg_is * 100) if avg_is != 0 else 0.0

    # Consistency: how many OOS windows were profitable
    profitable_oos = sum(1 for r in all_oos_returns if r > 0)
    consistency = (profitable_oos / len(all_oos_returns) * 100) if all_oos_returns else 0.0

    # Robustness verdict
    if wfe > 50 and consistency > 60:
        verdict = "robust"
    elif wfe > 25 and consistency > 40:
        verdict = "moderate"
    elif wfe > 0:
        verdict = "fragile"
    else:
        verdict = "overfit"

    return {
        "symbol": symbol,
        "strategy": strategy,
        "num_windows": len(windows),
        "in_sample_pct": in_sample_pct,
        "windows": windows,
        "summary": {
            "avg_in_sample_return": round(avg_is, 2),
            "avg_out_of_sample_return": round(avg_oos, 2),
            "walk_forward_efficiency": round(wfe, 1),
            "profitable_windows": profitable_oos,
            "total_windows": len(all_oos_returns),
            "consistency_pct": round(consistency, 1),
            "verdict": verdict,
        },
    }
