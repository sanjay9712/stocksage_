"use client";

import React, { createContext, useContext, useEffect, useRef, useState, useCallback } from "react";
import { getToken } from "@/lib/api";

// ---------------------------------------------------------------------------
// Live market context — subscribes to the backend SSE stream once and
// pushes price updates into React state. The UI never polls; prices update
// in place with a brief tick flash, so there is no visible "refresh".
// ---------------------------------------------------------------------------

export interface LiveIndex {
  name: string;
  last: number | null;
  change: number | null;
  pct_change: number | null;
  source: string;
  ts: number;
}

export interface LiveStatus {
  market_open: boolean;
  status_text?: string;
  source?: string;
  trade_date?: string;
}

interface LiveMarketState {
  connected: boolean;        // SSE stream is open
  status: LiveStatus | null;
  indices: Record<string, LiveIndex>;
  lastUpdated: number | null; // epoch ms of latest tick
}

interface LiveMarketCtx extends LiveMarketState {
  // Stable display ordering of the known headline indices.
  orderedIndices: LiveIndex[];
  // Per-index flash signal. `id` increments on every price move so the UI can
  // key on it to replay the tick animation each time.
  flashOf: (name: string) => { dir: "up" | "down"; id: number } | null;
}

// Display order for the headline indices (matches what /api/market/live returns).
const INDEX_ORDER = ["NIFTY 50", "NIFTY BANK", "NIFTY IT", "NIFTY MIDCAP 100", "INDIA VIX"];

const Ctx = createContext<LiveMarketCtx | null>(null);

export function LiveMarketProvider({ children }: { children: React.ReactNode }) {
  const [state, setState] = useState<LiveMarketState>({
    connected: false,
    status: null,
    indices: {},
    lastUpdated: null,
  });
  const wsRef = useRef<WebSocket | null>(null);
  // Track previous last to decide flash direction per index.
  const prevRef = useRef<Record<string, number>>({});
  // State (not a ref) so changes re-render; id replays the CSS animation.
  const [flashes, setFlashes] = useState<Record<string, { dir: "up" | "down"; id: number }>>({});

  // Reconnect when the auth token appears (post-login) or is cleared (logout).
  const [authTick, setAuthTick] = useState(0);
  useEffect(() => {
    const bump = () => setAuthTick((t) => t + 1);
    window.addEventListener("auth-change", bump);
    return () => window.removeEventListener("auth-change", bump);
  }, []);
  // Re-read on every render; authTick forces a re-render on login/logout.
  void authTick;
  const token = getToken();

  useEffect(() => {
    if (!token) return;
    let closed = false;
    let retryTimer: ReturnType<typeof setTimeout>;
    let retryDelay = 1000;

    const open = () => {
      if (closed) return;
      // WebSocket is the browser-facing transport: it streams through the
      // Cloudflare quick tunnel, whereas SSE responses get buffered there.
      const proto = window.location.protocol === "https:" ? "wss:" : "ws:";
      const ws = new WebSocket(
        `${proto}//${window.location.host}/api/market/stream-ws?token=${encodeURIComponent(token)}`
      );
      wsRef.current = ws;

      ws.onopen = () => {
        retryDelay = 1000;
        setState((s) => ({ ...s, connected: true }));
      };

      ws.onmessage = (e) => {
        let msg: { type: string; data: any };
        try {
          msg = JSON.parse(e.data as string);
        } catch {
          return;
        }
        if (msg.type === "snapshot") {
          const data = msg.data ?? {};
          setState((s) => ({
            connected: true,
            status: data.status ?? s.status,
            indices: normalizePrices(data.prices ?? {}, s.indices),
            lastUpdated: data.updated_at ? data.updated_at * 1000 : s.lastUpdated,
          }));
        } else if (msg.type === "tick") {
          const changed = msg.data ?? {};
          // Decide flash direction from the previous last price (kept in a ref).
          const moved: Record<string, { dir: "up" | "down" }> = {};
          for (const [name, idx] of Object.entries(changed)) {
            const prev = prevRef.current[name];
            if (prev != null && idx.last != null && idx.last !== prev) {
              moved[name] = { dir: idx.last > prev ? "up" : "down" };
            }
            if (idx.last != null) prevRef.current[name] = idx.last;
          }
          if (Object.keys(moved).length) {
            setFlashes((f) => {
              const next = { ...f };
              for (const name of Object.keys(moved)) {
                next[name] = { dir: moved[name].dir, id: (f[name]?.id ?? 0) + 1 };
              }
              return next;
            });
          }
          setState((s) => ({
            ...s,
            indices: normalizePrices(changed, s.indices),
            lastUpdated: Date.now(),
          }));
        }
        // type === "ping" → keepalive, nothing to render.
      };

      const handleClose = () => {
        if (closed) return;
        setState((s) => ({ ...s, connected: false }));
        retryTimer = setTimeout(open, retryDelay);
        retryDelay = Math.min(retryDelay * 2, 15000);
      };
      ws.onclose = handleClose;
      ws.onerror = handleClose;
    };

    open();
    return () => {
      closed = true;
      clearTimeout(retryTimer);
      wsRef.current?.close();
      wsRef.current = null;
    };
  }, [token]);

  const flashOf = useCallback(
    (name: string) => flashes[name] ?? null,
    [flashes]
  );

  const orderedIndices = Object.keys(state.indices)
    .sort((a, b) => {
      const ia = INDEX_ORDER.indexOf(a);
      const ib = INDEX_ORDER.indexOf(b);
      return (ia === -1 ? 99 : ia) - (ib === -1 ? 99 : ib);
    })
    .map((k) => state.indices[k]);

  return (
    <Ctx.Provider value={{ ...state, orderedIndices, flashOf }}>{children}</Ctx.Provider>
  );
}

function normalizePrices(
  prices: Record<string, any>,
  existing: Record<string, LiveIndex>
): Record<string, LiveIndex> {
  const out: Record<string, LiveIndex> = { ...existing };
  for (const [name, p] of Object.entries(prices)) {
    out[name] = {
      name,
      last: p.last ?? null,
      change: p.change ?? null,
      pct_change: p.pct_change ?? null,
      source: p.source ?? "",
      ts: p.ts ?? 0,
    };
  }
  return out;
}

export function useLiveMarket(): LiveMarketCtx {
  const ctx = useContext(Ctx);
  if (!ctx) throw new Error("useLiveMarket must be used within LiveMarketProvider");
  return ctx;
}
