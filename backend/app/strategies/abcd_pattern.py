"""ABCD Pattern — Fibonacci-based swing structure for intraday targets.

A classic harmonic pattern based on geometric price swings. The pattern
identifies a three-leg structure (AB, BC, CD) where point C is a Fibonacci
retracement of AB, and point D is a Fibonacci projection of AB from C.

Key parameters (from risk management principles):
  - Swing lookback:        30 bars (detect swings in recent price action)
  - Fib retracement range: 38.2%–61.8% (point C must be in this range of AB)
  - ATR multiple (stop):   1.0x (beyond point C)
  - Target:                Point D (Fibonacci projection: C + (B - A) for longs)
  - Minimum R:R:           1.5

Pattern structure (bullish ABCD):
  A = swing low (start of the up-move)
  B = swing high (end of the up-move, start of pullback)
  C = pullback low (38.2%–61.8% retracement of AB) → ENTRY POINT
  D = target = C + (B - A) (measured-move projection)

Pattern structure (bearish ABCD):
  A = swing high
  B = swing low
  C = pullback high (38.2%–61.8% retracement of AB) → ENTRY POINT
  D = target = C - (A - B) (measured-move projection)

Entry logic (long — mirror for short):
  1. Detect swing points A, B, C in the last 30 intraday bars.
  2. Point C retraces 38.2%–61.8% of the AB leg.
  3. Entry = point C (current price); SL = C - 1×ATR;
     Target = D = C + (B - A).
  4. AB and CD legs should be roughly symmetrical (within 20%).

Skip conditions:
  - Retracement outside 38.2%–61.8% range (not a valid ABCD).
  - R:R below 1.5 (target too close).
  - AB/CD asymmetry > 40% (pattern is distorted).
"""
from __future__ import annotations

from dataclasses import dataclass, field

import pandas as pd

from app import indicators as ind


@dataclass
class AbcdSignal:
    symbol: str
    side: str                 # "long" | "short"
    entry: float
    stop_loss: float
    target: float
    risk_reward: float
    confidence: float
    last_price: float
    point_a: float
    point_b: float
    point_c: float
    point_d: float            # projected target
    fib_retracement: float   # actual retracement ratio of C vs AB
    ab_length: float          # |B - A|
    cd_length: float          # |D - C| (projected)
    symmetry: float            # cd_length / ab_length (1.0 = perfect symmetry)
    atr: float
    explanation: str
    caveats: list[str] = field(default_factory=list)


def _find_swings(series: pd.Series, lookback: int = 30, min_swing_pct: float = 0.002) -> list[dict]:
    """Find alternating swing highs and lows in the last `lookback` bars.

    Uses a simple pivot detection: a swing high is a bar whose high is
    greater than the highs of `window` bars on either side.

    Returns a list of {"type": "high"|"low", "index": int, "value": float}
    ordered chronologically (oldest first).
    """
    if len(series) < lookback:
        lookback = len(series)
    recent = series.iloc[-lookback:]
    swings: list[dict] = []
    window = 2  # bars on each side to confirm a pivot

    for i in range(window, len(recent) - window):
        val = float(recent.iloc[i])
        # Check if this is a swing high.
        is_high = all(val >= float(recent.iloc[i - j]) for j in range(1, window + 1)) and \
                  all(val >= float(recent.iloc[i + j]) for j in range(1, window + 1))
        # Check if this is a swing low.
        is_low = all(val <= float(recent.iloc[i - j]) for j in range(1, window + 1)) and \
                 all(val <= float(recent.iloc[i + j]) for j in range(1, window + 1))

        if is_high:
            # Only add if it alternates from the last swing.
            if not swings or swings[-1]["type"] == "low":
                swings.append({"type": "high", "index": i, "value": val})
            elif val > swings[-1]["value"]:
                # Higher high — update the last swing.
                swings[-1] = {"type": "high", "index": i, "value": val}
        elif is_low:
            if not swings or swings[-1]["type"] == "high":
                swings.append({"type": "low", "index": i, "value": val})
            elif val < swings[-1]["value"]:
                swings[-1] = {"type": "low", "index": i, "value": val}

    return swings


def evaluate_abcd_pattern(
    symbol: str,
    daily: pd.DataFrame,
    intraday: pd.DataFrame,
    lookback: int = 30,
    min_rr: float = 1.2,
    atr_period: int = 14,
    min_retracement: float = 0.382,
    max_retracement: float = 0.618,
) -> AbcdSignal | None:
    """Evaluate a stock for an ABCD Pattern signal.

    Args:
        symbol: stock symbol (e.g. "RELIANCE").
        daily: daily OHLCV (used for ATR context).
        intraday: intraday 5-min OHLCV, tz-aware index.
        lookback: number of intraday bars to scan for swing points.
        min_rr: minimum risk:reward ratio to emit a signal.
        atr_period: ATR lookback (on daily bars).
        min_retracement: minimum Fib retracement for point C (0.382).
        max_retracement: maximum Fib retracement for point C (0.618).

    Returns:
        AbcdSignal if conditions are met, None otherwise.
    """
    if intraday is None or intraday.empty or len(intraday) < 15:
        return None
    if daily is None or daily.empty:
        return None

    # ATR from daily bars.
    atr_val = float(ind.atr(daily, atr_period).iloc[-1]) if len(daily) >= atr_period else 0.0
    if atr_val <= 0:
        return None

    # ---- Detect swing points in intraday bars ----
    # Use the Close series for swing detection — gives alternating swing
    # highs and lows based on closing prices, which is what ABCD needs.
    recent = intraday.tail(lookback)
    all_swings = _find_swings(recent["Close"], lookback)

    # We need at least 3 swings: A, B, C (alternating low-high-low or high-low-high).
    if len(all_swings) < 3:
        return None

    # Take the last 3 swings as A, B, C.
    a_swing, b_swing, c_swing = all_swings[-3], all_swings[-2], all_swings[-1]

    # Validate alternating structure.
    if a_swing["type"] == b_swing["type"] or b_swing["type"] == c_swing["type"]:
        return None

    point_a = a_swing["value"]
    point_b = b_swing["value"]
    point_c = c_swing["value"]

    # ---- Determine pattern direction ----
    # Bullish ABCD: A=low, B=high, C=low (pullback), D = C + (B - A)
    # Bearish ABCD: A=high, B=low, C=high (pullback), D = C - (A - B)
    if a_swing["type"] == "low" and b_swing["type"] == "high" and c_swing["type"] == "low":
        side = "long"
        ab_length = abs(point_b - point_a)
        if ab_length <= 0:
            return None
        # Retracement: how much of AB did BC retrace?
        retracement = (point_b - point_c) / ab_length
    elif a_swing["type"] == "high" and b_swing["type"] == "low" and c_swing["type"] == "high":
        side = "short"
        ab_length = abs(point_a - point_b)
        if ab_length <= 0:
            return None
        retracement = (point_c - point_b) / ab_length
    else:
        return None

    # ---- Fib retracement validation ----
    if retracement < min_retracement or retracement > max_retracement:
        return None

    # ---- Minimum AB length filter: AB must be meaningful relative to ATR ----
    # Swings smaller than 0.15*ATR are just market noise.
    if ab_length < 0.15 * atr_val:
        return None

    # ---- Project point D (measured-move target) ----
    if side == "long":
        point_d = point_c + (point_b - point_a)
    else:
        point_d = point_c - (point_a - point_b)

    cd_length = abs(point_d - point_c)

    # ---- Symmetry check: AB and CD should be roughly equal ----
    symmetry = cd_length / ab_length if ab_length > 0 else 0.0
    if symmetry < 0.5 or symmetry > 1.5:
        return None

    # ---- Entry, stop, target ----
    last_close = float(intraday["Close"].iloc[-1])
    entry = last_close

    # Stop buffer: proportional to the AB leg (the pattern's own scale).
    # Using daily ATR makes stops too wide relative to 5-min swing targets.
    stop_buffer = 0.3 * ab_length

    if side == "long":
        stop_loss = point_c - stop_buffer  # below point C
        risk = abs(entry - stop_loss)
        if risk <= 0:
            return None
        target = point_d
        # Target must be above entry.
        if target <= entry:
            return None
    else:
        stop_loss = point_c + stop_buffer  # above point C
        risk = abs(stop_loss - entry)
        if risk <= 0:
            return None
        target = point_d
        if target >= entry:
            return None

    rr = abs(target - entry) / risk
    if rr < min_rr - 1e-9:
        return None

    # ---- Confidence: 40% Fib retracement quality + 35% AB/CD symmetry + 25% R:R ----
    # Fib quality: 50% retracement is ideal (1.0 score), decaying toward 38.2% and 61.8%.
    fib_ideal = 0.5
    fib_dist = abs(retracement - fib_ideal)
    fib_score = max(1.0 - fib_dist / 0.118, 0.0)  # 0.118 = distance from 0.5 to 0.618

    # Symmetry: closer to 1.0 = better.
    sym_score = max(1.0 - abs(symmetry - 1.0) / 0.4, 0.0)

    # R:R score: higher is better, max at 3.0.
    rr_score = min(rr / 3.0, 1.0)

    confidence = round(
        0.40 * fib_score + 0.35 * sym_score + 0.25 * rr_score,
        3,
    )

    # ---- Explanation ----
    direction = "bullish" if side == "long" else "bearish"
    explanation = (
        f"{symbol} ABCD Pattern signal ({side.upper()}): {direction} swing structure detected — "
        f"A=₹{point_a:.2f} ({a_swing['type']}), B=₹{point_b:.2f} ({b_swing['type']}), "
        f"C=₹{point_c:.2f} ({c_swing['type']}). "
        f"BC retraced {retracement*100:.1f}% of AB (Fib zone {min_retracement*100:.1f}%–{max_retracement*100:.1f}%). "
        f"Projected D=₹{point_d:.2f} (AB/CD symmetry: {symmetry:.2f}). "
        f"Entry ₹{entry:.2f}, SL ₹{stop_loss:.2f} (C {'−' if side == 'long' else '+'} 1×ATR), "
        f"Target ₹{target:.2f} (point D). R:R = 1:{rr:.1f}."
    )

    caveats = [
        "ABCD is a geometric pattern — D is a projected target, not guaranteed.",
        f"Fib retracement is {retracement*100:.1f}% — 50% is ideal; deviations reduce reliability.",
        f"AB/CD symmetry is {symmetry:.2f} — patterns with symmetry near 1.0 are most reliable.",
        "If price breaks beyond point C, the pattern is invalid — exit immediately.",
    ]

    return AbcdSignal(
        symbol=symbol,
        side=side,
        entry=round(entry, 2),
        stop_loss=round(stop_loss, 2),
        target=round(target, 2),
        risk_reward=round(rr, 2),
        confidence=confidence,
        last_price=round(last_close, 2),
        point_a=round(point_a, 2),
        point_b=round(point_b, 2),
        point_c=round(point_c, 2),
        point_d=round(point_d, 2),
        fib_retracement=round(retracement, 4),
        ab_length=round(ab_length, 2),
        cd_length=round(cd_length, 2),
        symmetry=round(symmetry, 3),
        atr=round(atr_val, 2),
        explanation=explanation,
        caveats=caveats,
    )
