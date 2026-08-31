"""Opening-Range Breakout strategy.

Computes a candidate pick from a symbol's daily + intraday data. The strategy
is deliberately simple and transparent so the explainer can describe exactly
how each level was derived and the user can verify it on a chart.
"""
from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from app.config import settings
from app import indicators as ind


@dataclass
class StrategyContext:
    """Pre-computed inputs handed to the strategy, so tests can construct fixtures."""

    symbol: str
    daily: pd.DataFrame          # daily OHLCV, last row = previous trading day
    intraday: pd.DataFrame       # today's 5-min OHLCV, tz-aware index
    or_high: float | None
    or_low: float | None
    expiry_today: bool = False


@dataclass
class StrategyResult:
    symbol: str
    side: str | None             # "long" | "short" | None
    entry: float | None
    stop_loss: float | None
    target1: float | None
    target2: float | None
    confidence: float
    atr_value: float
    avg_volume_20: float
    pdh: float
    pdl: float
    pivot: dict[str, float]
    or_high: float | None
    or_low: float | None
    breakout: dict | None
    trend_up: bool
    notes: list[str]


def evaluate(ctx: StrategyContext) -> StrategyResult:
    daily = ctx.daily
    prev = daily.iloc[-1]
    pdh, pdl, pdc = float(prev["High"]), float(prev["Low"]), float(prev["Close"])
    piv = ind.pivots(pdh, pdl, pdc)
    atr_val = float(ind.atr(daily).iloc[-1]) if len(daily) >= 15 else 0.0
    avg_vol = ind.avg_volume(daily, 20)

    # Trend filter: close above 20-EMA on daily.
    trend_up = bool(prev["Close"] > ind.ema(daily["Close"], 20).iloc[-1]) if len(daily) >= 20 else True

    or_high, or_low = ctx.or_high, ctx.or_low
    breakout = None
    side = entry = sl = t1 = t2 = None
    confidence = 0.0
    notes: list[str] = []

    if or_high is not None and or_low is not None:
        breakout = ind.breakout_bar(ctx.intraday, or_high, or_low, avg_vol, settings.volume_ratio_min)
        if breakout is not None:
            side = "long"
            entry = or_high
            sl = or_low  # default: SL = OR-Low
            t1 = entry + atr_val
            t2 = entry + 2 * atr_val
            # Confidence: blend volume ratio, gap alignment, trend.
            vol_score = min(breakout["volume_ratio"] / 3.0, 1.0)
            trend_score = 1.0 if trend_up else 0.3
            confidence = round(0.5 * vol_score + 0.5 * trend_score, 3)
        else:
            notes.append("No breakout bar yet (price did not close above OR-High on required volume).")
    else:
        notes.append("Opening range not yet formed (market before 09:30 or no candles).")

    if ctx.expiry_today:
        notes.append("Expiry day: expect higher gamma and overnight gap risk. Avoid holding overnight.")

    return StrategyResult(
        symbol=ctx.symbol,
        side=side,
        entry=entry,
        stop_loss=sl,
        target1=t1,
        target2=t2,
        confidence=confidence,
        atr_value=atr_val,
        avg_volume_20=avg_vol,
        pdh=pdh,
        pdl=pdl,
        pivot=piv,
        or_high=or_high,
        or_low=or_low,
        breakout=breakout,
        trend_up=trend_up,
        notes=notes,
    )
