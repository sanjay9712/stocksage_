"""Long-term investing picks — sector-diversified portfolio.

Scans Nifty 100, scores with long-term weights (quality 40% / value 30% /
momentum 30%), groups by sector, picks the best stock from each of the
top sectors, and returns a diversified portfolio with full metrics.

Endpoints:
  GET   /api/long-term/picks          — curated sector-diversified picks
  POST  /api/long-term/picks/refresh  — force-refresh the cache
"""
from __future__ import annotations

import asyncio
from collections import defaultdict
from datetime import datetime, timezone

from fastapi import APIRouter, Depends

from app.api.auth import require_token
from app.api.cache import cached, invalidate
from app.market_hours import nse_status
from app.providers.factory import get_provider
from app.providers.fundamentals import (
    get_analyst_recommendations,
    get_stock_fundamentals,
)
from app.strategies import stock_screener as stock_scr
from app.strategies.multifactor import LONG_TERM_WEIGHTS
from app.universe import get_universe

router = APIRouter()

MAX_SECTORS = 10
MIN_COMPOSITE = 0.50
TTL = 3600  # 1 hour — long-term fundamentals change slowly


async def _build_long_term_picks() -> dict:
    """Scan Nifty 100, group by sector, pick best from each."""
    provider = get_provider()
    symbols = get_universe("nifty100")

    # Build symbol → name map from NSE list.
    from app.providers.nse_list import get_nse_stocks

    name_map: dict[str, str] = {}
    try:
        nse_stocks = await get_nse_stocks()
        for s in nse_stocks:
            name_map[s["symbol"]] = s.get("name", s["symbol"])
    except Exception:
        pass

    # Fetch benchmark (NIFTY 50) for relative strength.
    benchmark_close = None
    try:
        bench_daily = await provider.get_daily_history("^NSEI", 252)
        if not bench_daily.empty:
            benchmark_close = bench_daily["Close"]
    except Exception:
        pass

    sem = asyncio.Semaphore(20)

    async def _screen(s: str) -> dict | None:
        async with sem:
            return await stock_scr.screen_stock(
                provider, s, name_map.get(s, s),
                currency="₹", rf_annual=0.06,
                min_composite=MIN_COMPOSITE,
                benchmark_close=benchmark_close,
                weights=LONG_TERM_WEIGHTS,
            )

    tasks = [_screen(s) for s in symbols]
    results = await asyncio.gather(*tasks, return_exceptions=True)
    screened = [r for r in results if r is not None and not isinstance(r, Exception)]

    # Group by sector.
    by_sector: dict[str | None, list[dict]] = defaultdict(list)
    for r in screened:
        by_sector[r.get("sector")].append(r)

    # Rank sectors by average composite score.
    sector_ranking: list[dict] = []
    for sector, stocks in by_sector.items():
        if sector is None:
            continue
        avg_score = sum(s["composite"] for s in stocks) / len(stocks)
        stocks.sort(key=lambda d: d["composite"], reverse=True)
        sector_ranking.append({
            "sector": sector,
            "avg_composite": round(avg_score, 3),
            "stock_count": len(stocks),
            "top_stock": stocks[0],
            "runner_up": stocks[1] if len(stocks) > 1 else None,
        })
    sector_ranking.sort(key=lambda d: d["avg_composite"], reverse=True)

    # Pick top N sectors.
    selected = sector_ranking[:MAX_SECTORS]

    # Enrich top picks + runner-ups with extra fundamental data.
    async def _enrich(stock: dict) -> dict:
        try:
            fund, recs = await asyncio.gather(
                get_stock_fundamentals(stock["symbol"]),
                get_analyst_recommendations(stock["symbol"]),
            )
            stock["revenue_growth"] = fund.get("revenue_growth")
            stock["earnings_growth"] = fund.get("earnings_growth")
            stock["analyst_consensus"] = recs.get("consensus")
            stock["52w_high"] = fund.get("52w_high")
            stock["52w_low"] = fund.get("52w_low")
            hi = fund.get("52w_high")
            lo = fund.get("52w_low")
            price = stock.get("last_price", 0)
            if hi and lo and hi > lo and price > 0:
                stock["range_position"] = round((price - lo) / (hi - lo), 3)
            else:
                stock["range_position"] = None
        except Exception:
            stock.setdefault("revenue_growth", None)
            stock.setdefault("earnings_growth", None)
            stock.setdefault("analyst_consensus", None)
            stock.setdefault("52w_high", None)
            stock.setdefault("52w_low", None)
            stock.setdefault("range_position", None)
        return stock

    for s in selected:
        await _enrich(s["top_stock"])
        if s["runner_up"]:
            await _enrich(s["runner_up"])

    # Portfolio summary.
    portfolio = [s["top_stock"] for s in selected]
    avg_composite = sum(s["composite"] for s in portfolio) / len(portfolio) if portfolio else 0
    avg_sharpe = sum(s["sharpe"] for s in portfolio) / len(portfolio) if portfolio else 0
    avg_cagr = sum(s["cagr"] for s in portfolio) / len(portfolio) if portfolio else 0
    sectors_covered = [s["sector"] for s in selected]

    mk = nse_status()
    return {
        "picks": selected,
        "portfolio": {
            "stock_count": len(portfolio),
            "sectors": sectors_covered,
            "avg_composite": round(avg_composite, 3),
            "avg_sharpe": round(avg_sharpe, 2),
            "avg_cagr": round(avg_cagr, 4),
            "weights": LONG_TERM_WEIGHTS,
        },
        "refreshed_at": datetime.now(timezone.utc).isoformat(),
        "market_open": mk["market_open"],
        "market_status": mk["market_status"],
    }


@router.get("/long-term/picks")
async def long_term_picks(_t: str = Depends(require_token)):
    """Curated sector-diversified long-term portfolio from Nifty 100.

    Scores stocks with long-term weights (quality 40% / value 30% / momentum 30%),
    groups by sector, picks the best stock from each of the top sectors.
    """
    return await cached("long_term_picks", TTL, _build_long_term_picks)


@router.post("/long-term/picks/refresh")
async def long_term_picks_refresh(_t: str = Depends(require_token)):
    """Force-refresh the long-term picks cache."""
    invalidate("long_term_picks")
    return {"ok": True}
