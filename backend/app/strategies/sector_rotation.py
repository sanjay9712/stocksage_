"""Sector rotation screener.

Computes multi-timeframe performance for sector ETFs to detect which
sectors are leading vs lagging, and whether momentum is accelerating or
decelerating. This helps investors rotate capital into strong sectors.

Works for both NSE (Indian) and US markets via the same DataProvider.
"""
from __future__ import annotations

import asyncio
import logging
from typing import Any

import pandas as pd

from app import indicators as ind
from app.providers.base import DataProvider

log = logging.getLogger("sector_rotation")


# ---------------------------------------------------------------------------
# Sector universes
# ---------------------------------------------------------------------------

NSE_SECTORS = [
    {"symbol": "BANKBEES", "name": "Banking", "market": "in"},
    {"symbol": "ITBEES", "name": "IT", "market": "in"},
    {"symbol": "NIFTYBEES", "name": "Nifty 50 (Broad)", "market": "in"},
    {"symbol": "GOLDBEES", "name": "Gold", "market": "in"},
    {"symbol": "CPSEETF", "name": "PSU", "market": "in"},
    {"symbol": "MID150BEES", "name": "Midcap", "market": "in"},
    {"symbol": "SILVERBEES", "name": "Silver", "market": "in"},
]

US_SECTORS = [
    {"symbol": "XLK", "name": "Technology", "market": "us"},
    {"symbol": "XLF", "name": "Financials", "market": "us"},
    {"symbol": "XLE", "name": "Energy", "market": "us"},
    {"symbol": "XLV", "name": "Healthcare", "market": "us"},
    {"symbol": "XLU", "name": "Utilities", "market": "us"},
    {"symbol": "SPY", "name": "S&P 500 (Broad)", "market": "us"},
    {"symbol": "QQQ", "name": "Nasdaq 100", "market": "us"},
    {"symbol": "GLD", "name": "Gold", "market": "us"},
    {"symbol": "IWM", "name": "Russell 2000", "market": "us"},
]


# ---------------------------------------------------------------------------
# Single-sector screening
# ---------------------------------------------------------------------------

def _pct_return(close: pd.Series, bars: int) -> float:
    """Percentage return over the last N bars."""
    if len(close) < bars + 1:
        return 0.0
    return round(((close.iloc[-1] - close.iloc[-bars - 1]) / close.iloc[-bars - 1]) * 100, 2)


def _momentum_score(r1d: float, r1w: float, r1m: float, r3m: float) -> float:
    """Weighted composite momentum score, scaled 0-1.

    Weights: 1d=10%, 1w=20%, 1m=30%, 3m=40%.
    Returns a value in [0, 1] where 0.5 = flat, >0.5 = bullish, <0.5 = bearish.
    """
    # Normalize each return to [-1, +1] using a sigmoid-like tanh transform
    # centered at 0, so 10% return ≈ 0.76, 20% ≈ 0.96.
    import math

    n1d = math.tanh(r1d / 3.0)
    n1w = math.tanh(r1w / 5.0)
    n1m = math.tanh(r1m / 10.0)
    n3m = math.tanh(r3m / 20.0)

    composite = (n1d * 0.10 + n1w * 0.20 + n1m * 0.30 + n3m * 0.40)
    # composite is in [-1, +1]; map to [0, 1]
    return round((composite + 1) / 2, 4)


def _detect_rotation(r1d: float, r1w: float, r1m: float, r3m: float) -> str:
    """Classify rotation state by comparing short vs long-term returns."""
    short_term = (r1d + r1w) / 2
    long_term = (r1m + r3m) / 2

    if long_term <= 0 and short_term <= 0:
        return "bearish"
    if long_term > 0 and short_term <= 0:
        return "decelerating"
    if long_term > 0 and short_term > 0:
        if short_term > long_term:
            return "accelerating"
        # short_term <= long_term, both positive
        if short_term < long_term * 0.6:
            return "weakening"
        return "strengthening"
    # long_term <= 0 but short_term > 0 — early recovery
    return "accelerating"


def _detect_trend(ema50: float, ema200: float, last_price: float) -> str:
    """Bullish/bearish/neutral based on EMA alignment."""
    if ema50 > ema200 and last_price > ema50:
        return "bullish"
    if ema50 < ema200 and last_price < ema50:
        return "bearish"
    return "neutral"


async def screen_sector(
    provider: DataProvider, symbol: str, name: str, market: str
) -> dict[str, Any]:
    """Fetch daily data for one sector ETF and compute rotation metrics.

    Returns a dict with multi-timeframe returns, RSI, trend, Sharpe,
    rotation verdict, and momentum score.
    """
    # 90 trading days covers ~3 months; add buffer for EMA-200 warmup isn't
    # needed since we only use EMA-50/200 for trend direction (shorter window
    # still gives a usable trend signal). Fetch 200 for proper EMA-200.
    daily = await provider.get_daily_history(symbol, 250)
    if daily.empty or len(daily) < 30:
        return {
            "symbol": symbol,
            "name": name,
            "market": market,
            "last_price": 0.0,
            "return_1d": 0.0,
            "return_1w": 0.0,
            "return_1m": 0.0,
            "return_3m": 0.0,
            "rsi": 0.0,
            "trend": "neutral",
            "sharpe": 0.0,
            "rotation": "bearish",
            "momentum_score": 0.5,
        }

    close = daily["Close"]

    r1d = _pct_return(close, 1)
    r1w = _pct_return(close, 5)
    r1m = _pct_return(close, 21)
    r3m = _pct_return(close, 63)

    rsi_series = ind.rsi(close, 14)
    rsi_val = round(float(rsi_series.iloc[-1]), 1) if not rsi_series.empty and not pd.isna(rsi_series.iloc[-1]) else 50.0

    ema50 = float(ind.ema(close, 50).iloc[-1]) if len(close) >= 50 else float(close.iloc[-1])
    ema200 = float(ind.ema(close, 200).iloc[-1]) if len(close) >= 200 else ema50

    rf = 0.02 if market == "us" else 0.06
    sharpe = round(ind.sharpe_ratio(close, rf_annual=rf), 2)

    last_price = round(float(close.iloc[-1]), 2)
    trend = _detect_trend(ema50, ema200, last_price)
    rotation = _detect_rotation(r1d, r1w, r1m, r3m)
    score = _momentum_score(r1d, r1w, r1m, r3m)

    return {
        "symbol": symbol,
        "name": name,
        "market": market,
        "last_price": last_price,
        "return_1d": r1d,
        "return_1w": r1w,
        "return_1m": r1m,
        "return_3m": r3m,
        "rsi": rsi_val,
        "trend": trend,
        "sharpe": sharpe,
        "rotation": rotation,
        "momentum_score": score,
    }


# ---------------------------------------------------------------------------
# Batch screening
# ---------------------------------------------------------------------------

async def screen_all_sectors(
    provider: DataProvider, sectors: list[dict]
) -> list[dict[str, Any]]:
    """Screen all sectors in parallel with concurrency limiting."""
    sem = asyncio.Semaphore(8)

    async def _screen(s: dict) -> dict[str, Any]:
        async with sem:
            try:
                return await screen_sector(provider, s["symbol"], s["name"], s["market"])
            except Exception as e:
                log.warning("Failed to screen sector %s: %s", s["symbol"], e)
                return {
                    "symbol": s["symbol"],
                    "name": s["name"],
                    "market": s["market"],
                    "last_price": 0.0,
                    "return_1d": 0.0,
                    "return_1w": 0.0,
                    "return_1m": 0.0,
                    "return_3m": 0.0,
                    "rsi": 0.0,
                    "trend": "neutral",
                    "sharpe": 0.0,
                    "rotation": "bearish",
                    "momentum_score": 0.5,
                }

    results = await asyncio.gather(*[_screen(s) for s in sectors])
    # Sort by momentum score descending
    results.sort(key=lambda d: d.get("momentum_score", 0), reverse=True)
    return results
