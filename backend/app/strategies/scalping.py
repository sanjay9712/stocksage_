"""Scalping strategy — fast in-and-out trades on high-volume momentum stocks.

Unlike the intraday breakout strategy (which waits for an opening-range
breakout), scalping looks for candlestick pattern triggers throughout the
session with tight stops and small targets.

Key parameters (from risk management principles):
  - ATR multiple for stop-loss:  1.0x  (tight — scalpers cut losses fast)
  - ATR multiple for target:     1.5x  (R:R >= 1.5 required)
  - Minimum volume ratio:        1.5x  (needs above-average volume to enter)
  - Maximum hold bars:           ~6 candles (30 min on 5-min bars)

Entry logic:
  1. Stock must be in an intraday uptrend (price above 20-EMA on intraday).
  2. A bullish candlestick pattern fired on the most recent bar
     (engulfing, hammer, morning star, three white soldiers, piercing line, etc.).
  3. Volume on the signal bar >= 1.5x average volume.
  4. Entry = signal bar's close; SL = entry - 1xATR; target = entry + 1.5xATR.

Short scalps are the mirror image (bearish pattern + downtrend).
"""
from __future__ import annotations

from dataclasses import dataclass, field

import pandas as pd

from app import indicators as ind
from app.strategies.candlestick import detect_patterns, net_bias, PatternHit


@dataclass
class ScalpSignal:
    symbol: str
    side: str                # "long" | "short"
    entry: float
    stop_loss: float
    target: float
    risk_reward: float
    confidence: float
    last_price: float
    atr: float
    volume_ratio: float
    trend: str               # "uptrend" | "downtrend" | "sideways"
    patterns: list[dict]     # detected candlestick patterns [{name, bias, strength, description}]
    pattern_bias: str        # net aggregated bias
    explanation: str         # plain-English summary
    # Murphy confirmation indicators (enhanced scalping).
    stochastic_k: float = 0.0
    stochastic_signal: str = "neutral"   # "oversold_exit" | "overbought_exit" | "neutral"
    macd_histogram: float = 0.0
    adx_value: float = 0.0
    caveats: list[str] = field(default_factory=list)


# Only fire on patterns with directional conviction (not neutral doji/spinning top).
_DIRECITIONAL_PATTERNS = {
    "Bullish Engulfing", "Hammer", "Morning Star", "Three White Soldiers",
    "Piercing Line", "Bullish Harami", "Tweezer Bottoms", "Bullish Marubozu",
    "Bearish Engulfing", "Shooting Star", "Evening Star", "Three Black Crows",
    "Dark Cloud Cover", "Bearish Harami", "Tweezer Tops", "Bearish Marubozu",
}


def evaluate_scalp(
    symbol: str,
    daily: pd.DataFrame,
    intraday: pd.DataFrame,
    min_volume_ratio: float = 1.5,
    min_rr: float = 1.5,
    atr_period: int = 14,
    ema_period: int = 20,
) -> ScalpSignal | None:
    """Evaluate a stock for a scalping signal.

    Args:
        symbol: stock symbol (e.g. "RELIANCE").
        daily: daily OHLCV (used for ATR context + daily trend).
        intraday: intraday 5-min OHLCV, tz-aware index.
        min_volume_ratio: minimum volume/volume-avg ratio on signal bar.
        min_rr: minimum risk:reward ratio to emit a signal.
        atr_period: ATR lookback (on daily bars).
        ema_period: EMA period for trend filter (on intraday bars).

    Returns:
        ScalpSignal if conditions are met, None otherwise.
    """
    if intraday is None or intraday.empty or len(intraday) < ema_period + 2:
        return None
    if daily is None or daily.empty:
        return None

    # Compute ATR from daily bars (more stable than intraday ATR).
    atr_series = ind.atr(daily, atr_period)
    atr_val = float(atr_series.iloc[-1]) if len(atr_series) >= atr_period else 0.0
    if atr_val <= 0:
        return None

    # Average volume from intraday (last 20 bars excluding current).
    avg_vol = ind.avg_volume(intraday, 20)

    # Trend filter: intraday EMA.
    ema = ind.ema(intraday["Close"], ema_period)
    last_close = float(intraday["Close"].iloc[-1])
    ema_val = float(ema.iloc[-1]) if len(ema) >= ema_period else last_close

    if last_close > ema_val:
        trend = "uptrend"
    elif last_close < ema_val:
        trend = "downtrend"
    else:
        trend = "sideways"

    # Detect candlestick patterns on the last 5 intraday bars.
    recent = intraday.tail(5)
    hits = detect_patterns(recent, lookback=5)

    # Filter to directional patterns only.
    directional = [h for h in hits if h.name in _DIRECITIONAL_PATTERNS]
    if not directional:
        return None

    bias = net_bias(directional)
    if bias == "neutral":
        return None

    # Volume on the signal bar (most recent bar).
    signal_bar = intraday.iloc[-1]
    signal_vol = float(signal_bar["Volume"])
    vol_ratio = signal_vol / avg_vol if avg_vol > 0 else 0.0
    if vol_ratio < min_volume_ratio:
        return None

    # Pattern must align with the trend (bullish pattern in uptrend, etc.).
    if bias == "bullish" and trend == "uptrend":
        side = "long"
    elif bias == "bearish" and trend == "downtrend":
        side = "short"
    else:
        # Pattern against the trend — skip (counter-trend scalps are risky).
        return None

    # ---- Murphy confirmation: Stochastic, MACD, ADX ----
    # Need enough intraday bars for indicator computation.
    stoch_k_val = 0.0
    stoch_sig = "neutral"
    macd_hist_val = 0.0
    adx_val = 0.0
    stoch_confirms = True
    macd_confirms = True

    if len(intraday) >= 35:
        high_s = intraday["High"]
        low_s = intraday["Low"]
        close_s = intraday["Close"]

        # Stochastic oscillator — Murphy: buy when %K crosses above %D from
        # oversold zone (<20); sell when %K crosses below %D from overbought
        # (>80).
        try:
            st = ind.stochastic(high_s, low_s, close_s)
            stoch_k_series = st["k"]
            stoch_d_series = st["d"]
            if len(stoch_k_series) >= 2 and not stoch_k_series.iloc[-1] != stoch_k_series.iloc[-1]:
                stoch_k_val = float(stoch_k_series.iloc[-1])
                prev_k = float(stoch_k_series.iloc[-2])
                stoch_d_val = float(stoch_d_series.iloc[-1])
                prev_d = float(stoch_d_series.iloc[-2])

                if side == "long":
                    # Bullish confirmation: %K crossing above %D from oversold.
                    if prev_k < prev_d and stoch_k_val > stoch_d_val and prev_k < 20:
                        stoch_sig = "oversold_exit"
                    elif stoch_k_val < 20:
                        stoch_sig = "oversold_exit"  # still in oversold, early entry
                    else:
                        stoch_sig = "neutral"
                        stoch_confirms = False
                else:
                    # Bearish confirmation: %K crossing below %D from overbought.
                    if prev_k > prev_d and stoch_k_val < stoch_d_val and prev_k > 80:
                        stoch_sig = "overbought_exit"
                    elif stoch_k_val > 80:
                        stoch_sig = "overbought_exit"  # still overbought
                    else:
                        stoch_sig = "neutral"
                        stoch_confirms = False
        except Exception:
            stoch_confirms = False

        # MACD histogram — Murphy: buy when histogram >0 and rising; sell
        # when histogram <0 and falling.
        try:
            macd_res = ind.macd(close_s)
            hist_series = macd_res["histogram"]
            if len(hist_series) >= 2:
                macd_hist_val = float(hist_series.iloc[-1])
                prev_hist = float(hist_series.iloc[-2])
                if side == "long":
                    if macd_hist_val <= 0 or macd_hist_val < prev_hist:
                        macd_confirms = False
                else:
                    if macd_hist_val >= 0 or macd_hist_val > prev_hist:
                        macd_confirms = False
        except Exception:
            macd_confirms = False

        # ADX — Murphy: only trade when ADX > 20 (market is trending).
        try:
            adx_res = ind.adx(intraday, 14)
            adx_series = adx_res["adx"]
            if len(adx_series) >= 1:
                adx_val = float(adx_series.iloc[-1])
        except Exception:
            adx_val = 0.0

    # Murphy: if ADX < 20, market is not trending — skip the scalp entirely.
    if adx_val > 0 and adx_val < 20:
        return None

    # Compute entry, SL, target.
    entry = last_close
    if side == "long":
        stop_loss = entry - atr_val
        target = entry + 1.5 * atr_val
    else:
        stop_loss = entry + atr_val
        target = entry - 1.5 * atr_val

    risk = abs(entry - stop_loss)
    reward = abs(target - entry)
    rr = reward / risk if risk > 0 else 0.0
    if rr < min_rr:
        return None

    # Confidence: enhanced formula with Murphy confirmation.
    # 30% pattern + 25% volume + 20% trend + 15% stochastic + 10% MACD
    strong_count = sum(1 for h in directional if h.strength == "strong")
    moderate_count = sum(1 for h in directional if h.strength == "moderate")
    pattern_score = min((strong_count * 1.0 + moderate_count * 0.5) / 2.0, 1.0)
    vol_score = min(vol_ratio / 3.0, 1.0)
    trend_score = 1.0  # already confirmed alignment
    stoch_score = 1.0 if stoch_confirms else 0.0
    macd_score = 1.0 if macd_confirms else 0.0
    confidence = round(
        0.30 * pattern_score + 0.25 * vol_score + 0.20 * trend_score
        + 0.15 * stoch_score + 0.10 * macd_score,
        3,
    )
    # Murphy: if Stochastic or MACD don't confirm, reduce confidence by 30%.
    if not stoch_confirms or not macd_confirms:
        confidence = round(confidence * 0.7, 3)

    # Build explanation.
    pattern_names = ", ".join(f"{h.name} ({h.strength})" for h in directional)
    direction = "bullish" if side == "long" else "bearish"
    stoch_str = f"%K={stoch_k_val:.1f} ({stoch_sig})" if stoch_k_val > 0 else "N/A"
    macd_str = f"hist={macd_hist_val:.4f}" if macd_hist_val != 0 else "N/A"
    explanation = (
        f"{symbol} scalping signal ({side.upper()}): {trend} confirmed by "
        f"{ema_period}-EMA on intraday. {direction.capitalize()} candlestick "
        f"pattern(s) detected: {pattern_names}. Volume {vol_ratio:.1f}x average. "
        f"Stochastic {stoch_str}, MACD {macd_str}, ADX={adx_val:.1f}. "
        f"Entry ₹{entry:.2f}, SL ₹{stop_loss:.2f} (1×ATR), target ₹{target:.2f} "
        f"(1.5×ATR). R:R = 1:{rr:.1f}."
    )

    caveats = [
        "Scalp trade — exit within 30 min if target/SL not hit.",
        f"ATR-based stop is tight ({atr_val:.2f}); expect noise.",
    ]
    if trend == "sideways":
        caveats.append("Trend is sideways — signal reliability reduced.")
    if not stoch_confirms:
        caveats.append("Stochastic does not confirm — reduced confidence.")
    if not macd_confirms:
        caveats.append("MACD histogram does not confirm direction.")
    if 20 <= adx_val < 25:
        caveats.append("ADX below 25 — weak trend, trade with caution.")

    return ScalpSignal(
        symbol=symbol,
        side=side,
        entry=round(entry, 2),
        stop_loss=round(stop_loss, 2),
        target=round(target, 2),
        risk_reward=round(rr, 2),
        confidence=confidence,
        last_price=last_close,
        atr=round(atr_val, 2),
        volume_ratio=round(vol_ratio, 2),
        trend=trend,
        patterns=[
            {
                "name": h.name,
                "bias": h.bias,
                "strength": h.strength,
                "description": h.description,
            }
            for h in directional
        ],
        pattern_bias=bias,
        explanation=explanation,
        caveats=caveats,
        stochastic_k=round(stoch_k_val, 2),
        stochastic_signal=stoch_sig,
        macd_histogram=round(macd_hist_val, 6),
        adx_value=round(adx_val, 2),
    )
