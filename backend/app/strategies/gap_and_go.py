"""Gap-and-Go — gap-up momentum breakout strategy.

A classic intraday setup: stock gaps significantly at the open (>2%)
with above-average volume, then breaks out of the opening range in the
direction of the gap. This generates actual trade signals with entry,
stop, and targets — unlike the gap scanner which only reports gaps.

Key parameters (from risk management principles):
  - Minimum gap %:         2.0% (above previous close)
  - Minimum volume ratio:  2.0x (strong conviction on the gap)
  - OR window:              09:15–09:30 (15-min opening range, NSE)
  - Target 1:               Previous close (gap fill) if favorable
  - Target 2:               Entry + 2R (measured move)
  - Stop:                   OR low (long) / OR high (short)

Entry logic (long — mirror for short):
  1. Stock gaps up >2% at the open (first bar close vs prev daily close).
  2. Gap volume >= 2x average daily volume.
  3. First 5-min bar after 09:30 closes ABOVE OR-high (breakout confirms).
  4. Entry = breakout bar close; SL = OR low; T1 = prev close (gap fill);
     T2 = entry + 2R.

Skip conditions:
  - Gap is in the wrong direction (gap down + breakout up = counter-trend).
  - No opening range established yet (before 09:30).
  - Breakout bar doesn't clear the OR high/low.
"""
from __future__ import annotations

from dataclasses import dataclass, field

import pandas as pd

from app import indicators as ind


@dataclass
class GapAndGoSignal:
    symbol: str
    side: str                 # "long" | "short"
    entry: float
    stop_loss: float
    target1: float
    target2: float
    risk_reward: float
    confidence: float
    last_price: float
    gap_pct: float             # gap size as fraction (e.g. 0.025 = 2.5%)
    volume_ratio: float
    or_high: float
    or_low: float
    prev_close: float
    breakout_bar_close: float
    explanation: str
    caveats: list[str] = field(default_factory=list)


def evaluate_gap_and_go(
    symbol: str,
    daily: pd.DataFrame,
    intraday: pd.DataFrame,
    min_gap_pct: float = 0.02,
    min_volume_ratio: float = 2.0,
    min_rr: float = 1.5,
    atr_period: int = 14,
) -> GapAndGoSignal | None:
    """Evaluate a stock for a Gap-and-Go signal.

    Args:
        symbol: stock symbol (e.g. "RELIANCE").
        daily: daily OHLCV (used for prev close + ATR + avg volume).
        intraday: intraday 5-min OHLCV, tz-aware index.
        min_gap_pct: minimum gap size as fraction (0.02 = 2%).
        min_volume_ratio: minimum gap-bar volume / avg volume.
        min_rr: minimum risk:reward ratio for target 2.
        atr_period: ATR lookback (on daily bars).

    Returns:
        GapAndGoSignal if conditions are met, None otherwise.
    """
    if intraday is None or intraday.empty or len(intraday) < 5:
        return None
    if daily is None or daily.empty or len(daily) < 3:
        return None

    # Previous close (last completed daily bar).
    prev_close = float(daily["Close"].iloc[-1])
    if prev_close <= 0:
        return None

    # ATR for context (daily).
    atr_val = float(ind.atr(daily, atr_period).iloc[-1]) if len(daily) >= atr_period else 0.0
    if atr_val <= 0:
        return None

    # Average volume from intraday bars (for comparing gap bar and breakout bar).
    avg_vol = ind.avg_volume(intraday, 20)
    if avg_vol <= 0:
        return None

    # ---- Detect gap: first intraday bar's open vs prev close ----
    first_bar = intraday.iloc[0]
    first_open = float(first_bar["Open"])
    first_close = float(first_bar["Close"])
    first_volume = float(first_bar["Volume"])

    gap = first_open - prev_close
    gap_pct = gap / prev_close if prev_close > 0 else 0.0

    # Gap must be significant in either direction.
    if abs(gap_pct) < min_gap_pct:
        return None

    # Volume on the gap bar must be above average.
    vol_ratio = first_volume / avg_vol if avg_vol > 0 else 0.0
    if vol_ratio < min_volume_ratio:
        return None

    # Determine gap direction.
    gap_up = gap_pct > 0

    # ---- Opening range (09:15–09:30 NSE) ----
    or_result = ind.opening_range(intraday, "09:15", "09:30")
    if or_result is None:
        return None
    or_high, or_low = or_result

    # ---- Breakout bar: first 5-min bar after 09:30 that breaks OR ----
    breakout = ind.breakout_bar(intraday, or_high, or_low, avg_vol, 1.0)
    if breakout is None:
        return None

    breakout_close = breakout["close"]

    # ---- Direction logic: gap direction must match breakout direction ----
    # Long: gap up + breakout above OR high.
    # Short: gap down + breakout below OR low.
    # Note: breakout_bar() only finds breakouts ABOVE or_high. For shorts,
    # we need to check if the bar closed below or_low.
    if gap_up:
        side = "long"
        # Breakout bar must close above OR high.
        if breakout_close <= or_high:
            return None
    else:
        side = "short"
        # For shorts, we need a bar that closes below OR low.
        # breakout_bar() only returns upside breakouts, so we scan manually.
        breakout = None
        local = intraday.index
        tz = local.tz
        if tz is None:
            return None
        times = local.tz_convert("Asia/Kolkata").time if hasattr(local, "tz_convert") else local.time
        after_or = intraday[pd.Series(times, index=intraday.index) >= pd.to_datetime("09:30", format="%H:%M").time()]
        for ts, row in after_or.iterrows():
            if float(row["Close"]) < or_low and float(row["Volume"]) >= 1.0 * avg_vol:
                breakout = {
                    "ts": str(ts),
                    "close": float(row["Close"]),
                    "high": float(row["High"]),
                    "low": float(row["Low"]),
                    "volume": float(row["Volume"]),
                    "volume_ratio": float(row["Volume"] / avg_vol),
                }
                break
        if breakout is None:
            return None
        breakout_close = breakout["close"]

    # ---- Entry, stop, targets ----
    entry = breakout_close
    if side == "long":
        stop_loss = or_low
        risk = abs(entry - stop_loss)
        if risk <= 0:
            return None
        # T1: previous close (gap fill target) — only if it's above entry.
        # If prev close is below entry, the gap already filled; use 1R.
        target1 = prev_close if prev_close > entry else entry + risk
        target2 = entry + 2.0 * risk
    else:
        stop_loss = or_high
        risk = abs(stop_loss - entry)
        if risk <= 0:
            return None
        # T1: previous close (gap fill) — only if below entry.
        target1 = prev_close if prev_close < entry else entry - risk
        target2 = entry - 2.0 * risk

    rr = abs(target2 - entry) / risk
    if rr < min_rr - 1e-9:
        return None

    # ---- Confidence: 40% gap size + 35% volume ratio + 25% breakout strength ----
    gap_score = min(abs(gap_pct) / 0.06, 1.0)  # 6% gap = max score
    vol_score = min(vol_ratio / 5.0, 1.0)  # 5x volume = max score
    # Breakout strength: how far breakout close is beyond the OR boundary.
    breakout_strength = abs(breakout_close - (or_high if side == "long" else or_low)) / risk
    breakout_score = min(breakout_strength, 1.0)

    confidence = round(
        0.40 * gap_score + 0.35 * vol_score + 0.25 * breakout_score,
        3,
    )

    # ---- Explanation ----
    direction = "gap up" if gap_up else "gap down"
    explanation = (
        f"{symbol} Gap-and-Go signal ({side.upper()}): {direction} {abs(gap_pct)*100:.1f}% "
        f"at open (₹{first_open:.2f} vs prev close ₹{prev_close:.2f}) on {vol_ratio:.1f}x volume. "
        f"Opening range ₹{or_low:.2f}–₹{or_high:.2f}. Breakout bar closed at ₹{breakout_close:.2f} "
        f"{'above OR high' if side == 'long' else 'below OR low'}. "
        f"Entry ₹{entry:.2f}, SL ₹{stop_loss:.2f} (OR {'low' if side == 'long' else 'high'}), "
        f"T1 ₹{target1:.2f} (prev close), T2 ₹{target2:.2f} (2R). R:R = 1:{rr:.1f}."
    )

    caveats = [
        "Gap-and-Go is a momentum play — gaps can fade quickly if volume dries up.",
        f"Gap fill target (prev close ₹{prev_close:.2f}) may act as resistance/support.",
        "Best in the first 30 minutes of the session; avoid late-day gap breakouts.",
    ]

    return GapAndGoSignal(
        symbol=symbol,
        side=side,
        entry=round(entry, 2),
        stop_loss=round(stop_loss, 2),
        target1=round(target1, 2),
        target2=round(target2, 2),
        risk_reward=round(rr, 2),
        confidence=confidence,
        last_price=round(breakout_close, 2),
        gap_pct=round(gap_pct, 4),
        volume_ratio=round(vol_ratio, 2),
        or_high=round(or_high, 2),
        or_low=round(or_low, 2),
        prev_close=round(prev_close, 2),
        breakout_bar_close=round(breakout_close, 2),
        explanation=explanation,
        caveats=caveats,
    )
