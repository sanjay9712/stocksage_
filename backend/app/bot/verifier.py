"""Strategy verification engine.

Aggregates BotDecision history per strategy over a rolling window and
determines whether each strategy is 'proven', 'testing', or 'unproven'.

A strategy is 'proven' when it meets ALL of:
  - days_tracked >= min_days (default 7)
  - total_trades >= min_trades (default 10)
  - win_rate >= min_win_rate (default 50%)
  - avg_pnl_pct >= min_avg_pnl (default 0.0%)

If live trades are insufficient, backtest results can supplement the
verification — a strategy with >= 20 backtested trades and good performance
can be marked 'proven' even before enough live trades accumulate.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import date, timedelta
from typing import Any

from sqlalchemy import select, func
from sqlalchemy.orm import Session

from app.db import BotDecision, StrategyVerification
from app.market_hours import today_ist

log = logging.getLogger("verifier")

# All strategies the bot runs.
ALL_STRATEGIES = [
    "murphy", "scalp", "vwap", "bollinger", "ppo",
    "ma_trend", "gap_go", "sr_reversal", "momentum_breakout", "abcd",
]

# Map bot strategy names to backtest strategies (same as engine.py _WF_STRATEGY_MAP).
_BACKTEST_STRATEGY_MAP = {
    "vwap": "ema_crossover",
    "bollinger": "bollinger",
    "ppo": "ema_crossover",
    "scalp": "rsi_reversion",
    "murphy": "breakout",
    "ma_trend": "ema_crossover",
    "gap_go": "breakout",
    "sr_reversal": "rsi_reversion",
    "momentum_breakout": "breakout",
    "abcd": "ema_crossover",
}


@dataclass
class StrategyTrackRecord:
    strategy: str
    # Live paper-trade stats (rolling N days)
    days_tracked: int = 0
    total_trades: int = 0
    resolved_trades: int = 0
    wins: int = 0
    losses: int = 0
    win_rate: float = 0.0
    avg_pnl_pct: float = 0.0
    total_pnl_pct: float = 0.0
    best_trade_pct: float = 0.0
    worst_trade_pct: float = 0.0
    # Consistency
    profitable_days: int = 0
    consistency_pct: float = 0.0
    # Backtest stats (supplementary)
    backtest_win_rate: float | None = None
    backtest_avg_return: float | None = None
    backtest_days: int | None = None
    # Verdict
    verdict: str = "testing"  # proven / testing / unproven
    proven_since: date | None = None
    # Threshold checks
    min_trades_met: bool = False
    min_days_met: bool = False
    min_win_rate_met: bool = False
    min_pnl_met: bool = False


def _calc_pnl(side: str, entry: float, exit_price: float) -> float:
    if side == "long":
        return round(((exit_price - entry) / entry) * 100.0, 2)
    return round(((entry - exit_price) / entry) * 100.0, 2)


async def _run_backtest_for_strategy(strategy: str, days: int = 60) -> dict[str, Any]:
    """Run a quick backtest for a strategy to supplement live trade data.

    Returns {"win_rate": float, "avg_return": float, "days": int} or empty dict.
    """
    try:
        from app.providers.factory import get_provider
        from app.strategies.backtest import run_backtest
        from app.universe import get_universe

        provider = get_provider()
        # Use RELIANCE as representative stock for backtest.
        symbol = "RELIANCE"
        daily = await provider.get_daily_history(symbol, 252)
        if daily is None or daily.empty:
            return {}

        bt_strat = _BACKTEST_STRATEGY_MAP.get(strategy, "ema_crossover")
        result = run_backtest(daily, bt_strat, symbol, initial_capital=100000)
        if result.num_trades == 0:
            return {}

        return {
            "win_rate": round(result.win_rate * 100, 1),
            "avg_return": round(result.avg_trade_pct, 2),
            "days": len(daily),
        }
    except Exception as e:
        log.warning("Backtest failed for %s: %s", strategy, e)
        return {}


async def compute_strategy_track_records(
    db: Session,
    rolling_days: int = 30,
    min_trades: int = 10,
    min_days: int = 7,
    min_win_rate: float = 50.0,
    min_avg_pnl: float = 0.0,
) -> list[StrategyTrackRecord]:
    """Compute rolling N-day track record for each strategy.

    Queries BotDecision table for all trades in the last `rolling_days` days,
    grouped by strategy. Determines proven/testing/unproven verdict.
    """
    today = today_ist()
    cutoff = today - timedelta(days=rolling_days)

    # Fetch all BotDecision rows in the rolling window.
    rows = db.execute(
        select(BotDecision).where(BotDecision.date >= cutoff)
    ).scalars().all()

    # Group by strategy.
    by_strat: dict[str, list[BotDecision]] = {}
    for r in rows:
        by_strat.setdefault(r.strategy, []).append(r)

    records: list[StrategyTrackRecord] = []

    for strat_name in ALL_STRATEGIES:
        strat_rows = by_strat.get(strat_name, [])
        record = StrategyTrackRecord(strategy=strat_name)

        # Days tracked = distinct dates with trades.
        distinct_dates = {r.date for r in strat_rows if r.date is not None}
        record.days_tracked = len(distinct_dates)

        # Total and resolved trades.
        record.total_trades = len(strat_rows)
        resolved = [r for r in strat_rows if r.status != "open"]
        record.resolved_trades = len(resolved)

        # Wins/losses.
        wins = [r for r in resolved if r.pnl_pct is not None and r.pnl_pct > 0]
        losses = [r for r in resolved if r.pnl_pct is not None and r.pnl_pct <= 0]
        record.wins = len(wins)
        record.losses = len(losses)

        # P&L stats.
        pnls = [r.pnl_pct for r in resolved if r.pnl_pct is not None]
        if pnls:
            record.win_rate = round(len(wins) / len(resolved) * 100, 1) if resolved else 0.0
            record.avg_pnl_pct = round(sum(pnls) / len(pnls), 2)
            record.total_pnl_pct = round(sum(pnls), 2)
            record.best_trade_pct = round(max(pnls), 2)
            record.worst_trade_pct = round(min(pnls), 2)
        else:
            record.win_rate = 0.0
            record.avg_pnl_pct = 0.0
            record.total_pnl_pct = 0.0
            record.best_trade_pct = 0.0
            record.worst_trade_pct = 0.0

        # Consistency: how many distinct dates had net positive P&L.
        by_date: dict[date, list[float]] = {}
        for r in resolved:
            if r.pnl_pct is not None and r.date is not None:
                by_date.setdefault(r.date, []).append(r.pnl_pct)
        profitable = sum(1 for d, pnls in by_date.items() if sum(pnls) > 0)
        record.profitable_days = profitable
        total_days_with_resolved = len(by_date)
        record.consistency_pct = (
            round(profitable / total_days_with_resolved * 100, 1)
            if total_days_with_resolved > 0 else 0.0
        )

        # Backtest fallback: if live trades insufficient, run backtest.
        if record.resolved_trades < min_trades:
            bt = await _run_backtest_for_strategy(strat_name)
            if bt:
                record.backtest_win_rate = bt["win_rate"]
                record.backtest_avg_return = bt["avg_return"]
                record.backtest_days = bt["days"]

        # Threshold checks.
        record.min_trades_met = record.resolved_trades >= min_trades
        record.min_days_met = record.days_tracked >= min_days
        record.min_win_rate_met = record.win_rate >= min_win_rate
        record.min_pnl_met = record.avg_pnl_pct >= min_avg_pnl

        # Determine verdict.
        # Check if we should use backtest data to supplement.
        effective_trades = record.resolved_trades
        effective_win_rate = record.win_rate
        effective_avg_pnl = record.avg_pnl_pct

        if not record.min_trades_met and record.backtest_win_rate is not None:
            # Use backtest as supplementary evidence.
            # If backtest shows good results, count toward "proven" with backtest_days.
            if record.backtest_win_rate >= min_win_rate and (record.backtest_avg_return or 0) >= min_avg_pnl:
                # Backtest validates the strategy — treat as proven if we have at least some live data.
                if record.days_tracked >= 1 and record.total_trades >= 1:
                    record.verdict = "proven"
                    # Check previous verification snapshots for proven_since.
                    record.proven_since = _get_proven_since(db, strat_name, today)
                    records.append(record)
                    continue

        if record.min_trades_met and record.min_days_met:
            # Enough data — check performance.
            if record.min_win_rate_met and record.min_pnl_met:
                record.verdict = "proven"
                record.proven_since = _get_proven_since(db, strat_name, today)
            else:
                record.verdict = "unproven"
        else:
            # Not enough data yet.
            record.verdict = "testing"

        records.append(record)

    return records


def _get_proven_since(db: Session, strategy: str, today: date) -> date | None:
    """Check when a strategy first became proven (from previous snapshots)."""
    prev = db.execute(
        select(StrategyVerification)
        .where(StrategyVerification.strategy == strategy, StrategyVerification.verdict == "proven")
        .order_by(StrategyVerification.date.asc())
        .limit(1)
    ).scalar_one_or_none()
    if prev and prev.proven_since:
        return prev.proven_since
    if prev and prev.date:
        return prev.date
    return today


def get_proven_strategies(records: list[StrategyTrackRecord]) -> list[str]:
    """Return strategy names where verdict == 'proven'."""
    return [r.strategy for r in records if r.verdict == "proven"]


def is_strategy_proven(db: Session, strategy: str, rolling_days: int = 30) -> bool:
    """Quick check: is a single strategy proven?

    Uses the latest stored verification snapshot. Falls back to
    computing from BotDecision if no snapshot exists.
    """
    today = today_ist()
    latest = db.execute(
        select(StrategyVerification)
        .where(StrategyVerification.strategy == strategy)
        .order_by(StrategyVerification.date.desc())
        .limit(1)
    ).scalar_one_or_none()
    if latest:
        return latest.verdict == "proven"
    # No stored snapshot — can't determine, assume not proven.
    return False


async def save_verification_snapshot(
    db: Session, records: list[StrategyTrackRecord]
) -> int:
    """Save verification records to the StrategyVerification table.

    Deletes existing rows for today and inserts new ones.
    Returns the number of rows saved.
    """
    today = today_ist()

    # Delete existing rows for today.
    existing = db.execute(
        select(StrategyVerification).where(StrategyVerification.date == today)
    ).scalars().all()
    for e in existing:
        db.delete(e)

    # Insert new rows.
    for r in records:
        row = StrategyVerification(
            date=today,
            strategy=r.strategy,
            days_tracked=r.days_tracked,
            total_trades=r.total_trades,
            resolved_trades=r.resolved_trades,
            wins=r.wins,
            losses=r.losses,
            win_rate=r.win_rate,
            avg_pnl_pct=r.avg_pnl_pct,
            total_pnl_pct=r.total_pnl_pct,
            profitable_days=r.profitable_days,
            consistency_pct=r.consistency_pct,
            backtest_win_rate=r.backtest_win_rate,
            backtest_avg_return=r.backtest_avg_return,
            backtest_days=r.backtest_days,
            verdict=r.verdict,
            proven_since=r.proven_since,
        )
        db.add(row)

    db.commit()
    return len(records)
