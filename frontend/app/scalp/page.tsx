"use client";

import { useState } from "react";
import useSWR from "swr";
import Link from "next/link";
import { fetchScalping, type ScalpSignal, type ScalpNearMiss } from "@/lib/api";
import StockSearch from "@/components/StockSearch";
import { StrategyVerificationBadge } from "@/components/StrategyVerificationBadge";

export default function ScalpPage() {
  const { data, isLoading, mutate } = useSWR("scalping", fetchScalping, { refreshInterval: 300000, keepPreviousData: true });
  const signals = data?.signals || [];
  const summary = data?.scan_summary;
  const nearMisses = data?.near_misses || [];
  const [showNearMisses, setShowNearMisses] = useState(false);
  const [showFilters, setShowFilters] = useState(false);

  return (
    <div className="space-y-5">
      {/* Header */}
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 className="text-lg font-semibold text-slate-100">Scalping Signals</h1>
          <div className="mt-1.5">
            <StrategyVerificationBadge strategy="scalp" />
          </div>
          <p className="text-xs text-slate-500 mt-1.5">
            Candlestick pattern triggers with tight ATR stops. Fast in-and-out trades.
          </p>
        </div>
        <button
          onClick={() => mutate()}
          className="flex items-center gap-2 rounded-lg bg-gradient-to-r from-emerald-600 to-teal-600 hover:from-emerald-500 hover:to-teal-500 px-4 py-2 text-sm font-medium shadow-lg shadow-emerald-900/20 transition-all"
        >
          <svg className="w-4 h-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <path d="M21 12a9 9 0 11-6.219-8.56" />
          </svg>
          Refresh
        </button>
      </div>

      <StockSearch />

      {/* Scan Summary Banner */}
      {summary && (
        <div className="glass-card p-4">
          <div className="flex items-center justify-between flex-wrap gap-2">
            <div className="flex items-center gap-2">
              <svg className="w-5 h-5 text-emerald-400" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                <circle cx="11" cy="11" r="8" />
                <path d="M21 21l-4.35-4.35" />
              </svg>
              <span className="text-sm font-medium text-slate-200">Scan Summary</span>
            </div>
            <button
              onClick={() => setShowFilters(!showFilters)}
              className="text-xs text-emerald-400 hover:text-emerald-300 transition-colors"
            >
              {showFilters ? "Hide filters" : "Show filters & criteria"}
            </button>
          </div>
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 mt-3">
            <div className="text-center">
              <div className="text-xl font-bold tabular-nums text-slate-200">{summary.total_scanned}</div>
              <div className="text-[10px] uppercase tracking-wide text-slate-500">Stocks Scanned</div>
            </div>
            <div className="text-center">
              <div className="text-xl font-bold tabular-nums text-emerald-400">{summary.signals_found}</div>
              <div className="text-[10px] uppercase tracking-wide text-slate-500">Signals Found</div>
            </div>
            <div className="text-center">
              <div className="text-xl font-bold tabular-nums text-amber-400">{summary.near_misses}</div>
              <div className="text-[10px] uppercase tracking-wide text-slate-500">Near Misses</div>
            </div>
            <div className="text-center">
              <div className="text-xl font-bold tabular-nums text-slate-500">{summary.data_errors}</div>
              <div className="text-[10px] uppercase tracking-wide text-slate-500">Data Errors</div>
            </div>
          </div>

          {/* Filters & Criteria */}
          {showFilters && (
            <div className="mt-4 pt-3 border-t border-slate-800/50 space-y-2 fade-in">
              <div className="text-xs font-medium text-slate-300 mb-1">Patterns Scanned For ({summary.patterns_scanned.length}):</div>
              <div className="flex flex-wrap gap-1 mb-3">
                {summary.patterns_scanned.map((p, i) => (
                  <span key={i} className="text-[10px] text-slate-400 bg-slate-800/50 rounded px-1.5 py-0.5 border border-slate-700/30">
                    {p}
                  </span>
                ))}
              </div>
              <div className="text-xs font-medium text-slate-300 mb-1">Entry Filters:</div>
              <ul className="space-y-1">
                {summary.filters.map((f, i) => (
                  <li key={i} className="text-xs text-slate-400 pl-3 border-l-2 border-slate-700">
                    <span className="font-medium text-slate-300">{f.name}</span>
                    <span className="text-slate-500"> — {f.description}</span>
                  </li>
                ))}
              </ul>
            </div>
          )}
        </div>
      )}

      {/* Info banner */}
      <div className="glass-card p-3 border-emerald-800/20">
        <div className="flex items-start gap-2">
          <svg className="w-4 h-4 text-emerald-400 shrink-0 mt-0.5" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <path d="M12 2v4M12 18v4M4.93 4.93l2.83 2.83M16.24 16.24l2.83 2.83M2 12h4M18 12h4M4.93 19.07l2.83-2.83M16.24 7.76l2.83-2.83" />
          </svg>
          <p className="text-xs text-slate-400 leading-relaxed">
            Scalps fire when a <span className="text-emerald-400">directional candlestick pattern</span> aligns
            with the intraday trend (EMA-20) and volume is <span className="text-sky-400">&ge; 0.8&times;</span> average.
            Stop-loss = 1&times;ATR, target = 1.5&times;ATR, R:R &ge; 1.5. Exit within 30 min.
            Stochastic, MACD, and ADX act as confidence modifiers (not hard blocks).
          </p>
        </div>
      </div>

      {/* Signals grid */}
      {isLoading ? (
        <div className="glass-card p-8 text-center">
          <div className="shimmer h-4 w-48 mx-auto rounded mb-3" />
          <div className="shimmer h-4 w-32 mx-auto rounded" />
          <p className="text-xs text-slate-500 mt-3">Scanning universe for scalp signals…</p>
        </div>
      ) : signals.length === 0 ? (
        <div className="glass-card p-10 text-center">
          <div className="text-slate-500 mb-2">
            <svg className="w-12 h-12 mx-auto opacity-40" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
              <path d="M13 2L3 14h9l-1 8 10-12h-9l1-8z" />
            </svg>
          </div>
          <p className="text-slate-400 text-sm">No scalping signals right now.</p>
          <p className="text-slate-500 text-xs mt-1">
            Signals appear when candlestick patterns fire on high-volume bars. Try again in a few minutes.
          </p>
        </div>
      ) : (
        <div className="grid gap-3 sm:grid-cols-2 fade-in">
          {signals.map((s) => (
            <ScalpCard key={s.symbol} signal={s} />
          ))}
        </div>
      )}

      {/* Near-miss stocks */}
      {nearMisses.length > 0 && (
        <div className="glass-card p-4">
          <button
            onClick={() => setShowNearMisses(!showNearMisses)}
            className="flex items-center justify-between w-full"
          >
            <div className="flex items-center gap-2">
              <svg className="w-4 h-4 text-amber-400" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                <path d="M12 9v4M12 17h.01M10.29 3.86L1.82 18a2 2 0 001.71 3h16.94a2 2 0 001.71-3L13.71 3.86a2 2 0 00-3.42 0z" />
              </svg>
              <span className="text-sm font-medium text-slate-200">
                Near-Miss Stocks ({nearMisses.length})
              </span>
            </div>
            <span className="text-xs text-slate-500">{showNearMisses ? "Hide" : "Show"}</span>
          </button>
          <p className="text-xs text-slate-500 mt-1">
            These stocks had a directional candlestick pattern but didn&apos;t fully qualify. Shows what&apos;s being tested.
          </p>
          {showNearMisses && (
            <div className="mt-3 space-y-2 fade-in">
              {nearMisses.map((m) => (
                <NearMissCard key={m.symbol} miss={m} />
              ))}
            </div>
          )}
        </div>
      )}

      <p className="text-xs text-slate-600 text-center">
        Patterns based on Steve Nison&apos;s Japanese Candlestick Charting Techniques.
        Data delayed ~15 min via Yahoo Finance. Not investment advice.
      </p>
    </div>
  );
}

function sideBadge(side: string) {
  return side === "long"
    ? "bg-emerald-500/15 text-emerald-400 border-emerald-500/30"
    : "bg-rose-500/15 text-rose-400 border-rose-500/30";
}

function strengthBadge(strength: string) {
  if (strength === "strong") return "bg-amber-500/15 text-amber-400 border-amber-500/30";
  if (strength === "moderate") return "bg-sky-500/15 text-sky-400 border-sky-500/30";
  return "bg-slate-700/40 text-slate-400 border-slate-600/30";
}

function ScalpCard({ signal }: { signal: ScalpSignal }) {
  const [expanded, setExpanded] = useState(false);
  const confPct = Math.round(signal.confidence * 100);
  const isLong = signal.side === "long";

  return (
    <div className="glass-card-hover p-4">
      {/* Header */}
      <div className="flex items-start justify-between mb-3">
        <div>
          <div className="flex items-center gap-2">
            <Link href={`/stock/${signal.symbol}`} className="font-semibold text-slate-100 hover:text-emerald-400 transition-colors">
              {signal.symbol}
            </Link>
            <span className={`text-[10px] font-medium rounded border px-2 py-0.5 ${sideBadge(signal.side)}`}>
              {signal.side.toUpperCase()}
            </span>
          </div>
          <div className="flex items-center gap-1.5 mt-1">
            <span className="text-[10px] text-slate-400 uppercase tracking-wide">Trend</span>
            <span className={`text-xs font-medium ${isLong ? "text-emerald-400" : "text-rose-400"}`}>
              {signal.trend}
            </span>
          </div>
        </div>
        <div className="text-right">
          <div className="text-xs text-slate-500">Last</div>
          <div className="text-sm font-semibold tabular-nums text-slate-200">
            ₹{signal.last_price.toFixed(2)}
          </div>
        </div>
      </div>

      {/* Level pills */}
      <div className="grid grid-cols-3 gap-1 py-3 border-t border-b border-slate-800/50">
        <div className="flex flex-col items-center gap-0.5">
          <span className="text-[10px] uppercase tracking-wide text-slate-400">Entry</span>
          <span className="text-sm font-semibold tabular-nums text-sky-300">₹{signal.entry.toFixed(2)}</span>
        </div>
        <div className="flex flex-col items-center gap-0.5">
          <span className="text-[10px] uppercase tracking-wide text-slate-400">SL</span>
          <span className="text-sm font-semibold tabular-nums text-rose-300">₹{signal.stop_loss.toFixed(2)}</span>
        </div>
        <div className="flex flex-col items-center gap-0.5">
          <span className="text-[10px] uppercase tracking-wide text-slate-400">Target</span>
          <span className="text-sm font-semibold tabular-nums text-emerald-300">₹{signal.target.toFixed(2)}</span>
        </div>
      </div>

      {/* Pattern badges */}
      <div className="flex flex-wrap gap-1.5 mt-3">
        {signal.patterns.map((p, i) => (
          <span
            key={i}
            className={`text-[10px] font-medium rounded border px-1.5 py-0.5 ${strengthBadge(p.strength)} ${
              p.bias === "bullish" ? "" : p.bias === "bearish" ? "" : ""
            }`}
          >
            {p.name}
          </span>
        ))}
      </div>

      {/* Footer: confidence + R:R + volume */}
      <div className="flex items-center justify-between mt-3">
        <div className="flex items-center gap-2">
          <div className="h-1.5 w-20 bg-slate-800 rounded-full overflow-hidden">
            <div
              className="h-full rounded-full bg-gradient-to-r from-emerald-500 to-teal-400"
              style={{ width: `${confPct}%` }}
            />
          </div>
          <span className="text-xs text-slate-400 tabular-nums">{confPct}%</span>
        </div>
        <div className="flex items-center gap-3 text-xs">
          <span className="text-slate-500">
            R:R <span className="text-amber-300 font-medium tabular-nums">1:{signal.risk_reward}</span>
          </span>
          <span className="text-slate-500">
            Vol <span className="text-sky-400 font-medium tabular-nums">{signal.volume_ratio}x</span>
          </span>
        </div>
      </div>

      {/* Expand toggle */}
      <button
        onClick={() => setExpanded(!expanded)}
        className="mt-3 text-xs text-slate-500 hover:text-slate-300 transition-colors"
      >
        {expanded ? "Hide details" : "Show details"}
      </button>

      {expanded && (
        <div className="mt-2 space-y-2 fade-in">
          <p className="text-xs text-slate-300 leading-relaxed">{signal.explanation}</p>
          {signal.caveats.length > 0 && (
            <ul className="text-xs text-amber-300/70 list-disc list-inside space-y-0.5">
              {signal.caveats.map((c, i) => <li key={i}>{c}</li>)}
            </ul>
          )}
          {signal.patterns.map((p, i) => (
            <div key={i} className="text-xs text-slate-400 pl-2 border-l-2 border-slate-700">
              <span className="font-medium text-slate-300">{p.name}</span>
              {" — "}
              {p.description}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

function NearMissCard({ miss }: { miss: ScalpNearMiss }) {
  const d = miss.diagnostics;
  return (
    <div className="rounded-lg border border-slate-800/50 bg-slate-900/30 p-3">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <Link href={`/stock/${miss.symbol}`} className="text-sm font-medium text-slate-300 hover:text-emerald-400 transition-colors">
            {miss.symbol}
          </Link>
          <span className="text-[10px] text-slate-500">{miss.name}</span>
        </div>
        <span className="text-[10px] text-slate-600">₹{d?.last_close?.toFixed(2) || "—"}</span>
      </div>
      <p className="text-xs text-amber-400/60 mt-1">{miss.reason}</p>
      <div className="flex flex-wrap gap-2 mt-2 text-[10px] text-slate-500">
        {d?.trend && (
          <span className="bg-slate-800/40 rounded px-1.5 py-0.5">Trend: {d.trend}</span>
        )}
        {d?.volume_ratio !== undefined && (
          <span className="bg-slate-800/40 rounded px-1.5 py-0.5">Vol: {d.volume_ratio}x</span>
        )}
        {d?.adx !== undefined && d.adx > 0 && (
          <span className="bg-slate-800/40 rounded px-1.5 py-0.5">ADX: {d.adx}</span>
        )}
        {d?.directional_patterns && d.directional_patterns.length > 0 && (
          <span className="bg-slate-800/40 rounded px-1.5 py-0.5">
            Patterns: {d.directional_patterns.join(", ")}
          </span>
        )}
      </div>
    </div>
  );
}
