"""VWAP + 9 EMA pullback scalping strategy.

One of the highest-probability intraday setups: in an established trend
(price above both VWAP and the 9 EMA), wait for a pullback to the 9 EMA,
then enter on the bounce candle with volume confirmation.

Key parameters (from risk management principles):
  - EMA period (trend):       9   (short-term trend)
  - Volume ratio minimum:    1.2x (above-average volume on the bounce)
  - ATR multiple (stop):     1.0x (tight — below the pullback low)
  - Target 1:                VWAP / high of day (mean reversion to fair value)
  - Target 2:                1.5x risk (measured from entry to stop)

Entry logic (long — mirror for short):
  1. Price ABOVE both VWAP and 9 EMA (uptrend confirmed).
  2. Price pulls back to touch the 9 EMA.
  3. Current bar closes bullish (green) with volume >= 1.2x average.
  4. Entry = bounce candle close; SL = pullback low - small buffer;
     Target 1 = VWAP; Target 2 = entry + 1.5 x risk.

Skip conditions:
  - First 5 minutes of the session (too noisy, false signals).
  - Price chopping around VWAP with no clear trend.
  - Low volume (below 20-bar average).
"""
from __future__ import annotations

from dataclasses import dataclass, field

import pandas as pd

from app import indicators as ind


@dataclass
class VwapSignal:
    symbol: str
    side: str                 # "long" | "short"
    entry: float
    stop_loss: float
    target1: float
    target2: float
    risk_reward: float
    confidence: float
    last_price: float
    vwap: float
    ema9: float
    ema21: float
    trend: str                # "uptrend" | "downtrend" | "sideways"
    volume_ratio: float
    pullback_low: float
    explanation: str
    caveats: list[str] = field(default_factory=list)


def evaluate_vwap_pullback(
    symbol: str,
    daily: pd.DataFrame,
    intraday: pd.DataFrame,
    ema_fast: int = 9,
    ema_slow: int = 21,
    min_volume_ratio: float = 1.2,
    min_rr: float = 1.5,
    atr_period: int = 14,
) -> VwapSignal | None:
    """Evaluate a stock for a VWAP pullback scalping signal.

    Args:
        symbol: stock symbol (e.g. "RELIANCE").
        daily: daily OHLCV (used for ATR context).
        intraday: intraday 5-min OHLCV, tz-aware index.
        ema_fast: fast EMA period (pullback level).
        ema_slow: slow EMA period (secondary trend filter).
        min_volume_ratio: minimum volume/avg on the bounce bar.
        min_rr: minimum risk:reward for target 2.
        atr_period: ATR lookback (on daily bars).

    Returns:
        VwapSignal if conditions are met, None otherwise.
    """
    if intraday is None or intraday.empty or len(intraday) < ema_slow + 5:
        return None
    if daily is None or daily.empty:
        return None

    # ATR from daily bars (stable volatility context).
    atr_val = float(ind.atr(daily, atr_period).iloc[-1]) if len(daily) >= atr_period else 0.0
    if atr_val <= 0:
        return None

    # Skip the first 5 bars (~25 min on 5-min candles) — too noisy.
    if len(intraday) < 6:
        return None
    recent = intraday.iloc[5:]

    vwap_series = ind.vwap(intraday)
    ema9_series = ind.ema(intraday["Close"], ema_fast)
    ema21_series = ind.ema(intraday["Close"], ema_slow)

    last_close = float(recent["Close"].iloc[-1])
    vwap_val = float(vwap_series.iloc[-1])
    ema9_val = float(ema9_series.iloc[-1])
    ema21_val = float(ema21_series.iloc[-1])

    if any(pd.isna(x) for x in (vwap_val, ema9_val, ema21_val)):
        return None

    # Trend determination.
    if last_close > vwap_val and last_close > ema9_val and ema9_val > ema21_val:
        trend = "uptrend"
    elif last_close < vwap_val and last_close < ema9_val and ema9_val < ema21_val:
        trend = "downtrend"
    else:
        trend = "sideways"

    if trend == "sideways":
        return None

    side = "long" if trend == "uptrend" else "short"

    # Look for a pullback to the 9 EMA in the last 3 bars, then a bounce.
    # A pullback = a bar whose low touches/crosses the 9 EMA.
    # A bounce = a subsequent bar that closes back on the trend side.
    last3 = recent.tail(3)
    pullback_low = float(last3["Low"].min())

    if side == "long":
        # Need at least one bar in last 3 that touched the 9 EMA (low <= ema9).
        touched = any(
            float(last3["Low"].iloc[i]) <= float(ema9_series.reindex(last3.index).iloc[i]) * 1.001
            for i in range(len(last3))
        )
        if not touched:
            return None
        # Current bar must be a bullish bounce (close > open).
        curr = recent.iloc[-1]
        if curr["Close"] <= curr["Open"]:
            return None
    else:
        touched = any(
            float(last3["High"].iloc[i]) >= float(ema9_series.reindex(last3.index).iloc[i]) * 0.999
            for i in range(len(last3))
        )
        if not touched:
            return None
        curr = recent.iloc[-1]
        if curr["Close"] >= curr["Open"]:
            return None

    # Volume confirmation on the bounce bar.
    avg_vol = ind.avg_volume(intraday, 20)
    signal_vol = float(curr["Volume"])
    vol_ratio = signal_vol / avg_vol if avg_vol > 0 else 0.0
    if vol_ratio < min_volume_ratio:
        return None

    # Entry, stop, targets.
    entry = last_close
    if side == "long":
        stop_loss = pullback_low - 0.05  # small buffer below the pullback low
        target1 = vwap_val if vwap_val > entry else entry + atr_val
        risk = abs(entry - stop_loss)
        target2 = entry + 1.5 * risk
    else:
        # For shorts, use the high of the pullback as stop.
        pullback_high = float(last3["High"].max())
        stop_loss = pullback_high + 0.05
        target1 = vwap_val if vwap_val < entry else entry - atr_val
        risk = abs(entry - stop_loss)
        target2 = entry - 1.5 * risk

    if risk <= 0:
        return None
    rr = (abs(target2 - entry)) / risk
    if rr < min_rr - 1e-9:  # tolerance for floating-point edge cases
        return None

    # Confidence: blend trend alignment, volume, and pullback depth.
    trend_score = 1.0
    vol_score = min(vol_ratio / 3.0, 1.0)
    # Deeper pullback (closer to 9 EMA) = better entry.
    depth = min(abs(entry - ema9_val) / (atr_val or 1.0), 1.0)
    depth_score = 1.0 - depth  # closer to EMA = higher score
    confidence = round(0.4 * trend_score + 0.35 * vol_score + 0.25 * depth_score, 3)

    direction = "bullish" if side == "long" else "bearish"
    explanation = (
        f"{symbol} VWAP pullback signal ({side.upper()}): {trend} confirmed by "
        f"price above VWAP (₹{vwap_val:.2f}) and {ema_fast}-EMA (₹{ema9_val:.2f}). "
        f"Price pulled back to the {ema_fast}-EMA and bounced with a {direction} "
        f"candle on {vol_ratio:.1f}x volume. Entry ₹{entry:.2f}, SL ₹{stop_loss:.2f} "
        f"(below pullback low), Target 1 ₹{target1:.2f} (VWAP), Target 2 "
        f"₹{target2:.2f} (1.5R). R:R = 1:{rr:.1f}."
    )

    caveats = [
        "Scalp trade — exit within 30 min if neither target nor SL is hit.",
        f"VWAP-based target may already be reached if price is near VWAP.",
        "Skip in the first 5 minutes of the session (noise).",
    ]

    return VwapSignal(
        symbol=symbol,
        side=side,
        entry=round(entry, 2),
        stop_loss=round(stop_loss, 2),
        target1=round(target1, 2),
        target2=round(target2, 2),
        risk_reward=round(rr, 2),
        confidence=confidence,
        last_price=round(last_close, 2),
        vwap=round(vwap_val, 2),
        ema9=round(ema9_val, 2),
        ema21=round(ema21_val, 2),
        trend=trend,
        volume_ratio=round(vol_ratio, 2),
        pullback_low=round(pullback_low, 2),
        explanation=explanation,
        caveats=caveats,
    )
