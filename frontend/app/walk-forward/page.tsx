"use client";

import { useState } from "react";
import { runWalkForward, type WalkForwardResult, type WalkForwardRequest } from "@/lib/api";

const STRATEGIES = [
  { value: "ema_crossover", label: "EMA Crossover" },
  { value: "rsi_reversion", label: "RSI Mean Reversion" },
  { value: "bollinger", label: "Bollinger Bands" },
  { value: "breakout", label: "Donchian Breakout" },
];

const verdictConfig: Record<string, { color: string; label: string }> = {
  robust: { color: "text-emerald-400", label: "Robust — strategy generalizes well" },
  moderate: { color: "text-amber-400", label: "Moderate — some overfitting risk" },
  fragile: { color: "text-orange-400", label: "Fragile — likely overfit" },
  overfit: { color: "text-rose-400", label: "Overfit — do not trade live" },
};

export default function WalkForwardPage() {
  const [symbol, setSymbol] = useState("SPY");
  const [strategy, setStrategy] = useState("ema_crossover");
  const [days, setDays] = useState(730);
  const [numWindows, setNumWindows] = useState(5);
  const [inSamplePct, setInSamplePct] = useState(0.7);
  const [result, setResult] = useState<WalkForwardResult | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleRun = async () => {
    setLoading(true);
    setError(null);
    setResult(null);
    try {
      const req: WalkForwardRequest = {
        symbol: symbol.toUpperCase(),
        strategy: strategy as WalkForwardRequest["strategy"],
        days,
        in_sample_pct: inSamplePct,
        num_windows: numWindows,
        initial_capital: 100000,
      };
      const res = await runWalkForward(req);
      setResult(res);
    } catch (e: any) {
      setError(e.message || "Failed to run walk-forward analysis");
    } finally {
      setLoading(false);
    }
  };

  const verdict = result?.summary?.verdict ? verdictConfig[result.summary.verdict] : null;

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-xl font-bold text-slate-100">Walk-Forward Optimization</h1>
        <p className="text-sm text-slate-500 mt-1">
          Test strategy robustness — optimize on in-sample windows, validate out-of-sample. Detects overfitting.
        </p>
      </div>

      {/* Config */}
      <div className="glass-card p-4 space-y-4">
        <div className="grid grid-cols-1 sm:grid-cols-4 gap-3">
          <div>
            <label className="text-xs text-slate-500 block mb-1">Symbol</label>
            <input
              type="text"
              value={symbol}
              onChange={(e) => setSymbol(e.target.value)}
              className="w-full px-3 py-2 bg-slate-800 text-slate-100 rounded-lg text-sm border border-slate-700 focus:border-emerald-500 focus:outline-none"
            />
          </div>
          <div>
            <label className="text-xs text-slate-500 block mb-1">Strategy</label>
            <select
              value={strategy}
              onChange={(e) => setStrategy(e.target.value)}
              className="w-full px-3 py-2 bg-slate-800 text-slate-100 rounded-lg text-sm border border-slate-700"
            >
              {STRATEGIES.map((s) => <option key={s.value} value={s.value}>{s.label}</option>)}
            </select>
          </div>
          <div>
            <label className="text-xs text-slate-500 block mb-1">Period (days)</label>
            <select
              value={days}
              onChange={(e) => setDays(parseInt(e.target.value))}
              className="w-full px-3 py-2 bg-slate-800 text-slate-100 rounded-lg text-sm border border-slate-700"
            >
              <option value={365}>1 year</option>
              <option value={730}>2 years</option>
              <option value={1095}>3 years</option>
            </select>
          </div>
          <div>
            <label className="text-xs text-slate-500 block mb-1">Windows</label>
            <select
              value={numWindows}
              onChange={(e) => setNumWindows(parseInt(e.target.value))}
              className="w-full px-3 py-2 bg-slate-800 text-slate-100 rounded-lg text-sm border border-slate-700"
            >
              {[3, 4, 5, 6, 8, 10].map((n) => <option key={n} value={n}>{n}</option>)}
            </select>
          </div>
        </div>
        <div className="flex items-center gap-4">
          <div className="flex-1">
            <label className="text-xs text-slate-500 block mb-1">In-Sample %: {Math.round(inSamplePct * 100)}%</label>
            <input
              type="range"
              min={0.5}
              max={0.9}
              step={0.05}
              value={inSamplePct}
              onChange={(e) => setInSamplePct(parseFloat(e.target.value))}
              className="w-full accent-emerald-500"
            />
          </div>
          <button
            onClick={handleRun}
            disabled={loading}
            className="self-end px-6 py-2 bg-emerald-600 hover:bg-emerald-500 disabled:opacity-50 text-white rounded-lg text-sm font-medium"
          >
            {loading ? "Analyzing..." : "Run Analysis"}
          </button>
        </div>
      </div>

      {error && <div className="glass-card p-4 text-center"><p className="text-rose-300 text-sm">{error}</p></div>}

      {result?.error && <div className="glass-card p-8 text-center"><p className="text-amber-300 text-sm">{result.error}</p></div>}

      {result && !result.error && result.windows.length > 0 && (
        <>
          {/* Summary */}
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
            <div className="glass-card p-3">
              <div className="text-xs text-slate-500">Avg IS Return</div>
              <div className={`text-lg font-bold tabular-nums ${result.summary.avg_in_sample_return >= 0 ? "text-emerald-400" : "text-rose-400"}`}>
                {result.summary.avg_in_sample_return >= 0 ? "+" : ""}{result.summary.avg_in_sample_return.toFixed(1)}%
              </div>
            </div>
            <div className="glass-card p-3">
              <div className="text-xs text-slate-500">Avg OOS Return</div>
              <div className={`text-lg font-bold tabular-nums ${result.summary.avg_out_of_sample_return >= 0 ? "text-emerald-400" : "text-rose-400"}`}>
                {result.summary.avg_out_of_sample_return >= 0 ? "+" : ""}{result.summary.avg_out_of_sample_return.toFixed(1)}%
              </div>
            </div>
            <div className="glass-card p-3">
              <div className="text-xs text-slate-500">WFE (Efficiency)</div>
              <div className="text-lg font-bold text-amber-400 tabular-nums">{result.summary.walk_forward_efficiency.toFixed(0)}%</div>
            </div>
            <div className="glass-card p-3">
              <div className="text-xs text-slate-500">Consistency</div>
              <div className="text-lg font-bold text-sky-400 tabular-nums">{result.summary.consistency_pct.toFixed(0)}%</div>
            </div>
          </div>

          {/* Verdict */}
          {verdict && (
            <div className="glass-card p-4 text-center">
              <span className={`text-sm font-semibold ${verdict.color}`}>
                {result.summary.verdict.toUpperCase()} — {verdict.label}
              </span>
              <div className="text-xs text-slate-500 mt-1">
                {result.summary.profitable_windows}/{result.summary.total_windows} windows profitable out-of-sample
              </div>
            </div>
          )}

          {/* Window results */}
          <div className="glass-card overflow-x-auto">
            <div className="text-sm font-semibold text-slate-300 p-4 pb-2">Window-by-Window Results</div>
            <table className="w-full text-xs">
              <thead>
                <tr className="text-slate-500 border-b border-slate-800">
                  <th className="px-2 py-2 text-center font-medium">#</th>
                  <th className="px-2 py-2 text-left font-medium">Best Params</th>
                  <th className="px-2 py-2 text-right font-medium">IS Return</th>
                  <th className="px-2 py-2 text-right font-medium">IS Sharpe</th>
                  <th className="px-2 py-2 text-right font-medium">OOS Return</th>
                  <th className="px-2 py-2 text-right font-medium">OOS Sharpe</th>
                  <th className="px-2 py-2 text-right font-medium">OOS Max DD</th>
                  <th className="px-2 py-2 text-right font-medium">OOS Trades</th>
                </tr>
              </thead>
              <tbody>
                {result.windows.map((w) => (
                  <tr key={w.window} className="border-b border-slate-800/40 hover:bg-slate-800/30">
                    <td className="px-2 py-2.5 text-center text-slate-500">{w.window}</td>
                    <td className="px-2 py-2.5 text-slate-400 text-[10px]">
                      {Object.entries(w.best_params).map(([k, v]) => `${k}=${v}`).join(", ")}
                    </td>
                    <td className={`px-2 py-2.5 text-right tabular-nums ${w.in_sample_return >= 0 ? "text-emerald-400" : "text-rose-400"}`}>
                      {w.in_sample_return >= 0 ? "+" : ""}{w.in_sample_return.toFixed(1)}%
                    </td>
                    <td className="px-2 py-2.5 text-right tabular-nums text-slate-300">{w.in_sample_sharpe.toFixed(2)}</td>
                    <td className={`px-2 py-2.5 text-right tabular-nums font-bold ${w.out_of_sample_return >= 0 ? "text-emerald-400" : "text-rose-400"}`}>
                      {w.out_of_sample_return >= 0 ? "+" : ""}{w.out_of_sample_return.toFixed(1)}%
                    </td>
                    <td className="px-2 py-2.5 text-right tabular-nums text-slate-300">{w.out_of_sample_sharpe.toFixed(2)}</td>
                    <td className="px-2 py-2.5 text-right tabular-nums text-rose-400">{w.out_of_sample_max_dd.toFixed(1)}%</td>
                    <td className="px-2 py-2.5 text-right tabular-nums text-slate-500">{w.out_of_sample_trades}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </>
      )}
    </div>
  );
}
