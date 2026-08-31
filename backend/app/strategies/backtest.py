"""Backtesting engine for simple trading strategies.

Supports multiple strategy types:
- EMA Crossover (fast/slow EMA)
- RSI Mean Reversion (oversold buy / overbought sell)
- Bollinger Bands (buy at lower band, sell at upper band)
- Buy and Hold (benchmark)

The engine simulates trades with full position (all-in/all-out), tracks
an equity curve, and computes performance metrics including total return,
CAGR, max drawdown, Sharpe ratio, win rate, and trade-by-trade log.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

import numpy as np
import pandas as pd

from app import indicators as ind

log = logging.getLogger("backtest")

TRADING_DAYS = 252


@dataclass
class Trade:
    entry_date: str
    entry_price: float
    exit_date: str
    exit_price: float
    shares: float
    pnl: float
    pnl_pct: float
    bars_held: int


@dataclass
class BacktestResult:
    strategy: str
    symbol: str
    params: dict
    initial_capital: float
    final_equity: float
    total_return_pct: float
    cagr_pct: float
    max_drawdown_pct: float
    sharpe_ratio: float
    volatility_pct: float
    win_rate: float
    num_trades: int
    avg_trade_pct: float
    avg_bars_held: float
    trades: list[dict]
    equity_curve: list[dict]
    buy_hold_return_pct: float
    outperformance_pct: float


def _generate_signals(
    df: pd.DataFrame, strategy: str, params: dict
) -> pd.Series:
    """Generate buy (1) / sell (-1) / hold (0) signals for the given strategy."""
    close = df["Close"]
    signals = pd.Series(0, index=close.index)

    if strategy == "ema_crossover":
        fast = params.get("fast_period", 9)
        slow = params.get("slow_period", 21)
        ema_fast = ind.ema(close, fast)
        ema_slow = ind.ema(close, slow)
        # Buy when fast crosses above slow, sell when crosses below
        cross_up = (ema_fast > ema_slow) & (ema_fast.shift(1) <= ema_slow.shift(1))
        cross_down = (ema_fast < ema_slow) & (ema_fast.shift(1) >= ema_slow.shift(1))
        signals[cross_up] = 1
        signals[cross_down] = -1

    elif strategy == "rsi_reversion":
        period = params.get("rsi_period", 14)
        oversold = params.get("oversold", 30)
        overbought = params.get("overbought", 70)
        rsi = ind.rsi(close, period)
        # Buy when RSI crosses below oversold, sell when crosses above overbought
        signals[(rsi < oversold) & (rsi.shift(1) >= oversold)] = 1
        signals[(rsi > overbought) & (rsi.shift(1) <= overbought)] = -1

    elif strategy == "bollinger":
        period = params.get("bb_period", 20)
        num_std = params.get("bb_std", 2.0)
        bb = ind.bollinger_bands(close, period, num_std)
        # Buy when close crosses below lower band, sell when crosses above upper band
        lower = bb["lower"]
        upper = bb["upper"]
        signals[(close < lower) & (close.shift(1) >= lower.shift(1))] = 1
        signals[(close > upper) & (close.shift(1) <= upper.shift(1))] = -1

    elif strategy == "breakout":
        lookback = params.get("lookback", 20)
        rolling_high = close.rolling(lookback).max().shift(1)
        rolling_low = close.rolling(lookback).min().shift(1)
        signals[close > rolling_high] = 1
        signals[close < rolling_low] = -1

    return signals


def run_backtest(
    df: pd.DataFrame,
    strategy: str,
    symbol: str,
    initial_capital: float = 100000,
    params: dict | None = None,
    rf_annual: float = 0.06,
) -> BacktestResult:
    """Run a backtest on the given daily data.

    Simulates a simple long-only strategy: buy on signal=1 (all-in),
    sell on signal=-1 (all-out). Tracks equity curve and trade log.
    """
    params = params or {}
    df = df.dropna(subset=["Close"]).sort_index().copy()

    if len(df) < 30:
        return BacktestResult(
            strategy=strategy, symbol=symbol, params=params,
            initial_capital=initial_capital, final_equity=initial_capital,
            total_return_pct=0, cagr_pct=0, max_drawdown_pct=0,
            sharpe_ratio=0, volatility_pct=0, win_rate=0, num_trades=0,
            avg_trade_pct=0, avg_bars_held=0, trades=[],
            equity_curve=[], buy_hold_return_pct=0, outperformance_pct=0,
        )

    close = df["Close"]
    signals = _generate_signals(df, strategy, params)

    # Simulate
    position = 0.0  # shares held
    cash = initial_capital
    in_market = False
    entry_price = 0.0
    entry_date = None
    entry_bar = 0
    trades: list[Trade] = []
    equity_values: list[float] = []

    for i, (date, row) in enumerate(df.iterrows()):
        price = float(row["Close"])
        signal = int(signals.iloc[i])

        if signal == 1 and not in_market:
            # Buy all-in
            position = cash / price
            entry_price = price
            entry_date = str(date.date()) if hasattr(date, "date") else str(date)
            entry_bar = i
            cash = 0.0
            in_market = True

        elif signal == -1 and in_market:
            # Sell all
            cash = position * price
            pnl = cash - (position * entry_price)
            pnl_pct = (price - entry_price) / entry_price * 100
            trades.append(Trade(
                entry_date=entry_date or "",
                entry_price=round(entry_price, 2),
                exit_date=str(date.date()) if hasattr(date, "date") else str(date),
                exit_price=round(price, 2),
                shares=round(position, 4),
                pnl=round(pnl, 2),
                pnl_pct=round(pnl_pct, 2),
                bars_held=i - entry_bar,
            ))
            position = 0.0
            in_market = False

        # Track equity
        equity = cash + position * price
        equity_values.append(equity)

    # Close any open position at the end
    if in_market and len(df) > 0:
        final_price = float(close.iloc[-1])
        cash = position * final_price
        pnl = cash - (position * entry_price)
        pnl_pct = (final_price - entry_price) / entry_price * 100
        last_date = df.index[-1]
        trades.append(Trade(
            entry_date=entry_date or "",
            entry_price=round(entry_price, 2),
            exit_date=str(last_date.date()) if hasattr(last_date, "date") else str(last_date),
            exit_price=round(final_price, 2),
            shares=round(position, 4),
            pnl=round(pnl, 2),
            pnl_pct=round(pnl_pct, 2),
            bars_held=len(df) - 1 - entry_bar,
        ))
        equity_values[-1] = cash
        in_market = False

    final_equity = equity_values[-1] if equity_values else initial_capital
    total_return = (final_equity - initial_capital) / initial_capital * 100

    # Equity curve as list of {date, equity}
    equity_curve = [
        {"date": str(df.index[i].date()) if hasattr(df.index[i], "date") else str(df.index[i]),
         "equity": round(eq, 2)}
        for i, eq in enumerate(equity_values)
    ]

    # Performance metrics
    equity_series = pd.Series(equity_values)
    returns = equity_series.pct_change().dropna()
    volatility = float(returns.std() * np.sqrt(TRADING_DAYS) * 100) if len(returns) > 1 else 0.0

    # CAGR
    n_years = len(df) / TRADING_DAYS
    if n_years > 0 and final_equity > 0:
        cagr = ((final_equity / initial_capital) ** (1 / n_years) - 1) * 100
    else:
        cagr = 0.0

    # Max drawdown
    running_max = equity_series.cummax()
    drawdown = (equity_series - running_max) / running_max
    max_dd = float(drawdown.min() * 100) if len(drawdown) > 0 else 0.0

    # Sharpe ratio
    if len(returns) > 1 and returns.std() > 0:
        sharpe = float(returns.mean() / returns.std() * np.sqrt(TRADING_DAYS))
    else:
        sharpe = 0.0

    # Win rate
    winning = [t for t in trades if t.pnl > 0]
    win_rate = len(winning) / len(trades) * 100 if trades else 0.0
    avg_trade = np.mean([t.pnl_pct for t in trades]) if trades else 0.0
    avg_bars = np.mean([t.bars_held for t in trades]) if trades else 0.0

    # Buy and hold benchmark
    bh_return = (close.iloc[-1] / close.iloc[0] - 1) * 100 if len(close) > 1 else 0.0
    outperformance = total_return - bh_return

    return BacktestResult(
        strategy=strategy,
        symbol=symbol,
        params=params,
        initial_capital=initial_capital,
        final_equity=round(final_equity, 2),
        total_return_pct=round(total_return, 2),
        cagr_pct=round(cagr, 2),
        max_drawdown_pct=round(max_dd, 2),
        sharpe_ratio=round(sharpe, 2),
        volatility_pct=round(volatility, 2),
        win_rate=round(win_rate, 1),
        num_trades=len(trades),
        avg_trade_pct=round(float(avg_trade), 2),
        avg_bars_held=round(float(avg_bars), 1),
        trades=[
            {
                "entry_date": t.entry_date, "entry_price": t.entry_price,
                "exit_date": t.exit_date, "exit_price": t.exit_price,
                "shares": t.shares, "pnl": t.pnl, "pnl_pct": t.pnl_pct,
                "bars_held": t.bars_held,
            }
            for t in trades
        ],
        equity_curve=equity_curve,
        buy_hold_return_pct=round(bh_return, 2),
        outperformance_pct=round(outperformance, 2),
    )
