"use client";

import { useState } from "react";
import useSWR from "swr";
import Link from "next/link";
import {
  fetchBotStatus,
  fetchBotDecisions,
  fetchStrategyRankings,
  fetchDailyRecommendation,
  fetchBotHistory,
  triggerBotScan,
  fetchStrategyComparison,
  type BotDecision,
  type StrategyRanking,
  type DailyRecommendationData,
  type PaperDayHistory,
} from "@/lib/api";
import { useAuthContext } from "@/lib/auth-context";

const verdictColor: Record<string, string> = {
  robust: "text-emerald-400 border-emerald-500/30 bg-emerald-500/10",
  moderate: "text-sky-400 border-sky-500/30 bg-sky-500/10",
  fragile: "text-amber-400 border-amber-500/30 bg-amber-500/10",
  overfit: "text-rose-400 border-rose-500/30 bg-rose-500/10",
};

const recBadge: Record<string, string> = {
  recommended: "text-emerald-400 border-emerald-500/30 bg-emerald-500/10",
  caution: "text-amber-400 border-amber-500/30 bg-amber-500/10",
  avoid: "text-rose-400 border-rose-500/30 bg-rose-500/10",
};

const stratLabel: Record<string, string> = {
  murphy: "Murphy (Daily)",
  scalp: "Nison Scalp",
  vwap: "VWAP Pullback",
  bollinger: "Bollinger Squeeze",
  ppo: "PPO Momentum",
};

function timeAgo(iso: string | null): string {
  if (!iso) return "—";
  const diff = Date.now() - new Date(iso).getTime();
  const min = Math.floor(diff / 60000);
  if (min < 1) return "just now";
  if (min < 60) return `${min} min ago`;
  const hr = Math.floor(min / 60);
  if (hr < 24) return `${hr} hr ago`;
  return `${Math.floor(hr / 24)} day(s) ago`;
}

export default function BotPage() {
  const { user } = useAuthContext();
  const isGuest = user?.is_guest ?? true;

  const { data: status, isLoading: statusLoading, mutate: mutateStatus } = useSWR(
    "bot-status", fetchBotStatus, { refreshInterval: 10000, keepPreviousData: true }
  );
  const { data: decisionsData } = useSWR(
    "bot-decisions", () => fetchBotDecisions(undefined, undefined, 100), { refreshInterval: 10000, keepPreviousData: true }
  );
  const { data: rankingsData } = useSWR(
    "bot-rankings", () => fetchStrategyRankings(), { refreshInterval: 30000, keepPreviousData: true }
  );
  const { data: recData } = useSWR(
    "bot-rec", () => fetchDailyRecommendation(), { refreshInterval: 30000, keepPreviousData: true }
  );
  const { data: historyData } = useSWR(
    "bot-history", () => fetchBotHistory(30), { refreshInterval: 30000, keepPreviousData: true }
  );
  const { data: comparisonData } = useSWR(
    "bot-comparison", () => fetchStrategyComparison(30), { refreshInterval: 60000, keepPreviousData: true }
  );

  const [scanning, setScanning] = useState(false);

  async function handleScan() {
    setScanning(true);
    try {
      await triggerBotScan("nse");
      await Promise.all([mutateStatus()]);
    } finally {
      setScanning(false);
    }
  }

  if (isGuest) {
    return (
      <div className="glass-card p-8 text-center">
        <p className="text-amber-300 text-sm">The Trading Bot requires a registered account.</p>
        <Link href="/login" className="mt-3 inline-block rounded-lg bg-slate-800 hover:bg-slate-700 px-4 py-2 text-sm transition-colors">Login / Register</Link>
      </div>
    );
  }

  const decisions = decisionsData?.decisions || [];
  const openTrades = decisions.filter((d) => d.status === "open");
  const closedTrades = decisions.filter((d) => d.status !== "open").slice(0, 20);
  const rankings = rankingsData?.rankings || [];
  const rec = recData as DailyRecommendationData | undefined;
  const history = historyData?.history || [];
  const comparison = comparisonData?.comparison || {};

  const maxAbsPnl = Math.max(1, ...history.map((h) => Math.abs(h.pnl_pct)));

  return (
    <div className="space-y-5">
      {/* Status bar */}
      <div className="flex items-center justify-between gap-3 flex-wrap">
        <div>
          <div className="flex items-center gap-2">
            <h1 className="text-lg font-semibold text-slate-100">Autonomous Trading Bot</h1>
            {status?.total_signals != null && status.total_signals > 0 && (
              <span className="inline-flex items-center gap-1 text-[10px] font-semibold rounded-full border px-2 py-0.5 text-emerald-400 border-emerald-500/30 bg-emerald-500/10">
                <span className="inline-block w-1.5 h-1.5 rounded-full bg-emerald-400 live-dot" />
                ACTIVE
              </span>
            )}
          </div>
          <p className="text-xs text-slate-400 mt-0.5">
            5 strategies (Murphy + Nison + VWAP + Bollinger + PPO) · paper trading · not investment advice
          </p>
        </div>
        <div className="flex items-center gap-3">
          {status?.last_scan && (
            <span className="text-xs text-slate-500">Last scan: {timeAgo(status.last_scan)}</span>
          )}
          <button
            onClick={handleScan}
            disabled={scanning}
            className="flex items-center gap-2 rounded-lg bg-slate-800 hover:bg-slate-700 disabled:opacity-40 px-3 py-1.5 text-xs font-medium transition-colors"
          >
            <svg className={`w-3.5 h-3.5 ${scanning ? "animate-spin" : ""}`} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <path d="M21 12a9 9 011-6.219-8.56" />
            </svg>
            {scanning ? "Scanning…" : "Scan Now"}
          </button>
        </div>
      </div>

      {/* Status summary cards */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
        <div className="glass-card p-3 text-center">
          <div className="text-[10px] text-slate-400 uppercase">Today Signals</div>
          <div className="text-xl font-bold tabular-nums text-slate-100">{status?.total_signals ?? "—"}</div>
        </div>
        <div className="glass-card p-3 text-center">
          <div className="text-[10px] text-slate-400 uppercase">Open</div>
          <div className="text-xl font-bold tabular-nums text-sky-300">{status?.open ?? "—"}</div>
        </div>
        <div className="glass-card p-3 text-center">
          <div className="text-[10px] text-slate-400 uppercase">Resolved</div>
          <div className="text-xl font-bold tabular-nums text-slate-300">{status?.resolved ?? "—"}</div>
        </div>
        <div className="glass-card p-3 text-center">
          <div className="text-[10px] text-slate-400 uppercase">Strategies</div>
          <div className="text-xl font-bold tabular-nums text-emerald-400">{Object.keys(status?.by_strategy || {}).length}</div>
        </div>
      </div>

      {/* Daily recommendation */}
      {rec?.found && rec.symbol && (
        <div className="glass-card p-5 border-l-4 border-emerald-500/50">
          <div className="flex items-center gap-2 mb-3">
            <span className="text-[10px] font-bold rounded border px-2 py-0.5 text-emerald-400 border-emerald-500/30 bg-emerald-500/10">RECOMMENDED</span>
            <span className="text-xs text-slate-400">{rec.date}</span>
          </div>
          <div className="flex items-start justify-between mb-3">
            <div>
              <div className="flex items-center gap-2">
                <span className="text-xl font-bold text-slate-100">{rec.symbol}</span>
                <span className="text-[10px] bg-slate-800 px-1.5 py-0.5 rounded text-slate-400">{stratLabel[rec.strategy || ""] || rec.strategy}</span>
                <span className="text-[10px] text-slate-500 uppercase">{rec.side}</span>
              </div>
              {rec.explanation && <p className="text-xs text-slate-400 mt-1 leading-relaxed">{rec.explanation}</p>}
            </div>
            <div className="text-right shrink-0">
              <div className="text-lg font-bold tabular-nums text-slate-100">₹{rec.entry?.toFixed(2)}</div>
              <div className="text-xs text-slate-400">R:R {rec.risk_reward?.toFixed(2)}</div>
              {rec.composite_score != null && <div className="text-xs text-emerald-400">Score {rec.composite_score.toFixed(0)}/100</div>}
            </div>
          </div>
          <div className="grid grid-cols-3 gap-2 pt-2 border-t border-slate-800/50">
            <div className="text-center">
              <div className="text-[10px] text-slate-400 uppercase">Entry</div>
              <div className="text-sm font-semibold tabular-nums text-sky-300">₹{rec.entry?.toFixed(2)}</div>
            </div>
            <div className="text-center">
              <div className="text-[10px] text-slate-400 uppercase">Stop</div>
              <div className="text-sm font-semibold tabular-nums text-rose-300">₹{rec.stop_loss?.toFixed(2)}</div>
            </div>
            <div className="text-center">
              <div className="text-[10px] text-slate-400 uppercase">Target</div>
              <div className="text-sm font-semibold tabular-nums text-emerald-300">₹{rec.target?.toFixed(2)}</div>
            </div>
          </div>
          {rec.caveats && rec.caveats.length > 0 && (
            <div className="mt-2 flex flex-wrap gap-1">
              {rec.caveats.map((c, i) => (
                <span key={i} className="text-[10px] text-amber-300/70 bg-amber-500/5 px-1.5 py-0.5 rounded">{c}</span>
              ))}
            </div>
          )}
          {rec.alternatives && rec.alternatives.length > 0 && (
            <div className="mt-2">
              <div className="text-[10px] text-slate-500 uppercase mb-1">Alternatives</div>
              <div className="flex flex-wrap gap-1">
                {rec.alternatives.map((a, i) => (
                  <span key={i} className="text-[10px] bg-slate-800 px-1.5 py-0.5 rounded text-slate-400">
                    #{a.rank} {a.symbol} ({stratLabel[a.strategy] || a.strategy})
                  </span>
                ))}
              </div>
            </div>
          )}
        </div>
      )}

      {/* Strategy rankings table */}
      {rankings.length > 0 && (
        <div>
          <h2 className="text-sm font-semibold text-slate-400 mb-3">Strategy Rankings — {rankingsData?.date}</h2>
          <div className="glass-card overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="text-[10px] text-slate-500 uppercase border-b border-slate-800/50">
                  <th className="px-3 py-2 text-left">Rank</th>
                  <th className="px-3 py-2 text-left">Strategy</th>
                  <th className="px-3 py-2 text-right">Signals</th>
                  <th className="px-3 py-2 text-right">Win Rate</th>
                  <th className="px-3 py-2 text-right">Avg P&L</th>
                  <th className="px-3 py-2 text-right">Total</th>
                  <th className="px-3 py-2 text-center">WFE</th>
                  <th className="px-3 py-2 text-center">Verdict</th>
                  <th className="px-3 py-2 text-center">Rec</th>
                </tr>
              </thead>
              <tbody>
                {rankings.map((r: StrategyRanking) => (
                  <tr key={r.strategy} className="border-b border-slate-800/30 hover:bg-slate-800/20">
                    <td className="px-3 py-2 font-mono text-slate-500">#{r.rank}</td>
                    <td className="px-3 py-2 font-medium text-slate-100">{stratLabel[r.strategy] || r.strategy}</td>
                    <td className="px-3 py-2 text-right tabular-nums text-slate-300">{r.total_signals}</td>
                    <td className="px-3 py-2 text-right tabular-nums text-emerald-400">{r.win_rate.toFixed(1)}%</td>
                    <td className="px-3 py-2 text-right tabular-nums text-slate-300">{r.avg_pnl_pct.toFixed(2)}%</td>
                    <td className={`px-3 py-2 text-right tabular-nums ${r.total_pnl_pct >= 0 ? "text-emerald-400" : "text-rose-400"}`}>
                      {r.total_pnl_pct >= 0 ? "+" : ""}{r.total_pnl_pct.toFixed(2)}%
                    </td>
                    <td className="px-3 py-2 text-center tabular-nums text-slate-400">
                      {r.wfe_score != null ? `${r.wfe_score.toFixed(1)}%` : "—"}
                    </td>
                    <td className="px-3 py-2 text-center">
                      {r.wfe_verdict && (
                        <span className={`text-[10px] font-bold rounded border px-1.5 py-0.5 ${verdictColor[r.wfe_verdict] || ""}`}>
                          {r.wfe_verdict}
                        </span>
                      )}
                    </td>
                    <td className="px-3 py-2 text-center">
                      <span className={`text-[10px] font-bold rounded border px-1.5 py-0.5 ${recBadge[r.recommendation] || ""}`}>
                        {r.recommendation}
                      </span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* Multi-day strategy comparison */}
      {Object.keys(comparison).length > 0 && (
        <div>
          <h2 className="text-sm font-semibold text-slate-400 mb-3">Multi-Day Strategy Comparison (30 days)</h2>
          <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
            {Object.values(comparison).map((s: any) => (
              <div key={s.strategy} className="glass-card p-3">
                <div className="flex items-center justify-between mb-2">
                  <span className="font-medium text-slate-100 text-sm">{stratLabel[s.strategy] || s.strategy}</span>
                  {s.rank_1_count > 0 && (
                    <span className="text-[10px] text-emerald-400">#{s.rank_1_count}x top-ranked</span>
                  )}
                </div>
                <div className="grid grid-cols-3 gap-2 text-center">
                  <div>
                    <div className="text-[10px] text-slate-400 uppercase">Signals</div>
                    <div className="text-sm font-semibold tabular-nums text-slate-200">{s.total_signals}</div>
                  </div>
                  <div>
                    <div className="text-[10px] text-slate-400 uppercase">Win Rate</div>
                    <div className="text-sm font-semibold tabular-nums text-emerald-400">{s.win_rate.toFixed(1)}%</div>
                  </div>
                  <div>
                    <div className="text-[10px] text-slate-400 uppercase">Avg WFE</div>
                    <div className="text-sm font-semibold tabular-nums text-sky-300">{s.avg_wfe.toFixed(1)}%</div>
                  </div>
                </div>
                <div className="mt-2 pt-2 border-t border-slate-800/50 text-center">
                  <div className="text-[10px] text-slate-400 uppercase">Total P&L</div>
                  <div className={`text-sm font-bold tabular-nums ${s.total_pnl >= 0 ? "text-emerald-400" : "text-rose-400"}`}>
                    {s.total_pnl >= 0 ? "+" : ""}{s.total_pnl.toFixed(2)}%
                  </div>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Daily P&L chart */}
      {history.length > 0 && (
        <div>
          <h2 className="text-sm font-semibold text-slate-400 mb-3">Daily P&L History</h2>
          <div className="glass-card p-4">
            <div className="flex items-end gap-1 h-32">
              {history.slice().reverse().map((h: PaperDayHistory, i: number) => {
                const pct = (h.pnl_pct / maxAbsPnl) * 50; // max 50% of chart height
                const isPositive = h.pnl_pct >= 0;
                return (
                  <div key={i} className="flex-1 flex flex-col items-center justify-end h-full group relative">
                    <div
                      className={`w-full rounded-sm transition-all ${isPositive ? "bg-emerald-500/60" : "bg-rose-500/60"}`}
                      style={{ height: `${Math.abs(pct)}%`, minHeight: "2px" }}
                    />
                    <div className="absolute -top-8 hidden group-hover:block text-[10px] text-slate-300 bg-slate-900 px-2 py-1 rounded whitespace-nowrap z-10">
                      {h.date}: {h.pnl_pct >= 0 ? "+" : ""}{h.pnl_pct.toFixed(2)}%
                    </div>
                  </div>
                );
              })}
            </div>
          </div>
        </div>
      )}

      {/* Open decisions */}
      {openTrades.length > 0 && (
        <div>
          <h2 className="text-sm font-semibold text-slate-400 mb-3">Open Positions ({openTrades.length})</h2>
          <div className="glass-card overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="text-[10px] text-slate-500 uppercase border-b border-slate-800/50">
                  <th className="px-3 py-2 text-left">Symbol</th>
                  <th className="px-3 py-2 text-left">Strategy</th>
                  <th className="px-3 py-2 text-left">Side</th>
                  <th className="px-3 py-2 text-right">Entry</th>
                  <th className="px-3 py-2 text-right">Stop</th>
                  <th className="px-3 py-2 text-right">Target</th>
                  <th className="px-3 py-2 text-right">R:R</th>
                  <th className="px-3 py-2 text-right">Conf</th>
                  <th className="px-3 py-2 text-left">Scanned</th>
                </tr>
              </thead>
              <tbody>
                {openTrades.map((d: BotDecision) => (
                  <tr key={d.id} className="border-b border-slate-800/30 hover:bg-slate-800/20">
                    <td className="px-3 py-2">
                      <Link href={`/stock/${d.symbol}`} className="font-medium text-slate-100 hover:text-sky-400">{d.symbol}</Link>
                    </td>
                    <td className="px-3 py-2 text-slate-400">{stratLabel[d.strategy] || d.strategy}</td>
                    <td className="px-3 py-2 text-slate-400 uppercase">{d.side}</td>
                    <td className="px-3 py-2 text-right tabular-nums text-slate-300">₹{d.entry.toFixed(2)}</td>
                    <td className="px-3 py-2 text-right tabular-nums text-rose-300">₹{d.stop_loss.toFixed(2)}</td>
                    <td className="px-3 py-2 text-right tabular-nums text-emerald-300">₹{d.target.toFixed(2)}</td>
                    <td className="px-3 py-2 text-right tabular-nums text-slate-400">{d.risk_reward.toFixed(2)}</td>
                    <td className="px-3 py-2 text-right tabular-nums text-sky-300">{(d.confidence * 100).toFixed(0)}%</td>
                    <td className="px-3 py-2 text-xs text-slate-500">{timeAgo(d.scan_time)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* Recent closed trades */}
      {closedTrades.length > 0 && (
        <div>
          <h2 className="text-sm font-semibold text-slate-400 mb-3">Recent Closed Trades</h2>
          <div className="glass-card overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="text-[10px] text-slate-500 uppercase border-b border-slate-800/50">
                  <th className="px-3 py-2 text-left">Symbol</th>
                  <th className="px-3 py-2 text-left">Strategy</th>
                  <th className="px-3 py-2 text-left">Status</th>
                  <th className="px-3 py-2 text-right">Entry</th>
                  <th className="px-3 py-2 text-right">Exit</th>
                  <th className="px-3 py-2 text-right">P&L %</th>
                </tr>
              </thead>
              <tbody>
                {closedTrades.map((d: BotDecision) => (
                  <tr key={d.id} className="border-b border-slate-800/30 hover:bg-slate-800/20">
                    <td className="px-3 py-2">
                      <Link href={`/stock/${d.symbol}`} className="font-medium text-slate-100 hover:text-sky-400">{d.symbol}</Link>
                    </td>
                    <td className="px-3 py-2 text-slate-400">{stratLabel[d.strategy] || d.strategy}</td>
                    <td className="px-3 py-2">
                      <span className={`text-[10px] font-bold rounded border px-1.5 py-0.5 ${
                        d.status === "hit_target" ? "text-emerald-400 border-emerald-500/30 bg-emerald-500/10" :
                        d.status === "stopped_out" ? "text-rose-400 border-rose-500/30 bg-rose-500/10" :
                        "text-slate-400 border-slate-600/30 bg-slate-700/20"
                      }`}>{d.status}</span>
                    </td>
                    <td className="px-3 py-2 text-right tabular-nums text-slate-300">₹{d.entry.toFixed(2)}</td>
                    <td className="px-3 py-2 text-right tabular-nums text-slate-300">₹{d.exit_price?.toFixed(2) || "—"}</td>
                    <td className={`px-3 py-2 text-right tabular-nums font-semibold ${(d.pnl_pct || 0) >= 0 ? "text-emerald-400" : "text-rose-400"}`}>
                      {(d.pnl_pct || 0) >= 0 ? "+" : ""}{(d.pnl_pct || 0).toFixed(2)}%
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* Empty state */}
      {statusLoading && (
        <div className="glass-card p-8 text-center">
          <div className="shimmer h-5 w-48 rounded mx-auto mb-3" />
          <div className="shimmer h-3 w-full rounded mb-2" />
          <div className="shimmer h-3 w-2/3 rounded" />
        </div>
      )}

      {!statusLoading && (status?.total_signals ?? 0) === 0 && openTrades.length === 0 && (
        <div className="glass-card p-8 text-center">
          <p className="text-amber-300 text-sm">No bot signals yet. Click "Scan Now" to start the bot.</p>
        </div>
      )}

      <p className="text-xs text-slate-600 text-center">
        Bot runs 5 strategies: Murphy multi-indicator (daily) + Nison candlestick scalping (intraday) + VWAP + Bollinger + PPO.
        All trades are paper (no real money). Auto-scans every 5 min during market hours. Not investment advice.
      </p>
    </div>
  );
}
