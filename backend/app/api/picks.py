"""Picks endpoints.

GET /api/day/status        - today's no-trade / market status
GET /api/day/events         - scheduled high-impact events for today
GET /api/picks/today       - today's intraday picks (with explanations)
GET /api/picks/{symbol}    - single pick with full explanation
POST /api/picks/scan       - trigger a fresh scan now (manual run)
"""
from __future__ import annotations

import asyncio
import pandas as pd
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.auth import require_token
from app.api.cache import cached, invalidate
from app.db import DayStatusRow, DailyLevel, PickExplanation, PickRow, get_db
from app.market_hours import is_nse_open, today_ist
from app.models import DayStatus, Explanation, Pick
from app.providers.factory import get_provider

router = APIRouter()


def _row_to_pick(row: PickRow, name_map: dict[str, str] | None = None) -> Pick:
    payload = row.explanation.payload if row.explanation else {}
    name = (name_map or {}).get(row.symbol, row.symbol) if name_map else row.symbol
    return Pick(
        date=row.date,
        symbol=row.symbol,
        side=row.side,
        entry=row.entry,
        stop_loss=row.stop_loss,
        target1=row.target1,
        target2=row.target2,
        confidence=row.confidence,
        last_price=row.last_price if row.last_price else 0.0,
        name=name,
        expiry_day=bool(row.expiry_day),
        status=row.status,
        explanation=Explanation(**payload) if payload else Explanation(
            summary="", inputs={}, formula_trace=[], verification=[]
        ),
    )


@router.get("/day/status", response_model=DayStatus)
async def day_status(db: Session = Depends(get_db), _t: str = Depends(require_token)):
    row = db.execute(select(DayStatusRow).where(DayStatusRow.date == today_ist())).scalar_one_or_none()
    if not row:
        return DayStatus(date=today_ist(), market_open=False, no_trade=False)
    # `market_open` reflects whether NSE is literally open right now (weekday +
    # 09:15-15:30 IST), not merely whether today is a trading day. This keeps
    # /day/status consistent with /market/live (which shows real open/closed).
    return DayStatus(
        date=row.date,
        market_open=(not row.no_trade) and is_nse_open(),
        no_trade=bool(row.no_trade),
        reason=row.reason,
        expiry_day=bool(row.expiry_day),
        picks_count=row.picks_count,
    )


@router.get("/picks/today", response_model=list[Pick])
async def picks_today(db: Session = Depends(get_db), _t: str = Depends(require_token)):
    rows = db.execute(
        select(PickRow).where(PickRow.date == today_ist()).order_by(PickRow.confidence.desc())
    ).scalars().all()
    # Build symbol→name map from NSE stock list.
    name_map: dict[str, str] = {}
    try:
        from app.providers.nse_list import get_nse_stocks
        nse_stocks = await get_nse_stocks()
        for s in nse_stocks:
            name_map[s["symbol"]] = s.get("name", s["symbol"])
    except Exception:
        pass
    return [_row_to_pick(r, name_map) for r in rows]


@router.get("/picks/{symbol}", response_model=Pick)
async def pick_detail(symbol: str, db: Session = Depends(get_db), _t: str = Depends(require_token)):
    row = db.execute(
        select(PickRow).where(PickRow.date == today_ist(), PickRow.symbol == symbol.upper())
    ).scalar_one_or_none()
    if not row:
        raise HTTPException(status_code=404, detail="No pick for this symbol today")
    return _row_to_pick(row)


@router.post("/picks/scan", response_model=list[Pick])
async def run_scan(_t: str = Depends(require_token)):
    """Trigger a fresh scan immediately (useful outside scheduled hours)."""
    from app.screener.runner import run_scan
    return await run_scan()


@router.get("/day/events")
async def day_events(_t: str = Depends(require_token)):
    """Scheduled high-impact events for today (advisory only)."""
    from app.strategies.nobtrade import events_for_today, RECURRING_EVENTS
    today_ts = pd.Timestamp.now(tz="Asia/Kolkata")
    return {
        "date": today_ts.date().isoformat(),
        "events_today": events_for_today(today_ts),
        "known_recurring": [e["name"] for e in RECURRING_EVENTS],
    }


@router.get("/market/live")
async def market_live(_t: str = Depends(require_token)):
    """Live NSE market status with NIFTY 50 level.

    Primary source: nseindia.com API (market status + all indices).
    Fallback: yfinance (^NSEI, ^NSEBANK, etc.) when NSE blocks the request.
    """
    import asyncio

    # Maps display name → yfinance ticker for fallback.
    YF_INDEX_MAP = {
        "NIFTY 50": "^NSEI",
        "NIFTY BANK": "^NSEBANK",
        "NIFTY IT": "^NSEIT",
        "NIFTY MIDCAP 100": "^NIFTYMID100",
        "INDIA VIX": "^INDIAVIX",
    }

    async def _fetch():
        from app.providers.factory import get_provider
        provider = get_provider()

        # Try NSE direct API first.
        status = None
        indices = []
        if hasattr(provider, "get_market_status"):
            status = await provider.get_market_status()
            indices = await provider.get_all_indices() if hasattr(provider, "get_all_indices") else []

        # Extract key indices from NSE response.
        key_indices = []
        for idx in indices:
            sym = idx.get("indexSymbol", "")
            if sym in YF_INDEX_MAP:
                key_indices.append({
                    "name": sym,
                    "last": idx.get("last"),
                    "change": idx.get("variation"),
                    "pct_change": idx.get("percentChange"),
                })

        # If NSE returned no index data, fall back to yfinance.
        if not key_indices:
            from app.providers.yfinance_provider import YFinanceProvider
            yf_prov = YFinanceProvider()

            async def _fetch_index(name: str, ticker: str):
                try:
                    q = await yf_prov.get_quote(ticker)
                    last = q.price
                    prev = q.prev_close or last
                    change = round(last - prev, 2) if prev else None
                    pct = round((last - prev) / prev * 100, 2) if prev else None
                    return {"name": name, "last": round(last, 2), "change": change, "pct_change": pct}
                except Exception:
                    return None

            results = await asyncio.gather(*[
                _fetch_index(name, ticker) for name, ticker in YF_INDEX_MAP.items()
            ])
            key_indices = [r for r in results if r is not None]

            # If status is also missing, derive market open from NSE hours.
            if not status or status.get("source", "").endswith("(unreachable)"):
                from app.market_hours import nse_status
                mk = nse_status()
                status = {
                    "market_open": mk["market_open"],
                    "status_text": mk["market_status"],
                    "source": "yfinance (NSE unreachable)",
                }

        return {"status": status or {"market_open": False, "source": "unavailable"}, "indices": key_indices, "source": "nseindia.com" if key_indices and not str(status.get("source", "")).startswith("yfinance") else "yfinance"}

    # No cache — always fetch fresh from NSE for real-time index data.
    return await _fetch()


@router.get("/search/suggest")
async def search_suggest(q: str, _t: str = Depends(require_token)):
    """Autocomplete: return matching NSE stocks by symbol or company name."""
    from app.providers.nse_list import get_nse_stocks, search_stocks
    query = q.strip()
    if len(query) < 1:
        return {"results": []}
    stocks = await get_nse_stocks()
    matches = search_stocks(query, stocks, limit=12)
    return {"results": matches}


@router.get("/search")
async def search_stock(q: str, _t: str = Depends(require_token)):
    """Search any NSE stock by symbol. Returns live quote + fundamentals + today's pick."""
    from app.providers.factory import get_provider
    from app.providers.fundamentals import get_stock_fundamentals
    import asyncio
    symbol = q.strip().upper().replace(".NS", "").replace("NSE:", "")
    if not symbol:
        return {"symbol": symbol, "found": False, "message": "Enter a stock symbol."}

    async def _fetch():
        provider = get_provider()
        # Fetch quote + fundamentals in parallel.
        try:
            quote, fundamentals = await asyncio.gather(
                provider.get_quote(symbol),
                get_stock_fundamentals(symbol),
            )
        except Exception:
            return {"symbol": symbol, "found": False, "message": f"Could not fetch data for {symbol}."}
        # Check if there's a screener pick for this symbol today.
        db = next(get_db())
        row = db.execute(
            select(PickRow).where(PickRow.date == today_ist(), PickRow.symbol == symbol)
        ).scalar_one_or_none()
        pick = _row_to_pick(row) if row else None
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
            "pick": pick.model_dump() if pick else None,
            "fundamentals": {
                "company_name": fundamentals.get("company_name"),
                "sector": fundamentals.get("sector"),
                "industry": fundamentals.get("industry"),
                "trailing_pe": fundamentals.get("trailing_pe"),
                "forward_pe": fundamentals.get("forward_pe"),
                "market_cap": fundamentals.get("market_cap"),
                "description": fundamentals.get("description"),
            },
            "message": f"{symbol}: ₹{quote.price:.2f}" + (
                " (in today's picks)" if pick else ""
            ),
        }

    return await cached(f"search:{symbol}", 60, _fetch)


@router.get("/stock/{symbol}/details")
async def stock_details(symbol: str, _t: str = Depends(require_token)):
    """Full stock detail: fundamentals + financials + recommendations + investment levels."""
    from app.api.cache import cached
    from app.providers.factory import get_provider
    from app.providers.fundamentals import get_stock_detail
    from app.strategies.invest_levels import compute_invest_levels

    symbol = symbol.strip().upper().replace(".NS", "").replace("NSE:", "")

    async def _fetch():
        provider = get_provider()
        # Fetch daily history for investment levels.
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
        # Fetch fundamentals + financials + recommendations (cached).
        detail = await get_stock_detail(symbol)
        # Compute investment entry/exit levels.
        levels = compute_invest_levels(
            daily, symbol,
            high_52w=detail["fundamentals"].get("52w_high"),
            low_52w=detail["fundamentals"].get("52w_low"),
        )
        # Check for today's intraday pick.
        db = next(get_db())
        row = db.execute(
            select(PickRow).where(PickRow.date == today_ist(), PickRow.symbol == symbol)
        ).scalar_one_or_none()
        intraday_pick = _row_to_pick(row) if row else None
        return {
            "symbol": symbol,
            "fundamentals": detail["fundamentals"],
            "financials": detail["financials"],
            "recommendations": detail["recommendations"],
            "invest_levels": levels,
            "live_quote": live_quote,
            "intraday_pick": intraday_pick.model_dump() if intraday_pick else None,
        }

    # Fundamentals/financials are slow to fetch and change slowly — cache 10 min.
    # Live quote is always fetched fresh (no cache).
    from app.providers.factory import get_provider

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

    # Run cached fundamentals + fresh live quote in parallel.
    detail_task = cached(f"stock_detail_fund:{symbol}", 600, _fetch_fundamentals)
    quote_task = _fetch_live_quote()
    detail, live_quote = await asyncio.gather(detail_task, quote_task)

    # Compute invest levels using daily history.
    provider = get_provider()
    try:
        daily = await provider.get_daily_history(symbol, 252)
    except Exception:
        daily = pd.DataFrame()
    levels = compute_invest_levels(
        daily, symbol,
        high_52w=detail["fundamentals"].get("52w_high"),
        low_52w=detail["fundamentals"].get("52w_low"),
    )
    # Check for today's intraday pick.
    db = next(get_db())
    row = db.execute(
        select(PickRow).where(PickRow.date == today_ist(), PickRow.symbol == symbol)
    ).scalar_one_or_none()
    intraday_pick = _row_to_pick(row) if row else None

    return {
        "symbol": symbol,
        "fundamentals": detail["fundamentals"],
        "financials": detail["financials"],
        "recommendations": detail["recommendations"],
        "invest_levels": levels,
        "live_quote": live_quote,
        "intraday_pick": intraday_pick.model_dump() if intraday_pick else None,
    }


@router.get("/stock/screen")
async def stock_screen(_t: str = Depends(require_token)):
    """Screen NSE stocks — live data when NSE is open, cached when closed."""
    import asyncio
    from datetime import datetime, timezone
    from app.market_hours import nse_status, screen_cache_ttl
    from app.strategies import stock_screener as stock_scr
    from app.universe import get_universe

    sem = asyncio.Semaphore(20)
    mk = nse_status()

    async def _fetch():
        provider = get_provider()
        symbols = get_universe("nifty100")
        from app.providers.nse_list import get_nse_stocks

        # Build {symbol: name} from NSE list if available.
        name_map: dict[str, str] = {}
        try:
            nse_stocks = await get_nse_stocks()
            for s in nse_stocks:
                name_map[s["symbol"]] = s.get("name", s["symbol"])
        except Exception:
            pass

        # Fetch benchmark (NIFTY 50 index) once for relative strength calculation.
        benchmark_close = None
        try:
            bench_daily = await provider.get_daily_history("^NSEI", 252)
            if not bench_daily.empty:
                benchmark_close = bench_daily["Close"]
        except Exception:
            pass

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

    ttl = screen_cache_ttl(mk["market_open"])
    return await cached("nse_stock_screen", ttl, _fetch)


@router.post("/stock/screen/refresh")
async def stock_screen_refresh(_t: str = Depends(require_token)):
    """Force-refresh the NSE stock screen — clears cache so next GET fetches fresh data."""
    invalidate("nse_stock_screen")
    return {"ok": True}
