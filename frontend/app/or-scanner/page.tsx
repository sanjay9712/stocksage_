"use client";

import { useState, useCallback } from "react";
import useSWR from "swr";
import { fetchORScanner, refreshORScanner, type ORScanEntry } from "@/lib/api";

function timeAgo(iso: string): string {
  if (!iso) return "—";
  const diff = Date.now() - new Date(iso).getTime();
  const mins = Math.floor(diff / 60000);
  if (mins < 1) return "just now";
  if (mins < 60) return `${mins} min ago`;
  return `${Math.floor(mins / 60)}h ${mins % 60}m ago`;
}

function ORRow({ e }: { e: ORScanEntry }) {
  const isLong = e.side === "long";
  const fmtPrice = e.market === "us" ? `$` : `₹`;

  return (
    <tr className="hover:bg-slate-800/30 transition-colors border-b border-slate-800/40">
      <td className="px-2 py-2.5">
        <div className="text-xs font-medium text-slate-100">{e.symbol}</div>
        <div className="text-[10px] text-slate-500 truncate max-w-[100px]">{e.name}</div>
      </td>
      <td className="px-2 py-2.5 text-center">
        <span className={`inline-block px-1.5 py-0.5 rounded text-[10px] font-bold ${isLong ? "bg-emerald-950/50 text-emerald-300" : "bg-rose-950/50 text-rose-300"}`}>
          {e.side.toUpperCase()}
        </span>
      </td>
      <td className="px-2 py-2.5 text-right tabular-nums text-slate-300">{e.entry.toFixed(2)}</td>
      <td className="px-2 py-2.5 text-right tabular-nums text-rose-400">{e.stop_loss.toFixed(2)}</td>
      <td className="px-2 py-2.5 text-right tabular-nums text-emerald-400">{e.target1.toFixed(2)}</td>
      <td className="px-2 py-2.5 text-right tabular-nums text-emerald-400">{e.target2.toFixed(2)}</td>
      <td className="px-2 py-2.5 text-right tabular-nums text-amber-400">{e.risk_reward.toFixed(1)}</td>
      <td className="px-2 py-2.5 text-right tabular-nums text-slate-300">{e.volume_ratio.toFixed(1)}x</td>
      <td className="px-2 py-2.5 text-right">
        <div className="flex items-center justify-end gap-1">
          <div className="w-12 h-1.5 bg-slate-800 rounded-full overflow-hidden">
            <div
              className={`h-full rounded-full ${e.confidence > 0.7 ? "bg-emerald-500" : e.confidence > 0.4 ? "bg-amber-500" : "bg-slate-500"}`}
              style={{ width: `${e.confidence * 100}%` }}
            />
          </div>
          <span className="tabular-nums text-slate-400 w-6 text-xs">{(e.confidence * 100).toFixed(0)}</span>
        </div>
      </td>
    </tr>
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

export default function ORScannerPage() {
  const [tab, setTab] = useState<"nse" | "us">("nse");
  const [orMinutes, setOrMinutes] = useState(15);

  const { data, error, isLoading, mutate } = useSWR(
    ["or-scanner", tab, orMinutes],
    () => fetchORScanner(tab, orMinutes),
    { refreshInterval: 300000, keepPreviousData: true }
  );
  const [refreshing, setRefreshing] = useState(false);

  const handleRefresh = useCallback(async () => {
    setRefreshing(true);
    try {
      await refreshORScanner();
      await mutate();
    } finally {
      setRefreshing(false);
    }
  }, [mutate]);

  if (isLoading && !data) {
    return (
      <div className="space-y-6">
        <div>
          <h1 className="text-xl font-bold text-slate-100">Opening Range Breakout</h1>
          <p className="text-sm text-slate-500 mt-1">Scanning for OR breakouts...</p>
        </div>
        <div className="glass-card h-32 shimmer" />
      </div>
    );
  }

  if (error && !data) {
    return (
      <div className="text-center py-12">
        <p className="text-rose-300 mb-4">Failed to load OR scanner data</p>
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
          <h1 className="text-xl font-bold text-slate-100">Opening Range Breakout</h1>
          <p className="text-sm text-slate-500 mt-1">
            OR-{orMinutes} breakout signals — updated {data ? timeAgo(data.refreshed_at) : "—"}
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

      {/* Tabs + OR selector */}
      <div className="flex flex-wrap items-center gap-3">
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
        </div>
        <div className="flex gap-1">
          {[5, 15, 30].map((m) => (
            <button
              key={m}
              onClick={() => setOrMinutes(m)}
              className={`px-3 py-2 rounded-lg text-sm font-medium transition-colors ${orMinutes === m ? "bg-slate-700 text-slate-100" : "bg-slate-800/50 text-slate-400 hover:bg-slate-800"}`}
            >
              OR-{m}
            </button>
          ))}
        </div>
        <div className="ml-auto">
          <MarketBadge open={data?.market_status?.market_open ?? false} />
        </div>
      </div>

      {/* Summary */}
      <div className="grid grid-cols-3 gap-3">
        <div className="glass-card p-3">
          <div className="text-xs text-slate-500">Long Breakouts</div>
          <div className="text-lg font-bold text-emerald-400 tabular-nums">{data?.longs.length ?? 0}</div>
        </div>
        <div className="glass-card p-3">
          <div className="text-xs text-slate-500">Short Breakdowns</div>
          <div className="text-lg font-bold text-rose-400 tabular-nums">{data?.shorts.length ?? 0}</div>
        </div>
        <div className="glass-card p-3">
          <div className="text-xs text-slate-500">Total Signals</div>
          <div className="text-lg font-bold text-slate-200 tabular-nums">{data?.total ?? 0}</div>
        </div>
      </div>

      {/* Table */}
      <div className="glass-card overflow-x-auto">
        <table className="w-full text-xs">
          <thead>
            <tr className="text-slate-500 border-b border-slate-800">
              <th className="px-2 py-2 text-left font-medium">Symbol</th>
              <th className="px-2 py-2 text-center font-medium">Side</th>
              <th className="px-2 py-2 text-right font-medium">Entry</th>
              <th className="px-2 py-2 text-right font-medium">Stop</th>
              <th className="px-2 py-2 text-right font-medium">Target 1</th>
              <th className="px-2 py-2 text-right font-medium">Target 2</th>
              <th className="px-2 py-2 text-right font-medium">R:R</th>
              <th className="px-2 py-2 text-right font-medium">Vol Ratio</th>
              <th className="px-2 py-2 text-right font-medium">Confidence</th>
            </tr>
          </thead>
          <tbody>
            {(data?.signals ?? []).map((e) => (
              <ORRow key={`${e.symbol}-${e.or_minutes}`} e={e} />
            ))}
          </tbody>
        </table>
        {(!data || data.signals.length === 0) && (
          <div className="p-8 text-center text-slate-500 text-sm">
            No OR-{orMinutes} breakouts detected yet. Breakouts appear after the opening range completes.
          </div>
        )}
      </div>
    </div>
  );
}
