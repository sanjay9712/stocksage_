"use client";

import useSWR from "swr";
import { fetchDayStatus, fetchPicks, fetchMarketLive, triggerScan } from "@/lib/api";
import PicksTable from "@/components/PicksTable";
import StockSearch from "@/components/StockSearch";

export default function HomePage() {
  const { data: day, error: dayErr, mutate: mutateDay } = useSWR("day", fetchDayStatus, { refreshInterval: 10000, keepPreviousData: true });
  const { data: picks, error: picksErr, mutate: mutatePicks, isLoading } = useSWR("picks", fetchPicks, { refreshInterval: 10000, keepPreviousData: true });
  const { data: market, error: marketErr } = useSWR("market", fetchMarketLive, { refreshInterval: 1000, keepPreviousData: true });

  async function scan() {
    await triggerScan();
    await Promise.all([mutatePicks(), mutateDay()]);
  }

  const backendDown = !!dayErr && !!picksErr;

  if (backendDown) {
    return (
      <div className="glass-card p-8 text-center">
        <div className="text-rose-400 mb-3">
          <svg className="w-12 h-12 mx-auto opacity-50" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
            <path d="M10.29 3.86L1.82 18a2 2 0 001.71 3h16.94a2 2 0 001.71-3L13.71 3.86a2 2 0 00-3.42 0zM12 9v4M12 17h.01" />
          </svg>
        </div>
        <p className="text-rose-300 text-sm">Can&apos;t reach the backend on port 8000.</p>
        <button
          onClick={() => { mutateDay(); mutatePicks(); }}
          className="mt-3 rounded-lg bg-slate-800 hover:bg-slate-700 px-4 py-2 text-sm font-medium transition-colors"
        >
          Retry
        </button>
      </div>
    );
  }

  return (
    <div className="space-y-5">
      {/* Live NSE market status */}
      {market && (
        <div className="glass-card p-4 fade-in">
          <div className="flex items-center justify-between flex-wrap gap-2">
            <div className="flex items-center gap-2">
              <span className={`inline-block w-2.5 h-2.5 rounded-full ${market.status.market_open ? "bg-emerald-400 live-dot" : "bg-slate-600"}`} />
              <span className="text-sm font-semibold">
                NSE {market.status.market_open ? "Open" : "Closed"}
              </span>
              <span className="text-xs text-slate-400">{market.status.status_text}</span>
            </div>
            <span className="text-xs text-slate-600">
              {market.status.source} · {market.status.trade_date}
            </span>
            <span className="inline-flex items-center gap-1 text-[10px] font-semibold text-emerald-400">
              <span className="inline-block w-1.5 h-1.5 rounded-full bg-emerald-400 animate-pulse" />
              LIVE
            </span>
          </div>
          {market.indices.length > 0 && (
            <div className="grid grid-cols-3 sm:grid-cols-5 gap-2 mt-4">
              {market.indices.map((idx) => (
                <div key={idx.name} className="stat-box text-center">
                  <div className="text-[11px] text-slate-500 truncate">{idx.name}</div>
                  <div className="text-sm font-semibold tabular-nums text-slate-200">{idx.last?.toLocaleString()}</div>
                  <div className={`text-xs tabular-nums font-medium ${idx.pct_change >= 0 ? "text-emerald-400" : "text-rose-400"}`}>
                    {idx.pct_change >= 0 ? "▲" : "▼"} {Math.abs(idx.pct_change)?.toFixed(2)}%
                  </div>
                </div>
              ))}
            </div>
          )}
          {!market.status.market_open && (
            <p className="text-xs text-amber-300/70 mt-3">
              Market is closed. Index values are from the last trading session.
              New picks appear on the next trading day after 09:30 IST.
            </p>
          )}
        </div>
      )}

      {/* Stock search */}
      <StockSearch />

      {/* Picks section */}
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 className="text-lg font-semibold text-slate-100">Today&apos;s Picks</h1>
          <p className="text-xs text-slate-500 mt-0.5">
            {day ? (
              day.no_trade ? (
                <span className="text-amber-300">No-trade day: {day.reason}</span>
              ) : day.expiry_day ? (
                <span className="text-amber-300">Expiry day — higher gamma risk.</span>
              ) : day.market_open ? (
                <span>{day.picks_count} pick(s) · market open</span>
              ) : (
                <span className="text-slate-400">
                  Market closed — {day.picks_count} pick(s) from last scan.
                </span>
              )
            ) : (
              "Loading…"
            )}
          </p>
        </div>
        <button
          onClick={scan}
          className="flex items-center gap-2 rounded-lg bg-gradient-to-r from-emerald-600 to-teal-600 hover:from-emerald-500 hover:to-teal-500 px-4 py-2 text-sm font-medium shadow-lg shadow-emerald-900/20 transition-all"
        >
          <svg className="w-4 h-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <path d="M21 12a9 9 0 11-6.219-8.56" />
          </svg>
          Run scan now
        </button>
      </div>

      {isLoading ? (
        <div className="glass-card p-8 text-center">
          <div className="shimmer h-4 w-48 mx-auto rounded mb-3" />
          <div className="shimmer h-4 w-32 mx-auto rounded" />
          <p className="text-xs text-slate-500 mt-3">Loading picks…</p>
        </div>
      ) : (
        <PicksTable picks={picks || []} />
      )}

      <p className="text-xs text-slate-600 text-center">
        Strategy: Opening-Range Breakout (09:15–09:30 IST). Entry = OR-High · SL = OR-Low ·
        Targets = Entry + 1×/2× ATR(14). Click a pick for verifiable reasoning.
      </p>
    </div>
  );
}
