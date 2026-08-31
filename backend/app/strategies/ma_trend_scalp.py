"""Moving Average Trend Scalp — EMA crossover scalping strategy.

A pure mechanical EMA crossover system: when the fast EMA (9) crosses
the slow EMA (21) in the direction of the higher-timeframe trend (50-EMA),
enter on the signal bar close with a tight stop and measured-move target.

Key parameters (from risk management principles):
  - Fast EMA (signal):     9   (short-term momentum)
  - Slow EMA (signal):     21  (short-term trend)
  - Trend EMA (filter):    50  (higher-timeframe trend filter)
  - Stale signal max bars: 3   (skip if cross happened >3 bars ago)
  - ATR multiple (stop):   1.0x (tight — below swing low)
  - Target:                1.5x risk (measured-move)

Entry logic (long — mirror for short):
  1. 9-EMA crosses ABOVE 21-EMA (bullish crossover).
  2. Both 9-EMA and 21-EMA must be ABOVE 50-EMA (trend alignment).
  3. Cross must have happened within the last 3 bars (stale filter).
  4. Entry = signal bar close; SL = swing low (last 5 bars) - ATR buffer;
     Target = entry + 1.5 x risk.

Skip conditions:
  - Cross happened more than 3 bars ago (stale signal).
  - Trend EMAs not aligned (9 and 21 not both above/below 50).
  - Volume below average (no conviction).
"""
from __future__ import annotations

from dataclasses import dataclass, field

import pandas as pd

from app import indicators as ind


@dataclass
class MaTrendSignal:
    symbol: str
    side: str                 # "long" | "short"
    entry: float
    stop_loss: float
    target: float
    risk_reward: float
    confidence: float
    last_price: float
    ema9: float
    ema21: float
    ema_trend: float          # trend-filter EMA value
    trend: str                # "uptrend" | "downtrend"
    cross_bars_ago: int       # how many bars since the crossover
    volume_ratio: float
    swing_low: float          # or swing high for shorts
    explanation: str
    caveats: list[str] = field(default_factory=list)


def evaluate_ma_trend_scalp(
    symbol: str,
    daily: pd.DataFrame,
    intraday: pd.DataFrame,
    fast_period: int = 9,
    slow_period: int = 21,
    trend_period: int = 50,
    min_rr: float = 1.5,
    atr_period: int = 14,
    min_volume_ratio: float = 0.8,
    max_stale_bars: int = 3,
) -> MaTrendSignal | None:
    """Evaluate a stock for a Moving Average Trend Scalp signal.

    Args:
        symbol: stock symbol (e.g. "RELIANCE").
        daily: daily OHLCV (used for ATR context).
        intraday: intraday 5-min OHLCV, tz-aware index.
        fast_period: fast EMA period (crossover signal).
        slow_period: slow EMA period (crossover signal).
        trend_period: trend-filter EMA period (higher timeframe).
        min_rr: minimum risk:reward ratio to emit a signal.
        atr_period: ATR lookback (on daily bars).
        min_volume_ratio: minimum volume/avg ratio on the signal bar.
        max_stale_bars: skip if the crossover happened more than this many bars ago.

    Returns:
        MaTrendSignal if conditions are met, None otherwise.
    """
    if intraday is None or intraday.empty or len(intraday) < trend_period + 5:
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

    # Compute EMAs on intraday close.
    ema_fast = ind.ema(intraday["Close"], fast_period)
    ema_slow = ind.ema(intraday["Close"], slow_period)
    ema_trend = ind.ema(intraday["Close"], trend_period)

    last_close = float(intraday["Close"].iloc[-1])
    ema9_val = float(ema_fast.iloc[-1])
    ema21_val = float(ema_slow.iloc[-1])
    ema_trend_val = float(ema_trend.iloc[-1])

    if any(pd.isna(x) for x in (ema9_val, ema21_val, ema_trend_val)):
        return None

    # ---- Detect crossover within the last max_stale_bars ----
    # A bullish crossover at bar i: ema_fast[i] > ema_slow[i] AND ema_fast[i-1] <= ema_slow[i-1]
    # A bearish crossover at bar i: ema_fast[i] < ema_slow[i] AND ema_fast[i-1] >= ema_slow[i-1]
    lookback = min(len(intraday), max_stale_bars + 5)
    recent_fast = ema_fast.iloc[-lookback:]
    recent_slow = ema_slow.iloc[-lookback:]

    cross_idx = -1  # index within recent_fast/slow where the cross happened
    side = None

    # Scan from most recent backward.
    for i in range(len(recent_fast) - 1, 0, -1):
        prev_f = float(recent_fast.iloc[i - 1])
        curr_f = float(recent_fast.iloc[i])
        prev_s = float(recent_slow.iloc[i - 1])
        curr_s = float(recent_slow.iloc[i])

        if any(pd.isna(x) for x in (prev_f, curr_f, prev_s, curr_s)):
            continue

        # Bullish cross: fast crosses above slow.
        if prev_f <= prev_s and curr_f > curr_s:
            cross_idx = i
            side = "long"
            break
        # Bearish cross: fast crosses below slow.
        if prev_f >= prev_s and curr_f < curr_s:
            cross_idx = i
            side = "short"
            break

    if side is None:
        return None

    # How many bars ago was the cross? (distance from the last bar)
    cross_bars_ago = (len(recent_fast) - 1) - cross_idx
    if cross_bars_ago > max_stale_bars:
        return None

    # ---- Trend alignment filter ----
    # Long: 9-EMA and 21-EMA both above 50-EMA.
    # Short: 9-EMA and 21-EMA both below 50-EMA.
    if side == "long":
        if not (ema9_val > ema_trend_val and ema21_val > ema_trend_val):
            return None
        trend = "uptrend"
    else:
        if not (ema9_val < ema_trend_val and ema21_val < ema_trend_val):
            return None
        trend = "downtrend"

    # ---- Volume confirmation on the signal bar ----
    avg_vol = ind.avg_volume(intraday, 20)
    signal_bar = intraday.iloc[-1]
    signal_vol = float(signal_bar["Volume"])
    vol_ratio = signal_vol / avg_vol if avg_vol > 0 else 0.0
    if vol_ratio < min_volume_ratio:
        return None

    # ---- Entry, stop, target ----
    entry = last_close
    last5 = intraday.tail(5)

    if side == "long":
        swing_low = float(last5["Low"].min())
        stop_loss = swing_low - atr_val * 0.1  # small buffer below swing low
        risk = abs(entry - stop_loss)
        if risk <= 0:
            return None
        target = entry + 1.5 * risk
    else:
        swing_high = float(last5["High"].max())
        stop_loss = swing_high + atr_val * 0.1  # small buffer above swing high
        risk = abs(entry - stop_loss)
        if risk <= 0:
            return None
        target = entry - 1.5 * risk

    rr = abs(target - entry) / risk
    if rr < min_rr - 1e-9:
        return None

    # ---- Confidence: 35% cross freshness + 30% trend alignment + 20% volume + 15% EMA separation ----
    # Cross freshness: 1.0 if cross is on the current bar, decays to 0 at max_stale_bars.
    freshness_score = 1.0 - (cross_bars_ago / max(max_stale_bars, 1))
    # Trend alignment: how far the EMAs are from the trend EMA (normalized by ATR).
    sep = abs(ema9_val - ema_trend_val) + abs(ema21_val - ema_trend_val)
    trend_score = min(sep / (2.0 * atr_val), 1.0) if atr_val > 0 else 0.0
    vol_score = min(vol_ratio / 3.0, 1.0)
    # EMA separation between fast and slow (wider = stronger momentum).
    ema_sep = abs(ema9_val - ema21_val)
    sep_score = min(ema_sep / atr_val, 1.0) if atr_val > 0 else 0.0

    confidence = round(
        0.35 * freshness_score + 0.30 * trend_score + 0.20 * vol_score + 0.15 * sep_score,
        3,
    )

    # ---- Explanation ----
    direction = "bullish" if side == "long" else "bearish"
    swing_label = "swing low" if side == "long" else "swing high"
    swing_val = swing_low if side == "long" else swing_high
    explanation = (
        f"{symbol} MA Trend Scalp signal ({side.upper()}): {direction} crossover of "
        f"{fast_period}-EMA above {slow_period}-EMA {cross_bars_ago} bar(s) ago. "
        f"Trend confirmed — both EMAs {'above' if side == 'long' else 'below'} "
        f"{trend_period}-EMA (₹{ema_trend_val:.2f}). Volume {vol_ratio:.1f}x average. "
        f"Entry ₹{entry:.2f}, SL ₹{stop_loss:.2f} (below {swing_label} ₹{swing_val:.2f} - ATR buffer), "
        f"Target ₹{target:.2f} (1.5R). R:R = 1:{rr:.1f}."
    )

    caveats = [
        "Scalp trade — exit within 30 min if target/SL not hit.",
        f"Crossover was {cross_bars_ago} bar(s) ago — signal freshness matters.",
        "EMA crossovers can whipsaw in sideways markets; confirm with volume.",
    ]

    return MaTrendSignal(
        symbol=symbol,
        side=side,
        entry=round(entry, 2),
        stop_loss=round(stop_loss, 2),
        target=round(target, 2),
        risk_reward=round(rr, 2),
        confidence=confidence,
        last_price=round(last_close, 2),
        ema9=round(ema9_val, 2),
        ema21=round(ema21_val, 2),
        ema_trend=round(ema_trend_val, 2),
        trend=trend,
        cross_bars_ago=cross_bars_ago,
        volume_ratio=round(vol_ratio, 2),
        swing_low=round(swing_val, 2),
        explanation=explanation,
        caveats=caveats,
    )
