"""Commodity breakout strategy (previous-day high/low breakout).

Commodities via yfinance are global futures (~24h sessions), so the NSE
opening-range concept doesn't map cleanly. Instead we use a daily breakout:
if today's intraday high breaks above the previous day's high on volume,
flag a long candidate. Entry = PDH, SL = PDL, targets = entry + ATR multiples.
"""
from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from app import indicators as ind
from app.config import settings


@dataclass
class CommodityContext:
    name: str
    symbol: str          # yfinance ticker (e.g. GC=F)
    daily: pd.DataFrame
    intraday: pd.DataFrame   # today's 5-min bars (may be sparse for 24h futures)
    expiry_today: bool = False


@dataclass
class CommodityResult:
    name: str
    symbol: str
    side: str | None
    entry: float | None
    stop_loss: float | None
    target1: float | None
    target2: float | None
    confidence: float
    atr_value: float
    avg_volume_20: float
    pdh: float
    pdl: float
    pivot: dict[str, float]
    breakout: dict | None
    notes: list[str]


def evaluate(ctx: CommodityContext) -> CommodityResult:
    daily = ctx.daily
    if len(daily) < 15:
        return CommodityResult(
            name=ctx.name, symbol=ctx.symbol, side=None, entry=None,
            stop_loss=None, target1=None, target2=None, confidence=0.0,
            atr_value=0.0, avg_volume_20=0.0, pdh=0.0, pdl=0.0,
            pivot={"pivot": 0, "r1": 0, "r2": 0, "s1": 0, "s2": 0},
            breakout=None, notes=["Insufficient daily history (<15 bars)."],
        )
    prev = daily.iloc[-2]   # previous completed session
    today = daily.iloc[-1]
    pdh, pdl, pdc = float(prev["High"]), float(prev["Low"]), float(prev["Close"])
    piv = ind.pivots(pdh, pdl, pdc)
    atr_val = float(ind.atr(daily).iloc[-1])
    avg_vol = ind.avg_volume(ctx.intraday, 20) if len(ctx.intraday) >= 20 else ind.avg_volume(daily, 20)

    # Guard against degenerate previous-day bars (yfinance sometimes returns a
    # placeholder bar with H==L==C on holidays/gaps). A breakout level with no
    # range is meaningless, so skip the pick.
    day_range = pdh - pdl
    if pdh > 0 and day_range / pdh < 0.0005:
        return CommodityResult(
            name=ctx.name, symbol=ctx.symbol, side=None, entry=None,
            stop_loss=None, target1=None, target2=None, confidence=0.0,
            atr_value=atr_val, avg_volume_20=avg_vol, pdh=pdh, pdl=pdl,
            pivot=piv, breakout=None,
            notes=["Previous-day bar is degenerate (High≈Low) — likely a data gap. No valid breakout level."],
        )

    # Today's breakout bar: the first intraday bar whose High > PDH and volume
    # >= threshold. Falls back to the daily 'today' row if intraday is empty.
    breakout = None
    side = entry = sl = t1 = t2 = None
    confidence = 0.0
    notes: list[str] = []

    candidates = ctx.intraday if not ctx.intraday.empty else daily.iloc[[-1]]
    threshold = settings.volume_ratio_min
    for ts, row in candidates.iterrows():
        if row["High"] > pdh and (avg_vol <= 0 or row.get("Volume", 0) >= threshold * avg_vol):
            breakout = {
                "ts": str(ts),
                "high": float(row["High"]),
                "volume": float(row.get("Volume", 0)),
                "volume_ratio": float(row.get("Volume", 0) / avg_vol) if avg_vol > 0 else 0.0,
            }
            side = "long"
            entry = pdh
            sl = pdl  # stop at previous day low
            t1 = entry + atr_val
            t2 = entry + 2 * atr_val
            vol_score = min(breakout["volume_ratio"] / 3.0, 1.0) if avg_vol > 0 else 0.5
            confidence = round(0.6 * vol_score + 0.4, 3)
            break

    if breakout is None:
        notes.append("No breakout above previous-day high on required volume today.")
    notes.append("Commodity data is a global USD futures proxy for MCX; levels are reference, not INR tick data.")
    if ctx.expiry_today:
        notes.append("F&O expiry day: commodity options gamma risk elevated near close.")

    return CommodityResult(
        name=ctx.name, symbol=ctx.symbol, side=side, entry=entry, stop_loss=sl,
        target1=t1, target2=t2, confidence=confidence, atr_value=atr_val,
        avg_volume_20=avg_vol, pdh=pdh, pdl=pdl, pivot=piv,
        breakout=breakout, notes=notes,
    )
