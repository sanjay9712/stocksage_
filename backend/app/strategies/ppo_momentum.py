"""PPO (Percentage Price Oscillator) momentum scalping strategy.

PPO is a momentum oscillator expressing the difference between two moving
averages as a percentage of the slower average — comparable across securities
and price levels (unlike MACD which is dollar-based).

Key parameters (from risk management principles):
  - PPO fast/slow/signal:   12 / 26 / 9  (standard)
  - ATR multiple (stop):    1.0x (swing low/high of the signal bar)
  - ATR multiple (target):  1.5x (R:R >= 1.5 required)
  - Volume ratio minimum:   1.2x (mild volume confirmation)

Entry logic (long — mirror for short):
  1. PPO above zero (fast EMA > slow EMA — bullish momentum regime).
  2. PPO crosses above its signal line (momentum accelerating).
  3. Histogram expanding (confirmation).
  4. Entry = close of signal bar; SL = recent swing low; Target = 1.5R.
"""
from __future__ import annotations

from dataclasses import dataclass, field

import pandas as pd

from app import indicators as ind


@dataclass
class PpoSignal:
    symbol: str
    side: str                 # "long" | "short"
    entry: float
    stop_loss: float
    target: float
    risk_reward: float
    confidence: float
    last_price: float
    ppo_value: float
    signal_value: float
    histogram: float
    volume_ratio: float
    trend: str                # "uptrend" | "downtrend" | "sideways"
    swing_extreme: float      # swing low (long) or swing high (short) used for stop
    explanation: str
    caveats: list[str] = field(default_factory=list)


def evaluate_ppo(
    symbol: str,
    daily: pd.DataFrame,
    intraday: pd.DataFrame,
    fast: int = 12,
    slow: int = 26,
    signal: int = 9,
    min_volume_ratio: float = 1.2,
    min_rr: float = 1.5,
    atr_period: int = 14,
    swing_lookback: int = 5,
) -> PpoSignal | None:
    """Evaluate a stock for a PPO momentum signal.

    Args:
        symbol: stock symbol.
        daily: daily OHLCV (ATR context).
        intraday: intraday 5-min OHLCV.
        fast/slow/signal: PPO periods.
        min_volume_ratio: minimum volume/avg on the signal bar.
        min_rr: minimum risk:reward.
        atr_period: ATR lookback (on daily bars).
        swing_lookback: bars to scan for the swing low/high stop.

    Returns:
        PpoSignal if conditions are met, None otherwise.
    """
    if intraday is None or intraday.empty or len(intraday) < slow + signal + 2:
        return None
    if daily is None or daily.empty:
        return None

    atr_val = float(ind.atr(daily, atr_period).iloc[-1]) if len(daily) >= atr_period else 0.0
    if atr_val <= 0:
        return None

    ppo_res = ind.ppo(intraday["Close"], fast, slow, signal)
    ppo_line = ppo_res["ppo"]
    signal_line = ppo_res["signal"]
    histogram = ppo_res["histogram"]

    last_idx = intraday.index[-1]
    prev_idx = intraday.index[-2]
    ppo_val = float(ppo_line.iloc[-1])
    sig_val = float(signal_line.iloc[-1])
    hist_val = float(histogram.iloc[-1])
    ppo_prev = float(ppo_line.iloc[-2])
    sig_prev = float(signal_line.iloc[-2])

    if any(pd.isna(x) for x in (ppo_val, sig_val, hist_val, ppo_prev, sig_prev)):
        return None

    # Detect signal-line cross.
    crossed_up = ppo_prev <= sig_prev and ppo_val > sig_val
    crossed_down = ppo_prev >= sig_prev and ppo_val < sig_val

    side: str | None = None
    trend = "sideways"
    if crossed_up and ppo_val > 0:
        side = "long"
        trend = "uptrend"
    elif crossed_down and ppo_val < 0:
        side = "short"
        trend = "downtrend"
    else:
        return None

    # Histogram must be expanding in the trade direction (confirmation).
    if side == "long" and hist_val <= 0:
        return None
    if side == "short" and hist_val >= 0:
        return None

    # Volume confirmation.
    avg_vol = ind.avg_volume(intraday, 20)
    signal_vol = float(intraday["Volume"].iloc[-1])
    vol_ratio = signal_vol / avg_vol if avg_vol > 0 else 0.0
    if vol_ratio < min_volume_ratio:
        return None

    # Entry, stop (recent swing), target.
    last_close = float(intraday["Close"].iloc[-1])
    entry = last_close
    recent = intraday.tail(swing_lookback)
    if side == "long":
        swing = float(recent["Low"].min())
        stop_loss = swing - 0.05  # small buffer
        risk = abs(entry - stop_loss)
        target = entry + 1.5 * risk
    else:
        swing = float(recent["High"].max())
        stop_loss = swing + 0.05
        risk = abs(entry - stop_loss)
        target = entry - 1.5 * risk

    if risk <= 0:
        return None
    rr = abs(target - entry) / risk
    if rr < min_rr - 1e-9:  # tolerance for floating-point edge cases
        return None

    # Confidence: momentum strength, cross freshness, volume, histogram expansion.
    momentum_score = min(abs(ppo_val) / 2.0, 1.0)
    cross_score = 1.0  # fresh cross
    vol_score = min(vol_ratio / 3.0, 1.0)
    hist_score = min(abs(hist_val) / (abs(ppo_val) or 1.0), 1.0)
    confidence = round(0.35 * momentum_score + 0.25 * cross_score + 0.25 * vol_score + 0.15 * hist_score, 3)

    direction = "bullish" if side == "long" else "bearish"
    explanation = (
        f"{symbol} PPO momentum signal ({side.upper()}): PPO ({ppo_val:.2f}) "
        f"{'above' if side == 'long' else 'below'} zero with a fresh signal-line "
        f"cross {'up' if side == 'long' else 'down'} (signal {sig_val:.2f}). "
        f"Histogram expanding ({hist_val:.2f}) confirms {direction} momentum. "
        f"Volume {vol_ratio:.1f}x average. Entry ₹{entry:.2f}, SL ₹{stop_loss:.2f} "
        f"(recent swing {'low' if side == 'long' else 'high'}), Target ₹{target:.2f} "
        f"(1.5R). R:R = 1:{rr:.1f}."
    )

    caveats = [
        "Momentum scalp — exit within 30 min if momentum stalls (histogram flattens).",
        "Signal-line crosses can whipsaw in choppy markets — confirm with price structure.",
        f"ATR-based stop is tight ({atr_val:.2f}); expect noise.",
    ]

    return PpoSignal(
        symbol=symbol,
        side=side,
        entry=round(entry, 2),
        stop_loss=round(stop_loss, 2),
        target=round(target, 2),
        risk_reward=round(rr, 2),
        confidence=confidence,
        last_price=round(last_close, 2),
        ppo_value=round(ppo_val, 3),
        signal_value=round(sig_val, 3),
        histogram=round(hist_val, 3),
        volume_ratio=round(vol_ratio, 2),
        trend=trend,
        swing_extreme=round(swing, 2),
        explanation=explanation,
        caveats=caveats,
    )
