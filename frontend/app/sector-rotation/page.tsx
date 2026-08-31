"use client";

import { useState, useCallback } from "react";
import useSWR from "swr";
import { fetchSectorRotation, refreshSectorRotation, type SectorRotation } from "@/lib/api";

function timeAgo(iso: string): string {
  if (!iso) return "—";
  const diff = Date.now() - new Date(iso).getTime();
  const mins = Math.floor(diff / 60000);
  if (mins < 1) return "just now";
  if (mins < 60) return `${mins} min ago`;
  const hrs = Math.floor(mins / 60);
  return `${hrs}h ${mins % 60}m ago`;
}

const rotationConfig: Record<string, { icon: string; color: string }> = {
  accelerating: { icon: "M5 12l5 5L20 7", color: "text-emerald-400" },
  strengthening: { icon: "M3 17l6-6 4 4 8-8", color: "text-emerald-300" },
  weakening: { icon: "M3 7l6 6 4-4 8 8", color: "text-amber-300" },
  decelerating: { icon: "M3 7l6 6 4-4 8 8", color: "text-orange-400" },
  bearish: { icon: "M5 12l5-5L20 17", color: "text-rose-400" },
};

function cellColor(val: number): string {
  if (val > 0) {
    const intensity = Math.min(Math.abs(val) / 10, 1);
    const opacity = 0.15 + intensity * 0.55;
    return `bg-emerald-600/${Math.round(opacity * 100)}`;
  }
  if (val < 0) {
    const intensity = Math.min(Math.abs(val) / 10, 1);
    const opacity = 0.15 + intensity * 0.55;
    return `bg-rose-600/${Math.round(opacity * 100)}`;
  }
  return "bg-slate-800/40";
}

function retColor(val: number): string {
  if (val > 0) return "text-emerald-400";
  if (val < 0) return "text-rose-400";
  return "text-slate-400";
}

function fmtPrice(s: SectorRotation): string {
  return s.market === "us" ? `$${s.last_price.toFixed(2)}` : `₹${s.last_price.toFixed(2)}`;
}

function SectorCell({ s }: { s: SectorRotation }) {
  const [expanded, setExpanded] = useState(false);
  const rot = rotationConfig[s.rotation] || rotationConfig.bearish;

  return (
    <div
      onClick={() => setExpanded(!expanded)}
      className={`${cellColor(s.return_1m)} border border-slate-700/50 rounded-xl p-4 cursor-pointer hover:border-slate-600 transition-all fade-in`}
    >
      <div className="flex items-start justify-between mb-2">
        <div>
          <div className="text-sm font-semibold text-slate-100">{s.name}</div>
          <div className="text-xs text-slate-400">{s.symbol}</div>
        </div>
        <svg className={`w-4 h-4 ${rot.color}`} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
          <path d={rot.icon} />
        </svg>
      </div>

      <div className="text-lg font-bold text-slate-100 tabular-nums mb-1">
        {fmtPrice(s)}
      </div>
      <div className="text-xs text-slate-300 capitalize">{s.rotation}</div>

      <div className="grid grid-cols-4 gap-1 mt-3 text-xs">
        <div className="text-center">
          <div className="text-slate-500">1D</div>
          <div className={`font-medium tabular-nums ${retColor(s.return_1d)}`}>
            {s.return_1d > 0 ? "+" : ""}{s.return_1d}%
          </div>
        </div>
        <div className="text-center">
          <div className="text-slate-500">1W</div>
          <div className={`font-medium tabular-nums ${retColor(s.return_1w)}`}>
            {s.return_1w > 0 ? "+" : ""}{s.return_1w}%
          </div>
        </div>
        <div className="text-center">
          <div className="text-slate-500">1M</div>
          <div className={`font-medium tabular-nums ${retColor(s.return_1m)}`}>
            {s.return_1m > 0 ? "+" : ""}{s.return_1m}%
          </div>
        </div>
        <div className="text-center">
          <div className="text-slate-500">3M</div>
          <div className={`font-medium tabular-nums ${retColor(s.return_3m)}`}>
            {s.return_3m > 0 ? "+" : ""}{s.return_3m}%
          </div>
        </div>
      </div>

      {expanded && (
        <div className="mt-3 pt-3 border-t border-slate-700/50 space-y-2 text-xs">
          <div className="flex justify-between">
            <span className="text-slate-500">RSI(14)</span>
            <span className={`tabular-nums font-medium ${s.rsi > 70 ? "text-rose-400" : s.rsi < 30 ? "text-emerald-400" : "text-slate-300"}`}>
              {s.rsi.toFixed(1)}
            </span>
          </div>
          <div className="flex justify-between">
            <span className="text-slate-500">Trend</span>
            <span className={`font-medium ${s.trend === "bullish" ? "text-emerald-400" : s.trend === "bearish" ? "text-rose-400" : "text-slate-400"}`}>
              {s.trend}
            </span>
          </div>
          <div className="flex justify-between">
            <span className="text-slate-500">Sharpe</span>
            <span className="tabular-nums text-slate-300">{s.sharpe.toFixed(2)}</span>
          </div>
          <div className="flex justify-between">
            <span className="text-slate-500">Momentum</span>
            <div className="flex items-center gap-2">
              <div className="w-16 h-1.5 bg-slate-800 rounded-full overflow-hidden">
                <div
                  className={`h-full rounded-full ${s.momentum_score >= 0.5 ? "bg-emerald-500" : "bg-rose-500"}`}
                  style={{ width: `${s.momentum_score * 100}%` }}
                />
              </div>
              <span className="tabular-nums text-slate-400">{(s.momentum_score * 100).toFixed(0)}</span>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

function MarketBadge({ open }: { open: boolean }) {
  return open ? (
    <span className="inline-flex items-center gap-1.5 px-2 py-0.5 rounded-full text-xs font-medium bg-emerald-950/50 text-emerald-400 border border-emerald-800/50">
      <span className="w-1.5 h-1.5 rounded-full bg-emerald-400 animate-pulse" />
      LIVE
    </span>
  ) : (
    <span className="inline-flex items-center gap-1.5 px-2 py-0.5 rounded-full text-xs font-medium bg-slate-800/50 text-slate-400 border border-slate-700/50">
      CLOSED
    </span>
  );
}

export default function SectorRotationPage() {
  const { data, error, isLoading, mutate } = useSWR("sector-rotation", fetchSectorRotation, {
    refreshInterval: 300000,
    keepPreviousData: true,
  });
  const [refreshing, setRefreshing] = useState(false);

  const handleRefresh = useCallback(async () => {
    setRefreshing(true);
    try {
      await refreshSectorRotation();
      await mutate();
    } finally {
      setRefreshing(false);
    }
  }, [mutate]);

  if (isLoading && !data) {
    return (
      <div className="space-y-6">
        <div>
          <h1 className="text-xl font-bold text-slate-100">Sector Rotation</h1>
          <p className="text-sm text-slate-500 mt-1">Loading sector performance...</p>
        </div>
        <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
          {Array.from({ length: 9 }).map((_, i) => (
            <div key={i} className="glass-card h-36 shimmer" />
          ))}
        </div>
      </div>
    );
  }

  if (error && !data) {
    return (
      <div className="text-center py-12">
        <p className="text-rose-300 mb-4">Failed to load sector data</p>
        <button onClick={() => mutate()} className="px-4 py-2 bg-emerald-600 hover:bg-emerald-500 text-white rounded-lg text-sm">
          Retry
        </button>
      </div>
    );
  }

  return (
    <div className="space-y-8">
      {/* Header */}
      <div className="flex items-center justify-between flex-wrap gap-3">
        <div>
          <h1 className="text-xl font-bold text-slate-100">Sector Rotation</h1>
          <p className="text-sm text-slate-500 mt-1">
            Which sectors are leading vs lagging — updated {data ? timeAgo(data.refreshed_at) : "—"}
          </p>
        </div>
        <button
          onClick={handleRefresh}
          disabled={refreshing}
          className="px-3 py-1.5 bg-slate-800 hover:bg-slate-700 disabled:opacity-50 text-slate-300 rounded-lg text-sm flex items-center gap-2 transition-colors"
        >
          <svg className={`w-4 h-4 ${refreshing ? "animate-spin" : ""}`} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <path d="M3 12a9 9 0 0 1 15-6.7L21 8M21 3v5h-5M21 12a9 9 0 0 1-15 6.7L3 16M3 21v-5h5" />
          </svg>
          Refresh
        </button>
      </div>

      {/* Legend */}
      <div className="flex flex-wrap items-center gap-4 text-xs text-slate-500">
        <span>Color by 1-month return:</span>
        <div className="flex items-center gap-1">
          <div className="w-4 h-4 rounded bg-rose-600/60" />
          <span>Negative</span>
        </div>
        <div className="flex items-center gap-1">
          <div className="w-4 h-4 rounded bg-slate-800/40" />
          <span>Flat</span>
        </div>
        <div className="flex items-center gap-1">
          <div className="w-4 h-4 rounded bg-emerald-600/60" />
          <span>Positive</span>
        </div>
      </div>

      {/* NSE sectors */}
      {data?.nse && (
        <section>
          <div className="flex items-center gap-3 mb-4">
            <h2 className="text-lg font-semibold text-slate-200">NSE / India</h2>
            <MarketBadge open={data.nse_market?.market_open ?? false} />
          </div>
          <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4">
            {data.nse.map((s) => (
              <SectorCell key={s.symbol} s={s} />
            ))}
          </div>
        </section>
      )}

      {/* US sectors */}
      {data?.us && (
        <section>
          <div className="flex items-center gap-3 mb-4">
            <h2 className="text-lg font-semibold text-slate-200">US Markets</h2>
            <MarketBadge open={data.us_market?.market_open ?? false} />
          </div>
          <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4">
            {data.us.map((s) => (
              <SectorCell key={s.symbol} s={s} />
            ))}
          </div>
        </section>
      )}
    </div>
  );
}
