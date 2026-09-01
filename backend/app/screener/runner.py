"""Screener runner: universe -> daily+intraday data -> strategy -> picks -> DB."""
from __future__ import annotations

import asyncio
from datetime import date

import pandas as pd
from zoneinfo import ZoneInfo

from app import indicators as ind
from app.config import settings
from app.db import DayStatusRow, DailyLevel, PickExplanation, PickRow, SessionLocal
from app.explain import explainer
from app.market_hours import today_ist
from app.models import Pick
from app.providers.factory import get_expiry_provider, get_provider
from app.strategies import intraday_breakout as strat
from app.universe import get_universe

IST = ZoneInfo("Asia/Kolkata")


def _is_expiry_today(expiry_dates: list[date], today: date) -> bool:
    return any(d == today for d in expiry_dates)


async def run_scan() -> list[Pick]:
    provider = get_provider()
    symbols = get_universe(settings.universe)

    # Expiry calendar (best-effort; falls back gracefully).
    expiry_provider = get_expiry_provider()
    expiry_dates: list[date] = []
    if expiry_provider is not None:
        try:
            expiry_dates = await expiry_provider.get_expiry_calendar()
        except Exception:
            expiry_dates = []

    today = today_ist()
    expiry_today = _is_expiry_today(expiry_dates, today)

    picks: list[Pick] = []
    no_trade_reason: str | None = None

    # No-trade-day evaluation (gap + ATR regime + breadth placeholder).
    from app.strategies import nobtrade as nt
    try:
        nifty_daily = await provider.get_daily_history("^NSEI", 60)
        # Breadth: approximate as 50% (true breadth needs per-stock VWAP; computed
        # opportunistically below). Refined later.
        verdict = nt.evaluate(nifty_daily, breadth_above_vwap_pct=50.0)
        if verdict.no_trade:
            no_trade_reason = " ".join(verdict.reasons)
    except Exception:
        verdict = nt.NoTradeVerdict(no_trade=False)

    # If no-trade flag is set, persist day status and skip emitting picks.
    if no_trade_reason:
        _persist_day_status(today, no_trade_reason, expiry_today, 0)
        return []

    sem = asyncio.Semaphore(20)

    async def _scan_one(symbol: str):
        async with sem:
            try:
                daily = await provider.get_daily_history(symbol, 60)
                intraday = await provider.get_intraday(symbol, settings.intraday_interval, 1)
            except Exception:
                return None
            if daily.empty or intraday.empty:
                return None

            or_range = ind.opening_range(intraday, settings.or_start, settings.or_end)
            or_high, or_low = (or_range if or_range else (None, None))

            ctx = strat.StrategyContext(
                symbol=symbol,
                daily=daily,
                intraday=intraday,
                or_high=or_high,
                or_low=or_low,
                expiry_today=expiry_today,
            )
            res = strat.evaluate(ctx)

            # Cache daily levels for reproducibility.
            _persist_levels(res, today)
            if res.side is None:
                return None

            explanation = explainer.build(res)
            last_price = float(intraday["Close"].iloc[-1]) if not intraday.empty else 0.0
            return Pick(
                date=today,
                symbol=symbol,
                side=res.side,
                entry=res.entry,
                stop_loss=res.stop_loss,
                target1=res.target1,
                target2=res.target2,
                confidence=res.confidence,
                last_price=last_price,
                expiry_day=expiry_today,
                status="active",
                explanation=explanation,
            )

    results = await asyncio.gather(*[_scan_one(s) for s in symbols])
    picks = [p for p in results if p is not None]

    _persist_day_status(today, no_trade_reason, expiry_today, len(picks))
    _persist_picks(picks)
    return picks


def _overnight_gap_pct(daily: pd.DataFrame) -> float:
    if daily.empty or len(daily) < 2:
        return 0.0
    prev_close = float(daily["Close"].iloc[-2])
    today_open = float(daily["Open"].iloc[-1])
    if prev_close <= 0:
        return 0.0
    return (today_open - prev_close) / prev_close * 100.0


def _persist_levels(res, today: date) -> None:
    db = SessionLocal()
    try:
        piv = res.pivot
        existing = db.query(DailyLevel).filter_by(date=today, symbol=res.symbol).first()
        if existing:
            existing.pdh = res.pdh
            existing.pdl = res.pdl
            existing.pivot = piv["pivot"]
            existing.r1 = piv["r1"]
            existing.r2 = piv["r2"]
            existing.s1 = piv["s1"]
            existing.s2 = piv["s2"]
            existing.atr = res.atr_value
            existing.avg_volume_20 = res.avg_volume_20
            existing.or_high = res.or_high
            existing.or_low = res.or_low
        else:
            db.add(DailyLevel(
                date=today, symbol=res.symbol, pdh=res.pdh, pdl=res.pdl,
                pivot=piv["pivot"], r1=piv["r1"], r2=piv["r2"], s1=piv["s1"], s2=piv["s2"],
                atr=res.atr_value, avg_volume_20=res.avg_volume_20,
                or_high=res.or_high, or_low=res.or_low,
            ))
        db.commit()
    finally:
        db.close()


def _persist_day_status(today: date, no_trade_reason: str | None, expiry_today: bool, count: int) -> None:
    db = SessionLocal()
    try:
        existing = db.query(DayStatusRow).filter_by(date=today).first()
        if existing:
            existing.no_trade = 1 if no_trade_reason else 0
            existing.reason = no_trade_reason
            existing.expiry_day = 1 if expiry_today else 0
            existing.picks_count = count
        else:
            db.add(DayStatusRow(
                date=today, no_trade=1 if no_trade_reason else 0,
                reason=no_trade_reason, expiry_day=1 if expiry_today else 0,
                picks_count=count,
            ))
        db.commit()
    finally:
        db.close()


def _persist_picks(picks: list[Pick]) -> None:
    if not picks:
        return
    db = SessionLocal()
    try:
        # Replace today's picks for these symbols.
        for pick in picks:
            db.query(PickRow).filter_by(date=pick.date, symbol=pick.symbol).delete()
            row = PickRow(
                date=pick.date,
                symbol=pick.symbol,
                side=pick.side,
                entry=pick.entry,
                stop_loss=pick.stop_loss,
                target1=pick.target1,
                target2=pick.target2,
                confidence=pick.confidence,
                last_price=pick.last_price,
                expiry_day=1 if pick.expiry_day else 0,
                status=pick.status,
            )
            row.explanation = PickExplanation(payload=pick.explanation.model_dump(mode="json"))
            db.add(row)
        db.commit()
    finally:
        db.close()
