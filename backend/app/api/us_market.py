"""US market endpoints: US ETF screener, US stock detail, US stock search.

Separate from the NSE endpoints so caching and universe logic stay clean.
The yfinance provider already handles US tickers without suffix (via
is_us_symbol() in universe.py), so data fetching works transparently.
"""
from __future__ import annotations

import asyncio
from datetime import datetime, timezone

import pandas as pd
from fastapi import APIRouter, Depends
from sqlalchemy import select

from app.api.auth import require_token
from app.api.cache import cached, invalidate
from app.db import get_db, PickRow
from app.market_hours import is_us_open, screen_cache_ttl
from app.providers.factory import get_provider
from app.providers.fundamentals import get_stock_detail, get_stock_fundamentals
from app.strategies import etf_screener as scr
from app.strategies import stock_screener as stock_scr
from app.strategies.invest_levels import compute_invest_levels
from app.universe import get_us_etf_universe, get_us_stocks, US_STOCK_NAMES

router = APIRouter()


def _search_us_stocks(query: str, limit: int = 12) -> list[dict[str, str]]:
    """Search the US_STOCKS list by symbol or company name. Returns [{symbol, name}]."""
    q = query.strip().upper()
    if not q:
        return []
    symbol_starts = []
    symbol_contains = []
    name_contains = []
    for sym in get_us_stocks():
        name = US_STOCK_NAMES.get(sym, sym).upper()
        if sym.startswith(q):
            symbol_starts.append({"symbol": sym, "name": US_STOCK_NAMES.get(sym, sym)})
        elif q in sym:
            symbol_contains.append({"symbol": sym, "name": US_STOCK_NAMES.get(sym, sym)})
        elif q in name:
            name_contains.append({"symbol": sym, "name": US_STOCK_NAMES.get(sym, sym)})
    return (symbol_starts + symbol_contains + name_contains)[:limit]


@router.get("/us-etf/screener")
async def us_etf_screener(_t: str = Depends(require_token)):
    """US ETF invest screener — risk/return metrics sorted by Sharpe."""

    async def _fetch():
        provider = get_provider()
        etfs = get_us_etf_universe()
        tasks = [
            scr.screen_etf(provider, e["symbol"], e["name"], e["category"], e["horizon"], market="us")
            for e in etfs
        ]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        out = [scr.to_dict(s) for s in results if not isinstance(s, Exception)]
        out.sort(key=lambda d: d.get("sharpe", 0), reverse=True)
        return out

    return await cached("us_etf_screener", screen_cache_ttl(is_us_open()), _fetch)


@router.get("/us-etf/{symbol}/details")
async def us_etf_details(symbol: str, _t: str = Depends(require_token)):
    """Single US ETF detail with all enhanced fields."""
    symbol = symbol.strip().upper()

    async def _fetch():
        etfs = get_us_etf_universe()
        etf = next((e for e in etfs if e["symbol"].upper() == symbol), None)
        if not etf:
            etf = {"symbol": symbol, "name": symbol, "category": "unknown", "horizon": "long"}
        provider = get_provider()
        result = await scr.screen_etf(
            provider, etf["symbol"], etf["name"], etf["category"],
            etf.get("horizon", "long"), market="us",
        )
        try:
            fundamentals = await get_stock_fundamentals(symbol)
        except Exception:
            fundamentals = {}
        data = scr.to_dict(result)
        data["yf_fundamentals"] = {
            "trailing_pe": fundamentals.get("trailing_pe"),
            "market_cap": fundamentals.get("market_cap"),
            "52w_high": fundamentals.get("52w_high"),
            "52w_low": fundamentals.get("52w_low"),
            "avg_volume": fundamentals.get("avg_volume"),
        }
        return data

    return await cached(f"us_etf_detail:{symbol}", 600, _fetch)


@router.get("/us-stock/{symbol}/details")
async def us_stock_details(symbol: str, _t: str = Depends(require_token)):
    """Full US stock detail: fundamentals + financials + recommendations + investment levels."""
    from datetime import date

    symbol = symbol.strip().upper()

    async def _fetch():
        provider = get_provider()
        try:
            daily = await provider.get_daily_history(symbol, 252)
        except Exception:
            daily = pd.DataFrame()
        # Fetch live quote for current price + change.
        live_quote = None
        try:
            quote = await provider.get_quote(symbol)
            if quote and quote.price > 0:
                prev = quote.prev_close or (float(daily["Close"].iloc[-2]) if len(daily) >= 2 else None)
                change = round(quote.price - prev, 2) if prev else None
                change_pct = round((quote.price - prev) / prev * 100, 2) if prev else None
                live_quote = {
                    "price": round(quote.price, 2),
                    "prev_close": round(prev, 2) if prev else None,
                    "change": change,
                    "change_pct": change_pct,
                    "day_high": quote.day_high,
                    "day_low": quote.day_low,
                    "volume": quote.volume,
                }
        except Exception:
            pass
        detail = await get_stock_detail(symbol)
        levels = compute_invest_levels(
            daily, symbol,
            high_52w=detail["fundamentals"].get("52w_high"),
            low_52w=detail["fundamentals"].get("52w_low"),
            currency="$",
        )
        # US stocks don't have NSE intraday picks, so intraday_pick is always None.
        return {
            "symbol": symbol,
            "fundamentals": detail["fundamentals"],
            "financials": detail["financials"],
            "recommendations": detail["recommendations"],
            "invest_levels": levels,
            "live_quote": live_quote,
            "intraday_pick": None,
        }

    # Fundamentals/financials are slow — cache 10 min. Live quote always fresh.
    async def _fetch_fundamentals():
        return await get_stock_detail(symbol)

    async def _fetch_live_quote():
        provider = get_provider()
        try:
            quote = await provider.get_quote(symbol)
            if quote and quote.price > 0:
                try:
                    daily = await provider.get_daily_history(symbol, 252)
                except Exception:
                    daily = pd.DataFrame()
                prev = quote.prev_close or (float(daily["Close"].iloc[-2]) if len(daily) >= 2 else None)
                change = round(quote.price - prev, 2) if prev else None
                change_pct = round((quote.price - prev) / prev * 100, 2) if prev else None
                return {
                    "price": round(quote.price, 2),
                    "prev_close": round(prev, 2) if prev else None,
                    "change": change,
                    "change_pct": change_pct,
                    "day_high": quote.day_high,
                    "day_low": quote.day_low,
                    "volume": quote.volume,
                }
        except Exception:
            pass
        return None

    detail_task = cached(f"us_stock_detail_fund:{symbol}", 600, _fetch_fundamentals)
    quote_task = _fetch_live_quote()
    detail, live_quote = await asyncio.gather(detail_task, quote_task)

    provider = get_provider()
    try:
        daily = await provider.get_daily_history(symbol, 252)
    except Exception:
        daily = pd.DataFrame()
    levels = compute_invest_levels(
        daily, symbol,
        high_52w=detail["fundamentals"].get("52w_high"),
        low_52w=detail["fundamentals"].get("52w_low"),
        currency="$",
    )

    return {
        "symbol": symbol,
        "fundamentals": detail["fundamentals"],
        "financials": detail["financials"],
        "recommendations": detail["recommendations"],
        "invest_levels": levels,
        "live_quote": live_quote,
        "intraday_pick": None,
    }


@router.get("/us-stock/list")
async def us_stock_list(_t: str = Depends(require_token)):
    """Return all US stocks in the universe with company names."""
    return {"stocks": [{"symbol": s, "name": US_STOCK_NAMES.get(s, s)} for s in get_us_stocks()]}


async def _screen_one_stock(symbol: str, provider, benchmark_close=None) -> dict | None:
    """Screen a single US stock using the shared screener."""
    name = US_STOCK_NAMES.get(symbol, symbol)
    return await stock_scr.screen_stock(
        provider, symbol, name, currency="$", rf_annual=0.04,
        benchmark_close=benchmark_close,
    )


@router.get("/us-stock/screen")
async def us_stock_screen(_t: str = Depends(require_token)):
    """Screen all US stocks — live data when US market is open, cached when closed."""
    from app.market_hours import us_status, screen_cache_ttl

    sem = asyncio.Semaphore(20)
    mk = us_status()

    async def _fetch():
        provider = get_provider()
        stocks = get_us_stocks()

        # Fetch benchmark (SPY) once for relative strength calculation.
        benchmark_close = None
        try:
            bench_daily = await provider.get_daily_history("SPY", 252)
            if not bench_daily.empty:
                benchmark_close = bench_daily["Close"]
        except Exception:
            pass

        async def _screen(s):
            async with sem:
                return await _screen_one_stock(s, provider, benchmark_close=benchmark_close)

        tasks = [_screen(s) for s in stocks]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        out = [r for r in results if r is not None and not isinstance(r, Exception)]
        out.sort(key=lambda d: d.get("composite", 0), reverse=True)
        return {
            "stocks": out,
            "refreshed_at": datetime.now(timezone.utc).isoformat(),
            "market_open": mk["market_open"],
            "market_status": mk["market_status"],
        }

    ttl = screen_cache_ttl(mk["market_open"])
    return await cached("us_stock_screen", ttl, _fetch)


@router.post("/us-stock/screen/refresh")
async def us_stock_screen_refresh(_t: str = Depends(require_token)):
    """Force-refresh the US stock screen — clears cache so next GET fetches fresh data."""
    invalidate("us_stock_screen")
    return {"ok": True}


@router.get("/us-stock/search/suggest")
async def us_stock_search_suggest(q: str, _t: str = Depends(require_token)):
    """Autocomplete: return matching US stocks by symbol."""
    query = q.strip()
    if len(query) < 1:
        return {"results": []}
    matches = _search_us_stocks(query, limit=12)
    return {"results": matches}


@router.get("/us-stock/search")
async def us_stock_search(q: str, _t: str = Depends(require_token)):
    """Search a US stock by symbol. Returns live quote + fundamentals."""
    import asyncio
    from app.models import Quote

    symbol = q.strip().upper()
    if not symbol:
        return {"symbol": symbol, "found": False, "message": "Enter a stock symbol."}

    async def _fetch():
        provider = get_provider()
        try:
            quote, fundamentals = await asyncio.gather(
                provider.get_quote(symbol),
                get_stock_fundamentals(symbol),
            )
        except Exception:
            return {"symbol": symbol, "found": False, "message": f"Could not fetch data for {symbol}."}
        return {
            "symbol": symbol,
            "found": True,
            "quote": {
                "price": quote.price,
                "prev_close": quote.prev_close,
                "day_high": quote.day_high,
                "day_low": quote.day_low,
                "volume": quote.volume,
            },
            "pick": None,
            "fundamentals": {
                "company_name": fundamentals.get("company_name"),
                "sector": fundamentals.get("sector"),
                "industry": fundamentals.get("industry"),
                "trailing_pe": fundamentals.get("trailing_pe"),
                "forward_pe": fundamentals.get("forward_pe"),
                "market_cap": fundamentals.get("market_cap"),
                "description": fundamentals.get("description"),
            },
            "message": f"{symbol}: ${quote.price:.2f}",
        }

    return await cached(f"us_search:{symbol}", 60, _fetch)
