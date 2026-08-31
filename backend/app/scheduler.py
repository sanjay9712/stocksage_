"""APScheduler jobs on IST market hours.

  09:30 - first scan (opening range formed)
  every 5 min 09:30-15:00 - rescan for new breakouts
  every 10 min 09:30-15:00 - paper-trade scan + auto-resolve
  15:20 - expire all open paper trades (EOD cleanup)
  18:00 - daily AMFI NAV snapshot (builds MF history for risk metrics)
"""
from __future__ import annotations

import asyncio
import logging

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

from app.config import settings

log = logging.getLogger("scheduler")
_scheduler: AsyncIOScheduler | None = None


def _run_scan_sync():
    """Bridge sync APScheduler job -> async run_scan."""
    try:
        asyncio.get_running_loop()  # noqa: F841
    except RuntimeError:
        pass
    from app.screener.runner import run_scan
    try:
        asyncio.run(run_scan())
    except Exception as e:  # pragma: no cover
        log.exception("scan failed: %s", e)


def _run_paper_scan_sync():
    """Paper-trade scan: log new signals + auto-resolve open trades."""
    try:
        from app.db import SessionLocal
        from app.api.paper_trade import _auto_resolve_open_trades
        import app.api.paper_trade as pt

        async def _run():
            db = SessionLocal()
            try:
                # Auto-resolve open trades against current prices.
                result = await _auto_resolve_open_trades(db)
                if result["resolved"] > 0:
                    log.info("paper-trade: auto-resolved %d trades", result["resolved"])
            finally:
                db.close()

        asyncio.run(_run())
    except Exception as e:  # pragma: no cover
        log.exception("paper-trade scan failed: %s", e)


def _run_paper_expire_sync():
    """End-of-day: expire all remaining open paper trades."""
    try:
        from app.db import SessionLocal
        from app.providers.factory import get_provider
        from app.db import PaperTradeSignal
        from sqlalchemy import select

        async def _run():
            db = SessionLocal()
            try:
                open_trades = db.execute(
                    select(PaperTradeSignal).where(PaperTradeSignal.status == "open")
                ).scalars().all()
                if not open_trades:
                    return

                from datetime import datetime
                provider = get_provider()
                by_symbol: dict[str, list] = {}
                for t in open_trades:
                    by_symbol.setdefault(t.symbol, []).append(t)

                sem = asyncio.Semaphore(5)

                async def _expire(symbol, trades):
                    async with sem:
                        try:
                            quote = await provider.get_quote(symbol)
                            price = quote.price if quote and quote.price > 0 else None
                        except Exception:
                            price = None
                        for t in trades:
                            exit_price = price if price else t.entry
                            t.exit_price = exit_price
                            t.exit_time = datetime.utcnow()
                            t.status = "expired"
                            if t.side == "long":
                                t.pnl_pct = round(((exit_price - t.entry) / t.entry) * 100, 2)
                            else:
                                t.pnl_pct = round(((t.entry - exit_price) / t.entry) * 100, 2)

                await asyncio.gather(*[_expire(s, ts) for s, ts in by_symbol.items()])
                db.commit()
                log.info("paper-trade: expired %d open trades", len(open_trades))
            finally:
                db.close()

        asyncio.run(_run())
    except Exception as e:  # pragma: no cover
        log.exception("paper-trade expire failed: %s", e)


def _run_amfi_snapshot_sync():
    """Daily AMFI NAV snapshot — accumulates MF history for risk metrics."""
    try:
        from app.strategies.mf_screener import snapshot_amfi_navs
        asyncio.run(snapshot_amfi_navs())
    except Exception as e:  # pragma: no cover
        log.exception("AMFI NAV snapshot failed: %s", e)


def _run_daily_digest_sync():
    """Generate and store the daily market digest (emailed if SMTP configured)."""
    try:
        from app.strategies.daily_digest import generate_and_store_digest
        asyncio.run(generate_and_store_digest())
    except Exception as e:  # pragma: no cover
        log.exception("Daily digest generation failed: %s", e)


def _run_bot_scan_sync():
    """Bot scan: run all 10 strategies across universe, log signals, auto-resolve."""
    try:
        from app.bot.engine import run_bot_scan

        async def _run():
            result = await run_bot_scan("nse")
            if result["new_signals"] > 0 or result["resolved"] > 0:
                log.info("bot: %d new signals, %d resolved", result["new_signals"], result["resolved"])

        asyncio.run(_run())
    except Exception as e:  # pragma: no cover
        log.exception("bot scan failed: %s", e)


def _run_bot_ranking_sync():
    """End-of-day: compute strategy rankings + generate daily recommendation."""
    try:
        from app.bot.engine import compute_strategy_rankings, generate_daily_recommendation
        from app.db import SessionLocal
        from app.market_hours import today_ist

        async def _run():
            db = SessionLocal()
            try:
                today = today_ist()
                await compute_strategy_rankings(db, today)
                await generate_daily_recommendation(db, today)
                log.info("bot: rankings + recommendation generated for %s", today)
            finally:
                db.close()

        asyncio.run(_run())
    except Exception as e:  # pragma: no cover
        log.exception("bot ranking failed: %s", e)


def start_scheduler() -> AsyncIOScheduler:
    global _scheduler
    if _scheduler is not None:
        return _scheduler
    sched = AsyncIOScheduler(timezone=settings.tz)

    # Opening-range scan at 09:30, then every 5 minutes through 15:00.
    sched.add_job(
        _run_scan_sync,
        CronTrigger(hour="9-14", minute="30,35,40,45,50,55", timezone=settings.tz),
        id="scan-morning",
        misfire_grace_time=600,
        coalesce=True,
    )
    sched.add_job(
        _run_scan_sync,
        CronTrigger(hour="10-14", minute="*/5", timezone=settings.tz),
        id="scan-midday",
        misfire_grace_time=600,
        coalesce=True,
    )
    sched.add_job(
        _run_scan_sync,
        CronTrigger(hour="15", minute="0,5,10", timezone=settings.tz),
        id="scan-close",
        misfire_grace_time=600,
        coalesce=True,
    )
    # Paper-trade auto-resolve every 10 min during market hours (09:30-15:00).
    sched.add_job(
        _run_paper_scan_sync,
        CronTrigger(hour="9-14", minute="*/10", timezone=settings.tz),
        id="paper-resolve-morning",
        misfire_grace_time=600,
        coalesce=True,
    )
    sched.add_job(
        _run_paper_scan_sync,
        CronTrigger(hour="15", minute="0", timezone=settings.tz),
        id="paper-resolve-close",
        misfire_grace_time=600,
        coalesce=True,
    )
    # End-of-day: expire all remaining open paper trades at 15:20 IST.
    sched.add_job(
        _run_paper_expire_sync,
        CronTrigger(hour="15", minute="20", timezone=settings.tz),
        id="paper-expire-eod",
        misfire_grace_time=3600,
        coalesce=True,
    )
    # Daily AMFI NAV snapshot at 18:00 IST — builds MF history over time.
    sched.add_job(
        _run_amfi_snapshot_sync,
        CronTrigger(hour="18", minute="0", timezone=settings.tz),
        id="amfi-nav-snapshot",
        misfire_grace_time=3600,
        coalesce=True,
    )
    # Daily market digest at configured hour (default 16:00 IST — after close).
    sched.add_job(
        _run_daily_digest_sync,
        CronTrigger(hour=str(settings.digest_send_hour), minute="0", timezone=settings.tz),
        id="daily-digest",
        misfire_grace_time=3600,
        coalesce=True,
    )
    # Bot scan every 5 min during market hours (09:30-15:00).
    sched.add_job(
        _run_bot_scan_sync,
        CronTrigger(hour="9-14", minute="*/5", timezone=settings.tz),
        id="bot-scan-morning",
        misfire_grace_time=600,
        coalesce=True,
    )
    sched.add_job(
        _run_bot_scan_sync,
        CronTrigger(hour="15", minute="0,5,10", timezone=settings.tz),
        id="bot-scan-close",
        misfire_grace_time=600,
        coalesce=True,
    )
    # End-of-day: compute strategy rankings + daily recommendation at 15:25.
    sched.add_job(
        _run_bot_ranking_sync,
        CronTrigger(hour="15", minute="25", timezone=settings.tz),
        id="bot-rank-daily",
        misfire_grace_time=3600,
        coalesce=True,
    )
    sched.start()
    _scheduler = sched
    log.info("scheduler started (tz=%s)", settings.tz)
    return sched
