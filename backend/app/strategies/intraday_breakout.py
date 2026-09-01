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


def _find_breakdown_bar(intraday: pd.DataFrame, or_high: float, or_low: float, avg_vol: float, volume_ratio_min: float) -> dict | None:
    """Find the first 5-min candle after the OR window that closes below OR-Low
    on volume >= volume_ratio_min * avg_vol. Uses only the most recent trading
    day's bars. Returns the bar info or None.
    """
    if intraday.empty or avg_vol <= 0:
        return None
    local = intraday.index
    tz = local.tz
    if tz is None:
        return None
    kolkata_idx = local.tz_convert("Asia/Kolkata") if hasattr(local, "tz_convert") else local
    latest_date = kolkata_idx[-1].date()
    today_mask = pd.Series([d.date() == latest_date for d in kolkata_idx], index=intraday.index)
    today_bars = intraday[today_mask]
    if today_bars.empty:
        return None
    times = kolkata_idx[today_mask].time
    after_or = today_bars[pd.Series(times, index=today_bars.index) >= pd.to_datetime("09:30", format="%H:%M").time()]
    for ts, row in after_or.iterrows():
        if row["Close"] < or_low and row["Volume"] >= volume_ratio_min * avg_vol:
            return {
                "ts": str(ts),
                "close": float(row["Close"]),
                "high": float(row["High"]),
                "low": float(row["Low"]),
                "volume": float(row["Volume"]),
                "volume_ratio": float(row["Volume"] / avg_vol),
            }
    return None


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
    avg_vol = ind.avg_volume(ctx.intraday, 20) if len(ctx.intraday) >= 20 else ind.avg_volume(daily, 20)

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
            # Check for short breakdown (close below OR-Low on volume).
            breakout = _find_breakdown_bar(ctx.intraday, or_high, or_low, avg_vol, settings.volume_ratio_min)
            if breakout is not None:
                side = "short"
                entry = or_low
                sl = or_high
                t1 = entry - atr_val
                t2 = entry - 2 * atr_val
                vol_score = min(breakout["volume_ratio"] / 3.0, 1.0)
                trend_score = 0.3 if trend_up else 1.0
                confidence = round(0.5 * vol_score + 0.5 * trend_score, 3)
            else:
                notes.append("No breakout/breakdown bar yet (price did not close beyond OR on required volume).")
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
