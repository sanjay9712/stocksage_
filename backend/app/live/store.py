"""In-memory live price store with fan-out to SSE subscribers.

The live engine (app/live/engine.py) writes price updates here; SSE
endpoints subscribe and receive a batch of changed symbols every tick.
"""
from __future__ import annotations

import asyncio
import time
from typing import Any


class LiveStore:
    """Holds the latest price per symbol and fans out changes to subscribers.

    Thread-safe for asyncio: all access happens on the event loop.
    """

    def __init__(self):
        self._prices: dict[str, dict[str, Any]] = {}
        self._subscribers: list[asyncio.Queue] = []
        self._status: dict[str, Any] = {"market_open": False, "source": "starting"}
        self._updated_at: float = 0.0  # last price *change*
        self._polled_at: float = 0.0   # last successful engine poll (even if no change)

    # ---- writers (engine) ----

    def update_prices(self, prices: dict[str, dict[str, Any]]) -> dict[str, dict[str, Any]]:
        """Merge new prices; returns the changed subset (for push).

        Bumps `_polled_at` on every call — a successful poll makes the store
        "fresh" even when no price changed (e.g. market closed).
        """
        self._polled_at = time.time()
        changed: dict[str, dict[str, Any]] = {}
        for sym, p in prices.items():
            prev = self._prices.get(sym)
            if prev is None or prev.get("last") != p.get("last") or prev.get("pct_change") != p.get("pct_change"):
                self._prices[sym] = p
                changed[sym] = p
        if changed:
            self._updated_at = time.time()
        return changed

    def set_status(self, status: dict[str, Any]):
        self._status = status
        # A status refresh also counts as a successful poll.
        self._polled_at = time.time()

    # ---- readers (API / SSE) ----

    def snapshot(self) -> dict[str, Any]:
        """Full current state: status + all prices + freshness.

        Fresh = the engine polled successfully within ~1.5 idle-poll windows
        (covers the 30s closed-market cadence; closed values don't move, so
        serving them from memory is as good as a re-fetch).
        """
        from app.config import settings
        threshold = max(10.0, settings.live_idle_poll * 1.5)
        return {
            "status": dict(self._status),
            "prices": {s: dict(p) for s, p in self._prices.items()},
            "updated_at": self._updated_at,
            "fresh": (time.time() - self._polled_at) < threshold if self._polled_at else False,
        }

    def status(self) -> dict[str, Any]:
        return dict(self._status)

    # ---- subscription (SSE) ----

    def subscribe(self) -> asyncio.Queue:
        q: asyncio.Queue = asyncio.Queue(maxsize=16)
        self._subscribers.append(q)
        return q

    def unsubscribe(self, q: asyncio.Queue):
        if q in self._subscribers:
            self._subscribers.remove(q)

    def publish(self, changed: dict[str, dict[str, Any]]):
        """Send a changed-prices batch to every subscriber (drop on slow consumer)."""
        if not changed:
            return
        for q in list(self._subscribers):
            try:
                q.put_nowait(changed)
            except asyncio.QueueFull:
                # Slow consumer — drop the batch; it will get the next one
                # plus a fresh snapshot on reconnect.
                pass


# Process-wide singleton: one store shared by the engine and all SSE streams.
store = LiveStore()
