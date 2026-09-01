"""Daily Top-5 Stock Picks API — Murphy multi-indicator analysis.

Endpoints:
  GET  /api/daily-picks          — top 5 stocks today (cached, market-aware TTL)
  GET  /api/daily-picks/refresh  — force-refresh the cache
  GET  /api/daily-picks/{symbol} — full Murphy analysis for a single stock
  GET  /api/daily-picks/backtest — rolling backtest of the top-5 system (30 days)
"""
from __future__ import annotations

from dataclasses import asdict
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Query

from app.api.auth import require_token
from app.api.cache import cached, invalidate
from app.db import User
from app.market_hours import is_nse_open, screen_cache_ttl, nse_status
from app.providers.factory import get_provider
from app.providers.nse_list import get_nse_stocks
from app.strategies.murphy_analysis import scan_murphy, analyze_symbol
from app.strategies.daily_backtest import backtest_daily_picks
from app.universe import get_universe

router = APIRouter()


async def _build_symbol_name_pairs() -> list[tuple[str, str]]:
    """Build (symbol, name) pairs from the Nifty 100 universe + NSE name list."""
    symbols = get_universe("nifty100")
    name_map: dict[str, str] = {}
    try:
        nse_stocks = await get_nse_stocks()
        for s in nse_stocks:
            name_map[s["symbol"]] = s.get("name", s["symbol"])
    except Exception:
        pass
    return [(s, name_map.get(s, s)) for s in symbols]


async def _fetch_daily_picks() -> dict:
    """Run Murphy analysis on the Nifty 100 universe, return top 5."""
    provider = get_provider()
    symbols = await _build_symbol_name_pairs()
    analyses = await scan_murphy(provider, symbols, market="in")

    # Filter to actionable verdicts only.
    actionable = [a for a in analyses if a.verdict in ("strong_buy", "buy")]
    top_5 = actionable[:5]

    mk = nse_status()

    return {
        "picks": [
            {**asdict(a), "rank": i + 1}
            for i, a in enumerate(top_5)
        ],
        "total_scanned": len(analyses),
        "refreshed_at": datetime.now(timezone.utc).isoformat(),
        "market_status": mk["market_status"],
    }


@router.get("/daily-picks")
async def daily_picks(
    _t: User = Depends(require_token),
    proven_only: bool = Query(False),
):
    """Top 5 stocks today using Murphy multi-indicator analysis.

    Scans Nifty 50+Next 50 universe, computes Murphy analysis on each,
    returns top 5 by composite_score with full entry/exit/stop/target.

    If `proven_only=true`, picks are annotated with whether the Murphy
    strategy is proven (verified over time via virtual bets). If no
    strategies are proven yet, all picks are returned with a warning.
    """
    ttl = screen_cache_ttl(is_nse_open())
    result = await cached("daily:picks", ttl, _fetch_daily_picks)

    if proven_only:
        from app.db import SessionLocal
        from app.bot.verifier import compute_strategy_track_records, get_proven_strategies

        db = SessionLocal()
        try:
            records = await compute_strategy_track_records(db)
            proven = get_proven_strategies(records)
        finally:
            db.close()

        # Return a copy so we don't mutate the cached dict.
        result = dict(result)
        murphy_proven = "murphy" in proven
        result["murphy_proven"] = murphy_proven
        result["proven_strategies"] = proven
        if not proven:
            result["verification_warning"] = (
                "No strategies have been proven yet (need 7+ days of virtual trade data). "
                "Showing all picks — treat with caution until strategies are verified."
            )
        elif not murphy_proven:
            result["verification_warning"] = (
                "Murphy strategy is still in verification period. "
                "Showing picks but they haven't been verified yet."
            )
    return result


@router.get("/daily-picks/verification")
async def picks_verification(_t: User = Depends(require_token)):
    """Strategy verification dashboard — per-strategy track records with proven/testing/unproven verdict."""
    from app.db import SessionLocal
    from app.bot.verifier import compute_strategy_track_records

    db = SessionLocal()
    try:
        records = await compute_strategy_track_records(db)
    finally:
        db.close()

    return {
        "strategies": [
            {
                "strategy": r.strategy,
                "days_tracked": r.days_tracked,
                "total_trades": r.total_trades,
                "resolved_trades": r.resolved_trades,
                "wins": r.wins,
                "losses": r.losses,
                "win_rate": r.win_rate,
                "avg_pnl_pct": r.avg_pnl_pct,
                "total_pnl_pct": r.total_pnl_pct,
                "best_trade_pct": r.best_trade_pct,
                "worst_trade_pct": r.worst_trade_pct,
                "profitable_days": r.profitable_days,
                "consistency_pct": r.consistency_pct,
                "backtest_win_rate": r.backtest_win_rate,
                "backtest_avg_return": r.backtest_avg_return,
                "backtest_days": r.backtest_days,
                "verdict": r.verdict,
                "proven_since": r.proven_since.isoformat() if r.proven_since else None,
                "min_trades_met": r.min_trades_met,
                "min_days_met": r.min_days_met,
                "min_win_rate_met": r.min_win_rate_met,
                "min_pnl_met": r.min_pnl_met,
            }
            for r in records
        ],
        "proven_count": sum(1 for r in records if r.verdict == "proven"),
        "testing_count": sum(1 for r in records if r.verdict == "testing"),
        "unproven_count": sum(1 for r in records if r.verdict == "unproven"),
    }


@router.get("/daily-picks/refresh")
async def refresh_picks(_t: User = Depends(require_token)):
    """Force refresh the daily picks cache."""
    invalidate("daily:picks")
    return await _fetch_daily_picks()


@router.get("/daily-picks/backtest")
async def daily_picks_backtest(
    _t: User = Depends(require_token),
    days: int = Query(30, ge=5, le=60),
):
    """Rolling backtest of the Murphy top-5 system over the last N trading days."""
    async def _fetch():
        provider = get_provider()
        symbols = await _build_symbol_name_pairs()
        result = await backtest_daily_picks(provider, symbols, market="in", days=days)
        return {
            "days": [
                {
                    "date": d.date,
                    "picks": d.picks,
                    "day_pnl_pct": d.day_pnl_pct,
                }
                for d in result.days
            ],
            "summary": result.summary,
            "all_trades": [asdict(t) for t in result.all_trades],
        }

    # Backtest is expensive — cache for 1 hour.
    return await cached(f"daily:backtest:{days}", 3600, _fetch)


@router.get("/daily-picks/{symbol}")
async def pick_detail(symbol: str, _t: User = Depends(require_token)):
    """Full Murphy analysis for a single symbol."""
    symbol = symbol.strip().upper().replace(".NS", "").replace("NSE:", "")

    async def _fetch():
        provider = get_provider()
        name_map: dict[str, str] = {}
        try:
            nse_stocks = await get_nse_stocks()
            for s in nse_stocks:
                name_map[s["symbol"]] = s.get("name", s["symbol"])
        except Exception:
            pass
        name = name_map.get(symbol, symbol)
        analysis = await analyze_symbol(provider, symbol, name, market="in")
        if analysis is None:
            return {"symbol": symbol, "analysis": None, "message": "Insufficient data for analysis."}
        return {"symbol": symbol, "analysis": asdict(analysis)}

    return await cached(f"daily:pick:{symbol}", 300, _fetch)
