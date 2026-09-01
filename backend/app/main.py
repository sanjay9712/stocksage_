"""FastAPI entrypoint."""
from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.db import init_db
from app.api import picks as picks_api
from app.api import commodities as commodities_api
from app.api import etf as etf_api
from app.api import mf as mf_api
from app.api import holdings as holdings_api
from app.api import scalping as scalping_api
from app.api import us_market as us_market_api
from app.api import advanced as advanced_api
from app.api import paper_trade as paper_api
from app.api import sector_rotation as sector_rotation_api
from app.api import institutional_flow as institutional_flow_api
from app.api import ipo as ipo_api
from app.api import daily_top_picks as daily_picks_api
from app.api import dividends as dividends_api
from app.api import sip_calculator as sip_calculator_api
from app.api import tax_harvest as tax_harvest_api
from app.api import correlation as correlation_api
from app.api import momentum_rotation as momentum_rotation_api
from app.api import gap_scanner as gap_scanner_api
from app.api import volume_profile as volume_profile_api
from app.api import vwap_scanner as vwap_scanner_api
from app.api import opening_range_scanner as opening_range_scanner_api
from app.api import options_oi as options_oi_api
from app.api import backtest as backtest_api
from app.api import walk_forward as walk_forward_api
from app.api import portfolio_sim as portfolio_sim_api
from app.api import position_sizing as position_sizing_api
from app.api import price_alerts as price_alerts_api
from app.api import signal_alerts as signal_alerts_api
from app.api import daily_digest as daily_digest_api
from app.api import notifier as notifier_api
from app.api import broker_trade as broker_trade_api
from app.api import risk_analytics as risk_analytics_api
from app.api import rebalancing as rebalancing_api
from app.api import user_auth as user_auth_api
from app.api import bot as bot_api
from app.api import long_term as long_term_api


async def _prewarm_caches():
    """Warm the slowest endpoint caches in the background on startup.

    This eliminates the 5-8s cold-cache penalty for the first user after a
    server restart.  Runs as a background task so the server starts serving
    immediately.
    """
    import asyncio
    from app.api.cache import cached
    from app.api.advanced import _scan_universe
    from app.strategies import vwap_pullback as vwap_strat
    from app.strategies import bollinger_squeeze as bollinger_strat
    from app.strategies import ppo_momentum as ppo_strat
    from app.market_hours import is_nse_open, screen_cache_ttl

    ttl = screen_cache_ttl(is_nse_open())
    # Fire all three strategy scans + stock screen concurrently.
    await asyncio.gather(
        cached("strat:vwap:all", ttl, lambda: _scan_universe(vwap_strat.evaluate_vwap_pullback, "vwap")),
        cached("strat:bollinger:all", ttl, lambda: _scan_universe(bollinger_strat.evaluate_squeeze, "bollinger")),
        cached("strat:ppo:all", ttl, lambda: _scan_universe(ppo_strat.evaluate_ppo, "ppo")),
        cached("nse_stock_screen", ttl, _prewarm_stock_screen),
        return_exceptions=True,
    )


async def _prewarm_stock_screen():
    """Build the NSE stock screen result for cache pre-warming."""
    import asyncio
    from datetime import datetime, timezone
    from app.providers.factory import get_provider
    from app.market_hours import nse_status
    from app.strategies import stock_screener as stock_scr
    from app.universe import get_universe
    from app.providers.nse_list import get_nse_stocks

    provider = get_provider()
    symbols = get_universe("nifty100")
    mk = nse_status()

    name_map: dict[str, str] = {}
    try:
        nse_stocks = await get_nse_stocks()
        for s in nse_stocks:
            name_map[s["symbol"]] = s.get("name", s["symbol"])
    except Exception:
        pass

    benchmark_close = None
    try:
        bench_daily = await provider.get_daily_history("^NSEI", 252)
        if not bench_daily.empty:
            benchmark_close = bench_daily["Close"]
    except Exception:
        pass

    sem = asyncio.Semaphore(20)

    async def _screen(s):
        async with sem:
            return await stock_scr.screen_stock(
                provider, s, name_map.get(s, s), currency="₹", rf_annual=0.06,
                benchmark_close=benchmark_close,
            )

    tasks = [_screen(s) for s in symbols]
    results = await asyncio.gather(*tasks, return_exceptions=True)
    out = [r for r in results if r is not None and not isinstance(r, Exception)]
    out.sort(key=lambda d: d.get("composite", 0), reverse=True)
    return {
        "stocks": out,
        "refreshed_at": datetime.now(timezone.utc).isoformat(),
        "market_open": mk["market_open"],
        "market_status": mk["market_status"],
    }


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    # Start the scheduler only under the running server (not during tests).
    try:
        from app.scheduler import start_scheduler
        start_scheduler()
    except Exception:  # pragma: no cover - scheduler is non-critical for API
        pass
    # Pre-warm the slowest caches in the background so the first user
    # doesn't wait 5-8s for a cold-cache rebuild.
    import asyncio
    asyncio.create_task(_prewarm_caches())
    yield


app = FastAPI(title="Intraday Screener", version="0.1.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[o.strip() for o in settings.cors_origins.split(",") if o.strip()],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(picks_api.router, prefix="/api")
app.include_router(commodities_api.router, prefix="/api")
app.include_router(etf_api.router, prefix="/api")
app.include_router(mf_api.router, prefix="/api")
app.include_router(holdings_api.router, prefix="/api")
app.include_router(scalping_api.router, prefix="/api")
app.include_router(us_market_api.router, prefix="/api")
app.include_router(advanced_api.router, prefix="/api")
app.include_router(paper_api.router, prefix="/api")
app.include_router(sector_rotation_api.router, prefix="/api")
app.include_router(institutional_flow_api.router, prefix="/api")
app.include_router(dividends_api.router, prefix="/api")
app.include_router(ipo_api.router, prefix="/api")
app.include_router(daily_picks_api.router, prefix="/api")
app.include_router(sip_calculator_api.router, prefix="/api")
app.include_router(tax_harvest_api.router, prefix="/api")
app.include_router(correlation_api.router, prefix="/api")
app.include_router(momentum_rotation_api.router, prefix="/api")
app.include_router(gap_scanner_api.router, prefix="/api")
app.include_router(volume_profile_api.router, prefix="/api")
app.include_router(vwap_scanner_api.router, prefix="/api")
app.include_router(opening_range_scanner_api.router, prefix="/api")
app.include_router(options_oi_api.router, prefix="/api")
app.include_router(backtest_api.router, prefix="/api")
app.include_router(walk_forward_api.router, prefix="/api")
app.include_router(portfolio_sim_api.router, prefix="/api")
app.include_router(position_sizing_api.router, prefix="/api")
app.include_router(price_alerts_api.router, prefix="/api")
app.include_router(signal_alerts_api.router, prefix="/api")
app.include_router(daily_digest_api.router, prefix="/api")
app.include_router(notifier_api.router, prefix="/api")
app.include_router(broker_trade_api.router, prefix="/api")
app.include_router(risk_analytics_api.router, prefix="/api")
app.include_router(rebalancing_api.router, prefix="/api")
app.include_router(user_auth_api.router, prefix="/api")
app.include_router(bot_api.router, prefix="/api")
app.include_router(long_term_api.router, prefix="/api")


@app.get("/health")
async def health() -> dict:
    return {"status": "ok", "provider": settings.data_provider}
