"""Candlestick pattern detector.

Implements classic Japanese candlestick patterns from Steve Nison's
"Japanese Candlestick Charting Techniques". Each detector is a pure function
on the last N bars of OHLC data and returns a PatternHit or None.

Patterns detected (bullish / bearish):
  Single-bar:  Doji, Hammer, Inverted Hammer, Shooting Star, Marubozu, Spinning Top
  Two-bar:     Bullish/Bearish Engulfing, Piercing Line, Dark Cloud Cover,
               Bullish/Bearish Harami, Tweezer Tops/Bottoms
  Three-bar:   Morning Star, Evening Star, Three White Soldiers, Three Black Crows

All functions operate on a pandas DataFrame with columns Open/High/Low/Close
and are indexed chronologically (oldest first). The last row is the most recent bar.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

import pandas as pd

Bias = Literal["bullish", "bearish", "neutral"]
Strength = Literal["weak", "moderate", "strong"]


@dataclass
class PatternHit:
    name: str
    bias: Bias
    strength: Strength
    bar_index: int          # index in the passed DataFrame (last bar by default)
    description: str        # plain-English explanation of what the pattern means


def _body(o: float, c: float) -> float:
    return abs(c - o)


def _upper_shadow(h: float, o: float, c: float) -> float:
    top = max(o, c)
    return h - top


def _lower_shadow(l: float, o: float, c: float) -> float:
    bot = min(o, c)
    return bot - l


def _range(h: float, l: float) -> float:
    return h - l


def _is_bullish(o: float, c: float) -> bool:
    return c > o


def _is_bearish(o: float, c: float) -> bool:
    return c < o


def _body_pct(o: float, c: float, h: float, l: float) -> float:
    """Body size as a fraction of the total range (0..1)."""
    rng = _range(h, l)
    if rng <= 0:
        return 0.0
    return _body(o, c) / rng


# ---------------------------------------------------------------------------
# Single-bar patterns
# ---------------------------------------------------------------------------

def doji(row: pd.Series, doji_threshold: float = 0.05) -> PatternHit | None:
    """Doji: open and close are nearly equal (body < threshold * range).

    Signals indecision — neither buyers nor sellers won the session.
    """
    o, h, l, c = row["Open"], row["High"], row["Low"], row["Close"]
    rng = _range(h, l)
    if rng <= 0:
        return None
    if _body(o, c) / rng < doji_threshold:
        return PatternHit(
            name="Doji",
            bias="neutral",
            strength="weak",
            bar_index=-1,
            description="Open and close nearly equal — market indecision. "
                        "Watch for a breakout in either direction next bar.",
        )
    return None


def hammer(row: pd.Series, prev_row: pd.Series | None = None) -> PatternHit | None:
    """Hammer: small body at top, long lower shadow (>= 2x body), no/short upper shadow.

    Bullish reversal signal when it appears after a downtrend.
    """
    o, h, l, c = row["Open"], row["High"], row["Low"], row["Close"]
    body = _body(o, c)
    rng = _range(h, l)
    if rng <= 0 or body <= 0:
        return None
    lower = _lower_shadow(l, o, c)
    upper = _upper_shadow(h, o, c)
    if lower >= 2 * body and upper <= body * 0.3 and _body_pct(o, c, h, l) <= 0.4:
        # Confirm prior downtrend if available.
        in_downtrend = prev_row is None or prev_row["Close"] < prev_row["Open"]
        return PatternHit(
            name="Hammer",
            bias="bullish",
            strength="moderate" if in_downtrend else "weak",
            bar_index=-1,
            description="Long lower shadow with small body at top — sellers pushed "
                        "price down but buyers reclaimed control by close. Bullish "
                        "reversal signal after a downtrend.",
        )
    return None


def shooting_star(row: pd.Series, prev_row: pd.Series | None = None) -> PatternHit | None:
    """Shooting Star: small body at bottom, long upper shadow (>= 2x body).

    Bearish reversal signal when it appears after an uptrend.
    """
    o, h, l, c = row["Open"], row["High"], row["Low"], row["Close"]
    body = _body(o, c)
    rng = _range(h, l)
    if rng <= 0 or body <= 0:
        return None
    lower = _lower_shadow(l, o, c)
    upper = _upper_shadow(h, o, c)
    if upper >= 2 * body and lower <= body * 0.3 and _body_pct(o, c, h, l) <= 0.4:
        in_uptrend = prev_row is None or prev_row["Close"] > prev_row["Open"]
        return PatternHit(
            name="Shooting Star",
            bias="bearish",
            strength="moderate" if in_uptrend else "weak",
            bar_index=-1,
            description="Long upper shadow with small body at bottom — buyers pushed "
                        "price up but sellers slammed it back down by close. Bearish "
                        "reversal signal after an uptrend.",
        )
    return None


def marubozu(row: pd.Series) -> PatternHit | None:
    """Marubozu: no (or tiny) shadows — full body.

    Strong directional conviction. Bullish marubozu = strong buying pressure;
    bearish marubozu = strong selling pressure.
    """
    o, h, l, c = row["Open"], row["High"], row["Low"], row["Close"]
    body = _body(o, c)
    rng = _range(h, l)
    if rng <= 0 or body <= 0:
        return None
    upper = _upper_shadow(h, o, c)
    lower = _lower_shadow(l, o, c)
    if upper <= body * 0.05 and lower <= body * 0.05:
        bias: Bias = "bullish" if _is_bullish(o, c) else "bearish"
        return PatternHit(
            name=f"{'Bullish' if _is_bullish(o, c) else 'Bearish'} Marubozu",
            bias=bias,
            strength="strong",
            bar_index=-1,
            description="No shadows — price opened at the low and closed at the high "
                        "(bullish) or vice versa (bearish). Strong directional conviction.",
        )
    return None


def spinning_top(row: pd.Series) -> PatternHit | None:
    """Spinning Top: small body with long upper AND lower shadows.

    Indecision pattern — similar to doji but with a small real body.
    """
    o, h, l, c = row["Open"], row["High"], row["Low"], row["Close"]
    body = _body(o, c)
    rng = _range(h, l)
    if rng <= 0 or body <= 0:
        return None
    upper = _upper_shadow(h, o, c)
    lower = _lower_shadow(l, o, c)
    bp = _body_pct(o, c, h, l)
    if 0.1 < bp <= 0.35 and upper >= body and lower >= body:
        return PatternHit(
            name="Spinning Top",
            bias="neutral",
            strength="weak",
            bar_index=-1,
            description="Small body with long shadows on both sides — tug of war "
                        "between buyers and sellers with no clear winner. Indecision.",
        )
    return None


# ---------------------------------------------------------------------------
# Two-bar patterns
# ---------------------------------------------------------------------------

def bullish_engulfing(prev: pd.Series, curr: pd.Series) -> PatternHit | None:
    """Bullish Engulfing: current bullish candle's body completely engulfs the
    previous bearish candle's body.

    Strong bullish reversal signal after a downtrend.
    """
    if not _is_bearish(prev["Open"], prev["Close"]):
        return None
    if not _is_bullish(curr["Open"], curr["Close"]):
        return None
    if curr["Open"] <= prev["Close"] and curr["Close"] >= prev["Open"]:
        # Body of curr engulfs body of prev.
        return PatternHit(
            name="Bullish Engulfing",
            bias="bullish",
            strength="strong",
            bar_index=-1,
            description="Current bullish candle completely engulfs the previous "
                        "bearish body — buyers overwhelmed sellers. Strong bullish "
                        "reversal signal.",
        )
    return None


def bearish_engulfing(prev: pd.Series, curr: pd.Series) -> PatternHit | None:
    """Bearish Engulfing: current bearish candle engulfs the previous bullish body.

    Strong bearish reversal signal after an uptrend.
    """
    if not _is_bullish(prev["Open"], prev["Close"]):
        return None
    if not _is_bearish(curr["Open"], curr["Close"]):
        return None
    if curr["Open"] >= prev["Close"] and curr["Close"] <= prev["Open"]:
        return PatternHit(
            name="Bearish Engulfing",
            bias="bearish",
            strength="strong",
            bar_index=-1,
            description="Current bearish candle completely engulfs the previous "
                        "bullish body — sellers overwhelmed buyers. Strong bearish "
                        "reversal signal.",
        )
    return None


def piercing_line(prev: pd.Series, curr: pd.Series) -> PatternHit | None:
    """Piercing Line: after a bearish candle, next candle opens below prev low
    and closes above the midpoint of prev body.

    Bullish reversal signal (bottom).
    """
    if not _is_bearish(prev["Open"], prev["Close"]):
        return None
    if not _is_bullish(curr["Open"], curr["Close"]):
        return None
    prev_mid = (prev["Open"] + prev["Close"]) / 2
    if curr["Open"] < prev["Low"] and prev["Close"] < curr["Close"] < prev_mid:
        return PatternHit(
            name="Piercing Line",
            bias="bullish",
            strength="moderate",
            bar_index=-1,
            description="Opened below the prior low but closed above the midpoint "
                        "of the prior bearish body — buyers stepped in aggressively. "
                        "Bullish bottom reversal.",
        )
    return None


def dark_cloud_cover(prev: pd.Series, curr: pd.Series) -> PatternHit | None:
    """Dark Cloud Cover: after a bullish candle, next candle opens above prev high
    and closes below the midpoint of prev body.

    Bearish reversal signal (top).
    """
    if not _is_bullish(prev["Open"], prev["Close"]):
        return None
    if not _is_bearish(curr["Open"], curr["Close"]):
        return None
    prev_mid = (prev["Open"] + prev["Close"]) / 2
    if curr["Open"] > prev["High"] and prev_mid > curr["Close"] > prev["Close"]:
        return PatternHit(
            name="Dark Cloud Cover",
            bias="bearish",
            strength="moderate",
            bar_index=-1,
            description="Opened above the prior high but closed below the midpoint "
                        "of the prior bullish body — sellers took control. Bearish "
                        "top reversal.",
        )
    return None


def bullish_harami(prev: pd.Series, curr: pd.Series) -> PatternHit | None:
    """Bullish Harami: large bearish candle followed by a small bullish body
    contained within the prior body.

    Suggests the downtrend may be losing momentum.
    """
    if not _is_bearish(prev["Open"], prev["Close"]):
        return None
    if not _is_bullish(curr["Open"], curr["Close"]):
        return None
    if (curr["Open"] >= prev["Close"] and curr["Close"] <= prev["Open"] and
            _body(curr["Open"], curr["Close"]) < _body(prev["Open"], prev["Close"]) * 0.5):
        return PatternHit(
            name="Bullish Harami",
            bias="bullish",
            strength="moderate",
            bar_index=-1,
            description="Small bullish body inside the prior large bearish body — "
                        "selling pressure is fading. Potential bullish reversal.",
        )
    return None


def bearish_harami(prev: pd.Series, curr: pd.Series) -> PatternHit | None:
    """Bearish Harami: large bullish candle followed by small bearish body
    contained within the prior body.

    Suggests the uptrend may be stalling.
    """
    if not _is_bullish(prev["Open"], prev["Close"]):
        return None
    if not _is_bearish(curr["Open"], curr["Close"]):
        return None
    if (curr["Open"] <= prev["Close"] and curr["Close"] >= prev["Open"] and
            _body(curr["Open"], curr["Close"]) < _body(prev["Open"], prev["Close"]) * 0.5):
        return PatternHit(
            name="Bearish Harami",
            bias="bearish",
            strength="moderate",
            bar_index=-1,
            description="Small bearish body inside the prior large bullish body — "
                        "buying pressure is fading. Potential bearish reversal.",
        )
    return None


def tweezer_bottoms(prev: pd.Series, curr: pd.Series, tol: float = 0.001) -> PatternHit | None:
    """Tweezer Bottoms: two consecutive candles with nearly identical lows
    (first bearish, second bullish).

    Bullish reversal — support held twice.
    """
    if not _is_bearish(prev["Open"], prev["Close"]):
        return None
    if not _is_bullish(curr["Open"], curr["Close"]):
        return None
    if abs(prev["Low"] - curr["Low"]) / max(prev["Low"], 1) < tol:
        return PatternHit(
            name="Tweezer Bottoms",
            bias="bullish",
            strength="moderate",
            bar_index=-1,
            description="Two candles with matching lows — support held twice. "
                        "Bullish reversal signal.",
        )
    return None


def tweezer_tops(prev: pd.Series, curr: pd.Series, tol: float = 0.001) -> PatternHit | None:
    """Tweezer Tops: two consecutive candles with nearly identical highs
    (first bullish, second bearish).

    Bearish reversal — resistance held twice.
    """
    if not _is_bullish(prev["Open"], prev["Close"]):
        return None
    if not _is_bearish(curr["Open"], curr["Close"]):
        return None
    if abs(prev["High"] - curr["High"]) / max(prev["High"], 1) < tol:
        return PatternHit(
            name="Tweezer Tops",
            bias="bearish",
            strength="moderate",
            bar_index=-1,
            description="Two candles with matching highs — resistance held twice. "
                        "Bearish reversal signal.",
        )
    return None


# ---------------------------------------------------------------------------
# Three-bar patterns
# ---------------------------------------------------------------------------

def morning_star(p1: pd.Series, p2: pd.Series, p3: pd.Series) -> PatternHit | None:
    """Morning Star: bearish candle, small-body star (gap down), bullish candle
    that closes well into the first candle's body.

    Strong bullish bottom reversal.
    """
    if not _is_bearish(p1["Open"], p1["Close"]):
        return None
    if not _is_bullish(p3["Open"], p3["Close"]):
        return None
    # Middle candle has a small body (the "star").
    p2_body = _body(p2["Open"], p2["Close"])
    p1_body = _body(p1["Open"], p1["Close"])
    if p1_body <= 0 or p2_body > p1_body * 0.4:
        return None
    # Third candle closes above the midpoint of the first candle's body.
    p1_mid = (p1["Open"] + p1["Close"]) / 2
    if p3["Close"] > p1_mid:
        return PatternHit(
            name="Morning Star",
            bias="bullish",
            strength="strong",
            bar_index=-1,
            description="Three-bar bottom reversal: bearish candle → small star "
                        "(indecision) → bullish candle closing into the first body. "
                        "Strong bullish reversal.",
        )
    return None


def evening_star(p1: pd.Series, p2: pd.Series, p3: pd.Series) -> PatternHit | None:
    """Evening Star: bullish candle, small-body star (gap up), bearish candle
    that closes well into the first candle's body.

    Strong bearish top reversal.
    """
    if not _is_bullish(p1["Open"], p1["Close"]):
        return None
    if not _is_bearish(p3["Open"], p3["Close"]):
        return None
    p2_body = _body(p2["Open"], p2["Close"])
    p1_body = _body(p1["Open"], p1["Close"])
    if p1_body <= 0 or p2_body > p1_body * 0.4:
        return None
    p1_mid = (p1["Open"] + p1["Close"]) / 2
    if p3["Close"] < p1_mid:
        return PatternHit(
            name="Evening Star",
            bias="bearish",
            strength="strong",
            bar_index=-1,
            description="Three-bar top reversal: bullish candle → small star "
                        "(indecision) → bearish candle closing into the first body. "
                        "Strong bearish reversal.",
        )
    return None


def three_white_soldiers(p1: pd.Series, p2: pd.Series, p3: pd.Series) -> PatternHit | None:
    """Three White Soldiers: three consecutive bullish candles, each opening
    within the prior body and closing higher.

    Strong sustained bullish momentum.
    """
    for bar in (p1, p2, p3):
        if not _is_bullish(bar["Open"], bar["Close"]):
            return None
    if (p2["Open"] > p1["Close"] * 0.98 and p2["Close"] > p1["Close"] and
            p3["Open"] > p2["Close"] * 0.98 and p3["Close"] > p2["Close"]):
        return PatternHit(
            name="Three White Soldiers",
            bias="bullish",
            strength="strong",
            bar_index=-1,
            description="Three consecutive bullish candles, each opening within the "
                        "prior body and closing higher. Strong sustained buying momentum.",
        )
    return None


def three_black_crows(p1: pd.Series, p2: pd.Series, p3: pd.Series) -> PatternHit | None:
    """Three Black Crows: three consecutive bearish candles, each opening
    within the prior body and closing lower.

    Strong sustained bearish momentum.
    """
    for bar in (p1, p2, p3):
        if not _is_bearish(bar["Open"], bar["Close"]):
            return None
    if (p2["Open"] < p1["Close"] * 1.02 and p2["Close"] < p1["Close"] and
            p3["Open"] < p2["Close"] * 1.02 and p3["Close"] < p2["Close"]):
        return PatternHit(
            name="Three Black Crows",
            bias="bearish",
            strength="strong",
            bar_index=-1,
            description="Three consecutive bearish candles, each opening within the "
                        "prior body and closing lower. Strong sustained selling momentum.",
        )
    return None


# ---------------------------------------------------------------------------
# Master detection: scan the last few bars for all patterns.
# ---------------------------------------------------------------------------

def detect_patterns(df: pd.DataFrame, lookback: int = 5) -> list[PatternHit]:
    """Detect candlestick patterns in the last `lookback` bars.

    Returns a list of PatternHit (possibly empty). Patterns are checked on the
    most recent bar(s) — single-bar on the last bar, two-bar on the last two,
    three-bar on the last three.

    Args:
        df: DataFrame with Open/High/Low/Close columns, chronological order.
        lookback: how many bars from the end to scan (default 5).
    """
    if df is None or len(df) < 2:
        return []

    hits: list[PatternHit] = []
    n = len(df)
    start = max(0, n - lookback)

    # Scan the last `lookback` bars for single and multi-bar patterns.
    # We check the most recent occurrence first and deduplicate by name.
    seen_names: set[str] = set()

    for i in range(n - 1, start - 1, -1):
        curr = df.iloc[i]

        # Need at least 2 bars for two-bar patterns.
        if i >= 1:
            prev = df.iloc[i - 1]

            for check in (
                lambda: bullish_engulfing(prev, curr),
                lambda: bearish_engulfing(prev, curr),
                lambda: piercing_line(prev, curr),
                lambda: dark_cloud_cover(prev, curr),
                lambda: bullish_harami(prev, curr),
                lambda: bearish_harami(prev, curr),
                lambda: tweezer_bottoms(prev, curr),
                lambda: tweezer_tops(prev, curr),
            ):
                hit = check()
                if hit and hit.name not in seen_names:
                    hit.bar_index = i
                    hits.append(hit)
                    seen_names.add(hit.name)

            # Hammer / shooting star need context of prior bar.
            for check in (
                lambda: hammer(curr, prev),
                lambda: shooting_star(curr, prev),
            ):
                hit = check()
                if hit and hit.name not in seen_names:
                    hit.bar_index = i
                    hits.append(hit)
                    seen_names.add(hit.name)

        # Need at least 3 bars for three-bar patterns.
        if i >= 2:
            p1 = df.iloc[i - 2]
            p2 = df.iloc[i - 1]

            for check in (
                lambda: morning_star(p1, p2, curr),
                lambda: evening_star(p1, p2, curr),
                lambda: three_white_soldiers(p1, p2, curr),
                lambda: three_black_crows(p1, p2, curr),
            ):
                hit = check()
                if hit and hit.name not in seen_names:
                    hit.bar_index = i
                    hits.append(hit)
                    seen_names.add(hit.name)

        # Single-bar patterns (no prior needed).
        for check in (
            lambda: doji(curr),
            lambda: marubozu(curr),
            lambda: spinning_top(curr),
        ):
            hit = check()
            if hit and hit.name not in seen_names:
                hit.bar_index = i
                hits.append(hit)
                seen_names.add(hit.name)

    return hits


def net_bias(hits: list[PatternHit]) -> Bias:
    """Aggregate the bias of multiple pattern hits into a single net signal."""
    if not hits:
        return "neutral"
    # Weight by strength.
    weight = {"weak": 1, "moderate": 2, "strong": 3}
    score = 0
    for h in hits:
        if h.bias == "bullish":
            score += weight[h.strength]
        elif h.bias == "bearish":
            score -= weight[h.strength]
    if score > 0:
        return "bullish"
    if score < 0:
        return "bearish"
    return "neutral"
