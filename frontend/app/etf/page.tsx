"use client";

import { useState } from "react";
import useSWR from "swr";
import Link from "next/link";
import { fetchEtfScreen } from "@/lib/api";
import StockSearch from "@/components/StockSearch";

const riskColor: Record<string, string> = {
  low: "bg-emerald-500/15 text-emerald-400 border-emerald-500/30",
  moderate: "bg-amber-500/15 text-amber-400 border-amber-500/30",
  high: "bg-rose-500/15 text-rose-400 border-rose-500/30",
  unknown: "bg-slate-500/15 text-slate-400 border-slate-500/30",
};

function pct(v: number) { return `${(v * 100).toFixed(1)}%`; }

function MetricBar({ value, max, color }: { value: number; max: number; color: string }) {
  const w = Math.min(100, Math.max(0, (Math.abs(value) / max) * 100));
  return (
    <div className="h-1.5 w-full bg-slate-800 rounded-full overflow-hidden">
      <div className={`h-full rounded-full ${color}`} style={{ width: `${w}%` }} />
    </div>
  );
}

export default function EtfPage() {
  const { data, isLoading, error } = useSWR("etf", fetchEtfScreen, { refreshInterval: 300000, keepPreviousData: true });
  const [expanded, setExpanded] = useState<string | null>(null);

  if (isLoading) {
    return (
      <div className="space-y-4">
        <PageHeader />
        <StockSearch />
        <div className="grid gap-3 sm:grid-cols-2">
          {[1, 2, 3, 4].map((i) => (
            <div key={i} className="glass-card p-4">
              <div className="shimmer h-5 w-32 rounded mb-3" />
              <div className="shimmer h-3 w-full rounded mb-2" />
              <div className="shimmer h-3 w-2/3 rounded" />
            </div>
          ))}
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="space-y-4">
        <PageHeader />
        <StockSearch />
        <div className="glass-card p-8 text-center">
          <p className="text-rose-300 text-sm">Failed to load ETF data (yfinance may be throttling).</p>
          <button onClick={() => window.location.reload()} className="mt-3 rounded-lg bg-slate-800 hover:bg-slate-700 px-4 py-2 text-sm transition-colors">Retry</button>
        </div>
      </div>
    );
  }

  const rows = data || [];

  return (
    <div className="space-y-5">
      <PageHeader />

      <StockSearch />

      {/* Card grid */}
      <div className="grid gap-3 sm:grid-cols-2 fade-in">
        {rows.map((e, idx) => (
          <div
            key={e.symbol}
            className="glass-card-hover p-4 cursor-pointer"
            onClick={() => setExpanded(expanded === e.symbol ? null : e.symbol)}
          >
            {/* Header */}
            <div className="flex items-start justify-between mb-3">
              <div>
                <div className="flex items-center gap-2">
                  <span className="text-xs font-mono text-slate-500">#{idx + 1}</span>
                  <span className="font-semibold text-slate-100">{e.symbol}</span>
                  <span className={`text-[10px] uppercase rounded border px-1.5 py-0.5 ${riskColor[e.risk_level]}`}>
                    {e.risk_level}
                  </span>
                </div>
                <p className="text-xs text-slate-400 mt-0.5">{e.name}</p>
              </div>
              <div className="text-right">
                <div className="text-lg font-bold tabular-nums text-slate-100">₹{e.last_price.toFixed(2)}</div>
                {e.change_pct != null && (
                  <div className={`text-xs font-medium tabular-nums ${e.change_pct >= 0 ? "text-emerald-400" : "text-rose-400"}`}>
                    {e.change_pct >= 0 ? "▲" : "▼"} {Math.abs(e.change_pct).toFixed(2)}%
                  </div>
                )}
                <div className="text-[10px] text-slate-500 mt-0.5">Sharpe {e.sharpe.toFixed(2)}</div>
              </div>
            </div>

            {/* Metrics row */}
            <div className="grid grid-cols-4 gap-2 mb-3">
              <div className="text-center">
                <div className="text-[10px] text-slate-400 uppercase">CAGR</div>
                <div className="text-sm font-semibold tabular-nums text-slate-200">{pct(e.cagr)}</div>
              </div>
              <div className="text-center">
                <div className="text-[10px] text-slate-400 uppercase">Vol</div>
                <div className="text-sm font-semibold tabular-nums text-slate-300">{pct(e.volatility)}</div>
              </div>
              <div className="text-center">
                <div className="text-[10px] text-slate-400 uppercase">MaxDD</div>
                <div className="text-sm font-semibold tabular-nums text-rose-300">{pct(e.max_drawdown)}</div>
              </div>
              <div className="text-center">
                <div className="text-[10px] text-slate-400 uppercase">Horizon</div>
                <div className="text-sm font-medium text-slate-300">{e.suggested_horizon}</div>
              </div>
            </div>

            {/* Volatility bar */}
            <MetricBar value={e.volatility} max={0.5} color="bg-amber-500/60" />

            {/* Expandable detail */}
            {expanded === e.symbol && (
              <div className="mt-3 pt-3 border-t border-slate-800/50 space-y-2 fade-in">
                <p className="text-xs text-slate-300">{e.verdict}</p>
                {e.risks.length > 0 && (
                  <ul className="text-xs text-amber-300/80 list-disc list-inside space-y-0.5">
                    {e.risks.map((r, i) => <li key={i}>{r}</li>)}
                  </ul>
                )}
                <Link
                  href={`/etf/${e.symbol}`}
                  className="inline-block text-xs text-sky-400 hover:text-sky-300 mt-1"
                  onClick={(ev) => ev.stopPropagation()}
                >
                  View full details →
                </Link>
              </div>
            )}
          </div>
        ))}
      </div>
    </div>
  );
}

function PageHeader() {
  return (
    <div>
      <h1 className="text-lg font-semibold text-slate-100">ETF Invest Screener</h1>
      <p className="text-xs text-slate-400 mt-0.5">~2-year risk/return metrics · sorted by Sharpe (risk-adjusted) · not advice</p>
    </div>
  );
}
