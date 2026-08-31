"""Bollinger Band squeeze breakout strategy.

A squeeze (band contraction) signals low volatility and an impending
expansion. When price breaks out of the compressed bands on volume, it
often trends in the breakout direction.

Key parameters (from risk management principles):
  - BB period:               20  (standard)
  - BB std-dev:              2.0 (standard)
  - Squeeze lookback:        50  (compare current bandwidth to recent min)
  - Volume ratio minimum:    1.5x (needs conviction on the breakout)
  - ATR multiple (stop):     1.0x (mid-band as structural stop)
  - Target:                  1.5x risk minimum

Entry logic (long — mirror for short):
  1. Bandwidth is in the lowest 20% of its recent range (squeeze).
  2. Current bar closes ABOVE the upper band with volume >= 1.5x average.
  3. Entry = close of breakout bar; SL = middle band (20 SMA);
     Target = entry + 1.5 x risk.
"""
from __future__ import annotations

from dataclasses import dataclass, field

import pandas as pd

from app import indicators as ind


@dataclass
class SqueezeSignal:
    symbol: str
    side: str                 # "long" | "short"
    entry: float
    stop_loss: float
    target: float
    risk_reward: float
    confidence: float
    last_price: float
    upper_band: float
    lower_band: float
    middle_band: float
    bandwidth: float
    squeeze_pct: float        # 0..1, lower = tighter squeeze
    volume_ratio: float
    trend: str                # "uptrend" | "downtrend" | "sideways"
    explanation: str
    caveats: list[str] = field(default_factory=list)


def evaluate_squeeze(
    symbol: str,
    daily: pd.DataFrame,
    intraday: pd.DataFrame,
    bb_period: int = 20,
    num_std: float = 2.0,
    squeeze_lookback: int = 50,
    min_volume_ratio: float = 1.0,
    min_rr: float = 1.5,
    atr_period: int = 14,
    squeeze_percentile: float = 0.25,
) -> SqueezeSignal | None:
    """Evaluate a stock for a Bollinger squeeze breakout signal.

    Args:
        symbol: stock symbol.
        daily: daily OHLCV (ATR context).
        intraday: intraday 5-min OHLCV.
        bb_period: Bollinger Band SMA period.
        num_std: number of std devs for the bands.
        squeeze_lookback: bars to compare bandwidth against for squeeze detection.
        min_volume_ratio: minimum volume/avg on the breakout bar.
        min_rr: minimum risk:reward.
        atr_period: ATR lookback (on daily bars).
        squeeze_percentile: bandwidth must be in this percentile of recent range.

    Returns:
        SqueezeSignal if conditions are met, None otherwise.
    """
    if intraday is None or intraday.empty or len(intraday) < bb_period + squeeze_lookback:
        return None
    if daily is None or daily.empty:
        return None

    atr_val = float(ind.atr(daily, atr_period).iloc[-1]) if len(daily) >= atr_period else 0.0
    if atr_val <= 0:
        return None

    bb = ind.bollinger_bands(intraday["Close"], bb_period, num_std)
    bandwidth = bb["bandwidth"]
    upper = bb["upper"]
    lower = bb["lower"]
    middle = bb["middle"]

    last_idx = intraday.index[-1]
    last_close = float(intraday["Close"].iloc[-1])
    upper_val = float(upper.iloc[-1])
    lower_val = float(lower.iloc[-1])
    middle_val = float(middle.iloc[-1])
    bw_val = float(bandwidth.iloc[-1])

    if any(pd.isna(x) for x in (upper_val, lower_val, middle_val, bw_val)):
        return None

    # Squeeze detection: the PREVIOUS bar's bandwidth must be in the lowest
    # `squeeze_percentile` of its recent range (the compression state leading
    # into the breakout). The current bar is the breakout itself, which by
    # definition expands the bands.
    if len(bandwidth) < 2 or pd.isna(bandwidth.iloc[-2]):
        return None
    bw_pre = float(bandwidth.iloc[-2])  # last compressed bar before breakout
    bw_window = bandwidth.iloc[-squeeze_lookback:-1].dropna()
    if len(bw_window) < 10:
        return None
    bw_min = float(bw_window.min())
    bw_max = float(bw_window.max())
    if bw_max <= bw_min:
        return None
    squeeze_pct = (bw_pre - bw_min) / (bw_max - bw_min)
    if squeeze_pct > squeeze_percentile:
        return None  # not compressed enough

    # Volume confirmation.
    avg_vol = ind.avg_volume(intraday, 20)
    signal_vol = float(intraday["Volume"].iloc[-1])
    vol_ratio = signal_vol / avg_vol if avg_vol > 0 else 0.0
    if vol_ratio < min_volume_ratio:
        return None

    curr = intraday.iloc[-1]
    is_bullish = curr["Close"] > curr["Open"]

    # Breakout direction.
    if last_close > upper_val and is_bullish:
        side = "long"
        trend = "uptrend"
    elif last_close < lower_val and not is_bullish:
        side = "short"
        trend = "downtrend"
    else:
        return None  # no breakout close

    entry = last_close
    if side == "long":
        stop_loss = middle_val
        risk = abs(entry - stop_loss)
        target = entry + 1.5 * risk
    else:
        stop_loss = middle_val
        risk = abs(entry - stop_loss)
        target = entry - 1.5 * risk

    if risk <= 0:
        return None
    rr = abs(target - entry) / risk
    if rr < min_rr - 1e-9:  # tolerance for floating-point edge cases
        return None

    # Confidence: squeeze tightness, volume, breakout strength.
    squeeze_score = 1.0 - squeeze_pct  # tighter = higher
    vol_score = min(vol_ratio / 3.0, 1.0)
    breakout_strength = min(abs(last_close - (upper_val if side == "long" else lower_val)) / (atr_val or 1.0), 1.0)
    confidence = round(0.4 * squeeze_score + 0.35 * vol_score + 0.25 * breakout_strength, 3)

    direction = "bullish" if side == "long" else "bearish"
    explanation = (
        f"{symbol} Bollinger squeeze breakout ({side.upper()}): bandwidth in the "
        f"lowest {squeeze_pct * 100:.0f}% of its {squeeze_lookback}-bar range "
        f"(squeeze). Price closed {direction} above the {num_std}-std upper band "
        f"on {vol_ratio:.1f}x volume. Entry ₹{entry:.2f}, SL ₹{stop_loss:.2f} "
        f"(20-SMA mid-band), Target ₹{target:.2f} (1.5R). R:R = 1:{rr:.1f}."
    )

    caveats = [
        "Squeeze breakouts can fail — exit if price closes back inside the band.",
        "Mid-band stop is structural; price may overshoot it in volatile moves.",
        "First 5 min of session excluded implicitly (needs bandwidth history).",
    ]

    return SqueezeSignal(
        symbol=symbol,
        side=side,
        entry=round(entry, 2),
        stop_loss=round(stop_loss, 2),
        target=round(target, 2),
        risk_reward=round(rr, 2),
        confidence=confidence,
        last_price=round(last_close, 2),
        upper_band=round(upper_val, 2),
        lower_band=round(lower_val, 2),
        middle_band=round(middle_val, 2),
        bandwidth=round(bw_val, 4),
        squeeze_pct=round(squeeze_pct, 3),
        volume_ratio=round(vol_ratio, 2),
        trend=trend,
        explanation=explanation,
        caveats=caveats,
    )
