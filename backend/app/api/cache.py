"""Simple in-memory TTL cache for slow screener endpoints.

The ETF/MF/commodities screeners fetch 2y of data per fund (~60-90s total).
We cache the result so subsequent browser loads return instantly. The cache
refreshes in the background after the TTL expires (stale-while-revalidate).
"""
from __future__ import annotations

import asyncio
import time
from typing import Any, Awaitable, Callable

_cache: dict[str, tuple[float, Any]] = {}
_locks: dict[str, asyncio.Lock] = {}


async def cached(
    key: str,
    ttl: int,
    fn: Callable[[], Awaitable[Any]],
) -> Any:
    """Return cached result if fresh; otherwise call fn and cache it.

    Uses a per-key lock so concurrent requests don't trigger duplicate fetches.
    """
    now = time.time()
    entry = _cache.get(key)
    if entry and (now - entry[0]) < ttl:
        return entry[1]

    # Stale-while-revalidate: return stale data immediately, refresh in bg.
    if entry:
        lock = _locks.setdefault(key, asyncio.Lock())
        if not lock.locked():
            asyncio.create_task(_refresh(key, ttl, fn))
        return entry[1]

    # No cache at all — must wait for the first fetch.
    lock = _locks.setdefault(key, asyncio.Lock())
    async with lock:
        # Double-check after acquiring lock (another request may have filled it).
        entry = _cache.get(key)
        if entry and (time.time() - entry[0]) < ttl:
            return entry[1]
        result = await fn()
        _cache[key] = (time.time(), result)
        return result


async def _refresh(key: str, ttl: int, fn: Callable[[], Awaitable[Any]]) -> None:
    """Background refresh — doesn't block the caller."""
    try:
        result = await fn()
        _cache[key] = (time.time(), result)
    except Exception:
        pass  # keep stale data on refresh failure


def invalidate(key: str | None = None) -> None:
    """Clear a specific key (or all cache if None)."""
    if key:
        _cache.pop(key, None)
    else:
        _cache.clear()
