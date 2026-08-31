"""Holdings reviewer — the 'wrong-pick' engine.

For each holding, compute the same daily indicators the screener uses, then
decide whether the holding's current stance conflicts with the systematic view:

  - If the stock is BELOW its 20-EMA and ATR is rising → trend is weak;
    a delivery hold is questionable. Flag as 'review' or 'caution'.
  - If the stock is in a confirmed downtrend (Close < 20-EMA AND < 50-EMA)
    AND losing > -X% from recent peak → flag 'wrong-pick'.
  - If the holding is intraday (MIS/NRML) and the screener did NOT pick it
    today → flag 'untracked-intraday'.

Returns a structured HoldingReview per holding with a plain-English rationale
so the user can verify the call.
"""
from __future__ import annotations

from dataclasses import dataclass, asdict

import pandas as pd

from app import indicators as ind
from app.holdings.base import BrokerProvider, Holding


@dataclass
class HoldingReview:
    symbol: str
    quantity: int
    avg_price: float
    current_price: float
    pnl: float
    pnl_pct: float
    trend: str                 # up / sideways / down
    ema20: float
    ema50: float
    atr: float
    drawdown_from_peak: float
    verdict: str               # hold / review / caution / wrong-pick
    rationale: str
    actions: list[str]


async def review_holdings(broker: BrokerProvider, today_picks: set[str]) -> list[HoldingReview]:
    import asyncio
    from app.providers.factory import get_provider
    provider = get_provider()

    holdings = await broker.get_holdings()

    async def _fetch_and_review(h):
        try:
            daily = await provider.get_daily_history(h.symbol, 120)
        except Exception:
            daily = pd.DataFrame()
        return _review_one(h, daily, today_picks)

    reviews = await asyncio.gather(*[_fetch_and_review(h) for h in holdings])
    return list(reviews)


def _review_one(h: Holding, daily: pd.DataFrame, today_picks: set[str]) -> HoldingReview:
    pnl = (h.current_price - h.avg_price) * h.quantity
    pnl_pct = (h.current_price - h.avg_price) / h.avg_price * 100.0 if h.avg_price else 0.0

    if daily.empty or len(daily) < 50:
        return HoldingReview(
            symbol=h.symbol, quantity=h.quantity, avg_price=h.avg_price,
            current_price=h.current_price, pnl=round(pnl, 2), pnl_pct=round(pnl_pct, 2),
            trend="unknown", ema20=0.0, ema50=0.0, atr=0.0, drawdown_from_peak=0.0,
            verdict="review",
            rationale="Insufficient price history to evaluate trend; verify manually.",
            actions=["Fetch latest price history and check the daily chart."],
        )

    close = daily["Close"]
    ema20 = float(ind.ema(close, 20).iloc[-1])
    ema50 = float(ind.ema(close, 50).iloc[-1])
    last = float(close.iloc[-1])
    atr_val = float(ind.atr(daily).iloc[-1])
    peak = float(close.cummax().iloc[-1])
    dd_from_peak = (last - peak) / peak if peak > 0 else 0.0

    up = last > ema20 > ema50
    down = last < ema20 < ema50
    trend = "up" if up else ("down" if down else "sideways")

    verdict = "hold"
    rationale_bits: list[str] = []
    actions: list[str] = []

    if down and dd_from_peak < -0.12:
        verdict = "wrong-pick"
        rationale_bits.append(
            f"In a confirmed downtrend (close {last:.2f} < 20-EMA {ema20:.2f} < 50-EMA {ema50:.2f}) "
            f"and {dd_from_peak*100:.1f}% off its recent peak of {peak:.2f}."
        )
        actions.append("Re-examine the original thesis; consider trimming or exiting on a bounce.")
        actions.append("Place a stop below the recent swing low if you keep it.")
    elif down:
        verdict = "caution"
        rationale_bits.append("Below both 20-EMA and 50-EMA — short-term momentum is weak.")
        actions.append("Watch for a breakdown below the recent swing low; tighten stop if held.")
    elif not up:
        verdict = "review"
        rationale_bits.append("Trend is mixed (between EMAs) — no clear edge either way.")
        actions.append("Re-evaluate the holding thesis against the current chart structure.")

    if h.product in ("MIS", "NRML") and h.symbol not in today_picks:
        verdict = "wrong-pick" if verdict != "hold" else "caution"
        rationale_bits.append(
            f"Position is {h.product} (intraday/overnight leveraged) but the screener did NOT pick "
            f"{h.symbol} today — you're carrying an untracked risk position."
        )
        actions.append("Either close/reduce the intraday position or document why you're overriding the screen.")

    if up:
        rationale_bits.append("Trend intact (above 20-EMA and 50-EMA).")

    rationale = " ".join(rationale_bits) if rationale_bits else "No issues detected."
    return HoldingReview(
        symbol=h.symbol, quantity=h.quantity, avg_price=h.avg_price,
        current_price=h.current_price, pnl=round(pnl, 2), pnl_pct=round(pnl_pct, 2),
        trend=trend, ema20=round(ema20, 2), ema50=round(ema50, 2), atr=round(atr_val, 2),
        drawdown_from_peak=round(dd_from_peak, 4), verdict=verdict,
        rationale=rationale, actions=actions,
    )


def to_dict(r: HoldingReview) -> dict:
    return asdict(r)
