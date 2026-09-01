"use client";

import { useState } from "react";
import useSWR from "swr";
import Link from "next/link";
import {
  fetchLongTermPicks,
  refreshLongTermPicks,
  type LongTermPicksResponse,
  type SectorPick,
  type LongTermPick,
} from "@/lib/api";

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function pct(v: number | null | undefined): string {
  if (v == null) return "—";
  return `${(v * 100).toFixed(1)}%`;
}

function fmtInr(v: number | null | undefined): string {
  if (v == null) return "—";
  if (v >= 1e7) return `₹${(v / 1e7).toFixed(1)}Cr`;
  if (v >= 1e5) return `₹${(v / 1e5).toFixed(1)}L`;
  return `₹${v.toFixed(0)}`;
}

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

const consensusColor: Record<string, string> = {
  BUY: "text-emerald-400 border-emerald-500/30 bg-emerald-500/10",
  ACCUMULATE: "text-sky-400 border-sky-500/30 bg-sky-500/10",
  HOLD: "text-amber-400 border-amber-500/30 bg-amber-500/10",
  REDUCE: "text-orange-400 border-orange-500/30 bg-orange-500/10",
  SELL: "text-rose-400 border-rose-500/30 bg-rose-500/10",
};

// ---------------------------------------------------------------------------
// 52-week range bar
// ---------------------------------------------------------------------------
function RangeBar({ position, high, low, price }: {
  position: number | null;
  high: number | null;
  low: number | null;
  price: number;
}) {
  if (position == null) return null;
  const pos = Math.min(Math.max(position * 100, 0), 100);
  const color = pos > 80 ? "bg-amber-400" : pos > 50 ? "bg-emerald-400" : "bg-sky-400";
  return (
    <div className="mt-2">
      <div className="flex justify-between text-[10px] text-slate-500 mb-1">
        <span>52w Low ₹{low?.toFixed(0) ?? "—"}</span>
        <span className="text-slate-300">₹{price.toFixed(2)}</span>
        <span>52w High ₹{high?.toFixed(0) ?? "—"}</span>
      </div>
      <div className="h-1.5 bg-slate-800 rounded-full overflow-hidden relative">
        <div className="absolute inset-0 rounded-full">
          <div
            className={`absolute h-full w-1 ${color} rounded-full`}
            style={{ left: `${pos}%` }}
          />
        </div>
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Metric cell
// ---------------------------------------------------------------------------
function Metric({ label, value, color }: { label: string; value: string; color?: string }) {
  return (
    <div className="text-center">
      <div className="text-[9px] uppercase tracking-wide text-slate-500">{label}</div>
      <div className={`text-sm font-semibold tabular-nums ${color || "text-slate-200"}`}>{value}</div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Stock card
// ---------------------------------------------------------------------------
function StockCard({ stock, rank, isRunnerUp }: { stock: LongTermPick; rank: number; isRunnerUp?: boolean }) {
  const consensus = stock.analyst_consensus;
  const changeColor = (stock.change_pct ?? 0) >= 0 ? "text-emerald-400" : "text-rose-400";

  return (
    <div className={`glass-card-hover p-5 ${isRunnerUp ? "opacity-80" : ""}`}>
      {/* Header */}
      <div className="flex items-start gap-3 mb-4">
        <div className="flex items-center justify-center w-9 h-9 rounded-full bg-slate-800 text-sm font-bold text-slate-300 shrink-0">
          #{rank}
        </div>
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 flex-wrap">
            <Link href={`/stock/${stock.symbol}`} className="font-bold text-slate-100 hover:text-emerald-400 transition-colors">
              {stock.symbol}
            </Link>
            {stock.grade && (
              <span className={`text-[10px] font-bold rounded border px-2 py-0.5 ${gradeColor[stock.grade] || ""}`}>
                {stock.grade}
              </span>
            )}
            {consensus && (
              <span className={`text-[10px] font-medium rounded border px-2 py-0.5 ${consensusColor[consensus] || ""}`}>
                {consensus}
              </span>
            )}
          </div>
          <p className="text-xs text-slate-500 truncate">{stock.name}</p>
          {stock.sector && <p className="text-[10px] text-slate-600 mt-0.5">{stock.sector}</p>}
        </div>
        <div className="text-right shrink-0">
          <div className="text-lg font-bold tabular-nums text-slate-100">₹{stock.last_price.toFixed(2)}</div>
          {stock.change_pct != null && (
            <div className={`text-xs font-medium tabular-nums ${changeColor}`}>
              {stock.change_pct >= 0 ? "+" : ""}{stock.change_pct.toFixed(2)}%
            </div>
          )}
        </div>
      </div>

      {/* Score bars */}
      <div className="space-y-1.5 mb-4">
        {[
          { label: "Quality", score: stock.quality, weight: 40 },
          { label: "Value", score: stock.value, weight: 30 },
          { label: "Momentum", score: stock.momentum, weight: 30 },
        ].map(({ label, score, weight }) => (
          <div key={label} className="flex items-center gap-2">
            <div className="w-24 text-[10px] text-slate-500 shrink-0">{label} ({weight}%)</div>
            <div className="flex-1 h-2 bg-slate-800 rounded-full overflow-hidden">
              <div
                className={`h-full rounded-full transition-all ${score >= 0.7 ? "bg-emerald-500" : score >= 0.5 ? "bg-amber-500" : "bg-red-500"}`}
                style={{ width: `${score * 100}%` }}
              />
            </div>
            <div className="w-8 text-right text-[10px] font-semibold text-slate-400 tabular-nums">{(score * 100).toFixed(0)}</div>
          </div>
        ))}
      </div>

      {/* Performance metrics */}
      <div className="grid grid-cols-4 gap-2 mb-4 bg-slate-800/30 rounded-lg p-3">
        <Metric label="Composite" value={`${(stock.composite * 100).toFixed(0)}`} color="text-emerald-400" />
        <Metric label="CAGR" value={pct(stock.cagr)} color={stock.cagr >= 0 ? "text-emerald-400" : "text-rose-400"} />
        <Metric label="Sharpe" value={stock.sharpe.toFixed(2)} color={stock.sharpe >= 1 ? "text-emerald-400" : "text-amber-400"} />
        <Metric label="Max DD" value={pct(stock.max_drawdown)} color="text-rose-400" />
      </div>

      {/* Fundamentals */}
      <div className="grid grid-cols-3 sm:grid-cols-6 gap-2 mb-4">
        <Metric label="P/E" value={stock.trailing_pe != null ? stock.trailing_pe.toFixed(1) : "—"} />
        <Metric label="ROE" value={stock.return_on_equity != null ? pct(stock.return_on_equity) : "—"} />
        <Metric label="D/E" value={stock.debt_to_equity != null ? stock.debt_to_equity.toFixed(2) : "—"} />
        <Metric label="Margin" value={stock.profit_margins != null ? pct(stock.profit_margins) : "—"} />
        <Metric label="Div Yield" value={stock.dividend_yield != null ? pct(stock.dividend_yield) : "—"} />
        <Metric label="Rev Growth" value={stock.revenue_growth != null ? pct(stock.revenue_growth) : "—"} />
      </div>

      {/* Entry / SL / Target */}
      <div className="grid grid-cols-4 gap-2 mb-3">
        <div className="bg-sky-500/10 rounded-lg px-2 py-1.5 text-center">
          <div className="text-[9px] uppercase tracking-wide text-sky-400/70">Entry</div>
          <div className="text-sm font-semibold tabular-nums text-sky-300">₹{stock.entry.toFixed(2)}</div>
        </div>
        <div className="bg-rose-500/10 rounded-lg px-2 py-1.5 text-center">
          <div className="text-[9px] uppercase tracking-wide text-rose-400/70">Stop Loss</div>
          <div className="text-sm font-semibold tabular-nums text-rose-300">₹{stock.stop_loss.toFixed(2)}</div>
        </div>
        <div className="bg-emerald-500/10 rounded-lg px-2 py-1.5 text-center">
          <div className="text-[9px] uppercase tracking-wide text-emerald-400/70">Target</div>
          <div className="text-sm font-semibold tabular-nums text-emerald-300">₹{stock.target.toFixed(2)}</div>
        </div>
        <div className="bg-slate-800/40 rounded-lg px-2 py-1.5 text-center">
          <div className="text-[9px] uppercase tracking-wide text-slate-500">R:R</div>
          <div className="text-sm font-semibold tabular-nums text-slate-200">1:{stock.risk_reward.toFixed(1)}</div>
        </div>
      </div>

      {/* 52w range */}
      <RangeBar position={stock.range_position} high={stock["52w_high"]} low={stock["52w_low"]} price={stock.last_price} />

      {/* Market cap + Beta */}
      <div className="flex items-center gap-4 mt-3 text-[10px] text-slate-500">
        {stock.market_cap != null && <span>Mkt Cap: <span className="text-slate-300">{fmtInr(stock.market_cap)}</span></span>}
        <span>Beta: <span className="text-slate-300">{stock.beta.toFixed(2)}</span></span>
        <span>Trend: <span className="text-slate-300">{stock.trend}</span></span>
      </div>

      {/* Summary */}
      <p className="text-xs text-slate-400 leading-relaxed mt-2">{stock.summary}</p>

      {isRunnerUp && (
        <p className="text-[10px] text-amber-400/60 mt-2">Alternative pick in this sector</p>
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Sector section
// ---------------------------------------------------------------------------
function SectorSection({ pick, rank }: { pick: SectorPick; rank: number }) {
  return (
    <div>
      <div className="flex items-center gap-2 mb-3">
        <span className="flex items-center justify-center w-6 h-6 rounded-full bg-slate-800 text-[10px] font-bold text-slate-400">
          {rank}
        </span>
        <h3 className="text-sm font-semibold text-slate-200">{pick.sector}</h3>
        <span className="text-[10px] text-slate-500">
          {pick.stock_count} stock{pick.stock_count > 1 ? "s" : ""} · avg score {(pick.avg_composite * 100).toFixed(0)}
        </span>
      </div>
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        <StockCard stock={pick.top_stock} rank={1} />
        {pick.runner_up && <StockCard stock={pick.runner_up} rank={2} isRunnerUp />}
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Main page
// ---------------------------------------------------------------------------
export default function LongTermPage() {
  const { data, isLoading, error, mutate } = useSWR<LongTermPicksResponse>(
    "long-term-picks",
    fetchLongTermPicks,
    { refreshInterval: 300000, keepPreviousData: true }
  );
  const [refreshing, setRefreshing] = useState(false);

  async function handleRefresh() {
    setRefreshing(true);
    try {
      await refreshLongTermPicks();
      await mutate();
    } catch {
      // ignore
    } finally {
      setRefreshing(false);
    }
  }

  if (isLoading) {
    return (
      <div className="max-w-6xl mx-auto px-4 py-8">
        <div className="glass-card p-8 text-center">
          <div className="shimmer h-5 w-48 rounded mx-auto mb-3" />
          <div className="shimmer h-3 w-full rounded mb-2" />
          <div className="shimmer h-3 w-2/3 rounded" />
          <p className="text-xs text-slate-500 mt-3">
            Scanning Nifty 100 with long-term quality/value/momentum scoring and grouping by sector…
          </p>
        </div>
      </div>
    );
  }

  if (error || !data) {
    return (
      <div className="max-w-6xl mx-auto px-4 py-8">
        <div className="glass-card p-8 text-center">
          <p className="text-sm text-red-400">Failed to load long-term picks.</p>
          <button onClick={() => mutate()} className="mt-3 text-xs text-emerald-400 hover:underline">Retry</button>
        </div>
      </div>
    );
  }

  const p = data.portfolio;

  return (
    <div className="max-w-6xl mx-auto px-4 py-6 space-y-6">
      {/* Header */}
      <div className="flex items-start justify-between flex-wrap gap-3">
        <div>
          <h1 className="text-2xl font-bold text-slate-100">Long-Term Investing</h1>
          <p className="text-xs text-slate-500 mt-1.5">
            Sector-diversified portfolio from Nifty 100 · Quality 40% / Value 30% / Momentum 30%
            {data.market_status && ` · ${data.market_status}`}
            {data.refreshed_at && ` · refreshed ${timeAgo(data.refreshed_at)}`}
          </p>
        </div>
        <button
          onClick={handleRefresh}
          disabled={refreshing}
          className="text-xs px-3 py-1.5 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-300 transition-colors disabled:opacity-50"
        >
          {refreshing ? "Refreshing..." : "Refresh"}
        </button>
      </div>

      {/* Portfolio summary */}
      <div className="glass-card p-4">
        <div className="grid grid-cols-2 sm:grid-cols-5 gap-3">
          <div className="text-center">
            <div className="text-2xl font-bold text-emerald-400 tabular-nums">{p.stock_count}</div>
            <div className="text-[10px] text-slate-500 uppercase">Stocks</div>
          </div>
          <div className="text-center">
            <div className="text-2xl font-bold text-slate-100 tabular-nums">{p.sectors.length}</div>
            <div className="text-[10px] text-slate-500 uppercase">Sectors</div>
          </div>
          <div className="text-center">
            <div className="text-2xl font-bold text-slate-100 tabular-nums">{(p.avg_composite * 100).toFixed(0)}</div>
            <div className="text-[10px] text-slate-500 uppercase">Avg Score</div>
          </div>
          <div className="text-center">
            <div className={`text-2xl font-bold tabular-nums ${p.avg_sharpe >= 1 ? "text-emerald-400" : "text-amber-400"}`}>
              {p.avg_sharpe.toFixed(2)}
            </div>
            <div className="text-[10px] text-slate-500 uppercase">Avg Sharpe</div>
          </div>
          <div className="text-center">
            <div className={`text-2xl font-bold tabular-nums ${p.avg_cagr >= 0 ? "text-emerald-400" : "text-rose-400"}`}>
              {p.avg_cagr >= 0 ? "+" : ""}{pct(p.avg_cagr)}
            </div>
            <div className="text-[10px] text-slate-500 uppercase">Avg CAGR</div>
          </div>
        </div>
        {/* Sectors covered */}
        <div className="mt-3 pt-3 border-t border-slate-800/50">
          <div className="flex flex-wrap gap-1.5">
            {p.sectors.map((s) => (
              <span key={s} className="text-[10px] font-medium rounded border px-2 py-0.5 border-slate-600/30 bg-slate-700/20 text-slate-300">
                {s}
              </span>
            ))}
          </div>
        </div>
      </div>

      {/* Sector picks */}
      {data.picks.length > 0 ? (
        <div className="space-y-6">
          {data.picks.map((pick, i) => (
            <SectorSection key={pick.sector} pick={pick} rank={i + 1} />
          ))}
        </div>
      ) : (
        <div className="glass-card p-6 text-center">
          <p className="text-sm text-slate-400">No stocks meet the long-term criteria today.</p>
          <p className="text-xs text-slate-500 mt-1">Try refreshing or check back later.</p>
        </div>
      )}

      {/* Footer */}
      <p className="text-xs text-slate-600 text-center">
        Long-term scoring: Quality 40% (ROE, margins, debt health) · Value 30% (P/E, P/B) · Momentum 30% (returns, EMA alignment, 52w range).
        Entry/SL/target from 50-EMA and 200-EMA levels. All trades are paper — not investment advice.
      </p>
    </div>
  );
}
