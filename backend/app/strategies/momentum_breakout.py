"""Momentum Breakout (Range Expansion) — RSI-filtered OR breakout strategy.

An enhancement over the basic Opening Range Breakout: requires RSI momentum
confirmation (RSI > 60 for longs, RSI < 40 for shorts) in addition to
volume breakout. Targets are based on volume profile (POC, VAH/VAL).

Key parameters (from risk management principles):
  - OR window:              09:15–09:30 (15-min opening range, NSE)
  - RSI threshold (long):   > 60 (momentum confirmation)
  - RSI threshold (short):  < 40 (momentum confirmation)
  - Volume ratio min:       1.5x (above-average volume on breakout bar)
  - Target 1:               Volume profile POC (Point of Control)
  - Target 2:               VAH (long) / VAL (short) or 2R
  - Stop:                   OR low (long) / OR high (short)

Entry logic (long — mirror for short):
  1. Price breaks above 15-min OR high with volume >= 1.5x average.
  2. RSI(14) > 60 (momentum is strong, not just a low-volume drift).
  3. Entry = breakout bar close; SL = OR low; T1 = POC;
     T2 = VAH or entry + 2R (whichever is further).

Skip conditions:
  - RSI in the 40-60 neutral zone (no momentum conviction).
  - Breakout bar volume below 1.5x average.
  - No opening range established yet (before 09:30).
"""
from __future__ import annotations

from dataclasses import dataclass, field

import pandas as pd

from app import indicators as ind


@dataclass
class MomentumBreakoutSignal:
    symbol: str
    side: str                 # "long" | "short"
    entry: float
    stop_loss: float
    target1: float
    target2: float
    risk_reward: float
    confidence: float
    last_price: float
    rsi: float
    volume_ratio: float
    or_high: float
    or_low: float
    poc_price: float          # Point of Control from volume profile
    vah: float                # Value Area High
    val: float                # Value Area Low
    explanation: str
    caveats: list[str] = field(default_factory=list)


def evaluate_momentum_breakout(
    symbol: str,
    daily: pd.DataFrame,
    intraday: pd.DataFrame,
    rsi_period: int = 14,
    rsi_long_min: float = 60.0,
    rsi_short_max: float = 40.0,
    min_volume_ratio: float = 1.5,
    min_rr: float = 1.5,
    atr_period: int = 14,
) -> MomentumBreakoutSignal | None:
    """Evaluate a stock for a Momentum Breakout signal.

    Args:
        symbol: stock symbol (e.g. "RELIANCE").
        daily: daily OHLCV (used for ATR context).
        intraday: intraday 5-min OHLCV, tz-aware index.
        rsi_period: RSI lookback period.
        rsi_long_min: minimum RSI for long signals.
        rsi_short_max: maximum RSI for short signals.
        min_volume_ratio: minimum volume/avg ratio on the breakout bar.
        min_rr: minimum risk:reward ratio for target 2.
        atr_period: ATR lookback (on daily bars).

    Returns:
        MomentumBreakoutSignal if conditions are met, None otherwise.
    """
    if intraday is None or intraday.empty or len(intraday) < rsi_period + 5:
        return None
    if daily is None or daily.empty:
        return None

    # ATR from daily bars.
    atr_val = float(ind.atr(daily, atr_period).iloc[-1]) if len(daily) >= atr_period else 0.0
    if atr_val <= 0:
        return None

    # ---- Opening range (09:15–09:30 NSE) ----
    or_result = ind.opening_range(intraday, "09:15", "09:30")
    if or_result is None:
        return None
    or_high, or_low = or_result

    # Average volume (intraday).
    avg_vol = ind.avg_volume(intraday, 20)
    if avg_vol <= 0:
        return None

    # ---- RSI momentum filter ----
    rsi_series = ind.rsi(intraday["Close"], rsi_period)
    rsi_val = float(rsi_series.iloc[-1]) if len(rsi_series) >= rsi_period else 50.0
    if pd.isna(rsi_val):
        return None

    # Determine direction based on RSI.
    if rsi_val > rsi_long_min:
        side = "long"
    elif rsi_val < rsi_short_max:
        side = "short"
    else:
        # RSI in neutral zone — no momentum conviction.
        return None

    # ---- Breakout bar detection ----
    local = intraday.index
    tz = local.tz
    if tz is None:
        return None
    times = local.tz_convert("Asia/Kolkata").time if hasattr(local, "tz_convert") else local.time
    after_or = intraday[pd.Series(times, index=intraday.index) >= pd.to_datetime("09:30", format="%H:%M").time()]

    breakout = None
    for ts, row in after_or.iterrows():
        bar_vol = float(row["Volume"])
        vol_ratio = bar_vol / avg_vol if avg_vol > 0 else 0.0
        if vol_ratio < min_volume_ratio:
            continue
        if side == "long" and float(row["Close"]) > or_high:
            breakout = {
                "ts": str(ts),
                "close": float(row["Close"]),
                "high": float(row["High"]),
                "low": float(row["Low"]),
                "volume": bar_vol,
                "volume_ratio": vol_ratio,
            }
            break
        if side == "short" and float(row["Close"]) < or_low:
            breakout = {
                "ts": str(ts),
                "close": float(row["Close"]),
                "high": float(row["High"]),
                "low": float(row["Low"]),
                "volume": bar_vol,
                "volume_ratio": vol_ratio,
            }
            break

    if breakout is None:
        return None

    breakout_close = breakout["close"]
    vol_ratio = breakout["volume_ratio"]

    # ---- Volume profile (for targets) ----
    vp = ind.volume_profile(intraday, bins=50, value_area_pct=0.70)
    poc_price = float(vp.get("poc_price", 0.0))
    vah = float(vp.get("vah", 0.0))
    val = float(vp.get("val", 0.0))

    # ---- Entry, stop, targets ----
    entry = breakout_close
    if side == "long":
        stop_loss = or_low
        risk = abs(entry - stop_loss)
        # Ensure minimum risk using ATR (tight OR ranges produce meaningless R:R).
        effective_risk = max(risk, 0.5 * atr_val)
        if risk <= 0:
            return None
        # T1: POC if above entry, else 1×effective_risk. Ensure at least 1×ATR from entry.
        raw_t1 = poc_price if poc_price > entry else entry + effective_risk
        target1 = max(raw_t1, entry + 1.0 * atr_val)
        # T2: VAH or 2R, whichever is further.
        target2_vp = vah if vah > entry + effective_risk else 0.0
        target2 = max(target2_vp, entry + 2.0 * effective_risk)
    else:
        stop_loss = or_high
        risk = abs(stop_loss - entry)
        effective_risk = max(risk, 0.5 * atr_val)
        if risk <= 0:
            return None
        # T1: POC if below entry, else 1×effective_risk below. Ensure at least 1×ATR from entry.
        raw_t1 = poc_price if 0 < poc_price < entry else entry - effective_risk
        target1 = min(raw_t1, entry - 1.0 * atr_val)
        # T2: VAL or 2R, whichever is further (lower).
        target2_vp = val if 0 < val < entry - effective_risk else 0.0
        target2 = min(target2_vp if target2_vp > 0 else float("inf"), entry - 2.0 * effective_risk)

    # R:R check against target1 (first exit point).
    rr = abs(target1 - entry) / effective_risk
    if rr < min_rr - 1e-9:
        return None

    # ---- Confidence: 30% RSI momentum + 30% volume + 25% breakout strength + 15% VP alignment ----
    # RSI momentum: how far RSI is beyond the threshold.
    if side == "long":
        rsi_score = min((rsi_val - rsi_long_min) / 30.0, 1.0)  # 30 points above = max
    else:
        rsi_score = min((rsi_short_max - rsi_val) / 30.0, 1.0)

    vol_score = min(vol_ratio / 4.0, 1.0)  # 4x volume = max

    # Breakout strength: how far breakout close is beyond OR boundary.
    breakout_dist = abs(breakout_close - (or_high if side == "long" else or_low))
    breakout_score = min(breakout_dist / risk, 1.0)

    # VP alignment: POC in the favorable direction (above entry for longs, below for shorts).
    vp_score = 0.0
    if side == "long" and poc_price > entry:
        vp_score = 1.0
    elif side == "short" and 0 < poc_price < entry:
        vp_score = 1.0
    # Bonus if VAH/VAL are in the favorable direction.
    if side == "long" and vah > entry:
        vp_score = min(vp_score + 0.5, 1.0)
    elif side == "short" and 0 < val < entry:
        vp_score = min(vp_score + 0.5, 1.0)

    confidence = round(
        0.30 * rsi_score + 0.30 * vol_score + 0.25 * breakout_score + 0.15 * vp_score,
        3,
    )

    # ---- Explanation ----
    explanation = (
        f"{symbol} Momentum Breakout signal ({side.upper()}): broke {'above OR high ₹' + format(or_high, '.2f') if side == 'long' else 'below OR low ₹' + format(or_low, '.2f')}. "
        f"RSI({rsi_period})={rsi_val:.1f} ({'strong momentum' if side == 'long' else 'weak momentum, oversold breakdown'}). "
        f"Volume {vol_ratio:.1f}x average. "
        f"Volume profile: POC ₹{poc_price:.2f}, VAH ₹{vah:.2f}, VAL ₹{val:.2f}. "
        f"Entry ₹{entry:.2f}, SL ₹{stop_loss:.2f} (OR {'low' if side == 'long' else 'high'}), "
        f"T1 ₹{target1:.2f} (POC/1×ATR), T2 ₹{target2:.2f} ({'VAH' if side == 'long' else 'VAL'}/2R). "
        f"R:R (to T1) = 1:{rr:.1f}."
    )

    caveats = [
        "Breakout trade — if price falls back inside the OR, exit immediately.",
        f"RSI={rsi_val:.1f} — momentum can fade; trail stops as price moves in your favor.",
        "Volume-profile targets are dynamic; POC may shift as the session progresses.",
    ]
    if rsi_val > 75 and side == "long":
        caveats.append("RSI above 75 — overbought, risk of pullback.")
    if rsi_val < 25 and side == "short":
        caveats.append("RSI below 25 — oversold, risk of bounce.")

    return MomentumBreakoutSignal(
        symbol=symbol,
        side=side,
        entry=round(entry, 2),
        stop_loss=round(stop_loss, 2),
        target1=round(target1, 2),
        target2=round(target2, 2),
        risk_reward=round(rr, 2),
        confidence=confidence,
        last_price=round(breakout_close, 2),
        rsi=round(rsi_val, 2),
        volume_ratio=round(vol_ratio, 2),
        or_high=round(or_high, 2),
        or_low=round(or_low, 2),
        poc_price=round(poc_price, 2),
        vah=round(vah, 2),
        val=round(val, 2),
        explanation=explanation,
        caveats=caveats,
    )
