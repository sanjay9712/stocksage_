"""Autonomous trading bot API endpoints.

GET  /api/bot/status                — last scan time, open count, by-strategy breakdown
GET  /api/bot/decisions              — list bot decisions (filterable)
GET  /api/bot/rankings               — strategy rankings for a date
GET  /api/bot/recommendation         — daily recommendation
GET  /api/bot/history                — daily aggregate P&L history
POST /api/bot/scan                    — manually trigger bot scan
GET  /api/bot/strategy-comparison     — multi-day comparison of all strategies
"""
from __future__ import annotations

from datetime import date, datetime
from typing import Any

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select, func, desc
from sqlalchemy.orm import Session

from app.api.auth import require_user
from app.db import BotDecision, DailyRecommendation, StrategyRanking, User, get_db
from app.market_hours import today_ist

router = APIRouter()


@router.get("/bot/status")
async def bot_status(
    user: User = Depends(require_user),
    db: Session = Depends(get_db),
):
    """Bot status: last scan time, open count, today's signal count, by-strategy breakdown."""
    today = today_ist()

    # Last scan time.
    last_scan = db.execute(
        select(func.max(BotDecision.scan_time)).where(BotDecision.date == today)
    ).scalar()

    # Counts.
    open_count = db.execute(
        select(func.count()).select_from(BotDecision).where(
            BotDecision.date == today, BotDecision.status == "open"
        )
    ).scalar() or 0

    total_today = db.execute(
        select(func.count()).select_from(BotDecision).where(BotDecision.date == today)
    ).scalar() or 0

    resolved_today = db.execute(
        select(func.count()).select_from(BotDecision).where(
            BotDecision.date == today, BotDecision.status != "open"
        )
    ).scalar() or 0

    # By-strategy breakdown.
    all_today = db.execute(
        select(BotDecision).where(BotDecision.date == today)
    ).scalars().all()

    by_strat: dict[str, dict] = {}
    for r in all_today:
        s = r.strategy
        if s not in by_strat:
            by_strat[s] = {"total": 0, "open": 0, "wins": 0, "losses": 0, "pnl_sum": 0.0}
        by_strat[s]["total"] += 1
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
        d["total_pnl"] = round(d["pnl_sum"], 2)
        del d["pnl_sum"]

    # Check for recommendation.
    rec = db.execute(
        select(DailyRecommendation).where(DailyRecommendation.date == today)
    ).scalar_one_or_none()

    return {
        "last_scan": last_scan.isoformat() if last_scan else None,
        "today": str(today),
        "total_signals": total_today,
        "open": open_count,
        "resolved": resolved_today,
        "by_strategy": by_strat,
        "has_recommendation": rec is not None,
    }


@router.get("/bot/decisions")
async def bot_decisions(
    user: User = Depends(require_user),
    db: Session = Depends(get_db),
    strategy: str | None = Query(None),
    status: str | None = Query(None),
    limit: int = Query(100, le=500),
):
    """List bot decisions with optional filters."""
    stmt = select(BotDecision).order_by(desc(BotDecision.created_at)).limit(limit)
    if strategy:
        stmt = stmt.where(BotDecision.strategy == strategy)
    if status:
        stmt = stmt.where(BotDecision.status == status)
    rows = db.execute(stmt).scalars().all()

    return {
        "decisions": [
            {
                "id": r.id,
                "scan_time": r.scan_time.isoformat() if r.scan_time else None,
                "date": str(r.date),
                "symbol": r.symbol,
                "market": r.market,
                "strategy": r.strategy,
                "side": r.side,
                "entry": r.entry,
                "stop_loss": r.stop_loss,
                "target": r.target,
                "confidence": r.confidence,
                "risk_reward": r.risk_reward,
                "composite_score": r.composite_score,
                "verdict": r.verdict,
                "status": r.status,
                "exit_price": r.exit_price,
                "pnl_pct": r.pnl_pct,
                "explanation": r.explanation,
            }
            for r in rows
        ],
        "count": len(rows),
    }


@router.get("/bot/rankings")
async def bot_rankings(
    user: User = Depends(require_user),
    db: Session = Depends(get_db),
    target_date: str | None = Query(None, alias="date"),
):
    """Strategy rankings for a given date (defaults to today)."""
    if target_date:
        try:
            d = date.fromisoformat(target_date)
        except ValueError:
            d = today_ist()
    else:
        d = today_ist()

    rows = db.execute(
        select(StrategyRanking).where(StrategyRanking.date == d).order_by(StrategyRanking.rank)
    ).scalars().all()

    return {
        "date": str(d),
        "rankings": [
            {
                "rank": r.rank,
                "strategy": r.strategy,
                "total_signals": r.total_signals,
                "resolved": r.resolved,
                "wins": r.wins,
                "losses": r.losses,
                "win_rate": r.win_rate,
                "avg_pnl_pct": r.avg_pnl_pct,
                "total_pnl_pct": r.total_pnl_pct,
                "best_trade_pct": r.best_trade_pct,
                "worst_trade_pct": r.worst_trade_pct,
                "wfe_score": r.wfe_score,
                "wfe_verdict": r.wfe_verdict,
                "recommendation": r.recommendation,
            }
            for r in rows
        ],
        "count": len(rows),
    }


@router.get("/bot/recommendation")
async def bot_recommendation(
    user: User = Depends(require_user),
    db: Session = Depends(get_db),
    target_date: str | None = Query(None, alias="date"),
):
    """Daily recommendation — the bot's single best pick."""
    if target_date:
        try:
            d = date.fromisoformat(target_date)
        except ValueError:
            d = today_ist()
    else:
        d = today_ist()

    rec = db.execute(
        select(DailyRecommendation).where(DailyRecommendation.date == d)
    ).scalar_one_or_none()

    if not rec:
        return {"found": False, "date": str(d), "message": "No recommendation generated yet."}

    return {
        "found": True,
        "date": str(rec.date),
        "symbol": rec.symbol,
        "name": rec.name,
        "strategy": rec.strategy,
        "side": rec.side,
        "entry": rec.entry,
        "stop_loss": rec.stop_loss,
        "target": rec.target,
        "confidence": rec.confidence,
        "risk_reward": rec.risk_reward,
        "composite_score": rec.composite_score,
        "explanation": rec.explanation,
        "caveats": rec.caveats,
        "alternatives": rec.alternatives,
    }


@router.get("/bot/history")
async def bot_history(
    user: User = Depends(require_user),
    db: Session = Depends(get_db),
    limit: int = Query(30, le=365),
):
    """Daily aggregate P&L history for the bot."""
    rows = db.execute(
        select(BotDecision).order_by(desc(BotDecision.date)).limit(5000)
    ).scalars().all()

    if not rows:
        return {"history": [], "count": 0}

    by_date: dict[str, list[BotDecision]] = {}
    for r in rows:
        by_date.setdefault(str(r.date), []).append(r)

    history = []
    for day_str in sorted(by_date.keys(), reverse=True)[:limit]:
        day_trades = by_date[day_str]
        resolved = [t for t in day_trades if t.status != "open"]
        wins = [t for t in resolved if t.pnl_pct is not None and t.pnl_pct > 0]
        losses = [t for t in resolved if t.pnl_pct is not None and t.pnl_pct <= 0]
        pnls = [t.pnl_pct for t in resolved if t.pnl_pct is not None]

        history.append({
            "date": day_str,
            "total_signals": len(day_trades),
            "open": sum(1 for t in day_trades if t.status == "open"),
            "resolved": len(resolved),
            "wins": len(wins),
            "losses": len(losses),
            "win_rate": round(len(wins) / len(resolved) * 100, 1) if resolved else 0.0,
            "pnl_pct": round(sum(pnls), 2) if pnls else 0.0,
            "avg_pnl_pct": round(sum(pnls) / len(pnls), 2) if pnls else 0.0,
        })

    return {"history": history, "count": len(history)}


@router.post("/bot/scan")
async def trigger_bot_scan(
    user: User = Depends(require_user),
    market: str = Query("nse"),
):
    """Manually trigger a bot scan (useful for testing outside scheduled hours)."""
    from app.bot.engine import run_bot_scan
    result = await run_bot_scan(market)
    return result


@router.get("/bot/strategy-comparison")
async def strategy_comparison(
    user: User = Depends(require_user),
    db: Session = Depends(get_db),
    days: int = Query(30, le=90),
):
    """Multi-day comparison of all strategies across recent history."""
    rows = db.execute(
        select(StrategyRanking).order_by(desc(StrategyRanking.date)).limit(days * 5)
    ).scalars().all()

    if not rows:
        return {"comparison": {}, "count": 0}

    by_strat: dict[str, dict] = {}
    for r in rows:
        s = r.strategy
        if s not in by_strat:
            by_strat[s] = {
                "strategy": s,
                "days_ranked": 0,
                "total_signals": 0,
                "wins": 0,
                "losses": 0,
                "total_pnl": 0.0,
                "wfe_scores": [],
                "rank_1_count": 0,
                "recommended_count": 0,
            }
        d = by_strat[s]
        d["days_ranked"] += 1
        d["total_signals"] += r.total_signals
        d["wins"] += r.wins
        d["losses"] += r.losses
        d["total_pnl"] += r.total_pnl_pct
        if r.wfe_score is not None:
            d["wfe_scores"].append(r.wfe_score)
        if r.rank == 1:
            d["rank_1_count"] += 1
        if r.recommendation == "recommended":
            d["recommended_count"] += 1

    for s, d in by_strat.items():
        resolved = d["wins"] + d["losses"]
        d["win_rate"] = round(d["wins"] / resolved * 100, 1) if resolved > 0 else 0.0
        d["avg_pnl"] = round(d["total_pnl"] / resolved, 2) if resolved > 0 else 0.0
        d["total_pnl"] = round(d["total_pnl"], 2)
        d["avg_wfe"] = round(sum(d["wfe_scores"]) / len(d["wfe_scores"]), 1) if d["wfe_scores"] else 0.0
        del d["wfe_scores"]

    return {"comparison": by_strat, "count": len(by_strat)}
