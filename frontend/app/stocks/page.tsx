"use client";

import { useState } from "react";
import useSWR from "swr";
import Link from "next/link";
import { fetchNseStockScreen, refreshNseStockScreen, type NseStockScreen } from "@/lib/api";
import StockSearch from "@/components/StockSearch";

function fmtInr(v: number | null | undefined): string {
  if (v == null) return "—";
  if (v >= 1e7) return `₹${(v / 1e7).toFixed(1)}Cr`;
  if (v >= 1e5) return `₹${(v / 1e5).toFixed(1)}L`;
  return `₹${v.toFixed(0)}`;
}

function pct(v: number) { return `${(v * 100).toFixed(1)}%`; }

function timeAgo(iso: string): string {
  const diff = Date.now() - new Date(iso).getTime();
  const min = Math.floor(diff / 60000);
  if (min < 1) return "just now";
  if (min < 60) return `${min} min ago`;
  const hr = Math.floor(min / 60);
  if (hr < 24) return `${hr} hr ago`;
  return `${Math.floor(hr / 24)} day(s) ago`;
}

const gradeColor: Record<string, string> = {
  "A+": "text-emerald-400 border-emerald-500/30 bg-emerald-500/10",
  A: "text-emerald-400 border-emerald-500/30 bg-emerald-500/10",
  B: "text-sky-400 border-sky-500/30 bg-sky-500/10",
  C: "text-amber-400 border-amber-500/30 bg-amber-500/10",
  D: "text-rose-400 border-rose-500/30 bg-rose-500/10",
};

export default function NseStocksPage() {
  const { data, isLoading, error, mutate } = useSWR("nse-stock-screen", fetchNseStockScreen, {
    refreshInterval: 300000,
    keepPreviousData: true,
  });
  const [refreshing, setRefreshing] = useState(false);
  const rows = data?.stocks || [];
  const marketOpen = data?.market_open ?? false;

  async function handleRefresh() {
    setRefreshing(true);
    try {
      await refreshNseStockScreen();
      await mutate();
    } finally {
      setRefreshing(false);
    }
  }

  return (
    <div className="space-y-5">
      <div className="flex items-center justify-between gap-3 flex-wrap">
        <div>
          <div className="flex items-center gap-2">
            <h1 className="text-lg font-semibold text-slate-100">NSE Stocks — Top Picks</h1>
            {data?.market_open != null && (
              <span className={`inline-flex items-center gap-1 text-[10px] font-semibold rounded-full border px-2 py-0.5 ${
                data.market_open
                  ? "text-emerald-400 border-emerald-500/30 bg-emerald-500/10"
                  : "text-slate-500 border-slate-600/30 bg-slate-700/20"
              }`}>
                {data.market_open && <span className="inline-block w-1.5 h-1.5 rounded-full bg-emerald-400 live-dot" />}
                {data.market_open ? "LIVE" : "CLOSED"}
              </span>
            )}
          </div>
          <p className="text-xs text-slate-400 mt-0.5">
            {data?.market_status ? `${data.market_status} · ` : ""}screened by momentum + quality + value · not advice
          </p>
          <p className="text-[10px] text-amber-400/60 mt-0.5">Stock prices via Yahoo Finance (~15 min delayed)</p>
        </div>
        <div className="flex items-center gap-3">
          {data?.refreshed_at && (
            <span className="text-xs text-slate-500">Updated: {timeAgo(data.refreshed_at)}</span>
          )}
          <button
            onClick={handleRefresh}
            disabled={refreshing}
            className="flex items-center gap-2 rounded-lg bg-slate-800 hover:bg-slate-700 disabled:opacity-40 px-3 py-1.5 text-xs font-medium transition-colors"
          >
            <svg className={`w-3.5 h-3.5 ${refreshing ? "animate-spin" : ""}`} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <path d="M21 12a9 9 011-6.219-8.56" />
            </svg>
            {refreshing ? "Refreshing…" : "Refresh"}
          </button>
        </div>
      </div>

      <StockSearch />

      {isLoading && (
        <div className="grid gap-3 sm:grid-cols-2">
          {[1, 2, 3, 4].map((i) => (
            <div key={i} className="glass-card p-4">
              <div className="shimmer h-5 w-32 rounded mb-3" />
              <div className="shimmer h-3 w-full rounded mb-2" />
              <div className="shimmer h-3 w-2/3 rounded" />
            </div>
          ))}
        </div>
      )}

      {error && (
        <div className="glass-card p-8 text-center">
          <p className="text-rose-300 text-sm">Failed to load screened stocks.</p>
          <button onClick={() => window.location.reload()} className="mt-3 rounded-lg bg-slate-800 hover:bg-slate-700 px-4 py-2 text-sm transition-colors">Retry</button>
        </div>
      )}

      {data && rows.length === 0 && (
        <div className="glass-card p-8 text-center">
          <p className="text-amber-300 text-sm">No stocks passed the investment screen right now.</p>
        </div>
      )}

      {data && rows.length > 0 && (
        <div>
          <h2 className="text-sm font-semibold text-slate-400 mb-3">{rows.length} stocks passed the screen</h2>
          <div className="grid gap-3 sm:grid-cols-2 fade-in">
            {rows.map((s: NseStockScreen, idx) => (
              <Link key={s.symbol} href={`/stock/${s.symbol}`} className="glass-card-hover p-4">
                <div className="flex items-start justify-between mb-3">
                  <div className="min-w-0">
                    <div className="flex items-center gap-2">
                      <span className="text-xs font-mono text-slate-500">#{idx + 1}</span>
                      <span className="font-semibold text-slate-100">{s.symbol}</span>
                      <span className={`text-[10px] font-bold rounded border px-1.5 py-0.5 ${gradeColor[s.grade] || gradeColor.D}`}>
                        {s.grade}
                      </span>
                      {s.sector && <span className="text-[10px] bg-slate-800 px-1.5 py-0.5 rounded text-slate-500">{s.sector}</span>}
                    </div>
                    <p className="text-xs text-slate-400 mt-0.5 truncate">{s.name}</p>
                  </div>
                  <div className="text-right shrink-0">
                    <div className="text-lg font-bold tabular-nums text-slate-100">₹{s.last_price.toFixed(2)}</div>
                    {s.change_pct != null && (
                      <div className={`text-xs font-medium tabular-nums ${s.change_pct >= 0 ? "text-emerald-400" : "text-rose-400"}`}>
                        {s.change_pct >= 0 ? "▲" : "▼"} {Math.abs(s.change_pct).toFixed(2)}%
                      </div>
                    )}
                    <div className="text-xs text-slate-400">{s.trend}</div>
                  </div>
                </div>

                <div className="grid grid-cols-4 gap-2 mb-3">
                  <div className="text-center">
                    <div className="text-[10px] text-slate-400 uppercase">Score</div>
                    <div className="text-sm font-semibold tabular-nums text-emerald-400">{Math.round(s.composite * 100)}%</div>
                  </div>
                  <div className="text-center">
                    <div className="text-[10px] text-slate-400 uppercase">CAGR</div>
                    <div className="text-sm font-semibold tabular-nums text-slate-200">{pct(s.cagr)}</div>
                  </div>
                  <div className="text-center">
                    <div className="text-[10px] text-slate-400 uppercase">Sharpe</div>
                    <div className="text-sm font-semibold tabular-nums text-sky-300">{s.sharpe.toFixed(2)}</div>
                  </div>
                  <div className="text-center">
                    <div className="text-[10px] text-slate-400 uppercase">MaxDD</div>
                    <div className="text-sm font-semibold tabular-nums text-rose-300">{pct(s.max_drawdown)}</div>
                  </div>
                </div>

                <div className="grid grid-cols-4 gap-2 mb-3">
                  <div className="text-center">
                    <div className="text-[10px] text-slate-400 uppercase">P/E</div>
                    <div className="text-sm font-medium tabular-nums text-slate-300">{s.trailing_pe?.toFixed(1) || "—"}</div>
                  </div>
                  <div className="text-center">
                    <div className="text-[10px] text-slate-400 uppercase">ROE</div>
                    <div className="text-sm font-medium tabular-nums text-slate-300">{s.return_on_equity != null ? pct(s.return_on_equity) : "—"}</div>
                  </div>
                  <div className="text-center">
                    <div className="text-[10px] text-slate-400 uppercase">RS vs NIFTY</div>
                    <div className={`text-sm font-semibold tabular-nums ${s.rs_score > 0 ? "text-emerald-400" : s.rs_score < 0 ? "text-rose-400" : "text-slate-400"}`}>
                      {s.rs_score > 0 ? "+" : ""}{(s.rs_score * 100).toFixed(1)}%
                    </div>
                  </div>
                  <div className="text-center">
                    <div className="text-[10px] text-slate-400 uppercase">Beta</div>
                    <div className="text-sm font-medium tabular-nums text-slate-300">{s.beta.toFixed(2)}</div>
                  </div>
                </div>

                <div className="grid grid-cols-3 gap-2 pt-2 border-t border-slate-800/50">
                  <div className="text-center">
                    <div className="text-[10px] text-slate-400 uppercase">Entry</div>
                    <div className="text-sm font-semibold tabular-nums text-sky-300">₹{s.entry.toFixed(2)}</div>
                  </div>
                  <div className="text-center">
                    <div className="text-[10px] text-slate-400 uppercase">Stop</div>
                    <div className="text-sm font-semibold tabular-nums text-rose-300">₹{s.stop_loss.toFixed(2)}</div>
                  </div>
                  <div className="text-center">
                    <div className="text-[10px] text-slate-400 uppercase">Target</div>
                    <div className="text-sm font-semibold tabular-nums text-emerald-300">₹{s.target.toFixed(2)}</div>
                  </div>
                </div>
                <p className="text-[10px] text-slate-500 mt-2 leading-relaxed">{s.summary}</p>
              </Link>
            ))}
          </div>
        </div>
      )}

      <p className="text-xs text-slate-600 text-center">
        Screened via multi-factor score (momentum 50% · quality 30% · value 20%). NSE data via yfinance (delayed ~15 min). Not investment advice.
      </p>
    </div>
  );
}
