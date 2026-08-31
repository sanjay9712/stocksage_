"use client";

import { useState, useCallback, useMemo } from "react";
import useSWR from "swr";
import {
  fetchMomentumRotation,
  refreshMomentumRotation,
  type MomentumRotationEntry,
} from "@/lib/api";

function timeAgo(iso: string): string {
  if (!iso) return "—";
  const diff = Date.now() - new Date(iso).getTime();
  const mins = Math.floor(diff / 60000);
  if (mins < 1) return "just now";
  if (mins < 60) return `${mins} min ago`;
  const hrs = Math.floor(mins / 60);
  return `${hrs}h ${mins % 60}m ago`;
}

const tierConfig: Record<string, { bg: string; text: string; border: string }> = {
  "Strong Buy": { bg: "bg-emerald-950/60", text: "text-emerald-300", border: "border-emerald-700/50" },
  Accumulate: { bg: "bg-emerald-950/30", text: "text-emerald-400", border: "border-emerald-800/30" },
  Hold: { bg: "bg-slate-800/40", text: "text-slate-300", border: "border-slate-700/40" },
  Reduce: { bg: "bg-amber-950/30", text: "text-amber-400", border: "border-amber-800/30" },
  Avoid: { bg: "bg-rose-950/40", text: "text-rose-400", border: "border-rose-800/30" },
};

const signalConfig: Record<string, { color: string; icon: string }> = {
  bullish: { color: "text-emerald-400", icon: "M5 12l5 5L20 7" },
  overbought: { color: "text-amber-400", icon: "M12 9v4M12 17h.01M10.29 3.86L1.82 18a2 2 0 001.71 3h16.94a2 2 0 001.71-3L13.71 3.86a2 2 0 00-3.42 0z" },
  recovering: { color: "text-sky-400", icon: "M3 12h6l3-9 3 18 3-9h3" },
  bearish: { color: "text-rose-400", icon: "M5 12l5-5L20 17" },
  weakening: { color: "text-orange-400", icon: "M3 7l6 6 4-4 8 8" },
  neutral: { color: "text-slate-400", icon: "M5 12h14" },
};

function retColor(val: number): string {
  if (val > 0) return "text-emerald-400";
  if (val < 0) return "text-rose-400";
  return "text-slate-400";
}

function fmtPrice(e: MomentumRotationEntry): string {
  return e.market === "us" ? `$${e.last_price.toFixed(2)}` : `₹${e.last_price.toFixed(2)}`;
}

function MomentumRow({ e, expanded, onToggle }: { e: MomentumRotationEntry; expanded: boolean; onToggle: () => void }) {
  const tier = tierConfig[e.tier] || tierConfig.Hold;
  const sig = signalConfig[e.signal] || signalConfig.neutral;

  return (
    <>
      <tr onClick={onToggle} className="cursor-pointer hover:bg-slate-800/30 transition-colors border-b border-slate-800/40">
        <td className="px-2 py-2.5 text-center text-xs text-slate-500 tabular-nums">{e.rank}</td>
        <td className="px-2 py-2.5">
          <div className="flex items-center gap-2">
            <span className="text-xs font-medium text-slate-100">{e.symbol}</span>
            {e.type === "etf" && <span className="text-[10px] text-slate-500 bg-slate-800/50 px-1 rounded">ETF</span>}
          </div>
          <div className="text-[10px] text-slate-500 truncate max-w-[120px]">{e.name}</div>
        </td>
        <td className={`px-2 py-2.5 text-center`}>
          <span className={`inline-block px-2 py-0.5 rounded text-[10px] font-semibold ${tier.bg} ${tier.text} ${tier.border} border`}>
            {e.tier}
          </span>
        </td>
        <td className={`px-2 py-2.5 text-right tabular-nums font-bold ${retColor(e.momentum_12_1)}`}>
          {e.momentum_12_1 > 0 ? "+" : ""}{e.momentum_12_1.toFixed(1)}%
        </td>
        <td className={`px-2 py-2.5 text-right tabular-nums ${retColor(e.return_1m)}`}>
          {e.return_1m > 0 ? "+" : ""}{e.return_1m.toFixed(1)}%
        </td>
        <td className={`px-2 py-2.5 text-right tabular-nums ${retColor(e.return_3m)}`}>
          {e.return_3m > 0 ? "+" : ""}{e.return_3m.toFixed(1)}%
        </td>
        <td className={`px-2 py-2.5 text-right tabular-nums ${retColor(e.return_6m)}`}>
          {e.return_6m > 0 ? "+" : ""}{e.return_6m.toFixed(1)}%
        </td>
        <td className={`px-2 py-2.5 text-right tabular-nums ${retColor(e.return_12m)}`}>
          {e.return_12m > 0 ? "+" : ""}{e.return_12m.toFixed(1)}%
        </td>
        <td className={`px-2 py-2.5 text-right tabular-nums ${e.rsi > 70 ? "text-rose-400" : e.rsi < 30 ? "text-emerald-400" : "text-slate-300"}`}>
          {e.rsi.toFixed(0)}
        </td>
        <td className="px-2 py-2.5 text-right tabular-nums text-slate-300">{e.sharpe.toFixed(2)}</td>
        <td className="px-2 py-2.5 text-right">
          <svg className={`w-4 h-4 inline ${sig.color}`} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <path d={sig.icon} />
          </svg>
        </td>
      </tr>
      {expanded && (
        <tr className="bg-slate-900/40 border-b border-slate-800/40">
          <td colSpan={11} className="px-4 py-3">
            <div className="grid grid-cols-2 sm:grid-cols-4 gap-4 text-xs">
              <div>
                <span className="text-slate-500">Price</span>
                <div className="text-slate-200 font-medium tabular-nums">{fmtPrice(e)}</div>
              </div>
              <div>
                <span className="text-slate-500">Volatility (ann.)</span>
                <div className="text-slate-200 tabular-nums">{e.volatility.toFixed(1)}%</div>
              </div>
              <div>
                <span className="text-slate-500">Trend</span>
                <div className={`font-medium ${e.trend === "bullish" ? "text-emerald-400" : e.trend === "bearish" ? "text-rose-400" : "text-slate-400"}`}>
                  {e.trend}
                </div>
              </div>
              <div>
                <span className="text-slate-500">Percentile Rank</span>
                <div className="flex items-center gap-2">
                  <div className="w-20 h-1.5 bg-slate-800 rounded-full overflow-hidden">
                    <div
                      className={`h-full rounded-full ${e.rank_percentile >= 0.6 ? "bg-emerald-500" : e.rank_percentile >= 0.4 ? "bg-amber-500" : "bg-rose-500"}`}
                      style={{ width: `${e.rank_percentile * 100}%` }}
                    />
                  </div>
                  <span className="tabular-nums text-slate-400">{(e.rank_percentile * 100).toFixed(0)}%</span>
                </div>
              </div>
            </div>
            <div className="mt-2 text-xs text-slate-500">
              <span className="capitalize">{e.signal}</span> — {e.tier === "Strong Buy" ? "Top momentum pick, consider adding." : e.tier === "Avoid" ? "Weak momentum, consider trimming." : "Neutral position."}
            </div>
          </td>
        </tr>
      )}
    </>
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

export default function MomentumRotationPage() {
  const { data, error, isLoading, mutate } = useSWR("momentum-rotation", fetchMomentumRotation, {
    refreshInterval: 300000,
    keepPreviousData: true,
  });
  const [refreshing, setRefreshing] = useState(false);
  const [tab, setTab] = useState<"nse" | "us">("nse");
  const [expandedRow, setExpandedRow] = useState<string | null>(null);
  const [tierFilter, setTierFilter] = useState<string>("all");

  const handleRefresh = useCallback(async () => {
    setRefreshing(true);
    try {
      await refreshMomentumRotation();
      await mutate();
    } finally {
      setRefreshing(false);
    }
  }, [mutate]);

  const entries = useMemo(() => {
    const all = tab === "nse" ? data?.nse ?? [] : data?.us ?? [];
    if (tierFilter === "all") return all;
    return all.filter((e) => e.tier === tierFilter);
  }, [data, tab, tierFilter]);

  const stats = useMemo(() => {
    const source = tab === "nse" ? data?.nse ?? [] : data?.us ?? [];
    const winners = source.filter((e) => e.tier === "Strong Buy").length;
    const losers = source.filter((e) => e.tier === "Avoid").length;
    const avgMom = source.length > 0 ? source.reduce((s, e) => s + e.momentum_12_1, 0) / source.length : 0;
    return { total: source.length, winners, losers, avgMom };
  }, [data, tab]);

  if (isLoading && !data) {
    return (
      <div className="space-y-6">
        <div>
          <h1 className="text-xl font-bold text-slate-100">Momentum Rotation</h1>
          <p className="text-sm text-slate-500 mt-1">Loading momentum screen...</p>
        </div>
        <div className="glass-card h-64 shimmer" />
      </div>
    );
  }

  if (error && !data) {
    return (
      <div className="text-center py-12">
        <p className="text-rose-300 mb-4">Failed to load momentum data</p>
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
          <h1 className="text-xl font-bold text-slate-100">Momentum Rotation</h1>
          <p className="text-sm text-slate-500 mt-1">
            12-month momentum (excluding last month) — Jegadeesh-Titman ranking. Updated {data ? timeAgo(data.refreshed_at) : "—"}
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
      </div>

      {/* Summary stats */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
        <div className="glass-card p-3">
          <div className="text-xs text-slate-500">Screened</div>
          <div className="text-lg font-bold text-slate-200 tabular-nums">{stats.total}</div>
        </div>
        <div className="glass-card p-3">
          <div className="text-xs text-slate-500">Strong Buy</div>
          <div className="text-lg font-bold text-emerald-400 tabular-nums">{stats.winners}</div>
        </div>
        <div className="glass-card p-3">
          <div className="text-xs text-slate-500">Avoid</div>
          <div className="text-lg font-bold text-rose-400 tabular-nums">{stats.losers}</div>
        </div>
        <div className="glass-card p-3">
          <div className="text-xs text-slate-500">Avg Momentum</div>
          <div className={`text-lg font-bold tabular-nums ${stats.avgMom > 0 ? "text-emerald-400" : "text-rose-400"}`}>
            {stats.avgMom > 0 ? "+" : ""}{stats.avgMom.toFixed(1)}%
          </div>
        </div>
      </div>

      {/* Tier filter */}
      <div className="flex flex-wrap items-center gap-2 text-xs">
        <span className="text-slate-500">Filter:</span>
        {["all", "Strong Buy", "Accumulate", "Hold", "Reduce", "Avoid"].map((t) => (
          <button
            key={t}
            onClick={() => setTierFilter(t)}
            className={`px-2.5 py-1 rounded-lg font-medium transition-colors ${
              tierFilter === t
                ? "bg-slate-700 text-slate-100"
                : "bg-slate-800/50 text-slate-400 hover:bg-slate-800"
            }`}
          >
            {t === "all" ? "All" : t}
          </button>
        ))}
        <div className="ml-auto flex items-center gap-2">
          <span className="text-slate-500">{tab === "nse" ? "NSE" : "US"}</span>
          <MarketBadge open={tab === "nse" ? (data?.nse_market?.market_open ?? false) : (data?.us_market?.market_open ?? false)} />
        </div>
      </div>

      {/* Table */}
      <div className="glass-card overflow-x-auto">
        <table className="w-full text-xs">
          <thead>
            <tr className="text-slate-500 border-b border-slate-800">
              <th className="px-2 py-2 text-center font-medium">#</th>
              <th className="px-2 py-2 text-left font-medium">Symbol</th>
              <th className="px-2 py-2 text-center font-medium">Tier</th>
              <th className="px-2 py-2 text-right font-medium">12-1M Mom</th>
              <th className="px-2 py-2 text-right font-medium">1M</th>
              <th className="px-2 py-2 text-right font-medium">3M</th>
              <th className="px-2 py-2 text-right font-medium">6M</th>
              <th className="px-2 py-2 text-right font-medium">12M</th>
              <th className="px-2 py-2 text-right font-medium">RSI</th>
              <th className="px-2 py-2 text-right font-medium">Sharpe</th>
              <th className="px-2 py-2 text-center font-medium">Sig</th>
            </tr>
          </thead>
          <tbody>
            {entries.map((e) => (
              <MomentumRow
                key={`${e.market}-${e.symbol}`}
                e={e}
                expanded={expandedRow === `${e.market}-${e.symbol}`}
                onToggle={() => setExpandedRow(expandedRow === `${e.market}-${e.symbol}` ? null : `${e.market}-${e.symbol}`)}
              />
            ))}
          </tbody>
        </table>
        {entries.length === 0 && (
          <div className="p-8 text-center text-slate-500 text-sm">No entries match this filter.</div>
        )}
      </div>
    </div>
  );
}
