"use client";

import { useState } from "react";
import useSWR from "swr";
import Link from "next/link";
import {
  fetchVwapSignals,
  fetchBollingerSignals,
  fetchPpoSignals,
  fetchMaTrendSignals,
  fetchGapAndGoSignals,
  fetchSrReversalSignals,
  fetchMomentumBreakoutSignals,
  fetchAbcdSignals,
  fetchGlossary,
  fetchPaperSignals,
  fetchPaperStats,
  fetchPaperHistory,
  paperScan,
  paperAutoResolve,
  paperExpire,
  resolvePaperSignal,
  type StrategySignal,
  type PaperTrade,
  type PaperTradeStats,
  type PaperDayHistory,
} from "@/lib/api";
import { useAuthContext } from "@/lib/auth-context";

type Tab = "vwap" | "bollinger" | "ppo" | "ma_trend" | "gap_go" | "sr_reversal" | "momentum_breakout" | "abcd" | "paper";

export default function AdvancedPage() {
  const [tab, setTab] = useState<Tab>("vwap");
  const { user } = useAuthContext();
  const isGuest = user?.is_guest ?? false;

  const tabs: [Tab, string][] = [
    ["vwap", "VWAP Pullback"],
    ["bollinger", "Bollinger Squeeze"],
    ["ppo", "PPO Momentum"],
    ["ma_trend", "MA Trend Scalp"],
    ["gap_go", "Gap-and-Go"],
    ["sr_reversal", "S/R Reversal"],
    ["momentum_breakout", "Momentum Breakout"],
    ["abcd", "ABCD Pattern"],
    ...(isGuest ? [] : [["paper", "Paper Trading"]] as [Tab, string][]),
  ];

  return (
    <div className="space-y-5">
      {/* Header */}
      <div>
        <h1 className="text-lg font-semibold text-slate-100">Advanced Strategies</h1>
        <p className="text-xs text-slate-500 mt-0.5">
          8 intraday strategies — VWAP pullback, Bollinger squeeze, PPO momentum, MA Trend Scalp, Gap-and-Go, S/R Reversal, Momentum Breakout, and ABCD Pattern — with plain-English explanations for beginners.
        </p>
      </div>

      {/* Tab bar */}
      <div className="flex items-center gap-1 border-b border-slate-800/60">
        {tabs.map(([key, label]) => (
          <button
            key={key}
            onClick={() => setTab(key)}
            className={`px-4 py-2 text-sm font-medium border-b-2 transition-colors ${
              tab === key
                ? "border-emerald-500 text-emerald-400"
                : "border-transparent text-slate-400 hover:text-slate-200"
            }`}
          >
            {label}
          </button>
        ))}
        {isGuest && (
          <span className="px-4 py-2 text-xs text-amber-400/70 border-b-2 border-transparent">
            Paper Trading requires an account —{" "}
            <Link href="/login?reason=guest" className="underline hover:text-amber-400">login</Link>
          </span>
        )}
      </div>

      {tab === "vwap" && <StrategyTab strategy="vwap" fetcher={fetchVwapSignals} />}
      {tab === "bollinger" && <StrategyTab strategy="bollinger" fetcher={fetchBollingerSignals} />}
      {tab === "ppo" && <StrategyTab strategy="ppo" fetcher={fetchPpoSignals} />}
      {tab === "ma_trend" && <StrategyTab strategy="ma_trend" fetcher={fetchMaTrendSignals} />}
      {tab === "gap_go" && <StrategyTab strategy="gap_go" fetcher={fetchGapAndGoSignals} />}
      {tab === "sr_reversal" && <StrategyTab strategy="sr_reversal" fetcher={fetchSrReversalSignals} />}
      {tab === "momentum_breakout" && <StrategyTab strategy="momentum_breakout" fetcher={fetchMomentumBreakoutSignals} />}
      {tab === "abcd" && <StrategyTab strategy="abcd" fetcher={fetchAbcdSignals} />}
      {tab === "paper" && !isGuest && <PaperTradeTab />}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Strategy tab (shared for VWAP, Bollinger, PPO)
// ---------------------------------------------------------------------------

function StrategyTab({
  strategy,
  fetcher,
}: {
  strategy: string;
  fetcher: () => Promise<{ signals: StrategySignal[]; count: number; glossary?: Record<string, string> }>;
}) {
  const { data, isLoading, mutate } = useSWR(`strategies-${strategy}`, fetcher, {
    refreshInterval: 300000,
    keepPreviousData: true,
  });
  const signals = data?.signals || [];
  const loading = isLoading && !data;

  return (
    <div className="space-y-4">
      {/* Strategy description */}
      <div className="glass-card p-3 border-emerald-800/20">
        <p className="text-xs text-slate-400 leading-relaxed">
          {strategy === "vwap" && (
            <>
              Entry when price pulls back to the <span className="text-emerald-400">9 EMA</span> in an uptrend
              (above <span className="text-sky-400">VWAP</span>), then bounces with volume. Stop below pullback low,
              target at VWAP and 1.5R.
            </>
          )}
          {strategy === "bollinger" && (
            <>
              Entry when price breaks out of a <span className="text-emerald-400">Bollinger Band squeeze</span> (low
              volatility compression) on volume. Stop at the 20-SMA mid-band, target at 1.5R.
            </>
          )}
          {strategy === "ppo" && (
            <>
              Entry on a fresh <span className="text-emerald-400">PPO signal-line cross</span> above zero (bullish
              momentum accelerating). Stop at recent swing low, target at 1.5R.
            </>
          )}
          {strategy === "ma_trend" && (
            <>
              Entry when the <span className="text-emerald-400">9-EMA crosses the 21-EMA</span> in the direction of the
              50-EMA trend. Stop below recent swing low, target at 1.5R. A pure mechanical EMA crossover system.
            </>
          )}
          {strategy === "gap_go" && (
            <>
              Entry when a stock <span className="text-emerald-400">gaps &gt;2% at the open</span> with volume &gt;2x average,
              then breaks out of the 15-min opening range. Stop at OR low, T1 at previous close (gap fill), T2 at 2R.
            </>
          )}
          {strategy === "sr_reversal" && (
            <>
              Entry when a <span className="text-emerald-400">reversal candlestick pattern</span> fires at a key
              support/resistance level (PDL, pivot S1/R1, Fib 61.8%). Stop 0.5 ATR beyond the level, T1 at pivot, T2
              at next S/R.
            </>
          )}
          {strategy === "momentum_breakout" && (
            <>
              Entry when price breaks the 15-min opening range on volume &gt;1.5x with <span className="text-emerald-400">RSI
              momentum confirmation</span> (RSI &gt;60 long, &lt;40 short). T1 at volume-profile POC, T2 at VAH/VAL or 2R.
            </>
          )}
          {strategy === "abcd" && (
            <>
              Entry at point C of an <span className="text-emerald-400">ABCD swing pattern</span> where C retraces
              38.2%–61.8% of AB. Stop below C, target at projected point D = C + (B − A). Based on Fibonacci
              measured-move geometry.
            </>
          )}
        </p>
      </div>

      {/* Refresh button */}
      <div className="flex justify-end">
        <button
          onClick={() => mutate()}
          className="flex items-center gap-2 rounded-lg bg-gradient-to-r from-emerald-600 to-teal-600 hover:from-emerald-500 hover:to-teal-500 px-3 py-1.5 text-xs font-medium shadow-lg shadow-emerald-900/20 transition-all"
        >
          <svg className="w-3.5 h-3.5" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <path d="M21 12a9 9 0 11-6.219-8.56" />
          </svg>
          Refresh
        </button>
      </div>

      {/* Signals */}
      {loading ? (
        <div className="glass-card p-8 text-center">
          <div className="shimmer h-4 w-48 mx-auto rounded mb-3" />
          <div className="shimmer h-4 w-32 mx-auto rounded" />
          <p className="text-xs text-slate-500 mt-3">Scanning universe for {strategy} signals…</p>
        </div>
      ) : signals.length === 0 ? (
        <div className="glass-card p-10 text-center">
          <div className="text-slate-500 mb-2">
            <svg className="w-12 h-12 mx-auto opacity-40" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
              <path d="M12 2L2 7l10 5 10-5-10-5zM2 17l10 5 10-5M2 12l10 5 10-5" />
            </svg>
          </div>
          <p className="text-slate-400 text-sm">No {strategy} signals right now.</p>
          <p className="text-slate-500 text-xs mt-1">
            Signals appear during market hours when conditions are met. Try again in a few minutes.
          </p>
        </div>
      ) : (
        <div className="grid gap-3 sm:grid-cols-2 fade-in">
          {signals.map((s) => (
            <SignalCard key={s.symbol} signal={s} glossary={data?.glossary} />
          ))}
        </div>
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Signal card (shared)
// ---------------------------------------------------------------------------

function SignalCard({ signal, glossary }: { signal: StrategySignal; glossary?: Record<string, string> }) {
  const [expanded, setExpanded] = useState(false);
  const confPct = Math.round(signal.confidence * 100);
  const isLong = signal.side === "long";
  const target = signal.target ?? signal.target1 ?? 0;

  return (
    <div className="glass-card-hover p-4">
      {/* Header */}
      <div className="flex items-start justify-between mb-3">
        <div>
          <div className="flex items-center gap-2">
            <Link href={`/stock/${signal.symbol}`} className="font-semibold text-slate-100 hover:text-emerald-400 transition-colors">
              {signal.symbol}
            </Link>
            <span className={`text-[10px] font-medium rounded border px-2 py-0.5 ${
              isLong
                ? "bg-emerald-500/15 text-emerald-400 border-emerald-500/30"
                : "bg-rose-500/15 text-rose-400 border-rose-500/30"
            }`}>
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
          <span className="text-sm font-semibold tabular-nums text-emerald-300">₹{target.toFixed(2)}</span>
        </div>
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
          {glossary && (
            <details className="mt-2">
              <summary className="text-xs text-emerald-400 cursor-pointer hover:text-emerald-300">
                Glossary (term definitions)
              </summary>
              <dl className="mt-2 space-y-1 pl-2">
                {Object.entries(glossary).map(([term, def]) => (
                  <div key={term} className="text-xs">
                    <dt className="inline font-medium text-slate-300">{term}</dt>
                    {" — "}
                    <dd className="inline text-slate-500">{def}</dd>
                  </div>
                ))}
              </dl>
            </details>
          )}
        </div>
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Paper trading tab — full implementation
// ---------------------------------------------------------------------------

type PaperFilter = "all" | "open" | "resolved";
type PaperMarket = "nse" | "us";

function PaperTradeTab() {
  const [market, setMarket] = useState<PaperMarket>("nse");
  const cur = market === "us" ? "$" : "₹";
  const { data: statsData, mutate: mutateStats } = useSWR(["paper-stats", market], () => fetchPaperStats(market), { refreshInterval: 60000, keepPreviousData: true });
  const { data: historyData } = useSWR(["paper-history", market], () => fetchPaperHistory(market), { refreshInterval: 300000, keepPreviousData: true });
  const [filter, setFilter] = useState<PaperFilter>("all");
  const { data: signalsData, isLoading, mutate: mutateSignals } = useSWR(
    ["paper-signals", filter, market],
    ([, f, m]) => fetchPaperSignals(undefined, f === "all" ? undefined : f === "open" ? "open" : undefined, m),
    { refreshInterval: 300000, keepPreviousData: true }
  );
  const [scanning, setScanning] = useState(false);
  const [resolving, setResolving] = useState(false);
  const [expiring, setExpiring] = useState(false);
  const [scanResult, setScanResult] = useState<string | null>(null);

  const signals = signalsData?.signals || [];
  const stats = statsData;
  const history = historyData?.history || [];

  const refreshAll = async () => {
    await Promise.all([mutateStats(), mutateSignals()]);
  };

  const handleScan = async () => {
    setScanning(true);
    setScanResult(null);
    try {
      const result = await paperScan(market);
      setScanResult(`Logged ${result.new_signals} new signals, auto-resolved ${result.resolved} trades.`);
      await refreshAll();
    } catch {
      setScanResult("Scan failed. Try again.");
    } finally {
      setScanning(false);
    }
  };

  const handleAutoResolve = async () => {
    setResolving(true);
    try {
      const result = await paperAutoResolve();
      setScanResult(`Auto-resolved ${result.resolved} trades against current prices.`);
      await refreshAll();
    } catch {
      setScanResult("Auto-resolve failed.");
    } finally {
      setResolving(false);
    }
  };

  const handleExpire = async () => {
    setExpiring(true);
    try {
      const result = await paperExpire();
      setScanResult(`Expired ${result.expired} open trades at current prices.`);
      await refreshAll();
    } catch {
      setScanResult("Expire failed.");
    } finally {
      setExpiring(false);
    }
  };

  return (
    <div className="space-y-4">
      {/* Info banner */}
      <div className="glass-card p-3 border-emerald-800/20">
        <div className="flex items-start gap-2">
          <svg className="w-4 h-4 text-emerald-400 shrink-0 mt-0.5" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <path d="M9 12l2 2 4-4M12 2a10 10 0 100 20 10 10 0 000-20z" />
          </svg>
          <p className="text-xs text-slate-400 leading-relaxed">
            <span className="text-emerald-400">Paper trading</span> logs strategy signals, auto-resolves trades when
            target or stop-loss is hit, and tracks hypothetical P&L. No real orders. During market hours, the
            scheduler auto-resolves every 10 min.
          </p>
        </div>
      </div>

      {/* Market toggle */}
      <div className="flex items-center gap-1">
        {(["nse", "us"] as PaperMarket[]).map((m) => (
          <button
            key={m}
            onClick={() => setMarket(m)}
            className={`px-4 py-1.5 text-sm font-medium rounded-lg transition-colors ${
              market === m
                ? "bg-emerald-500/15 text-emerald-400 border border-emerald-500/30"
                : "text-slate-400 hover:text-slate-200 border border-transparent"
            }`}
          >
            {m === "nse" ? "India · NSE" : "US Markets"}
          </button>
        ))}
      </div>

      {/* Portfolio summary */}
      {stats && (
        <div className="glass-card p-4">
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
            <div>
              <div className="text-[10px] uppercase tracking-wide text-slate-500">Capital</div>
              <div className="text-lg font-bold text-slate-200 tabular-nums">
                {market === "nse"
                  ? `${cur}${(stats.capital / 100000).toFixed(0)}L`
                  : `${cur}${(stats.capital / 1000).toFixed(0)}K`}
              </div>
            </div>
            <div>
              <div className="text-[10px] uppercase tracking-wide text-slate-500">Per Trade</div>
              <div className="text-lg font-bold text-slate-200 tabular-nums">
                {market === "nse"
                  ? `${cur}${(stats.position_size / 1000).toFixed(0)}K`
                  : `${cur}${(stats.position_size / 1000).toFixed(0)}K`}
              </div>
            </div>
            <div>
              <div className="text-[10px] uppercase tracking-wide text-slate-500">P&L ({cur})</div>
              <div className={`text-lg font-bold tabular-nums ${stats.total_pnl_rupees >= 0 ? "text-emerald-400" : "text-rose-400"}`}>
                {stats.total_pnl_rupees >= 0 ? "+" : ""}{cur}{stats.total_pnl_rupees.toLocaleString("en-IN", { maximumFractionDigits: 0 })}
              </div>
            </div>
            <div>
              <div className="text-[10px] uppercase tracking-wide text-slate-500">Portfolio</div>
              <div className="text-lg font-bold text-slate-200 tabular-nums">{cur}{stats.portfolio_value.toLocaleString("en-IN", { maximumFractionDigits: 0 })}</div>
            </div>
          </div>
        </div>
      )}

      {/* Stats grid */}
      {stats && (
        <>
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-2">
            <StatCard label="Total" value={stats.total_signals.toString()} />
            <StatCard label="Open" value={stats.open.toString()} accent={stats.open > 0 ? "neutral" : undefined} />
            <StatCard label="Win Rate" value={`${stats.win_rate}%`} accent={stats.win_rate >= 50 ? "good" : "bad"} />
            <StatCard label="Total P&L" value={`${stats.total_pnl_pct}%`} accent={stats.total_pnl_pct >= 0 ? "good" : "bad"} />
          </div>

          {/* Per-strategy breakdown */}
          {Object.keys(stats.by_strategy).length > 0 && (
            <div className="glass-card p-3">
              <h3 className="text-xs font-semibold text-slate-400 uppercase tracking-wide mb-2">Per-Strategy Breakdown</h3>
              <div className="grid grid-cols-1 sm:grid-cols-3 gap-2">
                {Object.entries(stats.by_strategy).map(([name, s]) => (
                  <div key={name} className="bg-slate-800/40 rounded-lg p-2 border border-slate-700/30">
                    <div className="flex items-center justify-between mb-1">
                      <span className="text-xs font-medium text-slate-300 capitalize">{name}</span>
                      <span className="text-[10px] text-slate-500">{s.count} total</span>
                    </div>
                    <div className="flex items-center gap-3 text-[11px] tabular-nums">
                      <span className="text-slate-400">Open: <span className="text-sky-300">{s.open}</span></span>
                      <span className="text-slate-400">W: <span className="text-emerald-400">{s.wins}</span></span>
                      <span className="text-slate-400">L: <span className="text-rose-400">{s.losses}</span></span>
                    </div>
                    {(s.wins + s.losses) > 0 && (
                      <div className="mt-1 text-[11px]">
                        <span className="text-slate-500">Win rate: </span>
                        <span className={`font-medium ${s.win_rate >= 50 ? "text-emerald-400" : "text-rose-400"}`}>
                          {s.win_rate}%
                        </span>
                        <span className="text-slate-500"> · Avg: </span>
                        <span className={s.avg_pnl >= 0 ? "text-emerald-400" : "text-rose-400"}>
                          {s.avg_pnl >= 0 ? "+" : ""}{s.avg_pnl}%
                        </span>
                      </div>
                    )}
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Additional stats */}
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-2">
            <StatCard label="Resolved" value={stats.resolved.toString()} />
            <StatCard label="Wins" value={stats.wins.toString()} accent="good" />
            <StatCard label="Losses" value={stats.losses.toString()} accent="bad" />
            <StatCard label="Avg P&L" value={`${stats.avg_pnl_pct}%`} accent={stats.avg_pnl_pct >= 0 ? "good" : "bad"} />
          </div>

          {/* Best/Worst */}
          {stats.best_trade_pct !== null && stats.worst_trade_pct !== null && (
            <div className="grid grid-cols-2 gap-2">
              <StatCard label="Best Trade" value={`+${stats.best_trade_pct}%`} accent="good" />
              <StatCard label="Worst Trade" value={`${stats.worst_trade_pct}%`} accent="bad" />
            </div>
          )}
        </>
      )}

      {/* Daily history */}
      {history.length > 0 && (
        <div className="glass-card p-3">
          <h3 className="text-xs font-semibold text-slate-400 uppercase tracking-wide mb-2">Daily P&L History</h3>
          <div className="space-y-1 max-h-40 overflow-y-auto">
            {history.map((day) => (
              <div key={day.date} className="flex items-center justify-between text-xs py-1 border-b border-slate-800/30 last:border-0">
                <span className="text-slate-400 tabular-nums">{day.date}</span>
                <div className="flex items-center gap-3 tabular-nums">
                  <span className="text-slate-500">{day.total_signals} signals</span>
                  <span className="text-slate-500">{day.resolved} resolved</span>
                  <span className={day.pnl_pct >= 0 ? "text-emerald-400" : "text-rose-400"}>
                    {day.pnl_pct >= 0 ? "+" : ""}{day.pnl_pct}%
                  </span>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Action buttons */}
      <div className="flex flex-wrap items-center gap-2">
        <button
          onClick={handleScan}
          disabled={scanning}
          className="flex items-center gap-2 rounded-lg bg-gradient-to-r from-emerald-600 to-teal-600 hover:from-emerald-500 hover:to-teal-500 px-4 py-2 text-sm font-medium shadow-lg shadow-emerald-900/20 transition-all disabled:opacity-50"
        >
          <svg className="w-4 h-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <path d="M21 12a9 9 0 11-6.219-8.56" />
          </svg>
          {scanning ? "Scanning…" : "Scan & Log"}
        </button>
        <button
          onClick={handleAutoResolve}
          disabled={resolving}
          className="flex items-center gap-2 rounded-lg bg-slate-700 hover:bg-slate-600 px-3 py-2 text-xs font-medium transition-all disabled:opacity-50"
        >
          <svg className="w-3.5 h-3.5" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <path d="M9 12l2 2 4-4" />
            <circle cx="12" cy="12" r="10" />
          </svg>
          {resolving ? "Resolving…" : "Auto-Resolve"}
        </button>
        <button
          onClick={handleExpire}
          disabled={expiring}
          className="flex items-center gap-2 rounded-lg bg-slate-700 hover:bg-slate-600 px-3 py-2 text-xs font-medium transition-all disabled:opacity-50"
        >
          <svg className="w-3.5 h-3.5" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <path d="M12 9v2m0 4h.01M5 12a7 7 0 100-14 7 7 0 000 14z" />
          </svg>
          {expiring ? "Expiring…" : "Expire All (EOD)"}
        </button>
      </div>

      {/* Scan result message */}
      {scanResult && (
        <div className="glass-card p-2 border-emerald-800/20 fade-in">
          <p className="text-xs text-slate-400">{scanResult}</p>
        </div>
      )}

      {/* Filter tabs */}
      <div className="flex items-center gap-1">
        {(["all", "open", "resolved"] as PaperFilter[]).map((f) => (
          <button
            key={f}
            onClick={() => setFilter(f)}
            className={`px-3 py-1.5 text-xs font-medium rounded-lg transition-colors ${
              filter === f
                ? "bg-emerald-500/15 text-emerald-400 border border-emerald-500/30"
                : "text-slate-400 hover:text-slate-200 border border-transparent"
            }`}
          >
            {f === "all" ? "All" : f === "open" ? "Open" : "Resolved"}
          </button>
        ))}
      </div>

      {/* Signal list */}
      {isLoading ? (
        <div className="glass-card p-8 text-center">
          <div className="shimmer h-4 w-48 mx-auto rounded mb-3" />
          <p className="text-xs text-slate-500 mt-3">Loading paper-trade signals…</p>
        </div>
      ) : signals.length === 0 ? (
        <div className="glass-card p-10 text-center">
          <div className="text-slate-500 mb-2">
            <svg className="w-12 h-12 mx-auto opacity-40" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
              <path d="M9 12l2 2 4-4M12 2a10 10 0 100 20 10 10 0 000-20z" />
            </svg>
          </div>
          <p className="text-slate-400 text-sm">
            {filter === "resolved" ? "No resolved trades yet." : filter === "open" ? "No open trades." : "No paper-trade signals yet."}
          </p>
          <p className="text-slate-500 text-xs mt-1">
            Click &ldquo;Scan &amp; Log&rdquo; to run all strategies and record signals.
          </p>
        </div>
      ) : (
        <div className="space-y-2 fade-in">
          {signals.map((s) => (
            <PaperTradeRow key={s.id} signal={s} onResolve={refreshAll} positionSize={stats?.position_size || 0} cur={cur} />
          ))}
        </div>
      )}
    </div>
  );
}

function StatCard({ label, value, accent }: { label: string; value: string; accent?: "good" | "bad" | "neutral" }) {
  return (
    <div className="glass-card p-3 text-center">
      <div className="text-[10px] uppercase tracking-wide text-slate-500">{label}</div>
      <div className={`text-lg font-bold tabular-nums ${
        accent === "good" ? "text-emerald-400" : accent === "bad" ? "text-rose-400" : "text-slate-200"
      }`}>
        {value}
      </div>
    </div>
  );
}

function PaperTradeRow({ signal, onResolve, positionSize, cur }: { signal: PaperTrade; onResolve: () => void; positionSize: number; cur: string }) {
  const [resolving, setResolving] = useState(false);
  const isLong = signal.side === "long";
  const isOpen = signal.status === "open";
  const isWin = signal.pnl_pct !== null && signal.pnl_pct > 0;
  const stockHref = signal.market === "us" ? `/us-markets/stock/${signal.symbol}` : `/stock/${signal.symbol}`;

  const handleResolve = async (status: string) => {
    const exitPrice = status === "hit_target" ? signal.target : signal.stop_loss;
    setResolving(true);
    try {
      await resolvePaperSignal(signal.id, exitPrice, status);
      await onResolve();
    } catch {
      // ignore
    } finally {
      setResolving(false);
    }
  };

  return (
    <div className={`glass-card p-3 ${isOpen ? "" : isWin ? "border-l-2 border-l-emerald-500/50" : "border-l-2 border-l-rose-500/50"}`}>
      <div className="flex items-center justify-between gap-3">
        {/* Left: symbol + badges */}
        <div className="flex items-center gap-2 min-w-0">
          <Link href={stockHref} className="font-medium text-slate-100 hover:text-emerald-400 transition-colors text-sm">
            {signal.symbol}
          </Link>
          <span className={`text-[10px] font-medium rounded border px-1.5 py-0.5 ${
            isLong
              ? "bg-emerald-500/15 text-emerald-400 border-emerald-500/30"
              : "bg-rose-500/15 text-rose-400 border-rose-500/30"
          }`}>
            {signal.side.toUpperCase()}
          </span>
          <span className="text-[10px] text-slate-500 uppercase">{signal.strategy}</span>
          {!isOpen && (
            <span className={`text-[10px] font-medium px-1.5 py-0.5 rounded ${
              signal.status === "hit_target" ? "bg-emerald-500/10 text-emerald-400" :
              signal.status === "stopped_out" ? "bg-rose-500/10 text-rose-400" :
              "bg-amber-500/10 text-amber-400"
            }`}>
              {signal.status.replace("_", " ")}
            </span>
          )}
        </div>

        {/* Right: levels + P&L + actions */}
        <div className="flex items-center gap-3 text-xs tabular-nums text-slate-400">
          <span className="hidden sm:inline">Entry <span className="text-sky-300">{cur}{signal.entry.toFixed(2)}</span></span>
          <span className="hidden sm:inline">SL <span className="text-rose-300">{cur}{signal.stop_loss.toFixed(2)}</span></span>
          <span className="hidden sm:inline">Tgt <span className="text-emerald-300">{cur}{signal.target.toFixed(2)}</span></span>
          {signal.exit_price !== null && (
            <span className="hidden sm:inline">Exit <span className="text-slate-300">{cur}{signal.exit_price.toFixed(2)}</span></span>
          )}
          {signal.pnl_pct !== null && (
            <div className="flex flex-col items-end">
              <span className={`font-medium ${isWin ? "text-emerald-400" : "text-rose-400"}`}>
                {isWin ? "+" : ""}{signal.pnl_pct}%
              </span>
              {positionSize > 0 && (
                <span className={`text-[10px] ${isWin ? "text-emerald-500" : "text-rose-500"}`}>
                  {isWin ? "+" : ""}{cur}{Math.round(signal.pnl_pct * positionSize / 100).toLocaleString("en-IN")}
                </span>
              )}
            </div>
          )}
          {isOpen && (
            <div className="flex items-center gap-1">
              <button
                onClick={() => handleResolve("hit_target")}
                disabled={resolving}
                className="text-[10px] font-medium rounded border border-emerald-500/30 bg-emerald-500/10 text-emerald-400 px-2 py-1 hover:bg-emerald-500/20 transition-colors disabled:opacity-50"
              >
                Target
              </button>
              <button
                onClick={() => handleResolve("stopped_out")}
                disabled={resolving}
                className="text-[10px] font-medium rounded border border-rose-500/30 bg-rose-500/10 text-rose-400 px-2 py-1 hover:bg-rose-500/20 transition-colors disabled:opacity-50"
              >
                Stopped
              </button>
            </div>
          )}
        </div>
      </div>

      {/* Explanation for resolved trades */}
      {!isOpen && signal.explanation && (
        <div className="mt-2 pt-2 border-t border-slate-800/30">
          <p className="text-[11px] text-slate-500 leading-relaxed">
            {(signal.explanation as Record<string, unknown>)?.explanation as string || ""}
          </p>
        </div>
      )}
    </div>
  );
}
