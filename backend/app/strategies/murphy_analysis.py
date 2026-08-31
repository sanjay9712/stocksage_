"""Murphy multi-indicator analysis engine.

Implements the core principle from John J. Murphy's "Technical Analysis of
the Financial Markets": never trade on a single indicator — require
confirmation across four categories:

  1. Trend (30%)  — EMA stack, ADX, Supertrend
  2. Momentum (30%) — RSI, Stochastic, MACD histogram, Williams %R
  3. Volume (20%)  — OBV trend, volume ratio
  4. Support/Resistance (20%) — Fibonacci retracements, pivot points

A composite score (0-100) is computed and mapped to a verdict:
  >75 strong_buy, 60-74 buy, 45-59 hold, 30-44 avoid, <30 strong_avoid.
"""
from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field

import pandas as pd

from app import indicators as ind

log = logging.getLogger("murphy_analysis")


@dataclass
class MurphyAnalysis:
    symbol: str
    name: str
    last_price: float

    # Trend (3 indicators)
    trend_score: float
    trend_direction: str            # "bullish" | "bearish" | "neutral"
    ema_alignment: str              # "bullish_stack" | "bearish_stack" | "mixed"
    adx_value: float
    adx_strength: str              # "strong_trend" | "trending" | "weak"
    supertrend_dir: str             # "up" | "down"

    # Momentum (4 indicators)
    momentum_score: float
    rsi_value: float
    rsi_signal: str                 # "oversold" | "neutral" | "overbought"
    stochastic_k: float
    stochastic_signal: str          # "oversold" | "neutral" | "overbought"
    macd_histogram: float
    macd_signal: str                # "bullish_cross" | "bearish_cross" | "neutral"
    williams_r_value: float
    williams_r_signal: str          # "oversold" | "neutral" | "overbought"

    # Volume (2 indicators)
    volume_score: float
    obv_trend: str                  # "rising" | "falling" | "flat"
    volume_ratio: float

    # Support / Resistance
    fibonacci_levels: dict[str, float]
    nearest_support: float
    nearest_resistance: float
    pivot_levels: dict[str, float]
    price_vs_support: str           # "at_support" | "near_support" | "mid_range" | "at_resistance"

    # Composite
    composite_score: float
    verdict: str                    # "strong_buy" | "buy" | "hold" | "avoid" | "strong_avoid"

    # Entry / Exit
    entry: float
    stop_loss: float
    target1: float
    target2: float
    risk_reward: float
    atr_value: float

    # Breakdown
    factors: dict[str, float]       # {"trend": x, "momentum": x, "volume": x, "support_resistance": x}
    explanation: str
    caveats: list[str] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Scoring functions
# ---------------------------------------------------------------------------

def _score_trend(ema20, ema50, ema200, last_close, adx_val, st_dir) -> tuple[float, dict]:
    """Score trend category (0-100). Murphy: trade with the trend."""
    score = 0.0
    details = {}

    # EMA alignment (40 points)
    if ema20 > ema50 > ema200:
        score += 40
        details["ema_alignment"] = "bullish_stack"
        if last_close > ema20:
            score += 5  # price above all EMAs = strong uptrend
    elif ema20 < ema50 < ema200:
        score += 20  # bearish stack — still a strong trend, just down
        details["ema_alignment"] = "bearish_stack"
    else:
        score += 10
        details["ema_alignment"] = "mixed"

    # ADX trend strength (35 points)
    if adx_val > 25:
        score += 35
        details["adx"] = "strong_trend"
    elif adx_val > 20:
        score += 25
        details["adx"] = "trending"
    else:
        score += 5
        details["adx"] = "weak"

    # Supertrend direction (20 points)
    if st_dir == "up":
        score += 20
        details["supertrend"] = "up"
    else:
        details["supertrend"] = "down"

    return min(score, 100.0), details


def _score_momentum(rsi_val, stoch_k, stoch_d, macd_hist, wr_val, prev_macd_hist) -> tuple[float, dict]:
    """Score momentum category (0-100). Murphy: use oscillators for timing."""
    score = 0.0
    details = {}

    # RSI (25 points) — Murphy: 40-60 neutral rising is ideal for buying
    if 40 <= rsi_val <= 60:
        score += 25  # neutral — room to run
    elif 30 <= rsi_val < 40:
        score += 22  # oversold zone — potential reversal
    elif 60 < rsi_val <= 70:
        score += 15  # getting overbought
    elif rsi_val < 30:
        score += 20  # oversold — bounce likely
    elif rsi_val > 70:
        score += 5   # overbought — caution
    details["rsi"] = rsi_val

    # Stochastic (25 points)
    if stoch_k < 20:
        score += 20  # oversold
        if stoch_k > stoch_d:
            score += 5  # bullish cross from oversold
        details["stochastic"] = "oversold"
    elif stoch_k > 80:
        score += 5   # overbought
        if stoch_k < stoch_d:
            score += 0  # bearish cross from overbought — no bonus for buys
        details["stochastic"] = "overbought"
    else:
        score += 12
        if stoch_k > stoch_d:
            score += 3  # rising in neutral
        details["stochastic"] = "neutral"

    # MACD histogram (25 points)
    if macd_hist > 0 and macd_hist > prev_macd_hist:
        score += 25  # bullish and expanding
    elif macd_hist > 0:
        score += 15  # bullish but contracting
    elif macd_hist < 0 and macd_hist > prev_macd_hist:
        score += 10  # bearish but improving
    else:
        score += 3   # bearish and worsening
    details["macd_hist"] = macd_hist

    # Williams %R (25 points)
    if -80 <= wr_val < -50:
        score += 22  # oversold to neutral — good entry zone
    elif -50 <= wr_val <= -20:
        score += 10  # neutral
    elif wr_val < -80:
        score += 18  # deeply oversold
    elif wr_val > -20:
        score += 3   # overbought
    details["williams_r"] = wr_val

    return min(score, 100.0), details


def _score_volume(obv_series, volume_ratio, last_close) -> tuple[float, dict]:
    """Score volume category (0-100). Murphy: volume confirms price moves."""
    score = 0.0
    details = {}

    # OBV trend (50 points)
    if len(obv_series) >= 10:
        obv_now = float(obv_series.iloc[-1])
        obv_prev = float(obv_series.iloc[-10])
        if obv_now > obv_prev:
            score += 50  # rising OBV = accumulation
            details["obv"] = "rising"
        elif obv_now < obv_prev:
            score += 15  # falling OBV = distribution
            details["obv"] = "falling"
        else:
            score += 25
            details["obv"] = "flat"
    else:
        score += 25
        details["obv"] = "insufficient_data"

    # Volume ratio (50 points) — Murphy: volume must confirm the move.
    # Below-average volume means low conviction, even if OBV is rising.
    if volume_ratio >= 2.0:
        score += 50
    elif volume_ratio >= 1.5:
        score += 40
    elif volume_ratio >= 1.2:
        score += 25
    elif volume_ratio >= 0.8:
        score += 10
    else:
        score += 2   # well below average — almost no conviction
    details["volume_ratio"] = volume_ratio

    return min(score, 100.0), details


def _score_support_resistance(last_close, fib_levels, piv_levels) -> tuple[float, dict]:
    """Score S/R category (0-100). Murphy: buy near support, sell near resistance."""
    score = 0.0
    details = {}

    # Nearest support and resistance from Fibonacci + Pivots
    all_levels = []
    for label, price in fib_levels.items():
        all_levels.append(("fib_" + label, price))
    for label, price in piv_levels.items():
        all_levels.append(("piv_" + label, price))

    if not all_levels:
        return 50.0, {"note": "no_levels"}

    supports = [(n, p) for n, p in all_levels if p < last_close]
    resistances = [(n, p) for n, p in all_levels if p > last_close]

    nearest_support = max(supports, key=lambda x: x[1])[1] if supports else last_close * 0.95
    nearest_resistance = min(resistances, key=lambda x: x[1])[1] if resistances else last_close * 1.05

    # Position within range
    if nearest_support > 0 and nearest_resistance > nearest_support:
        position = (last_close - nearest_support) / (nearest_resistance - nearest_support)
    else:
        position = 0.5

    # Detect broken support: if price is below the previous day's low (fib 0.0),
    # the stock has broken through support — bearish, not a buy.
    fib_low = fib_levels.get("0.0", 0)
    fib_high = fib_levels.get("1.0", float("inf"))

    if last_close < fib_low:
        # Price below the entire previous range — broken support.
        score += 15  # bearish — support has failed
        details["position"] = "below_support"
    elif last_close > fib_high:
        # Price above the entire previous range — broken resistance (bullish).
        score += 60  # breakout above resistance
        details["position"] = "above_resistance"
    elif position <= 0.2:
        score += 90  # at support
        details["position"] = "at_support"
    elif position <= 0.4:
        score += 70  # near support
        details["position"] = "near_support"
    elif position <= 0.6:
        score += 50  # mid-range
        details["position"] = "mid_range"
    elif position <= 0.8:
        score += 30  # near resistance
        details["position"] = "near_resistance"
    else:
        score += 10  # at resistance
        details["position"] = "at_resistance"

    details["nearest_support"] = nearest_support
    details["nearest_resistance"] = nearest_resistance

    return min(score, 100.0), details


def _compute_entry_exit(last_close, nearest_support, nearest_resistance, atr_val, fib_levels, piv_levels):
    """Compute entry, stop-loss, and targets using Murphy's methodology.

    Guarantees a minimum R:R of 1.5 by adjusting both target and stop-loss.
    Murphy: risk:reward must be at least 1:1.5.
    """
    # Entry = current close (buy at market)
    entry = last_close

    # Stop-loss = below nearest support minus 0.5×ATR.
    # Cap the risk to 1.5×ATR (if support is far away) and ensure at least
    # 0.75×ATR (so stop isn't too tight — intraday noise).
    raw_stop = nearest_support - 0.5 * atr_val if nearest_support > 0 else entry - 1.0 * atr_val
    max_risk = 1.5 * atr_val
    min_risk = 0.75 * atr_val
    if entry - raw_stop > max_risk:
        stop_loss = entry - max_risk
    elif entry - raw_stop < min_risk:
        stop_loss = entry - min_risk
    else:
        stop_loss = raw_stop

    # Target1 = nearest resistance, but at least 1.5×risk above entry.
    risk = abs(entry - stop_loss)
    min_reward = 1.5 * risk
    min_target = entry + min_reward
    target1 = max(
        nearest_resistance if nearest_resistance > entry else min_target,
        min_target,
    )

    # Target2 = next resistance level (pivot R2 or fib 1.0 = prev_high)
    target2 = max(
        fib_levels.get("1.0", entry + 3 * atr_val),
        piv_levels.get("r2", entry + 3 * atr_val),
    )
    if target2 <= target1:
        target2 = target1 + 1.5 * atr_val

    reward = abs(target1 - entry)
    rr = reward / risk if risk > 0 else 0.0

    return entry, stop_loss, target1, target2, rr


# ---------------------------------------------------------------------------
# Main analysis function
# ---------------------------------------------------------------------------

def analyze_data(symbol: str, name: str, df: pd.DataFrame) -> MurphyAnalysis | None:
    """Analyze a daily OHLCV DataFrame using Murphy's multi-indicator methodology.

    Requires at least 200 bars for EMA-200 + ADX + Stochastic to be valid.
    Returns None on insufficient data.
    """
    if df is None or df.empty or len(df) < 60:
        return None

    close = df["Close"]
    high = df["High"]
    low = df["Low"]
    volume = df["Volume"].astype(float)
    last_close = float(close.iloc[-1])

    # --- Trend indicators ---
    ema20 = float(ind.ema(close, 20).iloc[-1]) if len(close) >= 20 else last_close
    ema50 = float(ind.ema(close, 50).iloc[-1]) if len(close) >= 50 else last_close
    ema200 = float(ind.ema(close, 200).iloc[-1]) if len(close) >= 200 else last_close

    adx_data = ind.adx(df, 14) if len(df) >= 28 else None
    adx_val = float(adx_data["adx"].iloc[-1]) if adx_data is not None and not pd.isna(adx_data["adx"].iloc[-1]) else 0.0

    st_series = ind.supertrend(df, 10, 3.0) if len(df) >= 12 else None
    st_val = float(st_series.iloc[-1]) if st_series is not None and not pd.isna(st_series.iloc[-1]) else last_close
    st_dir = "up" if last_close > st_val else "down"

    trend_score, trend_details = _score_trend(ema20, ema50, ema200, last_close, adx_val, st_dir)

    if ema20 > ema50 > ema200:
        trend_direction = "bullish"
    elif ema20 < ema50 < ema200:
        trend_direction = "bearish"
    else:
        trend_direction = "neutral"

    if adx_val > 25:
        adx_strength = "strong_trend"
    elif adx_val > 20:
        adx_strength = "trending"
    else:
        adx_strength = "weak"

    # --- Momentum indicators ---
    rsi_series = ind.rsi(close, 14) if len(close) >= 28 else None
    rsi_val = float(rsi_series.iloc[-1]) if rsi_series is not None and not pd.isna(rsi_series.iloc[-1]) else 50.0
    if rsi_val < 30:
        rsi_signal = "oversold"
    elif rsi_val > 70:
        rsi_signal = "overbought"
    else:
        rsi_signal = "neutral"

    stoch_data = ind.stochastic(high, low, close, 14, 3) if len(df) >= 17 else None
    stoch_k = float(stoch_data["k"].iloc[-1]) if stoch_data is not None and not pd.isna(stoch_data["k"].iloc[-1]) else 50.0
    stoch_d = float(stoch_data["d"].iloc[-1]) if stoch_data is not None and not pd.isna(stoch_data["d"].iloc[-1]) else 50.0
    if stoch_k < 20:
        stoch_signal = "oversold"
    elif stoch_k > 80:
        stoch_signal = "overbought"
    else:
        stoch_signal = "neutral"

    macd_data = ind.macd(close, 12, 26, 9) if len(close) >= 35 else None
    macd_hist = float(macd_data["histogram"].iloc[-1]) if macd_data is not None and not pd.isna(macd_data["histogram"].iloc[-1]) else 0.0
    prev_macd_hist = float(macd_data["histogram"].iloc[-2]) if macd_data is not None and len(macd_data["histogram"]) >= 2 and not pd.isna(macd_data["histogram"].iloc[-2]) else macd_hist
    if macd_hist > 0 and prev_macd_hist <= 0:
        macd_signal = "bullish_cross"
    elif macd_hist < 0 and prev_macd_hist >= 0:
        macd_signal = "bearish_cross"
    elif macd_hist > 0:
        macd_signal = "bullish"
    else:
        macd_signal = "bearish"

    wr_series = ind.williams_r(high, low, close, 14) if len(df) >= 15 else None
    wr_val = float(wr_series.iloc[-1]) if wr_series is not None and not pd.isna(wr_series.iloc[-1]) else -50.0
    if wr_val < -80:
        wr_signal = "oversold"
    elif wr_val > -20:
        wr_signal = "overbought"
    else:
        wr_signal = "neutral"

    momentum_score, momentum_details = _score_momentum(rsi_val, stoch_k, stoch_d, macd_hist, wr_val, prev_macd_hist)

    # --- Volume indicators ---
    # Note: if the market is still open, the last daily bar's volume is
    # incomplete (only a fraction of the full day's volume).  Using it
    # directly would give misleadingly low volume ratios.  So use the
    # last COMPLETE bar's volume (second-to-last) when the last bar might
    # be partial.  We detect this by checking if the last bar's volume is
    # significantly below the 20-bar average (which would be unusual for
    # a completed bar).
    obv_series = ind.obv(close, volume) if len(df) >= 2 else None
    avg_vol = ind.avg_volume(df, 20)
    last_vol = float(volume.iloc[-1]) if len(volume) > 0 else 0.0
    prev_vol = float(volume.iloc[-2]) if len(volume) > 1 else last_vol
    # If the last bar's volume looks partial (< 50% of average), use the
    # previous (complete) bar instead.
    if avg_vol > 0 and last_vol < 0.5 * avg_vol and len(volume) > 1:
        vol_ratio = prev_vol / avg_vol if avg_vol > 0 else 0.0
    else:
        vol_ratio = last_vol / avg_vol if avg_vol > 0 else 0.0
    volume_score, volume_details = _score_volume(obv_series if obv_series is not None else pd.Series(), vol_ratio, last_close)

    # --- Support / Resistance ---
    prev = df.iloc[-2] if len(df) >= 2 else df.iloc[-1]
    pdh, pdl = float(prev["High"]), float(prev["Low"])
    pdc = float(prev["Close"])
    piv = ind.pivots(pdh, pdl, pdc)
    fib = ind.fibonacci_levels(pdh, pdl)

    sr_score, sr_details = _score_support_resistance(last_close, fib, piv)
    nearest_support = sr_details.get("nearest_support", last_close * 0.95)
    nearest_resistance = sr_details.get("nearest_resistance", last_close * 1.05)
    price_vs_support = sr_details.get("position", "mid_range")

    # --- ATR for entry/exit ---
    atr_val = float(ind.atr(df, 14).iloc[-1]) if len(df) >= 15 else last_close * 0.02

    # --- Entry / Exit ---
    entry, stop_loss, target1, target2, rr = _compute_entry_exit(
        last_close, nearest_support, nearest_resistance, atr_val, fib, piv
    )

    # --- Composite score ---
    # Weights: Trend 30%, Momentum 30%, Volume 20%, S/R 20%
    composite = (
        0.30 * trend_score
        + 0.30 * momentum_score
        + 0.20 * volume_score
        + 0.20 * sr_score
    )
    composite = round(composite, 2)

    # --- Verdict ---
    # Murphy: volume must confirm. If volume is well below average, cap the
    # verdict at "hold" — don't recommend buying low-conviction setups.
    if composite > 75:
        verdict = "strong_buy"
    elif composite >= 60:
        verdict = "buy"
    elif composite >= 45:
        verdict = "hold"
    elif composite >= 30:
        verdict = "avoid"
    else:
        verdict = "strong_avoid"

    # Hard filter: low volume kills the signal regardless of other factors.
    if vol_ratio < 0.5 and verdict in ("strong_buy", "buy"):
        verdict = "hold"

    # --- Explanation ---
    bull_bear = "bullish" if trend_direction == "bullish" else ("bearish" if trend_direction == "bearish" else "mixed")
    explanation = (
        f"{symbol} ({name}): Composite score {composite:.1f}/100 — {verdict.replace('_', ' ').upper()}. "
        f"Trend: {trend_direction} (EMA20>50>200={ema20>ema50>ema200}, ADX={adx_val:.1f} {adx_strength}, Supertrend={st_dir}). "
        f"Momentum: RSI={rsi_val:.1f} ({rsi_signal}), Stoch %K={stoch_k:.1f} ({stoch_signal}), "
        f"MACD hist={macd_hist:.2f} ({macd_signal}), Williams %R={wr_val:.1f} ({wr_signal}). "
        f"Volume: OBV {volume_details.get('obv','?')}, vol ratio={vol_ratio:.2f}x. "
        f"S/R: price {price_vs_support} (support ₹{nearest_support:.2f}, resistance ₹{nearest_resistance:.2f}). "
        f"Entry ₹{entry:.2f}, SL ₹{stop_loss:.2f}, T1 ₹{target1:.2f}, T2 ₹{target2:.2f}, R:R=1:{rr:.1f}."
    )

    caveats = []
    if adx_val < 20:
        caveats.append(f"ADX={adx_val:.1f} — weak trend, range-bound conditions. Trend-following signals less reliable.")
    if rsi_val > 70:
        caveats.append(f"RSI={rsi_val:.1f} — overbought, wait for pullback.")
    if stoch_k > 80:
        caveats.append(f"Stochastic %K={stoch_k:.1f} — overbought, potential reversal risk.")
    if rr < 1.5:
        caveats.append(f"Risk:Reward is {rr:.1f} — below 1.5 minimum. Consider waiting for better entry.")
    if vol_ratio < 1.0:
        caveats.append(f"Volume ratio {vol_ratio:.2f}x — below average, conviction is low.")
    if trend_direction == "bearish":
        caveats.append("Bearish trend alignment — long entries are counter-trend.")

    return MurphyAnalysis(
        symbol=symbol,
        name=name,
        last_price=round(last_close, 2),
        trend_score=round(trend_score, 1),
        trend_direction=trend_direction,
        ema_alignment=trend_details.get("ema_alignment", "mixed"),
        adx_value=round(adx_val, 1),
        adx_strength=adx_strength,
        supertrend_dir=st_dir,
        momentum_score=round(momentum_score, 1),
        rsi_value=round(rsi_val, 1),
        rsi_signal=rsi_signal,
        stochastic_k=round(stoch_k, 1),
        stochastic_signal=stoch_signal,
        macd_histogram=round(macd_hist, 4),
        macd_signal=macd_signal,
        williams_r_value=round(wr_val, 1),
        williams_r_signal=wr_signal,
        volume_score=round(volume_score, 1),
        obv_trend=volume_details.get("obv", "flat"),
        volume_ratio=round(vol_ratio, 2),
        fibonacci_levels=fib,
        nearest_support=round(nearest_support, 2),
        nearest_resistance=round(nearest_resistance, 2),
        pivot_levels=piv,
        price_vs_support=price_vs_support,
        composite_score=composite,
        verdict=verdict,
        entry=round(entry, 2),
        stop_loss=round(stop_loss, 2),
        target1=round(target1, 2),
        target2=round(target2, 2),
        risk_reward=round(rr, 2),
        atr_value=round(atr_val, 2),
        factors={
            "trend": round(trend_score, 1),
            "momentum": round(momentum_score, 1),
            "volume": round(volume_score, 1),
            "support_resistance": round(sr_score, 1),
        },
        explanation=explanation,
        caveats=caveats,
    )


async def analyze_symbol(provider, symbol: str, name: str, market: str = "in") -> MurphyAnalysis | None:
    """Fetch data and run Murphy analysis for a single symbol."""
    try:
        suffix = "" if market == "us" or symbol.startswith("^") else ".NS"
        df = await provider.get_daily_history(f"{symbol}{suffix}" if suffix else symbol, 252)
        if df is None or df.empty or len(df) < 60:
            return None
        return analyze_data(symbol, name, df)
    except Exception as e:
        log.warning("Murphy analysis failed for %s: %s", symbol, e)
        return None


async def scan_murphy(provider, symbols: list[tuple[str, str]], market: str = "in") -> list[MurphyAnalysis]:
    """Scan the universe in parallel and return sorted by composite score.

    Args:
        provider: data provider
        symbols: list of (symbol, name) tuples
        market: "in" for NSE, "us" for US
    """
    sem = asyncio.Semaphore(15)

    async def _analyze(sym: str, name: str) -> MurphyAnalysis | None:
        async with sem:
            return await analyze_symbol(provider, sym, name, market)

    results = await asyncio.gather(
        *[_analyze(s, n) for s, n in symbols],
        return_exceptions=True,
    )
    out = [r for r in results if r is not None and not isinstance(r, Exception)]
    out.sort(key=lambda a: a.composite_score, reverse=True)
    return out
