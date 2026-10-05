"""Live market price streams: WebSocket (primary) + SSE (LAN/direct).

Two transports feed the same in-memory store (app.live.store):

  WebSocket  `WS /api/market/stream-ws?token=<jwt>`  — primary transport.
  SSE        `GET /api/market/stream?token=<jwt>`    — works on direct/LAN.

Both send `snapshot` (full state on connect) then `tick` (batch of changed
symbols when the live engine sees a move). The JWT arrives as a query param
(neither WS subprotocols nor EventSource can set an Authorization header
reliably through proxies); it's validated with the same decode_token the
other REST endpoints use.

Why both: Cloudflare quick tunnels (trycloudflare.com) buffer HTTP SSE
responses, so the browser-facing transport is WebSocket — cloudflared
upgrades WS connections and streams them frame-by-frame.
"""
from __future__ import annotations

import asyncio
import json
import time

from fastapi import APIRouter, HTTPException, Query, WebSocket, WebSocketDisconnect, status
from fastapi.responses import StreamingResponse

from app.api.auth import decode_token
from app.live.store import store

router = APIRouter(prefix="/api/market", tags=["live"])

HEARTBEAT_SECONDS = 15
TICK_BATCH_SECONDS = 1.0


@router.websocket("/stream-ws")
async def market_stream_ws(ws: WebSocket, token: str | None = Query(default=None)):
    await ws.accept()
    # Validate after accept so the client gets a clean close frame, not a
    # failed handshake.
    if not _token_ok(token):
        await ws.close(code=4401)
        return
    q = store.subscribe()
    try:
        await ws.send_text(json.dumps({"type": "snapshot", "data": store.snapshot()}))
        while True:
            try:
                changed = await asyncio.wait_for(q.get(), timeout=HEARTBEAT_SECONDS)
                await ws.send_text(json.dumps({"type": "tick", "data": changed}))
            except asyncio.TimeoutError:
                await ws.send_text(json.dumps({"type": "ping"}))
    except WebSocketDisconnect:
        pass
    finally:
        store.unsubscribe(q)


def _token_ok(token: str | None) -> bool:
    try:
        decode_token(f"Bearer {token}" if token else None)
        return True
    except HTTPException:
        return False


@router.get("/stream")
async def market_stream(token: str = Query(...)):
    # Validate JWT (same secret/algorithm as Authorization-header auth).
    try:
        decode_token(f"Bearer {token}")
    except HTTPException:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid stream token")

    async def event_gen():
        q = store.subscribe()
        try:
            # Full state first so a (re)connecting client syncs instantly.
            snap = store.snapshot()
            yield f"event: snapshot\ndata: {json.dumps(snap)}\n\n"
            last_beat = time.time()
            pending: dict = {}
            last_flush = time.time()
            while True:
                try:
                    changed = await asyncio.wait_for(q.get(), timeout=TICK_BATCH_SECONDS)
                    pending.update(changed)
                except asyncio.TimeoutError:
                    pass
                now = time.time()
                # Flush at most once per batch window; heartbeat if idle.
                if pending and now - last_flush >= 0.2:
                    yield f"event: tick\ndata: {json.dumps(pending)}\n\n"
                    pending = {}
                    last_flush = now
                if now - last_beat >= HEARTBEAT_SECONDS:
                    yield f": keepalive {int(now)}\n\n"
                    last_beat = now
        finally:
            store.unsubscribe(q)

    return StreamingResponse(
        event_gen(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",  # disable proxy buffering
        },
    )
