"""Autonomous paper trading bot engine.

Runs 10 strategies across the stock universe on a schedule:
  1. Murphy multi-indicator system (daily timeframe) — John Murphy's book
  2. Nison candlestick scalping (intraday) — Steve Nison's book
  3. VWAP pullback (intraday)
  4. Bollinger squeeze (intraday)
  5. PPO momentum (intraday)
  6. MA Trend Scalp (intraday) — EMA 9/21 crossover with 50-EMA trend filter
  7. Gap-and-Go (intraday) — gap up/down with opening range breakout
  8. S/R Reversal (intraday) — candlestick reversal at key support/resistance
  9. Momentum Breakout (intraday) — OR breakout with RSI + volume profile
  10. ABCD Pattern (intraday) — Fibonacci swing structure

Auto-resolves open trades when targets/stops are hit, expires at EOD,
computes strategy rankings with walk-forward validation, and generates
a single daily recommendation (best stock + best strategy).
"""
from __future__ import annotations

import asyncio
import logging
from datetime import date, datetime
from typing import Any

import pandas as pd
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import settings
from app.db import (
    BotDecision,
    DailyRecommendation,
    PaperTradeSignal,
    StrategyRanking,
    SessionLocal,
    User,
)
from app.market_hours import today_ist
from app.providers.factory import get_provider
from app.strategies import vwap_pullback as vwap_strat
from app.strategies import bollinger_squeeze as bollinger_strat
from app.strategies import ppo_momentum as ppo_strat
from app.strategies import scalping as scalp_strat
from app.strategies import ma_trend_scalp as ma_trend_strat
from app.strategies import gap_and_go as gap_go_strat
from app.strategies import sr_reversal as sr_reversal_strat
from app.strategies import momentum_breakout as mom_brk_strat
from app.strategies import abcd_pattern as abcd_strat
from app.strategies.murphy_analysis import scan_murphy
from app.strategies.walk_forward import run_walk_forward
from app.universe import get_universe

log = logging.getLogger("bot")

# Map bot strategy names to walk-forward backtest strategies.
_WF_STRATEGY_MAP = {
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


def _calc_pnl(side: str, entry: float, exit_price: float) -> float:
    if side == "long":
        return round(((exit_price - entry) / entry) * 100.0, 2)
    return round(((entry - exit_price) / entry) * 100.0, 2)


def _get_bot_user(db: Session) -> User:
    """Get or create the bot system user."""
    user = db.execute(select(User).where(User.email == "bot@system")).scalar_one_or_none()
    if not user:
        user = User(
            email="bot@system",
            name="Trading Bot",
            password_hash="!",
            capital=500000.0,
            is_guest=False,
        )
        db.add(user)
        db.commit()
        db.refresh(user)
    return user


# ---------------------------------------------------------------------------
# Resolve + expire (mirror paper_trade.py logic for BotDecision rows).
# ---------------------------------------------------------------------------

async def resolve_bot_decisions(db: Session) -> dict[str, Any]:
    """Check open BotDecision rows against current prices and auto-resolve."""
    open_trades = db.execute(
        select(BotDecision).where(BotDecision.status == "open")
    ).scalars().all()

    if not open_trades:
        return {"resolved": 0, "details": []}

    by_symbol: dict[str, list[BotDecision]] = {}
    for t in open_trades:
        by_symbol.setdefault(t.symbol, []).append(t)

    provider = get_provider()
    sem = asyncio.Semaphore(5)
    resolved_details: list[dict] = []

    async def _check_symbol(symbol: str, trades: list[BotDecision]):
        async with sem:
            try:
                quote = await provider.get_quote(symbol)
            except Exception as e:
                log.warning("Bot resolve: failed to fetch quote for %s: %s", symbol, e)
                return
            if not quote or quote.price <= 0:
                return
            price = quote.price
            for t in trades:
                hit_target = hit_stop = False
                if t.side == "long":
                    if price >= t.target:
                        hit_target = True
                    elif price <= t.stop_loss:
                        hit_stop = True
                else:
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
                        "id": t.id, "symbol": t.symbol, "strategy": t.strategy,
                        "side": t.side, "status": status,
                        "exit_price": exit_price, "pnl_pct": t.pnl_pct,
                    })

    await asyncio.gather(*[_check_symbol(s, ts) for s, ts in by_symbol.items()])
    if resolved_details:
        db.commit()
    return {"resolved": len(resolved_details), "details": resolved_details}


async def expire_bot_decisions(db: Session) -> dict[str, Any]:
    """EOD cleanup — expire all remaining open BotDecision rows."""
    open_trades = db.execute(
        select(BotDecision).where(BotDecision.status == "open")
    ).scalars().all()

    if not open_trades:
        return {"expired": 0, "details": []}

    by_symbol: dict[str, list[BotDecision]] = {}
    for t in open_trades:
        by_symbol.setdefault(t.symbol, []).append(t)

    provider = get_provider()
    sem = asyncio.Semaphore(5)
    expired_details: list[dict] = []

    async def _expire_symbol(symbol: str, trades: list[BotDecision]):
        async with sem:
            try:
                quote = await provider.get_quote(symbol)
            except Exception:
                quote = None
            price = quote.price if quote and quote.price > 0 else None
            for t in trades:
                exit_price = price if price else t.entry
                t.exit_price = exit_price
                t.exit_time = datetime.utcnow()
                t.status = "expired"
                t.pnl_pct = _calc_pnl(t.side, t.entry, exit_price)
                expired_details.append({
                    "id": t.id, "symbol": t.symbol,
                    "exit_price": exit_price, "pnl_pct": t.pnl_pct,
                })

    await asyncio.gather(*[_expire_symbol(s, ts) for s, ts in by_symbol.items()])
    db.commit()
    return {"expired": len(expired_details), "details": expired_details}


# ---------------------------------------------------------------------------
# Main bot scan — run all 5 strategies across the universe.
# ---------------------------------------------------------------------------

async def run_bot_scan(market: str = "nse") -> dict[str, Any]:
    """Scan universe with all 10 strategies, log signals, auto-resolve."""
    db = SessionLocal()
    try:
        bot_user = _get_bot_user(db)

        # Step 1: Auto-resolve existing open trades.
        resolve_result = await resolve_bot_decisions(db)

        # Step 2: Fetch universe.
        symbols = get_universe(settings.universe)
        provider = get_provider()
        sem = asyncio.Semaphore(10)
        today = today_ist()
        now = datetime.utcnow()

        # Deduplication: skip (symbol, strategy) pairs already logged today.
        existing = db.execute(
            select(BotDecision).where(BotDecision.date == today)
        ).scalars().all()
        existing_keys = {(r.symbol, r.strategy) for r in existing}

        # --- Murphy scan (daily timeframe, batch) ---
        murphy_signals = []
        try:
            sym_name_pairs = [(s, s) for s in symbols]
            murphy_results = await scan_murphy(provider, sym_name_pairs, market="in" if market == "nse" else "us")
            for analysis in murphy_results:
                if analysis.verdict not in ("buy", "strong_buy"):
                    continue
                if (analysis.symbol, "murphy") in existing_keys:
                    continue
                murphy_signals.append(analysis)
                if len(murphy_signals) >= 5:
                    break
        except Exception as e:
            log.warning("Murphy scan failed: %s", e)

        # --- Intraday strategies (per-symbol, fetch data once) ---
        strategy_fns = [
            ("scalp", scalp_strat.evaluate_scalp),
            ("vwap", vwap_strat.evaluate_vwap_pullback),
            ("bollinger", bollinger_strat.evaluate_squeeze),
            ("ppo", ppo_strat.evaluate_ppo),
            ("ma_trend", ma_trend_strat.evaluate_ma_trend_scalp),
            ("gap_go", gap_go_strat.evaluate_gap_and_go),
            ("sr_reversal", sr_reversal_strat.evaluate_sr_reversal),
            ("momentum_breakout", mom_brk_strat.evaluate_momentum_breakout),
            ("abcd", abcd_strat.evaluate_abcd_pattern),
        ]

        async def _fetch_and_eval(sym: str) -> list:
            async with sem:
                try:
                    daily = await provider.get_daily_history(sym, 60)
                    intraday = await provider.get_intraday(sym, settings.intraday_interval, 5)
                except Exception:
                    return []
                if daily is None or daily.empty or intraday is None or intraday.empty:
                    return []
                # Strip partial last bar (forming bar with very low volume).
                if len(intraday) > 20:
                    avg_vol = intraday["Volume"].iloc[-21:-1].mean()
                    last_vol = intraday["Volume"].iloc[-1]
                    if avg_vol > 0 and last_vol < 0.05 * avg_vol:
                        intraday = intraday.iloc[:-1]
                results = []
                for strat_name, fn in strategy_fns:
                    if (sym, strat_name) in existing_keys:
                        continue
                    try:
                        sig = fn(sym, daily, intraday)
                    except Exception:
                        continue
                    if sig is not None:
                        results.append((sym, strat_name, sig))
                return results

        all_results = await asyncio.gather(*[_fetch_and_eval(s) for s in symbols])

        # --- Log all signals to BotDecision + PaperTradeSignal ---
        new_signals: list[BotDecision] = []
        by_strategy_count: dict[str, int] = {
            "murphy": 0, "scalp": 0, "vwap": 0, "bollinger": 0, "ppo": 0,
            "ma_trend": 0, "gap_go": 0, "sr_reversal": 0,
            "momentum_breakout": 0, "abcd": 0,
        }

        # Murphy signals.
        for analysis in murphy_signals:
            if (analysis.symbol, "murphy") in existing_keys:
                continue
            existing_keys.add((analysis.symbol, "murphy"))
            row = BotDecision(
                scan_time=now, date=today, symbol=analysis.symbol,
                market=market.lower(), strategy="murphy",
                side="long", entry=analysis.entry,
                stop_loss=analysis.stop_loss, target=analysis.target1,
                confidence=analysis.composite_score / 100.0,
                risk_reward=analysis.risk_reward,
                composite_score=analysis.composite_score,
                verdict=analysis.verdict,
                status="open",
                explanation={
                    "explanation": analysis.explanation,
                    "caveats": analysis.caveats,
                    "factors": analysis.factors,
                    "risk_reward": analysis.risk_reward,
                },
            )
            db.add(row)
            new_signals.append(row)
            by_strategy_count["murphy"] += 1

            # Also log to PaperTradeSignal for unified stats.
            pt_row = PaperTradeSignal(
                user_id=bot_user.id, date=today, symbol=analysis.symbol,
                market=market.lower(), strategy="murphy",
                side="long", entry=analysis.entry,
                stop_loss=analysis.stop_loss, target=analysis.target1,
                confidence=analysis.composite_score / 100.0,
                status="open", entry_time=now,
                explanation={
                    "explanation": analysis.explanation,
                    "caveats": analysis.caveats,
                    "risk_reward": analysis.risk_reward,
                },
            )
            db.add(pt_row)

        # Intraday strategy signals.
        for results in all_results:
            for sym, strat_name, sig in results:
                if (sym, strat_name) in existing_keys:
                    continue
                existing_keys.add((sym, strat_name))
                target = sig.target if hasattr(sig, "target") else getattr(sig, "target1", sig.entry)
                rr = sig.risk_reward if hasattr(sig, "risk_reward") else 0.0
                row = BotDecision(
                    scan_time=now, date=today, symbol=sym,
                    market=market.lower(), strategy=strat_name,
                    side=sig.side, entry=sig.entry,
                    stop_loss=sig.stop_loss, target=target,
                    confidence=sig.confidence, risk_reward=rr,
                    status="open",
                    explanation={
                        "explanation": sig.explanation,
                        "caveats": getattr(sig, "caveats", []),
                        "risk_reward": rr,
                    },
                )
                db.add(row)
                new_signals.append(row)
                by_strategy_count[strat_name] = by_strategy_count.get(strat_name, 0) + 1

                pt_row = PaperTradeSignal(
                    user_id=bot_user.id, date=today, symbol=sym,
                    market=market.lower(), strategy=strat_name,
                    side=sig.side, entry=sig.entry,
                    stop_loss=sig.stop_loss, target=target,
                    confidence=sig.confidence,
                    status="open",
                    explanation={
                        "explanation": sig.explanation,
                        "caveats": getattr(sig, "caveats", []),
                        "risk_reward": rr,
                    },
                )
                db.add(pt_row)

        if new_signals:
            db.commit()

        return {
            "new_signals": len(new_signals),
            "resolved": resolve_result["resolved"],
            "by_strategy": by_strategy_count,
            "scan_time": now.isoformat(),
        }
    finally:
        db.close()


# ---------------------------------------------------------------------------
# Strategy rankings — daily performance comparison + walk-forward validation.
# ---------------------------------------------------------------------------

async def compute_strategy_rankings(db: Session, target_date: date) -> list[StrategyRanking]:
    """Compute daily strategy rankings using win rate + walk-forward efficiency."""
    rows = db.execute(
        select(BotDecision).where(BotDecision.date == target_date)
    ).scalars().all()

    # Group by strategy.
    by_strat: dict[str, list[BotDecision]] = {}
    for r in rows:
        by_strat.setdefault(r.strategy, []).append(r)

    # Fetch walk-forward data once (RELIANCE.NS, 252 days).
    wf_data: pd.DataFrame | None = None
    try:
        provider = get_provider()
        wf_data = await provider.get_daily_history("RELIANCE.NS", 252)
    except Exception as e:
        log.warning("Walk-forward data fetch failed: %s", e)

    rankings: list[StrategyRanking] = []
    for strat_name, strat_rows in by_strat.items():
        total = len(strat_rows)
        resolved = [r for r in strat_rows if r.status != "open"]
        wins = [r for r in resolved if r.pnl_pct is not None and r.pnl_pct > 0]
        losses = [r for r in resolved if r.pnl_pct is not None and r.pnl_pct <= 0]
        pnls = [r.pnl_pct for r in resolved if r.pnl_pct is not None]

        win_rate = round(len(wins) / len(resolved) * 100, 1) if resolved else 0.0
        avg_pnl = round(sum(pnls) / len(pnls), 2) if pnls else 0.0
        total_pnl = round(sum(pnls), 2) if pnls else 0.0

        # Walk-forward validation.
        wfe_score: float | None = None
        wfe_verdict: str | None = None
        if wf_data is not None and not wf_data.empty:
            wf_strat = _WF_STRATEGY_MAP.get(strat_name, "ema_crossover")
            try:
                wf_result = run_walk_forward(
                    wf_data, wf_strat, "RELIANCE", num_windows=3,
                )
                wfe_score = wf_result["summary"]["walk_forward_efficiency"]
                wfe_verdict = wf_result["summary"]["verdict"]
            except Exception as e:
                log.warning("Walk-forward failed for %s: %s", strat_name, e)

        rankings.append(StrategyRanking(
            date=target_date, strategy=strat_name,
            total_signals=total, resolved=len(resolved),
            wins=len(wins), losses=len(losses),
            win_rate=win_rate, avg_pnl_pct=avg_pnl, total_pnl_pct=total_pnl,
            best_trade_pct=max(pnls) if pnls else None,
            worst_trade_pct=min(pnls) if pnls else None,
            wfe_score=wfe_score, wfe_verdict=wfe_verdict,
        ))

    # Compute ranking score: 0.4*win_rate + 0.3*normalized_avg_pnl + 0.3*wfe_score
    # Normalize avg_pnl to 0-100 scale (assume ±5% range → cap at ±5).
    # Normalize wfe to 0-100 scale (already 0-100, but can be negative → floor at 0).
    for r in rankings:
        norm_pnl = max(0.0, min(100.0, (r.avg_pnl_pct + 5.0) / 10.0 * 100.0)) if r.avg_pnl_pct is not None else 0.0
        norm_wfe = max(0.0, min(100.0, r.wfe_score)) if r.wfe_score is not None else 0.0
        score = 0.4 * r.win_rate + 0.3 * norm_pnl + 0.3 * norm_wfe
        r.recommendation = "recommended" if score > 50 else "caution" if score > 25 else "avoid"

    rankings.sort(key=lambda r: 0.4 * r.win_rate + 0.3 * (r.avg_pnl_pct or 0) + 0.3 * (r.wfe_score or 0), reverse=True)
    for i, r in enumerate(rankings):
        r.rank = i + 1

    # Delete existing rankings for this date and insert new ones.
    existing = db.execute(
        select(StrategyRanking).where(StrategyRanking.date == target_date)
    ).scalars().all()
    for e in existing:
        db.delete(e)
    for r in rankings:
        db.add(r)
    db.commit()
    return rankings


# ---------------------------------------------------------------------------
# Daily recommendation — the bot's single best pick.
# ---------------------------------------------------------------------------

async def generate_daily_recommendation(db: Session, target_date: date) -> DailyRecommendation | None:
    """Pick the best stock/strategy combination for the day.

    Filters to proven strategies first (verified over time via virtual bets).
    If no strategies are proven yet (first week), uses all strategies but
    adds a caveat about the verification period.
    """
    # NEW: Get proven strategies first.
    from app.bot.verifier import compute_strategy_track_records, get_proven_strategies
    records = await compute_strategy_track_records(db)
    proven = get_proven_strategies(records)

    # Ensure rankings exist.
    rankings = db.execute(
        select(StrategyRanking).where(StrategyRanking.date == target_date)
    ).scalars().all()
    if not rankings:
        rankings = await compute_strategy_rankings(db, target_date)

    if not rankings:
        return None

    # Filter to proven strategies only.
    verification_caveats: list[str] = []
    if proven:
        filtered = [r for r in rankings if r.strategy in proven]
        if filtered:
            rankings = filtered
            verification_caveats.append(
                f"Recommendation from proven strategy: {rankings[0].strategy} "
                f"(verified over {next((r.days_tracked for r in records if r.strategy == rankings[0].strategy), 0)} days)."
            )
        else:
            verification_caveats.append(
                "No proven strategies had signals today — using best available strategy."
            )
    else:
        verification_caveats.append(
            "No strategies have been proven yet (need 7+ days of virtual trade data). "
            "Recommendation is based on today's performance only — treat with caution."
        )

    top_strategy = rankings[0].strategy

    # Get all BotDecision rows for this strategy today.
    decisions = db.execute(
        select(BotDecision).where(
            BotDecision.date == target_date,
            BotDecision.strategy == top_strategy,
        )
    ).scalars().all()

    if not decisions:
        return None

    # Pick the best signal: highest composite_score (Murphy) or confidence*risk_reward (others).
    def _score(d: BotDecision) -> float:
        if d.composite_score is not None:
            return d.composite_score
        return (d.confidence or 0) * (d.risk_reward or 0) * 100

    decisions = sorted(decisions, key=_score, reverse=True)
    best = decisions[0]

    # Collect alternatives from other strategies.
    alternatives = []
    for ranking in rankings[1:]:
        alt_decisions = db.execute(
            select(BotDecision).where(
                BotDecision.date == target_date,
                BotDecision.strategy == ranking.strategy,
            )
        ).scalars().all()
        if alt_decisions:
            alt_best = max(alt_decisions, key=_score)
            alternatives.append({
                "symbol": alt_best.symbol,
                "strategy": ranking.strategy,
                "rank": ranking.rank,
                "entry": alt_best.entry,
                "stop_loss": alt_best.stop_loss,
                "target": alt_best.target,
                "confidence": alt_best.confidence,
            })

    explanation_text = (
        f"Top pick: {best.symbol} via {top_strategy} strategy. "
        f"Entry ₹{best.entry:.2f}, SL ₹{best.stop_loss:.2f}, Target ₹{best.target:.2f}. "
        f"R:R = {best.risk_reward:.2f}. "
    )
    if best.verdict:
        explanation_text += f"Murphy verdict: {best.verdict} (score {best.composite_score:.0f}/100). "
    if best.explanation and isinstance(best.explanation, dict):
        caveats = best.explanation.get("caveats", [])
    else:
        caveats = []
    caveats = list(caveats) + verification_caveats

    # Upsert by date.
    existing = db.execute(
        select(DailyRecommendation).where(DailyRecommendation.date == target_date)
    ).scalar_one_or_none()
    if existing:
        db.delete(existing)
        db.commit()

    rec = DailyRecommendation(
        date=target_date, symbol=best.symbol, name=best.symbol,
        strategy=top_strategy, side=best.side,
        entry=best.entry, stop_loss=best.stop_loss, target=best.target,
        confidence=best.confidence, risk_reward=best.risk_reward,
        composite_score=best.composite_score,
        explanation=explanation_text, caveats=caveats,
        alternatives=alternatives[:5],
    )
    db.add(rec)
    db.commit()
    db.refresh(rec)
    return rec
