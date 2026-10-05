"""Background live-market engine.

Polls NSE (market status + all indices) continuously and pushes changes
into the in-memory LiveStore, which fans them out to SSE subscribers.
Individual stock quotes (watchlist) are polled from the active provider
with throttling so NSE/brokers don't see request bursts.

Design notes:
  - The NSE public feed updates roughly every 3s; we poll every
    live_index_poll seconds while the market is open and slow down to
    live_idle_poll when it's closed (values are static then anyway).
  - On NSE failure (403/timeout) we back off exponentially (2s → 30s)
    and fall back to yfinance for the key indices, mirroring the
    fallback logic that /api/market/live already uses.
  - Phase 2 (IND Money) will add a faster stock-quote source here; the
    SSE stream and store stay unchanged.
"""
from __future__ import annotations

import asyncio
import logging
import time

from app.config import settings
from app.live.store import store

log = logging.getLogger("live.engine")

# Key indices to surface (display name → yfinance ticker for fallback).
YF_INDEX_MAP = {
    "NIFTY 50": "^NSEI",
    "NIFTY BANK": "^NSEBANK",
    "NIFTY IT": "^NSEIT",
    "NIFTY MIDCAP 100": "^NIDMID100",
    "INDIA VIX": "^INDIAVIX",
}

MAX_BACKOFF = 30.0


class LiveEngine:
    def __init__(self):
        self._task: asyncio.Task | None = None
        self._stop = asyncio.Event()
        self._nse_failures = 0

    async def start(self):
        if self._task and not self._task.done():
            return
        self._stop.clear()
        self._task = asyncio.create_task(self._run(), name="live-engine")
        log.info("live engine started")

    async def stop(self):
        self._stop.set()
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except (asyncio.CancelledError, Exception):
                pass
            self._task = None
        log.info("live engine stopped")

    async def _run(self):
        # Two independent loops: indices (fast) and watchlist stocks (throttled).
        await asyncio.gather(self._index_loop(), self._watchlist_loop())

    # ---- indices / market status ----

    async def _index_loop(self):
        from app.providers.factory import get_provider

        provider = get_provider()
        while not self._stop.is_set():
            interval = settings.live_index_poll
            try:
                ok = await self._fetch_indices(provider)
                self._nse_failures = 0 if ok else self._nse_failures + 1
                if not ok:
                    interval = min(MAX_BACKOFF, settings.live_index_poll * (2 ** min(self._nse_failures, 4)))
            except Exception:
                log.exception("index fetch failed")
            # Idle cadence when market is closed — values don't move.
            if not store.status().get("market_open", False):
                interval = max(interval, settings.live_idle_poll)
            try:
                await asyncio.wait_for(self._stop.wait(), timeout=interval)
            except asyncio.TimeoutError:
                pass

    async def _fetch_indices(self, provider) -> bool:
        """Fetch NSE status + indices; returns True on NSE success."""
        prices: dict = {}
        status: dict = {}
        source = "nse"

        nse_ok = False
        if hasattr(provider, "get_market_status"):
            status = await provider.get_market_status()
            if status.get("source") == "nse":
                nse_ok = True
        if nse_ok and hasattr(provider, "get_all_indices"):
            indices = await provider.get_all_indices()
            for idx in indices:
                sym = idx.get("indexSymbol", "")
                if sym in YF_INDEX_MAP:
                    prices[sym] = {
                        "last": idx.get("last"),
                        "change": idx.get("variation"),
                        "pct_change": idx.get("percentChange"),
                        "source": "nse",
                        "ts": time.time(),
                    }

        if not prices:
            # yfinance fallback for the key indices (slower, but keeps the
            # dashboard alive when NSE blocks us).
            from app.providers.yfinance_provider import YFinanceProvider
            yf = YFinanceProvider()

            async def _one(name: str, ticker: str):
                try:
                    q = await yf.get_quote(ticker)
                    last = q.price
                    prev = q.prev_close or last
                    change = round(last - prev, 2) if prev else None
                    pct = round((last - prev) / prev * 100, 2) if prev else None
                    return name, {"last": round(last, 2), "change": change, "pct_change": pct, "source": "yfinance", "ts": time.time()}
                except Exception:
                    return name, None

            results = await asyncio.gather(*[_one(n, t) for n, t in YF_INDEX_MAP.items()])
            for name, p in results:
                if p:
                    prices[name] = p
            source = "yfinance"
            if not status or status.get("source") == "nse (unreachable)":
                from app.market_hours import nse_status
                mk = nse_status()
                status = {
                    "market_open": mk["market_open"],
                    "status_text": mk["market_status"],
                    "source": "yfinance (NSE unreachable)",
                }

        store.set_status(status or {"market_open": False, "source": "unavailable"})
        store.publish(store.update_prices(prices))
        return nse_ok or bool(prices)

    # ---- watchlist stocks ----

    async def _watchlist_loop(self):
        symbols = [s.strip().upper() for s in settings.live_watchlist.split(",") if s.strip()]
        if not symbols:
            return  # indices only; stocks arrive with the IND Money source in phase 2
        from app.providers.factory import get_provider
        provider = get_provider()
        sem = asyncio.Semaphore(5)
        last_fetch: dict[str, float] = {}

        while not self._stop.is_set():
            due = [s for s in symbols if time.time() - last_fetch.get(s, 0) >= settings.live_watchlist_poll]
            if due:
                async def _one(sym: str):
                    async with sem:
                        try:
                            q = await provider.get_quote(sym)
                        except Exception:
                            return None
                        last = q.price
                        prev = q.prev_close or last
                        change = round(last - prev, 2) if prev else None
                        pct = round((last - prev) / prev * 100, 2) if prev else None
                        return {
                            "last": round(last, 2),
                            "change": change,
                            "pct_change": pct,
                            "source": "provider",
                            "ts": time.time(),
                            "high": q.day_high,
                            "low": q.day_low,
                            "volume": q.volume,
                        }
                results = await asyncio.gather(*[_one(s) for s in due])
                prices = {s: p for s, p in zip(due, results) if p}
                for s in due:
                    last_fetch[s] = time.time()
                if prices:
                    store.publish(store.update_prices(prices))
            try:
                await asyncio.wait_for(self._stop.wait(), timeout=min(settings.live_watchlist_poll, 5.0))
            except asyncio.TimeoutError:
                pass
