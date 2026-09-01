"""Simple in-memory TTL cache for slow screener endpoints.

The ETF/MF/commodities screeners fetch 2y of data per fund (~60-90s total).
We cache the result so subsequent browser loads return instantly. The cache
refreshes in the background after the TTL expires (stale-while-revalidate).
"""
from __future__ import annotations

import asyncio
import logging
import time
from typing import Any, Awaitable, Callable

log = logging.getLogger("cache")

_cache: dict[str, tuple[float, Any]] = {}
_locks: dict[str, asyncio.Lock] = {}

# Max time to serve stale data before forcing a synchronous refresh (5 min).
_MAX_STALE_SECONDS = 300


async def cached(
    key: str,
    ttl: int,
    fn: Callable[[], Awaitable[Any]],
) -> Any:
    """Return cached result if fresh; otherwise call fn and cache it.

    Uses a per-key lock so concurrent requests don't trigger duplicate fetches.
    Stale data is served for up to _MAX_STALE_SECONDS past TTL, then a
    synchronous refresh is forced.
    """
    now = time.time()
    entry = _cache.get(key)
    if entry and (now - entry[0]) < ttl:
        return entry[1]

    # Stale-while-revalidate: return stale data immediately, refresh in bg.
    if entry and (now - entry[0]) < ttl + _MAX_STALE_SECONDS:
        lock = _locks.setdefault(key, asyncio.Lock())
        if not lock.locked():
            asyncio.create_task(_refresh(key, ttl, fn))
        return entry[1]

    # Stale data too old or no cache — must wait for the fetch.
    lock = _locks.setdefault(key, asyncio.Lock())
    async with lock:
        # Double-check after acquiring lock (another request may have filled it).
        entry = _cache.get(key)
        if entry and (time.time() - entry[0]) < ttl + _MAX_STALE_SECONDS:
            return entry[1]
        result = await fn()
        _cache[key] = (time.time(), result)
        return result


async def _refresh(key: str, ttl: int, fn: Callable[[], Awaitable[Any]]) -> None:
    """Background refresh — doesn't block the caller."""
    try:
        result = await fn()
        _cache[key] = (time.time(), result)
    except Exception as e:
        log.warning("Background refresh failed for key=%s: %s", key, e)


def invalidate(key: str | None = None) -> None:
    """Clear a specific key (or all cache if None)."""
    if key:
        _cache.pop(key, None)
    else:
        _cache.clear()
