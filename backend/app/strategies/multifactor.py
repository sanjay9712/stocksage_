"""Multi-factor stock scoring: Momentum + Value + Quality.

Inspired by the "Smart Momentum" approach: a single momentum metric is noisy,
so combine it with value (is it cheap?) and quality (is the business sound?).
Each factor is scored 0..1, then weighted into a composite score.

Factor weights (configurable):
  - Momentum: 50%  (price trend + relative strength)
  - Quality:   30%  (profitability + debt health)
  - Value:     20%  (valuation vs earnings)

This runs on top of the daily OHLCV + yfinance fundamentals already fetched
elsewhere. It's a pure function so it's unit-testable with fixtures.
"""
from __future__ import annotations

import pandas as pd

from app import indicators as ind


def momentum_score(daily: pd.DataFrame) -> float:
    """Score 0..1 based on multi-timeframe price momentum.

    Combines:
      - 20-day return (short-term momentum)
      - 50-day return (medium-term momentum)
      - Position within 52-week range (relative strength)
      - EMA alignment (20 above 50 = uptrend)
    """
    if daily is None or daily.empty or len(daily) < 5:
        return 0.5

    close = daily["Close"]
    score = 0.0

    # 1. Short-term momentum: 20-day return.
    if len(close) >= 21:
        ret_20 = (close.iloc[-1] / close.iloc[-21] - 1)
        # Map: < -5% → 0, 0% → 0.5, > +5% → 1.0 (capped).
        score += min(max(ret_20 / 0.05, -1), 1) * 0.5 + 0.5
    else:
        score += 0.5
    score *= 0.3  # weight: 30%

    # 2. Medium-term momentum: 50-day return.
    if len(close) >= 51:
        ret_50 = (close.iloc[-1] / close.iloc[-51] - 1)
        score += (min(max(ret_50 / 0.10, -1), 1) * 0.5 + 0.5) * 0.3
    else:
        score += 0.5 * 0.3

    # 3. 52-week range position: where is price within its recent range?
    if len(close) >= 20:
        high_52w = float(close.tail(min(252, len(close))).max())
        low_52w = float(close.tail(min(252, len(close))).min())
        if high_52w > low_52w:
            pos = (close.iloc[-1] - low_52w) / (high_52w - low_52w)
            score += float(pos) * 0.2
        else:
            score += 0.5 * 0.2
    else:
        score += 0.5 * 0.2

    # 4. EMA alignment: 20-EMA above 50-EMA = uptrend.
    if len(close) >= 50:
        ema20 = ind.ema(close, 20).iloc[-1]
        ema50 = ind.ema(close, 50).iloc[-1]
        score += (1.0 if ema20 > ema50 else 0.0) * 0.2
    elif len(close) >= 20:
        ema20 = ind.ema(close, 20).iloc[-1]
        score += (1.0 if close.iloc[-1] > ema20 else 0.3) * 0.2
    else:
        score += 0.5 * 0.2

    return round(min(max(score, 0.0), 1.0), 3)


def value_score(fundamentals: dict) -> float:
    """Score 0..1 based on valuation metrics (lower P/E = better value).

    Uses trailing P/E, forward P/E, and price-to-book from yfinance .info.
    """
    pe = fundamentals.get("trailing_pe")
    fpe = fundamentals.get("forward_pe")
    pb = fundamentals.get("price_to_book")

    score = 0.0
    components = 0

    # P/E: < 10 → 1.0, 10-15 → 0.8, 15-25 → 0.5, 25-40 → 0.2, > 40 → 0.0
    if pe is not None and pe > 0:
        components += 1
        if pe < 10:
            score += 1.0
        elif pe < 15:
            score += 0.8
        elif pe < 25:
            score += 0.5
        elif pe < 40:
            score += 0.2
        else:
            score += 0.0

    # Forward P/E: same scale (forward earnings growth potential).
    if fpe is not None and fpe > 0:
        components += 1
        if fpe < 10:
            score += 1.0
        elif fpe < 15:
            score += 0.8
        elif fpe < 25:
            score += 0.5
        elif fpe < 40:
            score += 0.2

    # Price-to-book: < 1 → 1.0, 1-3 → 0.7, 3-5 → 0.4, > 5 → 0.2
    if pb is not None and pb > 0:
        components += 1
        if pb < 1:
            score += 1.0
        elif pb < 3:
            score += 0.7
        elif pb < 5:
            score += 0.4
        else:
            score += 0.2

    if components == 0:
        return 0.5  # no data → neutral

    return round(score / components, 3)


def quality_score(fundamentals: dict) -> float:
    """Score 0..1 based on business quality: profitability + balance sheet health.

    Uses ROE, profit margins, operating margins, debt-to-equity, current ratio.
    """
    roe = fundamentals.get("return_on_equity")
    pm = fundamentals.get("profit_margins")
    om = fundamentals.get("operating_margins")
    de = fundamentals.get("debt_to_equity")
    cr = fundamentals.get("current_ratio")

    score = 0.0
    components = 0

    # ROE: > 20% → 1.0, 15-20% → 0.8, 10-15% → 0.6, 5-10% → 0.3, < 5% → 0.0
    if roe is not None:
        components += 1
        roe_pct = roe * 100 if roe < 1 else roe  # handle both fraction and percent
        if roe_pct > 20:
            score += 1.0
        elif roe_pct > 15:
            score += 0.8
        elif roe_pct > 10:
            score += 0.6
        elif roe_pct > 5:
            score += 0.3

    # Profit margin: > 20% → 1.0, 10-20% → 0.7, 5-10% → 0.4, < 5% → 0.1
    if pm is not None:
        components += 1
        pm_pct = pm * 100 if pm < 1 else pm
        if pm_pct > 20:
            score += 1.0
        elif pm_pct > 10:
            score += 0.7
        elif pm_pct > 5:
            score += 0.4
        else:
            score += 0.1

    # Operating margin: > 25% → 1.0, 15-25% → 0.7, 5-15% → 0.4, < 5% → 0.1
    if om is not None:
        components += 1
        om_pct = om * 100 if om < 1 else om
        if om_pct > 25:
            score += 1.0
        elif om_pct > 15:
            score += 0.7
        elif om_pct > 5:
            score += 0.4
        else:
            score += 0.1

    # Debt-to-equity: < 0.3 → 1.0, 0.3-0.6 → 0.7, 0.6-1.0 → 0.4, > 1.0 → 0.1
    if de is not None and de >= 0:
        components += 1
        if de < 0.3:
            score += 1.0
        elif de < 0.6:
            score += 0.7
        elif de < 1.0:
            score += 0.4
        else:
            score += 0.1

    # Current ratio: > 2.0 → 1.0, 1.5-2.0 → 0.8, 1.0-1.5 → 0.5, < 1.0 → 0.2
    if cr is not None and cr > 0:
        components += 1
        if cr > 2.0:
            score += 1.0
        elif cr > 1.5:
            score += 0.8
        elif cr > 1.0:
            score += 0.5
        else:
            score += 0.2

    if components == 0:
        return 0.5

    return round(score / components, 3)


# Factor weights: momentum is the primary driver (Smart Momentum approach),
# quality filters out junk, value avoids overpaying.
WEIGHTS = {"momentum": 0.50, "quality": 0.30, "value": 0.20}

# Long-term investing preset: quality-first, value-conscious, momentum as confirmation.
LONG_TERM_WEIGHTS = {"momentum": 0.30, "quality": 0.40, "value": 0.30}


def composite_score(
    daily: pd.DataFrame | None,
    fundamentals: dict,
    weights: dict[str, float] | None = None,
) -> dict:
    """Compute the multi-factor composite score for a stock.

    Returns a dict with individual factor scores, the composite, and a grade.
    """
    w = weights or WEIGHTS

    mom = momentum_score(daily) if daily is not None and not daily.empty else 0.5
    val = value_score(fundamentals)
    qual = quality_score(fundamentals)

    composite = (
        mom * w["momentum"]
        + qual * w["quality"]
        + val * w["value"]
    )
    composite = round(composite, 3)

    # Grade: A+ (>= 0.8), A (>= 0.65), B (>= 0.5), C (>= 0.35), D (< 0.35)
    if composite >= 0.8:
        grade = "A+"
    elif composite >= 0.65:
        grade = "A"
    elif composite >= 0.5:
        grade = "B"
    elif composite >= 0.35:
        grade = "C"
    else:
        grade = "D"

    return {
        "momentum": mom,
        "value": val,
        "quality": qual,
        "composite": composite,
        "grade": grade,
        "weights": w,
        "summary": _build_summary(mom, val, qual, composite, grade),
    }


def _build_summary(mom: float, val: float, qual: float, comp: float, grade: str) -> str:
    """Plain-English summary of the factor scores."""
    def tier(s: float) -> str:
        if s >= 0.7:
            return "strong"
        if s >= 0.5:
            return "moderate"
        return "weak"

    parts = [
        f"Momentum {tier(mom)} ({mom:.0%})",
        f"Value {tier(val)} ({val:.0%})",
        f"Quality {tier(qual)} ({qual:.0%})",
    ]
    return f"Grade {grade} (composite {comp:.0%}) — " + ", ".join(parts) + "."
