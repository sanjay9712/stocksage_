"""Paper-trading API endpoints — full implementation.

Logs strategy signals into a DB table, auto-resolves open trades when
targets or stop-losses are hit, and tracks hypothetical P&L over time.
No real orders are placed.

Endpoints:
POST   /api/paper/log              — manually log a signal
GET    /api/paper/signals           — list signals (filterable)
GET    /api/paper/signals/{id}      — single signal
GET    /api/paper/stats             — aggregate performance stats
GET    /api/paper/history           — daily P&L history
POST   /api/paper/resolve/{id}      — manually resolve a signal
POST   /api/paper/scan              — scan for new signals + auto-resolve open ones
POST   /api/paper/auto-resolve      — check open trades against current prices
POST   /api/paper/expire            — expire all remaining open trades (EOD)
DELETE /api/paper/signals/{id}      — delete a signal
"""
from __future__ import annotations

import asyncio
import logging
from datetime import date, datetime
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.auth import require_user
from app.config import settings
from app.db import PaperTradeSignal, User, get_db  # noqa: F401 — User used in type hints
from app.market_hours import today_ist
from app.models import PaperTrade, PaperTradeStats
from app.providers.factory import get_provider
from app.strategies import vwap_pullback as vwap_strat
from app.strategies import bollinger_squeeze as bollinger_strat
from app.strategies import ppo_momentum as ppo_strat
from app.universe import get_universe, get_us_stocks

log = logging.getLogger("paper_trade")
router = APIRouter()


# ---------------------------------------------------------------------------
# Row <-> Pydantic conversion.
# ---------------------------------------------------------------------------

def _row_to_pydantic(row: PaperTradeSignal) -> PaperTrade:
    return PaperTrade(
        id=row.id,
        date=row.date,
        symbol=row.symbol,
        market=row.market or "nse",
        strategy=row.strategy,
        side=row.side,
        entry=row.entry,
        stop_loss=row.stop_loss,
        target=row.target,
        confidence=row.confidence,
        status=row.status,
        entry_time=row.entry_time,
        exit_time=row.exit_time,
        exit_price=row.exit_price,
        pnl_pct=row.pnl_pct,
        explanation=row.explanation,
        created_at=row.created_at,
    )


def _calc_pnl(side: str, entry: float, exit_price: float) -> float:
    """P&L percentage for a trade."""
    if side == "long":
        return round(((exit_price - entry) / entry) * 100.0, 2)
    return round(((entry - exit_price) / entry) * 100.0, 2)


# ---------------------------------------------------------------------------
# List signals.
# ---------------------------------------------------------------------------

@router.get("/paper/signals")
async def list_signals(
    user: User = Depends(require_user),
    db: Session = Depends(get_db),
    strategy: str | None = Query(None),
    symbol: str | None = Query(None),
    status: str | None = Query(None),
    market: str | None = Query(None),
    limit: int = Query(100, le=500),
):
    """List paper-trade signals, optionally filtered by strategy/symbol/status/market."""
    stmt = select(PaperTradeSignal).where(PaperTradeSignal.user_id == user.id).order_by(PaperTradeSignal.created_at.desc()).limit(limit)
    if strategy:
        stmt = stmt.where(PaperTradeSignal.strategy == strategy)
    if symbol:
        stmt = stmt.where(PaperTradeSignal.symbol == symbol.upper())
    if status:
        stmt = stmt.where(PaperTradeSignal.status == status)
    if market:
        stmt = stmt.where(PaperTradeSignal.market == market)
    rows = db.execute(stmt).scalars().all()
    return {"signals": [_row_to_pydantic(r).model_dump() for r in rows], "count": len(rows)}


@router.get("/paper/signals/{signal_id}")
async def get_signal(signal_id: int, user: User = Depends(require_user), db: Session = Depends(get_db)):
    """Get a single paper-trade signal by ID."""
    row = db.get(PaperTradeSignal, signal_id)
    if not row or row.user_id != user.id:
        raise HTTPException(status_code=404, detail="Signal not found")
    return _row_to_pydantic(row).model_dump()


# ---------------------------------------------------------------------------
# Log a signal.
# ---------------------------------------------------------------------------

@router.post("/paper/log")
async def log_signal(
    payload: dict,
    user: User = Depends(require_user),
    db: Session = Depends(get_db),
):
    """Manually log a paper-trade signal."""
    required = ("symbol", "strategy", "side", "entry", "stop_loss", "target")
    missing = [f for f in required if f not in payload]
    if missing:
        raise HTTPException(status_code=400, detail=f"Missing fields: {', '.join(missing)}")

    row = PaperTradeSignal(
        user_id=user.id,
        date=today_ist(),
        symbol=payload["symbol"].upper(),
        market=payload.get("market", "nse"),
        strategy=payload["strategy"].lower(),
        side=payload["side"].lower(),
        entry=float(payload["entry"]),
        stop_loss=float(payload["stop_loss"]),
        target=float(payload["target"]),
        confidence=float(payload.get("confidence", 0.0)),
        status="open",
        entry_time=datetime.utcnow(),
        explanation=payload.get("explanation"),
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return _row_to_pydantic(row).model_dump()


# ---------------------------------------------------------------------------
# Resolve a signal (manual).
# ---------------------------------------------------------------------------

@router.post("/paper/resolve/{signal_id}")
async def resolve_signal(
    signal_id: int,
    payload: dict,
    user: User = Depends(require_user),
    db: Session = Depends(get_db),
):
    """Manually resolve an open paper-trade signal with an exit price."""
    row = db.get(PaperTradeSignal, signal_id)
    if not row or row.user_id != user.id:
        raise HTTPException(status_code=404, detail="Signal not found")
    if row.status != "open":
        raise HTTPException(status_code=400, detail=f"Signal already resolved as '{row.status}'")

    exit_price = float(payload.get("exit_price", 0))
    if exit_price <= 0:
        raise HTTPException(status_code=400, detail="exit_price must be positive")

    new_status = payload.get("status", "hit_target")
    if new_status not in ("hit_target", "stopped_out", "expired"):
        raise HTTPException(status_code=400, detail="status must be hit_target, stopped_out, or expired")

    row.exit_price = exit_price
    row.exit_time = datetime.utcnow()
    row.status = new_status
    row.pnl_pct = _calc_pnl(row.side, row.entry, exit_price)

    db.commit()
    db.refresh(row)
    return _row_to_pydantic(row).model_dump()


# ---------------------------------------------------------------------------
# Auto-resolve: check open trades against current prices.
# ---------------------------------------------------------------------------

async def _auto_resolve_open_trades(db: Session) -> dict[str, Any]:
    """Fetch current prices for all symbols with open trades, check if
    target or stop-loss has been hit, and auto-resolve.

    Returns: {"resolved": count, "details": [...]}
    """
    open_trades = db.execute(
        select(PaperTradeSignal).where(PaperTradeSignal.status == "open")
    ).scalars().all()

    if not open_trades:
        return {"resolved": 0, "details": []}

    # Group by symbol to minimize quote fetches.
    by_symbol: dict[str, list[PaperTradeSignal]] = {}
    for t in open_trades:
        by_symbol.setdefault(t.symbol, []).append(t)

    provider = get_provider()
    sem = asyncio.Semaphore(5)
    resolved_details: list[dict] = []

    async def _check_symbol(symbol: str, trades: list[PaperTradeSignal]):
        async with sem:
            try:
                quote = await provider.get_quote(symbol)
            except Exception as e:
                log.warning("Failed to fetch quote for %s: %s", symbol, e)
                return
            if not quote or quote.price <= 0:
                return
            price = quote.price

            for t in trades:
                hit_target = False
                hit_stop = False

                if t.side == "long":
                    if price >= t.target:
                        hit_target = True
                    elif price <= t.stop_loss:
                        hit_stop = True
                else:  # short
                    if price <= t.target:
                        hit_target = True
                    elif price >= t.stop_loss:
                        hit_stop = True

                if hit_target or hit_stop:
                    exit_price = t.target if hit_target else t.stop_loss
                    status = "hit_target" if hit_target else "stopped_out"
                    t.exit_price = exit_price
                    t.exit_time = datetime.utcnow()
                    t.status = status
                    t.pnl_pct = _calc_pnl(t.side, t.entry, exit_price)
                    resolved_details.append({
                        "id": t.id,
                        "symbol": t.symbol,
                        "strategy": t.strategy,
                        "side": t.side,
                        "status": status,
                        "exit_price": exit_price,
                        "pnl_pct": t.pnl_pct,
                    })

    await asyncio.gather(*[_check_symbol(s, ts) for s, ts in by_symbol.items()])

    if resolved_details:
        db.commit()

    return {"resolved": len(resolved_details), "details": resolved_details}


@router.post("/paper/auto-resolve")
async def auto_resolve_endpoint(user: User = Depends(require_user), db: Session = Depends(get_db)):
    """Check all open paper trades against current prices and auto-resolve
    any that have hit their target or stop-loss."""
    return await _auto_resolve_open_trades(db)


# ---------------------------------------------------------------------------
# Scan: run all strategies, log new signals, and auto-resolve existing ones.
# ---------------------------------------------------------------------------

@router.post("/paper/scan")
async def scan_and_log(
    market: str = Query("nse"),
    user: User = Depends(require_user),
    db: Session = Depends(get_db),
):
    """Run all three advanced strategies across the universe, auto-log new
    signals, and auto-resolve any open trades that have hit target/SL.

    Returns counts of both new signals and resolved trades.
    """
    # Step 1: Auto-resolve existing open trades first.
    resolve_result = await _auto_resolve_open_trades(db)

    # Step 2: Scan for new signals.
    if market.lower() == "us":
        symbols = get_us_stocks()
    else:
        symbols = get_universe(settings.universe)
    provider = get_provider()
    sem = asyncio.Semaphore(10)
    today = today_ist()

    # Fetch existing signals for today to avoid duplicates (per-user).
    existing = db.execute(
        select(PaperTradeSignal).where(
            PaperTradeSignal.date == today,
            PaperTradeSignal.user_id == user.id,
        )
    ).scalars().all()
    existing_keys = {(r.symbol, r.strategy) for r in existing}

    strategy_fns = [
        ("vwap", vwap_strat.evaluate_vwap_pullback),
        ("bollinger", bollinger_strat.evaluate_squeeze),
        ("ppo", ppo_strat.evaluate_ppo),
    ]

    async def _fetch_and_eval(sym: str) -> list:
        async with sem:
            try:
                daily = await provider.get_daily_history(sym, 60)
                intraday = await provider.get_intraday(sym, settings.intraday_interval, 1)
            except Exception:
                return []
            if daily.empty or intraday.empty:
                return []
            results = []
            for strat_name, fn in strategy_fns:
                if (sym, strat_name) in existing_keys:
                    continue
                sig = fn(sym, daily, intraday)
                if sig is not None:
                    results.append((sym, strat_name, sig))
            return results

    all_results = await asyncio.gather(*[_fetch_and_eval(s) for s in symbols])

    new_signals = []
    for results in all_results:
        for sym, strat_name, sig in results:
            row = PaperTradeSignal(
                user_id=user.id,
                date=today,
                symbol=sym,
                market=market.lower(),
                strategy=strat_name,
                side=sig.side,
                entry=sig.entry,
                stop_loss=sig.stop_loss,
                target=sig.target if hasattr(sig, "target") else sig.target1,
                confidence=sig.confidence,
                status="open",
                entry_time=datetime.utcnow(),
                explanation={
                    "explanation": sig.explanation,
                    "caveats": sig.caveats,
                    "risk_reward": sig.risk_reward,
                },
            )
            db.add(row)
            new_signals.append(row)

    if new_signals:
        db.commit()
        for r in new_signals:
            db.refresh(r)

    return {
        "new_signals": len(new_signals),
        "resolved": resolve_result["resolved"],
        "resolve_details": resolve_result["details"],
        "signals": [_row_to_pydantic(r).model_dump() for r in new_signals],
    }


# ---------------------------------------------------------------------------
# Expire all open trades (end-of-day cleanup).
# ---------------------------------------------------------------------------

@router.post("/paper/expire")
async def expire_open_trades(user: User = Depends(require_user), db: Session = Depends(get_db)):
    """Mark all remaining open trades as expired. Used at end of trading day.

    P&L is calculated using the last known price for each symbol.
    """
    open_trades = db.execute(
        select(PaperTradeSignal).where(
            PaperTradeSignal.status == "open",
            PaperTradeSignal.user_id == user.id,
        )
    ).scalars().all()

    if not open_trades:
        return {"expired": 0, "details": []}

    by_symbol: dict[str, list[PaperTradeSignal]] = {}
    for t in open_trades:
        by_symbol.setdefault(t.symbol, []).append(t)

    provider = get_provider()
    sem = asyncio.Semaphore(5)
    expired_details: list[dict] = []

    async def _expire_symbol(symbol: str, trades: list[PaperTradeSignal]):
        async with sem:
            try:
                quote = await provider.get_quote(symbol)
            except Exception:
                # If we can't get a price, expire at entry (zero P&L).
                for t in trades:
                    t.exit_price = t.entry
                    t.exit_time = datetime.utcnow()
                    t.status = "expired"
                    t.pnl_pct = 0.0
                    expired_details.append({"id": t.id, "symbol": t.symbol, "exit_price": t.entry, "pnl_pct": 0.0})
                return
            price = quote.price if quote and quote.price > 0 else None
            for t in trades:
                exit_price = price if price else t.entry
                t.exit_price = exit_price
                t.exit_time = datetime.utcnow()
                t.status = "expired"
                t.pnl_pct = _calc_pnl(t.side, t.entry, exit_price)
                expired_details.append({
                    "id": t.id, "symbol": t.symbol, "exit_price": exit_price, "pnl_pct": t.pnl_pct
                })

    await asyncio.gather(*[_expire_symbol(s, ts) for s, ts in by_symbol.items()])
    db.commit()

    return {"expired": len(expired_details), "details": expired_details}


# ---------------------------------------------------------------------------
# Performance stats.
# ---------------------------------------------------------------------------

@router.get("/paper/stats")
async def stats(
    user: User = Depends(require_user),
    db: Session = Depends(get_db),
    strategy: str | None = Query(None),
    market: str | None = Query(None),
):
    """Aggregate performance stats for paper-trade signals."""
    stmt = select(PaperTradeSignal).where(PaperTradeSignal.user_id == user.id)
    if strategy:
        stmt = stmt.where(PaperTradeSignal.strategy == strategy)
    if market:
        stmt = stmt.where(PaperTradeSignal.market == market)
    rows = db.execute(stmt).scalars().all()

    capital = user.capital
    position_size = capital * 0.10

    if not rows:
        return PaperTradeStats(
            total_signals=0, open=0, resolved=0, wins=0, losses=0,
            win_rate=0.0, avg_pnl_pct=0.0, total_pnl_pct=0.0,
            best_trade_pct=None, worst_trade_pct=None, by_strategy={},
            capital=capital, position_size=position_size,
            total_pnl_rupees=0.0, portfolio_value=capital,
        ).model_dump()

    total = len(rows)
    open_count = sum(1 for r in rows if r.status == "open")
    resolved = [r for r in rows if r.status != "open"]
    wins = [r for r in resolved if r.pnl_pct is not None and r.pnl_pct > 0]
    losses = [r for r in resolved if r.pnl_pct is not None and r.pnl_pct <= 0]
    pnls = [r.pnl_pct for r in resolved if r.pnl_pct is not None]

    # Per-strategy breakdown.
    by_strat: dict[str, dict] = {}
    for r in rows:
        s = r.strategy
        if s not in by_strat:
            by_strat[s] = {"count": 0, "wins": 0, "losses": 0, "open": 0, "pnl_sum": 0.0}
        by_strat[s]["count"] += 1
        if r.status == "open":
            by_strat[s]["open"] += 1
        elif r.pnl_pct is not None:
            if r.pnl_pct > 0:
                by_strat[s]["wins"] += 1
            else:
                by_strat[s]["losses"] += 1
            by_strat[s]["pnl_sum"] += r.pnl_pct

    for s, d in by_strat.items():
        resolved_s = d["wins"] + d["losses"]
        d["win_rate"] = round(d["wins"] / resolved_s * 100, 1) if resolved_s > 0 else 0.0
        d["avg_pnl"] = round(d["pnl_sum"] / resolved_s, 2) if resolved_s > 0 else 0.0
        del d["pnl_sum"]

    total_pnl_pct = round(sum(pnls), 2) if pnls else 0.0
    total_pnl_rupees = round(sum(p * position_size / 100 for p in pnls), 2) if pnls else 0.0

    return PaperTradeStats(
        total_signals=total,
        open=open_count,
        resolved=len(resolved),
        wins=len(wins),
        losses=len(losses),
        win_rate=round(len(wins) / len(resolved) * 100, 1) if resolved else 0.0,
        avg_pnl_pct=round(sum(pnls) / len(pnls), 2) if pnls else 0.0,
        total_pnl_pct=total_pnl_pct,
        best_trade_pct=max(pnls) if pnls else None,
        worst_trade_pct=min(pnls) if pnls else None,
        by_strategy=by_strat,
        capital=capital,
        position_size=position_size,
        total_pnl_rupees=total_pnl_rupees,
        portfolio_value=round(capital + total_pnl_rupees, 2),
    ).model_dump()


# ---------------------------------------------------------------------------
# Daily P&L history.
# ---------------------------------------------------------------------------

@router.get("/paper/history")
async def daily_history(
    user: User = Depends(require_user),
    db: Session = Depends(get_db),
    market: str | None = Query(None),
    limit: int = Query(90, le=365),
):
    """Daily aggregate P&L history for performance charting.

    Returns one row per trading day with: date, signals, new_signals,
    resolved, wins, losses, pnl_pct.
    """
    stmt = (
        select(PaperTradeSignal)
        .where(PaperTradeSignal.user_id == user.id)
        .order_by(PaperTradeSignal.date.desc())
        .limit(5000)
    )
    if market:
        stmt = stmt.where(PaperTradeSignal.market == market)
    rows = db.execute(stmt).scalars().all()

    if not rows:
        return {"history": [], "count": 0}

    # Group by date.
    by_date: dict[str, list[PaperTradeSignal]] = {}
    for r in rows:
        key = str(r.date)
        by_date.setdefault(key, []).append(r)

    history = []
    for day_str in sorted(by_date.keys(), reverse=True)[:limit]:
        day_trades = by_date[day_str]
        resolved = [t for t in day_trades if t.status != "open"]
        wins = [t for t in resolved if t.pnl_pct is not None and t.pnl_pct > 0]
        losses = [t for t in resolved if t.pnl_pct is not None and t.pnl_pct <= 0]
        pnls = [t.pnl_pct for t in resolved if t.pnl_pct is not None]
        open_count = sum(1 for t in day_trades if t.status == "open")

        history.append({
            "date": day_str,
            "total_signals": len(day_trades),
            "open": open_count,
            "resolved": len(resolved),
            "wins": len(wins),
            "losses": len(losses),
            "win_rate": round(len(wins) / len(resolved) * 100, 1) if resolved else 0.0,
            "pnl_pct": round(sum(pnls), 2) if pnls else 0.0,
            "avg_pnl_pct": round(sum(pnls) / len(pnls), 2) if pnls else 0.0,
        })

    return {"history": history, "count": len(history)}


# ---------------------------------------------------------------------------
# Delete a signal.
# ---------------------------------------------------------------------------

@router.delete("/paper/signals/{signal_id}")
async def delete_signal(signal_id: int, user: User = Depends(require_user), db: Session = Depends(get_db)):
    """Delete a paper-trade signal by ID."""
    row = db.get(PaperTradeSignal, signal_id)
    if not row or row.user_id != user.id:
        raise HTTPException(status_code=404, detail="Signal not found")
    db.delete(row)
    db.commit()
    return {"deleted": signal_id}
