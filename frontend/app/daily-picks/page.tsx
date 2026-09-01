"use client";

import { useState } from "react";
import useSWR from "swr";
import Link from "next/link";
import {
  fetchDailyPicks,
  refreshDailyPicks,
  fetchDailyBacktest,
  type DailyPick,
  type DailyBacktestResult,
  type DailyBacktestTrade,
} from "@/lib/api";
import { StrategyVerificationBadge } from "@/components/StrategyVerificationBadge";

// ---------------------------------------------------------------------------
// Verdict badge
// ---------------------------------------------------------------------------
function VerdictBadge({ verdict }: { verdict: string }) {
  const styles: Record<string, string> = {
    strong_buy: "bg-emerald-500/15 text-emerald-400 border-emerald-500/30",
    buy: "bg-green-500/15 text-green-400 border-green-500/30",
    hold: "bg-amber-500/15 text-amber-400 border-amber-500/30",
    avoid: "bg-orange-500/15 text-orange-400 border-orange-500/30",
    strong_avoid: "bg-red-500/15 text-red-400 border-red-500/30",
  };
  const cls = styles[verdict] || "bg-slate-700/30 text-slate-400 border-slate-600/30";
  return (
    <span className={`text-[10px] font-bold rounded border px-2 py-0.5 ${cls}`}>
      {verdict.replace("_", " ").toUpperCase()}
    </span>
  );
}

// ---------------------------------------------------------------------------
// Score bar
// ---------------------------------------------------------------------------
function ScoreBar({ score, label, weight }: { score: number; label: string; weight: number }) {
  const color = score >= 70 ? "bg-emerald-500" : score >= 50 ? "bg-amber-500" : "bg-red-500";
  return (
    <div className="flex items-center gap-2">
      <div className="w-28 text-[10px] text-slate-500 shrink-0">{label} ({weight}%)</div>
      <div className="flex-1 h-2 bg-slate-800 rounded-full overflow-hidden">
        <div className={`h-full ${color} rounded-full transition-all`} style={{ width: `${score}%` }} />
      </div>
      <div className="w-8 text-right text-[10px] font-semibold text-slate-400 tabular-nums">{score.toFixed(0)}</div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Rank badge
// ---------------------------------------------------------------------------
function RankBadge({ rank }: { rank: number }) {
  const styles: Record<number, string> = {
    1: "bg-gradient-to-br from-yellow-400 to-amber-600 text-yellow-950",
    2: "bg-gradient-to-br from-slate-300 to-slate-500 text-slate-900",
    3: "bg-gradient-to-br from-orange-400 to-amber-700 text-orange-950",
  };
  const cls = styles[rank] || "bg-slate-700 text-slate-300";
  return (
    <div className={`flex items-center justify-center w-9 h-9 rounded-full font-bold text-sm shrink-0 ${cls}`}>
      #{rank}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Indicator mini-badge
// ---------------------------------------------------------------------------
function IndicatorBadge({ label, value, signal }: { label: string; value: string; signal?: string }) {
  const sigColor =
    signal === "oversold" || signal === "oversold_exit" || signal === "bullish" || signal === "bullish_cross" || signal === "up" || signal === "rising"
      ? "text-emerald-400"
      : signal === "overbought" || signal === "overbought_exit" || signal === "bearish" || signal === "bearish_cross" || signal === "down" || signal === "falling"
      ? "text-red-400"
      : "text-slate-400";
  return (
    <div className="flex flex-col items-center gap-0.5 bg-slate-800/40 rounded-lg px-2 py-1.5">
      <span className="text-[9px] text-slate-500 uppercase tracking-wide">{label}</span>
      <span className="text-xs font-semibold text-slate-200 tabular-nums">{value}</span>
      {signal && <span className={`text-[9px] font-medium ${sigColor}`}>{signal.replace(/_/g, " ")}</span>}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Price pill
// ---------------------------------------------------------------------------
function PricePill({ label, value, color }: { label: string; value: number; color: string }) {
  return (
    <div className={`flex flex-col items-center rounded-lg px-3 py-1.5 ${color}`}>
      <span className="text-[9px] uppercase tracking-wide opacity-70">{label}</span>
      <span className="text-sm font-semibold tabular-nums">₹{value.toFixed(2)}</span>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Pick card
// ---------------------------------------------------------------------------
function PickCard({ pick }: { pick: DailyPick }) {
  const score = pick.composite_score;
  const scoreColor = score >= 75 ? "text-emerald-400" : score >= 60 ? "text-green-400" : score >= 45 ? "text-amber-400" : "text-red-400";

  return (
    <div className="glass-card-hover p-5 fade-in">
      {/* Header */}
      <div className="flex items-start gap-3 mb-4">
        <RankBadge rank={pick.rank} />
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 flex-wrap">
            <Link href={`/stock/${pick.symbol}`} className="font-bold text-slate-100 hover:text-emerald-400 transition-colors">
              {pick.symbol}
            </Link>
            <VerdictBadge verdict={pick.verdict} />
          </div>
          <p className="text-xs text-slate-500 truncate">{pick.name}</p>
        </div>
        <div className="text-right shrink-0">
          <div className={`text-2xl font-bold tabular-nums ${scoreColor}`}>{score.toFixed(1)}</div>
          <div className="text-[9px] text-slate-500 uppercase">Score</div>
        </div>
      </div>

      {/* Entry / SL / T1 / T2 */}
      <div className="grid grid-cols-4 gap-2 mb-4">
        <PricePill label="Entry" value={pick.entry} color="bg-sky-500/10 text-sky-400" />
        <PricePill label="SL" value={pick.stop_loss} color="bg-rose-500/10 text-rose-400" />
        <PricePill label="T1" value={pick.target1} color="bg-emerald-500/10 text-emerald-400" />
        <PricePill label="T2" value={pick.target2} color="bg-emerald-500/10 text-emerald-400" />
      </div>

      {/* R:R + Last Price */}
      <div className="flex items-center gap-4 mb-4 text-xs">
        <div>
          <span className="text-slate-500">R:R </span>
          <span className="font-semibold text-slate-200">1:{pick.risk_reward.toFixed(1)}</span>
        </div>
        <div>
          <span className="text-slate-500">LTP </span>
          <span className="font-semibold text-slate-200 tabular-nums">₹{pick.last_price.toFixed(2)}</span>
        </div>
        <div>
          <span className="text-slate-500">ATR </span>
          <span className="font-semibold text-slate-200 tabular-nums">{pick.atr_value.toFixed(2)}</span>
        </div>
      </div>

      {/* Factor breakdown bars */}
      <div className="space-y-1.5 mb-4">
        <ScoreBar score={pick.factors.trend} label="Trend" weight={30} />
        <ScoreBar score={pick.factors.momentum} label="Momentum" weight={30} />
        <ScoreBar score={pick.factors.volume} label="Volume" weight={20} />
        <ScoreBar score={pick.factors.support_resistance} label="S/R" weight={20} />
      </div>

      {/* Indicator grid */}
      <div className="grid grid-cols-4 gap-2 mb-4">
        <IndicatorBadge label="RSI" value={pick.rsi_value.toFixed(1)} signal={pick.rsi_signal} />
        <IndicatorBadge label="Stoch %K" value={pick.stochastic_k.toFixed(1)} signal={pick.stochastic_signal} />
        <IndicatorBadge label="MACD" value={pick.macd_histogram.toFixed(4)} signal={pick.macd_signal} />
        <IndicatorBadge label="ADX" value={pick.adx_value.toFixed(1)} signal={pick.adx_strength} />
        <IndicatorBadge label="Williams %R" value={pick.williams_r_value.toFixed(1)} signal={pick.williams_r_signal} />
        <IndicatorBadge label="OBV" value={pick.obv_trend} />
        <IndicatorBadge label="Supertrend" value={pick.supertrend_dir} signal={pick.supertrend_dir} />
        <IndicatorBadge label="Vol Ratio" value={`${pick.volume_ratio.toFixed(2)}x`} />
      </div>

      {/* S/R levels */}
      <div className="flex items-center gap-4 mb-3 text-xs">
        <div>
          <span className="text-slate-500">Support </span>
          <span className="font-semibold text-emerald-400 tabular-nums">₹{pick.nearest_support.toFixed(2)}</span>
        </div>
        <div>
          <span className="text-slate-500">Resistance </span>
          <span className="font-semibold text-rose-400 tabular-nums">₹{pick.nearest_resistance.toFixed(2)}</span>
        </div>
        <div>
          <span className="text-slate-500">Position </span>
          <span className="font-semibold text-slate-300">{pick.price_vs_support.replace(/_/g, " ")}</span>
        </div>
      </div>

      {/* Explanation */}
      <p className="text-xs text-slate-400 leading-relaxed mb-2">{pick.explanation}</p>

      {/* Caveats */}
      {pick.caveats.length > 0 && (
        <ul className="space-y-1 mt-2">
          {pick.caveats.map((c, i) => (
            <li key={i} className="text-[10px] text-amber-400/80 flex items-start gap-1">
              <span className="text-amber-500/50">!</span>
              <span>{c}</span>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Backtest section
// ---------------------------------------------------------------------------
function BacktestSection() {
  const { data, error, isLoading } = useSWR<DailyBacktestResult>("daily-backtest", () => fetchDailyBacktest(30), {
    refreshInterval: 0,
  });

  if (isLoading) {
    return (
      <div className="glass-card p-6 text-center">
        <p className="text-sm text-slate-400">Running 30-day backtest... this may take a moment.</p>
      </div>
    );
  }

  if (error || !data) {
    return (
      <div className="glass-card p-6 text-center">
        <p className="text-sm text-slate-500">Backtest unavailable.</p>
      </div>
    );
  }

  const s = data.summary;

  return (
    <div className="glass-card p-6">
      <h2 className="text-lg font-bold text-slate-100 mb-4">30-Day Backtest</h2>

      {/* Summary */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 mb-6">
        <div className="bg-slate-800/40 rounded-xl p-3 text-center">
          <div className="text-2xl font-bold text-slate-100 tabular-nums">{s.total_trades}</div>
          <div className="text-[10px] text-slate-500 uppercase">Trades</div>
        </div>
        <div className="bg-emerald-500/10 rounded-xl p-3 text-center">
          <div className="text-2xl font-bold text-emerald-400 tabular-nums">{s.wins}</div>
          <div className="text-[10px] text-slate-500 uppercase">Wins</div>
        </div>
        <div className="bg-red-500/10 rounded-xl p-3 text-center">
          <div className="text-2xl font-bold text-red-400 tabular-nums">{s.losses}</div>
          <div className="text-[10px] text-slate-500 uppercase">Losses</div>
        </div>
        <div className="bg-slate-800/40 rounded-xl p-3 text-center">
          <div className={`text-2xl font-bold tabular-nums ${s.win_rate >= 50 ? "text-emerald-400" : "text-amber-400"}`}>
            {s.win_rate.toFixed(1)}%
          </div>
          <div className="text-[10px] text-slate-500 uppercase">Win Rate</div>
        </div>
      </div>

      {/* Avg return */}
      <div className="mb-4 flex items-center gap-4">
        <div>
          <span className="text-xs text-slate-500">Avg Return/Trade: </span>
          <span className={`text-sm font-bold tabular-nums ${s.avg_return_pct >= 0 ? "text-emerald-400" : "text-red-400"}`}>
            {s.avg_return_pct >= 0 ? "+" : ""}{s.avg_return_pct.toFixed(2)}%
          </span>
        </div>
      </div>

      {/* Trade log */}
      {data.all_trades.length > 0 ? (
        <div className="overflow-x-auto">
          <table className="w-full text-xs">
            <thead>
              <tr className="text-slate-500 border-b border-slate-800">
                <th className="text-left py-2 px-2 font-medium">Date</th>
                <th className="text-left py-2 px-2 font-medium">Symbol</th>
                <th className="text-right py-2 px-2 font-medium">Entry</th>
                <th className="text-right py-2 px-2 font-medium">Exit</th>
                <th className="text-left py-2 px-2 font-medium">Outcome</th>
                <th className="text-right py-2 px-2 font-medium">P&L %</th>
              </tr>
            </thead>
            <tbody>
              {data.all_trades.slice(0, 50).map((t: DailyBacktestTrade, i: number) => (
                <tr key={i} className="border-b border-slate-800/50 hover:bg-slate-800/30">
                  <td className="py-1.5 px-2 text-slate-400">{t.date}</td>
                  <td className="py-1.5 px-2 font-medium text-slate-200">{t.symbol}</td>
                  <td className="py-1.5 px-2 text-right tabular-nums text-slate-300">₹{t.entry.toFixed(2)}</td>
                  <td className="py-1.5 px-2 text-right tabular-nums text-slate-300">₹{t.exit_price.toFixed(2)}</td>
                  <td className="py-1.5 px-2">
                    <span className={`text-[10px] font-medium ${
                      t.outcome === "target_hit" ? "text-emerald-400" : t.outcome === "stopped_out" ? "text-red-400" : "text-slate-400"
                    }`}>
                      {t.outcome.replace(/_/g, " ")}
                    </span>
                  </td>
                  <td className={`py-1.5 px-2 text-right tabular-nums font-semibold ${t.pnl_pct >= 0 ? "text-emerald-400" : "text-red-400"}`}>
                    {t.pnl_pct >= 0 ? "+" : ""}{t.pnl_pct.toFixed(2)}%
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
          {data.all_trades.length > 50 && (
            <p className="text-center text-[10px] text-slate-500 mt-2">Showing 50 of {data.all_trades.length} trades</p>
          )}
        </div>
      ) : (
        <p className="text-xs text-slate-500 text-center py-4">No trades in backtest period.</p>
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Main page
// ---------------------------------------------------------------------------
export default function DailyPicksPage() {
  const { data, error, isLoading, mutate } = useSWR("daily-picks", fetchDailyPicks, {
    refreshInterval: 300000,
  });
  const [refreshing, setRefreshing] = useState(false);

  async function handleRefresh() {
    setRefreshing(true);
    try {
      const result = await refreshDailyPicks();
      mutate(result, false);
    } catch {
      // ignore — SWR will show stale data
    } finally {
      setRefreshing(false);
    }
  }

  if (isLoading) {
    return (
      <div className="max-w-6xl mx-auto px-4 py-8">
        <div className="glass-card p-8 text-center">
          <p className="text-sm text-slate-400">Scanning Nifty 100 universe with Murphy multi-indicator analysis...</p>
        </div>
      </div>
    );
  }

  if (error || !data) {
    return (
      <div className="max-w-6xl mx-auto px-4 py-8">
        <div className="glass-card p-8 text-center">
          <p className="text-sm text-red-400">Failed to load daily picks.</p>
          <button onClick={() => mutate()} className="mt-3 text-xs text-emerald-400 hover:underline">Retry</button>
        </div>
      </div>
    );
  }

  const picks = data.picks;
  const strongBuys = picks.filter((p) => p.verdict === "strong_buy").length;
  const buys = picks.filter((p) => p.verdict === "buy").length;
  const avgScore = picks.length > 0 ? picks.reduce((a, p) => a + p.composite_score, 0) / picks.length : 0;

  return (
    <div className="max-w-6xl mx-auto px-4 py-6 space-y-6">
      {/* Header */}
      <div className="flex items-start justify-between flex-wrap gap-3">
        <div>
          <h1 className="text-2xl font-bold text-slate-100">Daily Top 5 Picks</h1>
          <div className="mt-1.5">
            <StrategyVerificationBadge strategy="murphy" />
          </div>
          <p className="text-xs text-slate-500 mt-1.5">
            Murphy multi-indicator analysis — {data.total_scanned} stocks scanned
            {data.refreshed_at && ` · refreshed ${new Date(data.refreshed_at).toLocaleTimeString()}`}
            {data.market_status && ` · ${data.market_status}`}
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

      {/* Summary bar */}
      {picks.length > 0 ? (
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
          <div className="glass-card p-3 text-center">
            <div className="text-xl font-bold text-emerald-400 tabular-nums">{strongBuys}</div>
            <div className="text-[10px] text-slate-500 uppercase">Strong Buys</div>
          </div>
          <div className="glass-card p-3 text-center">
            <div className="text-xl font-bold text-green-400 tabular-nums">{buys}</div>
            <div className="text-[10px] text-slate-500 uppercase">Buys</div>
          </div>
          <div className="glass-card p-3 text-center">
            <div className="text-xl font-bold text-slate-200 tabular-nums">{avgScore.toFixed(1)}</div>
            <div className="text-[10px] text-slate-500 uppercase">Avg Score</div>
          </div>
          <div className="glass-card p-3 text-center">
            <div className="text-xl font-bold text-slate-200 tabular-nums">{picks.length}</div>
            <div className="text-[10px] text-slate-500 uppercase">Picks</div>
          </div>
        </div>
      ) : (
        <div className="glass-card p-6 text-center">
          <p className="text-sm text-slate-400">
            No stocks meet the Murphy buy criteria today (composite score &ge; 60 with trend + momentum confirmation).
          </p>
          <p className="text-xs text-slate-500 mt-2">
            This is normal in range-bound or bearish markets — Murphy&apos;s principle is to wait for confirmation.
          </p>
        </div>
      )}

      {/* Pick cards */}
      {picks.length > 0 && (
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
          {picks.map((pick) => (
            <PickCard key={pick.symbol} pick={pick} />
          ))}
        </div>
      )}

      {/* Backtest */}
      <BacktestSection />
    </div>
  );
}
