"use client";

import { useState, useCallback } from "react";
import useSWR from "swr";
import { fetchGapScanner, refreshGapScanner, type GapScanEntry } from "@/lib/api";

function timeAgo(iso: string): string {
  if (!iso) return "—";
  const diff = Date.now() - new Date(iso).getTime();
  const mins = Math.floor(diff / 60000);
  if (mins < 1) return "just now";
  if (mins < 60) return `${mins} min ago`;
  return `${Math.floor(mins / 60)}h ${mins % 60}m ago`;
}

function gapColor(val: number): string {
  if (val > 0) {
    const intensity = Math.min(Math.abs(val) / 5, 1);
    return `text-emerald-400`;
  }
  if (val < 0) return "text-rose-400";
  return "text-slate-400";
}

function magnitudeBadge(mag: string): string {
  switch (mag) {
    case "extreme": return "bg-rose-950/60 text-rose-300 border-rose-700/50";
    case "large": return "bg-amber-950/40 text-amber-300 border-amber-700/40";
    case "moderate": return "bg-sky-950/30 text-sky-300 border-sky-700/30";
    case "small": return "bg-slate-800/40 text-slate-400 border-slate-700/40";
    default: return "bg-slate-800/30 text-slate-500 border-slate-700/30";
  }
}

function playIcon(play: string): { icon: string; color: string } {
  switch (play) {
    case "continuation_long": return { icon: "M5 12l5 5L20 7", color: "text-emerald-400" };
    case "continuation_short": return { icon: "M5 12l5-5L20 17", color: "text-rose-400" };
    case "watch": return { icon: "M12 2a10 10 0 100 20 10 10 0 000-20zM12 6v6l4 2", color: "text-amber-400" };
    default: return { icon: "M5 12h14", color: "text-slate-500" };
  }
}

function GapRow({ e, expanded, onToggle }: { e: GapScanEntry; expanded: boolean; onToggle: () => void }) {
  const mag = magnitudeBadge(e.magnitude);
  const play = playIcon(e.play);
  const fmtPrice = e.market === "us" ? `$${e.current_price.toFixed(2)}` : `₹${e.current_price.toFixed(2)}`;

  return (
    <>
      <tr onClick={onToggle} className="cursor-pointer hover:bg-slate-800/30 transition-colors border-b border-slate-800/40">
        <td className="px-2 py-2.5">
          <div className="text-xs font-medium text-slate-100">{e.symbol}</div>
          <div className="text-[10px] text-slate-500 truncate max-w-[100px]">{e.name}</div>
        </td>
        <td className="px-2 py-2.5 text-center">
          <span className={`inline-block px-1.5 py-0.5 rounded text-[10px] font-semibold border ${mag}`}>
            {e.magnitude}
          </span>
        </td>
        <td className={`px-2 py-2.5 text-right tabular-nums font-bold ${gapColor(e.gap_pct)}`}>
          {e.gap_pct > 0 ? "+" : ""}{e.gap_pct.toFixed(2)}%
        </td>
        <td className="px-2 py-2.5 text-right tabular-nums text-slate-300">{fmtPrice}</td>
        <td className="px-2 py-2.5 text-right tabular-nums text-slate-400">{e.prev_close.toFixed(2)}</td>
        <td className="px-2 py-2.5 text-right tabular-nums text-slate-300">
          {e.volume_ratio > 0 ? `${e.volume_ratio.toFixed(1)}x` : "—"}
        </td>
        <td className="px-2 py-2.5 text-right tabular-nums text-slate-400">{e.expected_move_pct.toFixed(1)}%</td>
        <td className="px-2 py-2.5 text-center">
          <svg className={`w-4 h-4 inline ${play.color}`} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <path d={play.icon} />
          </svg>
        </td>
      </tr>
      {expanded && (
        <tr className="bg-slate-900/40 border-b border-slate-800/40">
          <td colSpan={8} className="px-4 py-3">
            <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 text-xs">
              <div>
                <span className="text-slate-500">Prev High</span>
                <div className="text-slate-200 tabular-nums">{e.prev_high.toFixed(2)}</div>
              </div>
              <div>
                <span className="text-slate-500">Prev Low</span>
                <div className="text-slate-200 tabular-nums">{e.prev_low.toFixed(2)}</div>
              </div>
              <div>
                <span className="text-slate-500">Gap Range</span>
                <div className="text-slate-200 tabular-nums">{e.gap_low.toFixed(2)} – {e.gap_high.toFixed(2)}</div>
              </div>
              <div>
                <span className="text-slate-500">ATR</span>
                <div className="text-slate-200 tabular-nums">{e.atr.toFixed(2)}</div>
              </div>
            </div>
            <div className="mt-2 text-xs text-slate-400">{e.strategy}</div>
          </td>
        </tr>
      )}
    </>
  );
}

function MarketBadge({ open }: { open: boolean }) {
  return open ? (
    <span className="inline-flex items-center gap-1.5 px-2 py-0.5 rounded-full text-xs font-medium bg-emerald-950/50 text-emerald-400 border border-emerald-800/50">
      <span className="w-1.5 h-1.5 rounded-full bg-emerald-400 animate-pulse" />LIVE
    </span>
  ) : (
    <span className="inline-flex items-center gap-1.5 px-2 py-0.5 rounded-full text-xs font-medium bg-slate-800/50 text-slate-400 border border-slate-700/50">
      CLOSED
    </span>
  );
}

export default function GapScannerPage() {
  const [tab, setTab] = useState<"nse" | "us">("nse");
  const [minGap, setMinGap] = useState(0.5);
  const [view, setView] = useState<"all" | "up" | "down">("all");
  const [expandedRow, setExpandedRow] = useState<string | null>(null);

  const { data, error, isLoading, mutate } = useSWR(
    ["gap-scanner", tab, minGap],
    () => fetchGapScanner(tab, minGap),
    { refreshInterval: 300000, keepPreviousData: true }
  );
  const [refreshing, setRefreshing] = useState(false);

  const handleRefresh = useCallback(async () => {
    setRefreshing(true);
    try {
      await refreshGapScanner();
      await mutate();
    } finally {
      setRefreshing(false);
    }
  }, [mutate]);

  const entries = data ? (view === "up" ? data.gap_ups : view === "down" ? data.gap_downs : data.gaps) : [];

  if (isLoading && !data) {
    return (
      <div className="space-y-6">
        <div>
          <h1 className="text-xl font-bold text-slate-100">Gap Scanner</h1>
          <p className="text-sm text-slate-500 mt-1">Scanning for opening gaps...</p>
        </div>
        <div className="glass-card h-32 shimmer" />
      </div>
    );
  }

  if (error && !data) {
    return (
      <div className="text-center py-12">
        <p className="text-rose-300 mb-4">Failed to load gap data</p>
        <button onClick={() => mutate()} className="px-4 py-2 bg-emerald-600 hover:bg-emerald-500 text-white rounded-lg text-sm">
          Retry
        </button>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between flex-wrap gap-3">
        <div>
          <h1 className="text-xl font-bold text-slate-100">Gap Scanner</h1>
          <p className="text-sm text-slate-500 mt-1">
            Stocks gapping from previous close — updated {data ? timeAgo(data.refreshed_at) : "—"}
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

      {/* Tabs */}
      <div className="flex gap-2">
        <button
          onClick={() => setTab("nse")}
          className={`px-4 py-2 rounded-lg text-sm font-medium transition-colors ${tab === "nse" ? "bg-emerald-600 text-white" : "bg-slate-800 text-slate-400 hover:bg-slate-700"}`}
        >
          NSE / India
        </button>
        <button
          onClick={() => setTab("us")}
          className={`px-4 py-2 rounded-lg text-sm font-medium transition-colors ${tab === "us" ? "bg-emerald-600 text-white" : "bg-slate-800 text-slate-400 hover:bg-slate-700"}`}
        >
          US Markets
        </button>
        <div className="ml-auto flex items-center gap-2">
          <MarketBadge open={data?.market_status?.market_open ?? false} />
        </div>
      </div>

      {/* Controls */}
      <div className="flex flex-wrap items-center gap-3 text-xs">
        <div className="flex items-center gap-2">
          <span className="text-slate-500">Min gap %:</span>
          <input
            type="range"
            min="0"
            max="5"
            step="0.5"
            value={minGap}
            onChange={(e) => setMinGap(parseFloat(e.target.value))}
            className="w-24 accent-emerald-500"
          />
          <span className="tabular-nums text-slate-300 w-8">{minGap.toFixed(1)}%</span>
        </div>
        <div className="flex gap-1">
          {(["all", "up", "down"] as const).map((v) => (
            <button
              key={v}
              onClick={() => setView(v)}
              className={`px-2.5 py-1 rounded-lg font-medium transition-colors ${
                view === v ? "bg-slate-700 text-slate-100" : "bg-slate-800/50 text-slate-400 hover:bg-slate-800"
              }`}
            >
              {v === "all" ? "All" : v === "up" ? "Gap Up" : "Gap Down"}
            </button>
          ))}
        </div>
        <span className="ml-auto text-slate-500">{entries.length} results</span>
      </div>

      {/* Summary */}
      <div className="grid grid-cols-3 gap-3">
        <div className="glass-card p-3">
          <div className="text-xs text-slate-500">Gap Ups</div>
          <div className="text-lg font-bold text-emerald-400 tabular-nums">{data?.gap_ups.length ?? 0}</div>
        </div>
        <div className="glass-card p-3">
          <div className="text-xs text-slate-500">Gap Downs</div>
          <div className="text-lg font-bold text-rose-400 tabular-nums">{data?.gap_downs.length ?? 0}</div>
        </div>
        <div className="glass-card p-3">
          <div className="text-xs text-slate-500">Largest Gap</div>
          <div className="text-lg font-bold text-amber-400 tabular-nums">
            {data && data.gaps.length > 0 ? `${data.gaps[0].symbol} ${data.gaps[0].gap_pct > 0 ? "+" : ""}${data.gaps[0].gap_pct.toFixed(1)}%` : "—"}
          </div>
        </div>
      </div>

      {/* Table */}
      <div className="glass-card overflow-x-auto">
        <table className="w-full text-xs">
          <thead>
            <tr className="text-slate-500 border-b border-slate-800">
              <th className="px-2 py-2 text-left font-medium">Symbol</th>
              <th className="px-2 py-2 text-center font-medium">Magnitude</th>
              <th className="px-2 py-2 text-right font-medium">Gap %</th>
              <th className="px-2 py-2 text-right font-medium">Price</th>
              <th className="px-2 py-2 text-right font-medium">Prev Close</th>
              <th className="px-2 py-2 text-right font-medium">Vol Ratio</th>
              <th className="px-2 py-2 text-right font-medium">Exp Move</th>
              <th className="px-2 py-2 text-center font-medium">Play</th>
            </tr>
          </thead>
          <tbody>
            {entries.map((e) => (
              <GapRow
                key={e.symbol}
                e={e}
                expanded={expandedRow === e.symbol}
                onToggle={() => setExpandedRow(expandedRow === e.symbol ? null : e.symbol)}
              />
            ))}
          </tbody>
        </table>
        {entries.length === 0 && (
          <div className="p-8 text-center text-slate-500 text-sm">
            No gaps found with min {minGap}% threshold. Try lowering the filter.
          </div>
        )}
      </div>
    </div>
  );
}
