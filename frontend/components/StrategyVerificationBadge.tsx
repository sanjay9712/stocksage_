"use client";

import useSWR from "swr";
import { fetchProvenStrategies, type StrategyTrackRecord } from "@/lib/api";

const STRATEGY_LABELS: Record<string, string> = {
  murphy: "Murphy (Daily)",
  scalp: "Nison Scalp",
  vwap: "VWAP Pullback",
  bollinger: "Bollinger Squeeze",
  ppo: "PPO Momentum",
  ma_trend: "MA Trend",
  gap_go: "Gap-and-Go",
  sr_reversal: "S/R Reversal",
  momentum_breakout: "Momentum Breakout",
  abcd: "ABCD Pattern",
};

const VERDICT_STYLES: Record<string, string> = {
  proven: "bg-emerald-500/15 text-emerald-400 border-emerald-500/30",
  testing: "bg-amber-500/15 text-amber-400 border-amber-500/30",
  unproven: "bg-rose-500/15 text-rose-400 border-rose-500/30",
};

const VERDICT_ICONS: Record<string, string> = {
  proven: "M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z",
  testing: "M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z",
  unproven: "M10 14l2-2m0 0l2-2m-2 2l-2-2m2 2l2 2m7-3a9 9 0 11-18 0 9 9 0 0118 0z",
};

export function StrategyVerificationBadge({ strategy }: { strategy: string }) {
  const { data } = useSWR("proven-strategies", () => fetchProvenStrategies(30), {
    refreshInterval: 300000,
  });
  const record = data?.strategies.find((s) => s.strategy === strategy);

  if (!record) return null;

  const label = STRATEGY_LABELS[strategy] || strategy;
  const style = VERDICT_STYLES[record.verdict] || VERDICT_STYLES.testing;
  const iconPath = VERDICT_ICONS[record.verdict] || VERDICT_ICONS.testing;

  return (
    <div className={`inline-flex items-center gap-2 px-3 py-1.5 rounded-lg border text-xs font-medium ${style}`}>
      <svg className="w-4 h-4 shrink-0" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
        <path d={iconPath} />
      </svg>
      <span className="capitalize">{record.verdict}</span>
      <span className="text-slate-500">·</span>
      <span className="text-slate-400">{label}</span>
      {record.resolved_trades > 0 && (
        <>
          <span className="text-slate-500">·</span>
          <span className="text-slate-400">
            {record.win_rate.toFixed(0)}% win · {record.resolved_trades} trades
          </span>
        </>
      )}
      {record.backtest_win_rate != null && record.resolved_trades === 0 && (
        <>
          <span className="text-slate-500">·</span>
          <span className="text-slate-400">
            BT: {record.backtest_win_rate.toFixed(0)}% win
          </span>
        </>
      )}
    </div>
  );
}

export function StrategyVerificationCard({ record }: { record: StrategyTrackRecord }) {
  const label = STRATEGY_LABELS[record.strategy] || record.strategy;
  const style = VERDICT_STYLES[record.verdict] || VERDICT_STYLES.testing;
  const iconPath = VERDICT_ICONS[record.verdict] || VERDICT_ICONS.testing;

  const progressItems = [
    { label: "Days", value: record.days_tracked, target: 7, met: record.min_days_met },
    { label: "Trades", value: record.resolved_trades, target: 10, met: record.min_trades_met },
    { label: "Win %", value: record.win_rate, target: 50, met: record.min_win_rate_met },
    { label: "Avg P&L", value: record.avg_pnl_pct, target: 0, met: record.min_pnl_met },
  ];

  return (
    <div className="glass-card p-4 rounded-xl">
      <div className="flex items-center justify-between mb-3">
        <div className="flex items-center gap-2">
          <svg className={`w-5 h-5 ${style.includes("emerald") ? "text-emerald-400" : style.includes("amber") ? "text-amber-400" : "text-rose-400"}`} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <path d={iconPath} />
          </svg>
          <span className="text-sm font-semibold text-slate-100">{label}</span>
        </div>
        <span className={`px-2 py-0.5 rounded-md text-[10px] font-bold uppercase border ${style}`}>
          {record.verdict}
        </span>
      </div>

      {/* Stats row */}
      <div className="grid grid-cols-4 gap-2 mb-3">
        <div className="text-center">
          <div className="text-lg font-bold text-slate-100">{record.resolved_trades}</div>
          <div className="text-[10px] text-slate-500 uppercase">Trades</div>
        </div>
        <div className="text-center">
          <div className={`text-lg font-bold ${record.win_rate >= 50 ? "text-emerald-400" : "text-rose-400"}`}>
            {record.win_rate.toFixed(0)}%
          </div>
          <div className="text-[10px] text-slate-500 uppercase">Win Rate</div>
        </div>
        <div className="text-center">
          <div className={`text-lg font-bold ${record.avg_pnl_pct >= 0 ? "text-emerald-400" : "text-rose-400"}`}>
            {record.avg_pnl_pct >= 0 ? "+" : ""}{record.avg_pnl_pct.toFixed(2)}%
          </div>
          <div className="text-[10px] text-slate-500 uppercase">Avg P&L</div>
        </div>
        <div className="text-center">
          <div className={`text-lg font-bold ${record.total_pnl_pct >= 0 ? "text-emerald-400" : "text-rose-400"}`}>
            {record.total_pnl_pct >= 0 ? "+" : ""}{record.total_pnl_pct.toFixed(1)}%
          </div>
          <div className="text-[10px] text-slate-500 uppercase">Total P&L</div>
        </div>
      </div>

      {/* Progress bars toward "proven" */}
      <div className="space-y-1.5">
        {progressItems.map((item) => (
          <div key={item.label} className="flex items-center gap-2 text-xs">
            <span className="w-14 text-slate-500">{item.label}</span>
            <div className="flex-1 h-1.5 bg-slate-800 rounded-full overflow-hidden">
              <div
                className={`h-full rounded-full ${item.met ? "bg-emerald-500" : "bg-amber-500"}`}
                style={{ width: `${Math.min(100, (item.value / Math.max(1, item.target)) * 100)}%` }}
              />
            </div>
            <span className={`w-12 text-right ${item.met ? "text-emerald-400" : "text-slate-400"}`}>
              {item.value.toFixed(item.label === "Avg P&L" ? 1 : 0)}
            </span>
          </div>
        ))}
      </div>

      {/* Consistency + backtest */}
      <div className="flex items-center justify-between mt-3 pt-3 border-t border-slate-800 text-[11px] text-slate-500">
        <span>
          Profitable {record.profitable_days}/{Math.max(1, record.days_tracked)} days ({record.consistency_pct.toFixed(0)}%)
        </span>
        {record.backtest_win_rate != null && (
          <span>
            BT: {record.backtest_win_rate.toFixed(0)}% win · {record.backtest_avg_return?.toFixed(1)}% avg
          </span>
        )}
        {record.proven_since && (
          <span className="text-emerald-500/70">Since {record.proven_since}</span>
        )}
      </div>
    </div>
  );
}
