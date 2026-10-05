"""Disk persistence layer of the API cache (expensive results survive restarts)."""
import asyncio

import pytest

from app.api import cache as cache_mod


@pytest.fixture(autouse=True)
def _isolate_cache(tmp_path, monkeypatch):
    """Point the cache at a fresh memory dict and a tmp disk dir per test."""
    monkeypatch.setattr(cache_mod, "_cache", {})
    monkeypatch.setattr(cache_mod, "_locks", {})
    monkeypatch.setattr(cache_mod, "_DISK_DIR", tmp_path)
    yield


def test_persists_when_ttl_above_threshold():
    cache_mod._store("k1", 600, {"a": 1})
    assert cache_mod._disk_path("k1").exists()
    # Simulate a restart: memory is gone, disk must serve.
    cache_mod._cache.pop("k1")
    entry = cache_mod._disk_get("k1")
    assert entry is not None and entry[1] == {"a": 1}


def test_not_persisted_below_threshold():
    cache_mod._store("k2", 60, {"a": 1})
    assert not cache_mod._disk_path("k2").exists()


def test_invalidate_removes_disk_file():
    cache_mod._store("k3", 600, {"a": 1})
    cache_mod.invalidate("k3")
    assert not cache_mod._disk_path("k3").exists()


def test_corrupt_disk_entry_ignored():
    p = cache_mod._disk_path("k4")
    p.write_text("{not json")
    assert cache_mod._disk_get("k4") is None


def test_cached_serves_from_disk_after_memory_clear():
    calls = []

    async def fn():
        calls.append(1)
        return {"v": 2}

    async def run():
        r1 = await cache_mod.cached("k5", 600, fn)
        cache_mod._cache.clear()  # simulate restart
        r2 = await cache_mod.cached("k5", 600, fn)
        return r1, r2

    r1, r2 = asyncio.run(run())
    assert r1 == r2 == {"v": 2}
    assert len(calls) == 1  # second read came from disk, not a refetch
