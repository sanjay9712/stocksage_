"""Simple in-memory TTL cache for slow screener endpoints.

The ETF/MF/commodities screeners fetch 2y of data per fund (~60-90s total).
We cache the result so subsequent browser loads return instantly. The cache
refreshes in the background after the TTL expires (stale-while-revalidate).

Entries with TTL >= _DISK_MIN_TTL are also persisted to disk (data/api_cache/)
so expensive results (e.g. the 30-day daily-picks backtest, ~5-10 min cold)
survive backend restarts.
"""
from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import time
from pathlib import Path
from typing import Any, Awaitable, Callable

log = logging.getLogger("cache")

_cache: dict[str, tuple[float, Any]] = {}
_locks: dict[str, asyncio.Lock] = {}

# Max time to serve stale data before forcing a synchronous refresh (5 min).
_MAX_STALE_SECONDS = 300

# Only persist entries that are expensive enough to be worth a disk round-trip.
_DISK_MIN_TTL = 300
_DISK_DIR = Path(__file__).resolve().parents[2] / "data" / "api_cache"


def _disk_path(key: str) -> Path:
    return _DISK_DIR / f"{hashlib.sha1(key.encode()).hexdigest()}.json"


def _disk_get(key: str) -> tuple[float, Any] | None:
    """Load a persisted entry if present; None on miss or corruption."""
    path = _disk_path(key)
    try:
        if not path.exists():
            return None
        with open(path, "r", encoding="utf-8") as f:
            raw = json.load(f)
        return (float(raw["ts"]), raw["value"])
    except Exception:
        return None


def _disk_set(key: str, ts: float, value: Any) -> None:
    """Best-effort persist; non-JSON-serializable values are memory-only."""
    if value is None:
        return
    try:
        json.dumps(value)
    except (TypeError, ValueError):
        return
    try:
        _DISK_DIR.mkdir(parents=True, exist_ok=True)
        with open(_disk_path(key), "w", encoding="utf-8") as f:
            json.dump({"ts": ts, "value": value}, f)
    except Exception as e:
        log.warning("Disk cache write failed for key=%s: %s", key, e)


def _store(key: str, ttl: int, result: Any) -> None:
    ts = time.time()
    _cache[key] = (ts, result)
    if ttl >= _DISK_MIN_TTL:
        _disk_set(key, ts, result)


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
    if entry is None and ttl >= _DISK_MIN_TTL:
        entry = _disk_get(key)
        if entry is not None:
            _cache[key] = entry

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
        if entry is None and ttl >= _DISK_MIN_TTL:
            entry = _disk_get(key)
        if entry and (time.time() - entry[0]) < ttl + _MAX_STALE_SECONDS:
            _cache[key] = entry
            return entry[1]
        result = await fn()
        _store(key, ttl, result)
        return result


async def _refresh(key: str, ttl: int, fn: Callable[[], Awaitable[Any]]) -> None:
    """Background refresh — doesn't block the caller."""
    try:
        result = await fn()
        _store(key, ttl, result)
    except Exception as e:
        log.warning("Background refresh failed for key=%s: %s", key, e)


def invalidate(key: str | None = None) -> None:
    """Clear a specific key (or all cache if None)."""
    if key:
        _cache.pop(key, None)
        # Always unlink the disk file (no-op if the key was never persisted).
        # We don't track per-key TTLs here, and a stale disk entry would be
        # served after a restart — worse than a cold refetch.
        try:
            _disk_path(key).unlink(missing_ok=True)
        except Exception:
            pass
    else:
        _cache.clear()
        try:
            for p in _DISK_DIR.glob("*.json"):
                p.unlink()
        except Exception:
            pass
