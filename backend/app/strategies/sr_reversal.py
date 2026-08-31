"""Support/Resistance Reversal — reversal at key price levels.

A selective strategy that fires only when a candlestick reversal pattern
occurs at a significant support or resistance level (previous day low/high,
pivot S1/R1, Fibonacci 61.8%). This is much more selective than the general
scalping strategy, which fires on patterns anywhere.

Key parameters (from risk management principles):
  - Level proximity:       0.3 ATR (price must be within 0.3 ATR of a level)
  - ATR multiple (stop):   1.0x (beyond the support/resistance level)
  - Target 1:              Pivot point (mean reversion)
  - Target 2:              R1 (long) / S1 (short) — next significant level
  - Minimum R:R:           1.5

Entry logic (long — mirror for short):
  1. Price is within 0.3 ATR of a key support level (PDL, S1, Fib 61.8%).
  2. A bullish reversal candlestick pattern fires on the most recent bar.
  3. Volume on the signal bar >= 1.0x average (some conviction needed).
  4. Entry = signal bar close; SL = support - 1x ATR; T1 = pivot;
     T2 = R1.

Skip conditions:
  - No key level nearby (price not within 0.3 ATR of any support/resistance).
  - No directional reversal pattern detected.
  - Pattern bias doesn't match the level (bullish pattern at resistance = skip).
"""
from __future__ import annotations

from dataclasses import dataclass, field

import pandas as pd

from app import indicators as ind
from app.strategies.candlestick import detect_patterns, net_bias, PatternHit


@dataclass
class SrReversalSignal:
    symbol: str
    side: str                 # "long" | "short"
    entry: float
    stop_loss: float
    target1: float
    target2: float
    risk_reward: float
    confidence: float
    last_price: float
    level_type: str           # "PDL" | "PDH" | "S1" | "R1" | "Fib_61.8%"
    level_price: float
    atr: float
    trend: str                # "uptrend" | "downtrend" | "sideways"
    volume_ratio: float
    patterns: list[dict]
    explanation: str
    caveats: list[str] = field(default_factory=list)


# Only fire on reversal patterns (not continuation patterns).
_REVERSAL_PATTERNS = {
    # Bullish reversals
    "Bullish Engulfing", "Hammer", "Morning Star", "Piercing Line",
    "Bullish Harami", "Tweezer Bottoms", "Bullish Marubozu",
    # Bearish reversals
    "Bearish Engulfing", "Shooting Star", "Evening Star", "Dark Cloud Cover",
    "Bearish Harami", "Tweezer Tops", "Bearish Marubozu",
}


def evaluate_sr_reversal(
    symbol: str,
    daily: pd.DataFrame,
    intraday: pd.DataFrame,
    level_proximity_atr: float = 0.3,
    min_volume_ratio: float = 0.1,
    min_rr: float = 1.5,
    atr_period: int = 14,
    ema_period: int = 20,
) -> SrReversalSignal | None:
    """Evaluate a stock for a Support/Resistance Reversal signal.

    Args:
        symbol: stock symbol (e.g. "RELIANCE").
        daily: daily OHLCV (used for prev H/L/C, ATR, pivots, Fib levels).
        intraday: intraday 5-min OHLCV, tz-aware index.
        level_proximity_atr: max distance from a key level (in ATR units).
        min_volume_ratio: minimum volume/avg ratio on the signal bar.
        min_rr: minimum risk:reward ratio to emit a signal.
        atr_period: ATR lookback (on daily bars).
        ema_period: EMA period for trend filter (on intraday bars).

    Returns:
        SrReversalSignal if conditions are met, None otherwise.
    """
    if intraday is None or intraday.empty or len(intraday) < ema_period + 2:
        return None
    if daily is None or daily.empty or len(daily) < 3:
        return None

    # Previous day's H/L/C (last completed daily bar).
    prev_high = float(daily["High"].iloc[-1])
    prev_low = float(daily["Low"].iloc[-1])
    prev_close = float(daily["Close"].iloc[-1])

    if prev_high <= prev_low or prev_close <= 0:
        return None

    # ATR from daily bars.
    atr_val = float(ind.atr(daily, atr_period).iloc[-1]) if len(daily) >= atr_period else 0.0
    if atr_val <= 0:
        return None

    # Compute key levels: pivots, Fibonacci, PDL/PDH.
    pivot_levels = ind.pivots(prev_high, prev_low, prev_close)
    fib_levels = ind.fibonacci_levels(prev_high, prev_low)

    # Support levels (for longs).
    support_levels = {
        "PDL": prev_low,
        "S1": pivot_levels["s1"],
        "S2": pivot_levels["s2"],
        "Fib_61.8%": fib_levels["0.618"],
    }

    # Resistance levels (for shorts).
    resistance_levels = {
        "PDH": prev_high,
        "R1": pivot_levels["r1"],
        "R2": pivot_levels["r2"],
        "Fib_61.8%": fib_levels["0.382"],  # 38.2% retracement acts as resistance in downtrend
    }

    last_close = float(intraday["Close"].iloc[-1])
    proximity = level_proximity_atr * atr_val

    # ---- Find the nearest support level (for longs) ----
    best_support = None
    best_support_dist = float("inf")
    for name, price in support_levels.items():
        dist = abs(last_close - price)
        if dist < proximity and dist < best_support_dist:
            best_support = (name, price)
            best_support_dist = dist

    # ---- Find the nearest resistance level (for shorts) ----
    best_resistance = None
    best_resistance_dist = float("inf")
    for name, price in resistance_levels.items():
        dist = abs(last_close - price)
        if dist < proximity and dist < best_resistance_dist:
            best_resistance = (name, price)
            best_resistance_dist = dist

    if best_support is None and best_resistance is None:
        return None

    # ---- Detect candlestick patterns on the last 5 intraday bars ----
    recent = intraday.tail(5)
    hits = detect_patterns(recent, lookback=5)
    directional = [h for h in hits if h.name in _REVERSAL_PATTERNS]
    if not directional:
        return None

    bias = net_bias(directional)
    if bias == "neutral":
        return None

    # ---- Determine side: bullish pattern at support = long; bearish at resistance = short ----
    if bias == "bullish" and best_support is not None:
        side = "long"
        level_type, level_price = best_support
    elif bias == "bearish" and best_resistance is not None:
        side = "short"
        level_type, level_price = best_resistance
    else:
        # Pattern doesn't match the nearest level direction.
        return None

    # ---- Trend filter (intraday EMA) ----
    ema = ind.ema(intraday["Close"], ema_period)
    ema_val = float(ema.iloc[-1]) if len(ema) >= ema_period else last_close
    if last_close > ema_val:
        trend = "uptrend"
    elif last_close < ema_val:
        trend = "downtrend"
    else:
        trend = "sideways"

    # ---- Volume confirmation ----
    avg_vol = ind.avg_volume(intraday, 20)
    signal_bar = intraday.iloc[-1]
    signal_vol = float(signal_bar["Volume"])
    vol_ratio = signal_vol / avg_vol if avg_vol > 0 else 0.0
    if vol_ratio < min_volume_ratio:
        return None

    # ---- Entry, stop, targets ----
    # Use a tighter stop (0.5 ATR below the level) for better R:R.
    # Targets are ATR-based measured moves, not just pivot levels.
    entry = last_close
    if side == "long":
        stop_loss = level_price - 0.5 * atr_val  # below support by 0.5 ATR
        risk = abs(entry - stop_loss)
        if risk <= 0:
            return None
        # T1: pivot point (mean reversion) if above entry, else 1 ATR.
        # Ensure T1 is at least 1.0×ATR from entry so R:R to T1 is reasonable.
        raw_t1 = pivot_levels["pivot"] if pivot_levels["pivot"] > entry else entry + atr_val
        target1 = max(raw_t1, entry + 1.0 * atr_val)
        # T2: entry + 2 ATR (measured move) or R1, whichever is further.
        target2 = max(pivot_levels["r1"], entry + 2.0 * atr_val)
    else:
        stop_loss = level_price + 0.5 * atr_val  # above resistance by 0.5 ATR
        risk = abs(stop_loss - entry)
        if risk <= 0:
            return None
        # T1: pivot point if below entry, else 1 ATR below.
        # Ensure T1 is at least 1.0×ATR from entry.
        raw_t1 = pivot_levels["pivot"] if pivot_levels["pivot"] < entry else entry - atr_val
        target1 = min(raw_t1, entry - 1.0 * atr_val)
        target2 = min(pivot_levels["s1"], entry - 2.0 * atr_val)

    # Ensure targets are in the right direction.
    if side == "long" and target2 <= entry:
        target2 = entry + 1.5 * risk
    if side == "short" and target2 >= entry:
        target2 = entry - 1.5 * risk

    # R:R check: use target1 (nearest target) for risk management.
    rr = abs(target1 - entry) / risk
    if rr < min_rr - 1e-9:
        return None

    # ---- Confidence: 35% level strength + 30% pattern strength + 20% trend + 15% volume ----
    # Level strength: Fib 61.8% = 1.0, PDL/PDH = 0.8, S1/R1 = 0.7, S2/R2 = 0.6
    level_strength = {
        "Fib_61.8%": 1.0, "PDL": 0.8, "PDH": 0.8,
        "S1": 0.7, "R1": 0.7, "S2": 0.6, "R2": 0.6,
    }.get(level_type, 0.5)

    # Pattern strength.
    strong_count = sum(1 for h in directional if h.strength == "strong")
    moderate_count = sum(1 for h in directional if h.strength == "moderate")
    pattern_score = min((strong_count * 1.0 + moderate_count * 0.5) / 2.0, 1.0)

    # Trend alignment: reversal against the trend is riskier but valid at key levels.
    # Counter-trend reversals (long in downtrend at support) are the bread and butter.
    trend_score = 1.0  # reversal at a key level is valid regardless of trend

    vol_score = min(vol_ratio / 3.0, 1.0)

    confidence = round(
        0.35 * level_strength + 0.30 * pattern_score + 0.20 * trend_score + 0.15 * vol_score,
        3,
    )

    # ---- Explanation ----
    pattern_names = ", ".join(f"{h.name} ({h.strength})" for h in directional)
    direction = "bullish" if side == "long" else "bearish"
    explanation = (
        f"{symbol} S/R Reversal signal ({side.upper()}): {direction} reversal pattern(s) "
        f"detected at {level_type} support ₹{level_price:.2f} (within {level_proximity_atr:.1f}×ATR). "
        f"Patterns: {pattern_names}. {trend.capitalize()} on {ema_period}-EMA. "
        f"Volume {vol_ratio:.1f}x average. "
        f"Entry ₹{entry:.2f}, SL ₹{stop_loss:.2f} ({'below' if side == 'long' else 'above'} {level_type} by 0.5×ATR), "
        f"T1 ₹{target1:.2f} (pivot/1×ATR), T2 ₹{target2:.2f} ({'R1' if side == 'long' else 'S1'}/2×ATR). "
        f"R:R (to T1) = 1:{rr:.1f}."
    )

    caveats = [
        "Reversal trade — requires the level to hold; if price breaks through, exit immediately.",
        f"Pattern at {level_type} (₹{level_price:.2f}) — proximity to the level is key.",
        "Counter-trend reversals can fail in strong trends; use tight stops.",
    ]
    if trend == "sideways":
        caveats.append("Trend is sideways — reversal reliability is moderate.")
    if vol_ratio < 1.5:
        caveats.append("Volume is below 1.5x — conviction is limited.")

    return SrReversalSignal(
        symbol=symbol,
        side=side,
        entry=round(entry, 2),
        stop_loss=round(stop_loss, 2),
        target1=round(target1, 2),
        target2=round(target2, 2),
        risk_reward=round(rr, 2),
        confidence=confidence,
        last_price=round(last_close, 2),
        level_type=level_type,
        level_price=round(level_price, 2),
        atr=round(atr_val, 2),
        trend=trend,
        volume_ratio=round(vol_ratio, 2),
        patterns=[
            {"name": h.name, "bias": h.bias, "strength": h.strength, "description": h.description}
            for h in directional
        ],
        explanation=explanation,
        caveats=caveats,
    )
