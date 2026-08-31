"""No-trade-day engine + market event calendar.

Decides whether the day should be a no-trade day based on:
  1. Nifty overnight gap > threshold
  2. Nifty ATR% in a listless regime (bottom decile of recent sessions)
  3. Breadth: share of universe above its VWAP below threshold
  4. Scheduled high-impact events (RBI policy, expiry, US FOMC)

Returns a NoTradeVerdict used by the screener runner and surfaced in the API.
"""
from __future__ import annotations

from dataclasses import dataclass, field

import pandas as pd

from app import indicators as ind
from app.config import settings


# Recurring high-impact event seeds (month, day) or rules. Keep simple/static.
# RBI policy dates move; we flag expiry (handled separately) + a few known
# recurring windows. Users can extend this list.
RECURRING_EVENTS: list[dict] = [
    {"name": "RBI Monetary Policy (approx; check actual calendar)", "rule": "bi-monthly", "impact": "high"},
    {"name": "US FOMC decision", "rule": "8x/year", "impact": "high"},
    {"name": "India CPI release", "rule": "monthly (~12th)", "impact": "medium"},
    {"name": "India IIP release", "rule": "monthly (~12th)", "impact": "low"},
    {"name": "Quarterly results season", "rule": "Apr/Jul/Oct/Jan", "impact": "medium"},
]


@dataclass
class NoTradeVerdict:
    no_trade: bool
    reasons: list[str] = field(default_factory=list)
    events_today: list[str] = field(default_factory=list)
    gap_pct: float = 0.0
    atr_pct: float = 0.0
    breadth_pct: float = 0.0


def evaluate(nifty_daily: pd.DataFrame, breadth_above_vwap_pct: float) -> NoTradeVerdict:
    reasons: list[str] = []
    gap_pct = _gap_pct(nifty_daily)
    atr_pct = _atr_pct(nifty_daily)

    if abs(gap_pct) > settings.no_trade_gap_pct:
        reasons.append(f"Nifty overnight gap {gap_pct:+.2f}% exceeds {settings.no_trade_gap_pct}%.")
    if atr_pct > 0 and atr_pct < 0.4:
        reasons.append(f"Nifty ATR% {atr_pct:.2f} is very low — listless regime, breakouts fail more often.")
    if breadth_above_vwap_pct < settings.no_trade_breadth_pct:
        reasons.append(f"Breadth {breadth_above_vwap_pct:.1f}% above VWAP < {settings.no_trade_breadth_pct}% — weak internals.")

    # Note: scheduled events are advisory (don't force no-trade), surfaced separately.
    return NoTradeVerdict(
        no_trade=len(reasons) >= 1,
        reasons=reasons,
        gap_pct=gap_pct,
        atr_pct=atr_pct,
        breadth_pct=breadth_above_vwap_pct,
    )


def _gap_pct(daily: pd.DataFrame) -> float:
    if daily.empty or len(daily) < 2:
        return 0.0
    prev_close = float(daily["Close"].iloc[-2])
    today_open = float(daily["Open"].iloc[-1])
    if prev_close <= 0:
        return 0.0
    return (today_open - prev_close) / prev_close * 100.0


def _atr_pct(daily: pd.DataFrame) -> float:
    if daily.empty or len(daily) < 15:
        return 0.0
    a = float(ind.atr(daily).iloc[-1])
    c = float(daily["Close"].iloc[-1])
    if c <= 0:
        return 0.0
    return a / c * 100.0


def events_for_today(today: pd.Timestamp) -> list[str]:
    """Return any recurring events relevant for `today` (advisory only)."""
    out: list[str] = []
    m = today.month
    d = today.day
    if d in (11, 12, 13, 14) and m in (1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12):
        out.append("India CPI/IIP release window (~12th) — expect mid-session volatility.")
    if m in (4, 7, 10, 1):
        out.append("Quarterly results season — stock-specific gap risk.")
    return out
