"""Momentum rotation strategy (Jegadeesh-Titman 12-1).

The classic Jegadeesh-Titman (1993) momentum anomaly: stocks that
outperformed over the past 12 months (excluding the most recent month)
tend to continue outperforming for the next 3-12 months. This module
screens a universe of stocks/ETFs and ranks them by their "12-1 month"
momentum, classifying each into a recommendation tier.

We skip the most recent month to avoid short-term reversal / mean-reversion
noise that would dilute the momentum signal.
"""
from __future__ import annotations

import asyncio
import logging
import math
from typing import Any

import pandas as pd

from app import indicators as ind
from app.providers.base import DataProvider
from app.universe import (
    ETF_UNIVERSE,
    US_ETF_UNIVERSE,
    NIFTY_50,
    NIFTY_NEXT_50,
    US_STOCKS,
    US_STOCK_NAMES,
    get_us_stocks,
)

log = logging.getLogger("momentum_rotation")


# ---------------------------------------------------------------------------
# Universes — we screen liquid ETFs + large-cap stocks for both markets
# ---------------------------------------------------------------------------

NSE_MOMENTUM_UNIVERSE = [
    {"symbol": s, "name": s, "market": "in", "type": "stock"}
    for s in (NIFTY_50 + NIFTY_NEXT_50)
] + [
    {"symbol": e["symbol"], "name": e["name"], "market": "in", "type": "etf"}
    for e in ETF_UNIVERSE
]

US_MOMENTUM_UNIVERSE = [
    {"symbol": s, "name": US_STOCK_NAMES.get(s, s), "market": "us", "type": "stock"}
    for s in US_STOCKS[:30]
] + [
    {"symbol": e["symbol"], "name": e["name"], "market": "us", "type": "etf"}
    for e in US_ETF_UNIVERSE
]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _pct_return(close: pd.Series, bars: int) -> float:
    """Percentage return over the last N bars."""
    if len(close) < bars + 1:
        return 0.0
    return round(((close.iloc[-1] - close.iloc[-bars - 1]) / close.iloc[-bars - 1]) * 100, 2)


def _momentum_12_1(close: pd.Series) -> float:
    """The classic JT 12-1 momentum: return from t-252 to t-21 (12 months
    minus the most recent month). This skips the last ~21 trading days
    to avoid short-term reversal noise.
    """
    if len(close) < 252:
        # Fall back to as much history as we have (minus 1 month)
        if len(close) < 42:
            return 0.0
        return round(((close.iloc[-21] - close.iloc[0]) / close.iloc[0]) * 100, 2)
    return round(((close.iloc[-21] - close.iloc[-252]) / close.iloc[-252]) * 100, 2)


def _classify_tier(rank_percentile: float, momentum: float) -> str:
    """Classify into recommendation tiers based on percentile rank.

    - Strong Buy: top 20% with positive momentum
    - Accumulate: 20-40th percentile, positive momentum
    - Hold: 40-60th percentile
    - Reduce: 60-80th percentile, negative or weak momentum
    - Avoid: bottom 20%
    """
    if rank_percentile >= 0.80 and momentum > 0:
        return "Strong Buy"
    if rank_percentile >= 0.60 and momentum > 0:
        return "Accumulate"
    if rank_percentile >= 0.40:
        return "Hold"
    if rank_percentile >= 0.20:
        return "Reduce"
    return "Avoid"


def _signal(momentum: float, rsi: float, trend: str) -> str:
    """Refine the momentum signal with RSI and trend context."""
    if momentum > 0 and trend == "bullish" and rsi < 75:
        return "bullish"
    if momentum > 0 and rsi >= 75:
        return "overbought"
    if momentum > 0 and trend == "bearish":
        return "recovering"
    if momentum < 0 and trend == "bearish":
        return "bearish"
    if momentum < 0 and trend == "bullish":
        return "weakening"
    return "neutral"


def _detect_trend(ema50: float, ema200: float, last_price: float) -> str:
    if ema50 > ema200 and last_price > ema50:
        return "bullish"
    if ema50 < ema200 and last_price < ema50:
        return "bearish"
    return "neutral"


# ---------------------------------------------------------------------------
# Single-symbol screening
# ---------------------------------------------------------------------------

async def screen_momentum(
    provider: DataProvider, symbol: str, name: str, market: str, sec_type: str
) -> dict[str, Any]:
    """Screen one symbol for momentum rotation metrics.

    Returns 12-1 month momentum, multi-timeframe returns, RSI, Sharpe,
    trend, volatility, and classification tier.
    """
    daily = await provider.get_daily_history(symbol, 260)
    if daily.empty or len(daily) < 42:
        return {
            "symbol": symbol,
            "name": name,
            "market": market,
            "type": sec_type,
            "last_price": 0.0,
            "momentum_12_1": 0.0,
            "return_1m": 0.0,
            "return_3m": 0.0,
            "return_6m": 0.0,
            "return_12m": 0.0,
            "rsi": 50.0,
            "sharpe": 0.0,
            "volatility": 0.0,
            "trend": "neutral",
            "signal": "neutral",
            "tier": "Hold",
            "rank_percentile": 0.5,
        }

    close = daily["Close"]

    mom = _momentum_12_1(close)
    r1m = _pct_return(close, 21)
    r3m = _pct_return(close, 63)
    r6m = _pct_return(close, 126)
    r12m = _pct_return(close, 252) if len(close) >= 253 else _pct_return(close, len(close) - 1)

    rsi_series = ind.rsi(close, 14)
    rsi_val = (
        round(float(rsi_series.iloc[-1]), 1)
        if not rsi_series.empty and not pd.isna(rsi_series.iloc[-1])
        else 50.0
    )

    ema50 = float(ind.ema(close, 50).iloc[-1]) if len(close) >= 50 else float(close.iloc[-1])
    ema200 = float(ind.ema(close, 200).iloc[-1]) if len(close) >= 200 else ema50

    rf = 0.02 if market == "us" else 0.06
    sharpe = round(ind.sharpe_ratio(close, rf_annual=rf), 2)
    vol = round(float(ind.annualized_volatility(close)), 1)

    last_price = round(float(close.iloc[-1]), 2)
    trend = _detect_trend(ema50, ema200, last_price)
    signal = _signal(mom, rsi_val, trend)

    return {
        "symbol": symbol,
        "name": name,
        "market": market,
        "type": sec_type,
        "last_price": last_price,
        "momentum_12_1": mom,
        "return_1m": r1m,
        "return_3m": r3m,
        "return_6m": r6m,
        "return_12m": r12m,
        "rsi": rsi_val,
        "sharpe": sharpe,
        "volatility": vol,
        "trend": trend,
        "signal": signal,
        "tier": "Hold",  # assigned after ranking
        "rank_percentile": 0.5,  # assigned after ranking
    }


# ---------------------------------------------------------------------------
# Batch screening + ranking
# ---------------------------------------------------------------------------

async def screen_all_momentum(
    provider: DataProvider, universe: list[dict]
) -> list[dict[str, Any]]:
    """Screen all symbols in parallel, rank by 12-1 momentum, assign tiers."""
    sem = asyncio.Semaphore(8)

    async def _screen(s: dict) -> dict[str, Any]:
        async with sem:
            try:
                return await screen_momentum(
                    provider, s["symbol"], s["name"], s["market"], s["type"]
                )
            except Exception as e:
                log.warning("Failed to screen %s: %s", s["symbol"], e)
                return {
                    "symbol": s["symbol"],
                    "name": s["name"],
                    "market": s["market"],
                    "type": s["type"],
                    "last_price": 0.0,
                    "momentum_12_1": -999.0,  # sort to bottom
                    "return_1m": 0.0,
                    "return_3m": 0.0,
                    "return_6m": 0.0,
                    "return_12m": 0.0,
                    "rsi": 50.0,
                    "sharpe": 0.0,
                    "volatility": 0.0,
                    "trend": "neutral",
                    "signal": "neutral",
                    "tier": "Avoid",
                    "rank_percentile": 0.0,
                }

    results = await asyncio.gather(*[_screen(s) for s in universe])

    # Filter out symbols with no data
    valid = [r for r in results if r["momentum_12_1"] != -999.0]
    failed = [r for r in results if r["momentum_12_1"] == -999.0]
    for r in failed:
        r["momentum_12_1"] = 0.0

    # Sort by 12-1 momentum descending
    valid.sort(key=lambda d: d["momentum_12_1"], reverse=True)

    # Assign percentile ranks
    n = len(valid)
    for i, r in enumerate(valid):
        r["rank_percentile"] = round((n - i - 1) / max(n - 1, 1), 4) if n > 1 else 1.0
        # rank_percentile: 1.0 = best (rank 0), 0.0 = worst (rank n-1)
        r["rank"] = i + 1
        r["tier"] = _classify_tier(r["rank_percentile"], r["momentum_12_1"])

    # Append failed entries at the bottom
    for r in failed:
        r["rank"] = n + 1
        r["rank_percentile"] = 0.0

    return valid + failed
