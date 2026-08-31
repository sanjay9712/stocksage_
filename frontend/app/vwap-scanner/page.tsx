"use client";

import { useState, useCallback } from "react";
import useSWR from "swr";
import { fetchVwapScanner, refreshVwapScanner, type VwapScanEntry } from "@/lib/api";

function timeAgo(iso: string): string {
  if (!iso) return "—";
  const diff = Date.now() - new Date(iso).getTime();
  const mins = Math.floor(diff / 60000);
  if (mins < 1) return "just now";
  if (mins < 60) return `${mins} min ago`;
  return `${Math.floor(mins / 60)}h ${mins % 60}m ago`;
}

function devColor(val: number): string {
  if (val > 1.5) return "text-rose-400";
  if (val > 0) return "text-amber-400";
  if (val < -1.5) return "text-emerald-400";
  if (val < 0) return "text-sky-400";
  return "text-slate-400";
}

function signalBadge(signal: string): string {
  switch (signal) {
    case "overbought_premium": return "bg-rose-950/50 text-rose-300 border-rose-700/40";
    case "premium": return "bg-amber-950/40 text-amber-300 border-amber-700/30";
    case "oversold_discount": return "bg-emerald-950/50 text-emerald-300 border-emerald-700/40";
    case "discount": return "bg-sky-950/40 text-sky-300 border-sky-700/30";
    default: return "bg-slate-800/40 text-slate-400 border-slate-700/30";
  }
}

function VwapRow({ e }: { e: VwapScanEntry }) {
  const badge = signalBadge(e.signal);
  const fmtPrice = e.market === "us" ? `$${e.current_price.toFixed(2)}` : `₹${e.current_price.toFixed(2)}`;

  return (
    <tr className="hover:bg-slate-800/30 transition-colors border-b border-slate-800/40">
      <td className="px-2 py-2.5">
        <div className="text-xs font-medium text-slate-100">{e.symbol}</div>
        <div className="text-[10px] text-slate-500 truncate max-w-[100px]">{e.name}</div>
      </td>
      <td className="px-2 py-2.5 text-center">
        <span className={`inline-block px-1.5 py-0.5 rounded text-[10px] font-semibold border ${badge}`}>
          {e.signal.replace(/_/g, " ")}
        </span>
      </td>
      <td className={`px-2 py-2.5 text-right tabular-nums font-bold ${devColor(e.deviation_pct)}`}>
        {e.deviation_pct > 0 ? "+" : ""}{e.deviation_pct.toFixed(2)}%
      </td>
      <td className="px-2 py-2.5 text-right tabular-nums text-slate-300">{fmtPrice}</td>
      <td className="px-2 py-2.5 text-right tabular-nums text-slate-400">{e.vwap.toFixed(2)}</td>
      <td className={`px-2 py-2.5 text-right tabular-nums ${e.rsi > 70 ? "text-rose-400" : e.rsi < 30 ? "text-emerald-400" : "text-slate-300"}`}>
        {e.rsi.toFixed(0)}
      </td>
      <td className="px-2 py-2.5 text-right tabular-nums text-slate-400">
        {e.volume_ratio > 0 ? `${e.volume_ratio.toFixed(1)}x` : "—"}
      </td>
      <td className="px-2 py-2.5 text-right">
        <div className="flex items-center gap-1 justify-end">
          <div className="w-12 h-1.5 bg-slate-800 rounded-full overflow-hidden">
            <div
              className={`h-full rounded-full ${e.range_position > 0.7 ? "bg-rose-500" : e.range_position < 0.3 ? "bg-emerald-500" : "bg-slate-500"}`}
              style={{ width: `${e.range_position * 100}%` }}
            />
          </div>
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

export default function VwapScannerPage() {
  const [tab, setTab] = useState<"nse" | "us">("nse");
  const [minDev, setMinDev] = useState(0.5);
  const [view, setView] = useState<"all" | "premium" | "discount">("all");

  const { data, error, isLoading, mutate } = useSWR(
    ["vwap-scanner", tab, minDev],
    () => fetchVwapScanner(tab, minDev),
    { refreshInterval: 300000, keepPreviousData: true }
  );
  const [refreshing, setRefreshing] = useState(false);

  const handleRefresh = useCallback(async () => {
    setRefreshing(true);
    try {
      await refreshVwapScanner();
      await mutate();
    } finally {
      setRefreshing(false);
    }
  }, [mutate]);

  const entries = data ? (view === "premium" ? data.premiums : view === "discount" ? data.discounts : data.results) : [];

  if (isLoading && !data) {
    return (
      <div className="space-y-6">
        <div>
          <h1 className="text-xl font-bold text-slate-100">VWAP Scanner</h1>
          <p className="text-sm text-slate-500 mt-1">Scanning VWAP deviations...</p>
        </div>
        <div className="glass-card h-32 shimmer" />
      </div>
    );
  }

  if (error && !data) {
    return (
      <div className="text-center py-12">
        <p className="text-rose-300 mb-4">Failed to load VWAP data</p>
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
          <h1 className="text-xl font-bold text-slate-100">VWAP Scanner</h1>
          <p className="text-sm text-slate-500 mt-1">
            Premium/discount to VWAP — updated {data ? timeAgo(data.refreshed_at) : "—"}
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
          <span className="text-slate-500">Min deviation %:</span>
          <input
            type="range"
            min="0"
            max="3"
            step="0.25"
            value={minDev}
            onChange={(e) => setMinDev(parseFloat(e.target.value))}
            className="w-24 accent-emerald-500"
          />
          <span className="tabular-nums text-slate-300 w-8">{minDev.toFixed(2)}%</span>
        </div>
        <div className="flex gap-1">
          {(["all", "premium", "discount"] as const).map((v) => (
            <button
              key={v}
              onClick={() => setView(v)}
              className={`px-2.5 py-1 rounded-lg font-medium transition-colors capitalize ${
                view === v ? "bg-slate-700 text-slate-100" : "bg-slate-800/50 text-slate-400 hover:bg-slate-800"
              }`}
            >
              {v}
            </button>
          ))}
        </div>
        <span className="ml-auto text-slate-500">{entries.length} results</span>
      </div>

      {/* Summary */}
      <div className="grid grid-cols-3 gap-3">
        <div className="glass-card p-3">
          <div className="text-xs text-slate-500">Premiums</div>
          <div className="text-lg font-bold text-amber-400 tabular-nums">{data?.premiums.length ?? 0}</div>
        </div>
        <div className="glass-card p-3">
          <div className="text-xs text-slate-500">Discounts</div>
          <div className="text-lg font-bold text-sky-400 tabular-nums">{data?.discounts.length ?? 0}</div>
        </div>
        <div className="glass-card p-3">
          <div className="text-xs text-slate-500">Largest Deviation</div>
          <div className="text-lg font-bold text-rose-400 tabular-nums">
            {data && data.results.length > 0
              ? `${data.results[0].symbol} ${data.results[0].deviation_pct > 0 ? "+" : ""}${data.results[0].deviation_pct.toFixed(1)}%`
              : "—"}
          </div>
        </div>
      </div>

      {/* Table */}
      <div className="glass-card overflow-x-auto">
        <table className="w-full text-xs">
          <thead>
            <tr className="text-slate-500 border-b border-slate-800">
              <th className="px-2 py-2 text-left font-medium">Symbol</th>
              <th className="px-2 py-2 text-center font-medium">Signal</th>
              <th className="px-2 py-2 text-right font-medium">Dev %</th>
              <th className="px-2 py-2 text-right font-medium">Price</th>
              <th className="px-2 py-2 text-right font-medium">VWAP</th>
              <th className="px-2 py-2 text-right font-medium">RSI</th>
              <th className="px-2 py-2 text-right font-medium">Vol Ratio</th>
              <th className="px-2 py-2 text-right font-medium">Range Pos</th>
            </tr>
          </thead>
          <tbody>
            {entries.map((e) => (
              <VwapRow key={e.symbol} e={e} />
            ))}
          </tbody>
        </table>
        {entries.length === 0 && (
          <div className="p-8 text-center text-slate-500 text-sm">
            No VWAP deviations found with min {minDev}% threshold.
          </div>
        )}
      </div>
    </div>
  );
}
