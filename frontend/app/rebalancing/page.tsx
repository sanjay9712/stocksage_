"use client";

import { useState } from "react";
import { computeRebalancing, type RebalancingResult } from "@/lib/api";

const METHODS = [
  { value: "equal_weight", label: "Equal Weight", desc: "Same % in each position" },
  { value: "risk_parity", label: "Risk Parity", desc: "Inverse volatility weighting" },
  { value: "custom", label: "Custom", desc: "Set your own target weights" },
] as const;

export default function RebalancingPage() {
  const [method, setMethod] = useState<string>("equal_weight");
  const [threshold, setThreshold] = useState(5.0);
  const [result, setResult] = useState<RebalancingResult | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleRun = async () => {
    setLoading(true);
    setError(null);
    setResult(null);
    try {
      const res = await computeRebalancing({
        method: method as "equal_weight" | "custom" | "risk_parity",
        threshold_pct: threshold,
      });
      setResult(res);
    } catch (e: any) {
      setError(e.message || "Failed to compute rebalancing");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-xl font-bold text-slate-100">Portfolio Rebalancing</h1>
        <p className="text-sm text-slate-500 mt-1">
          Compare your current allocation against a target and get buy/sell suggestions to rebalance.
        </p>
      </div>

      {/* Config */}
      <div className="glass-card p-4 space-y-4">
        <div>
          <label className="text-xs text-slate-500 block mb-2">Rebalancing Method</label>
          <div className="flex gap-2">
            {METHODS.map((m) => (
              <button
                key={m.value}
                onClick={() => setMethod(m.value)}
                className={`px-3 py-1.5 rounded-lg text-xs font-medium ${
                  method === m.value ? "bg-emerald-600 text-white" : "bg-slate-800 text-slate-400 hover:bg-slate-700"
                }`}
              >
                {m.label}
              </button>
            ))}
          </div>
          <p className="text-[10px] text-slate-600 mt-1">
            {METHODS.find((m) => m.value === method)?.desc}
          </p>
        </div>
        <div>
          <label className="text-xs text-slate-500 block mb-1">Rebalance Threshold: {threshold}%</label>
          <input
            type="range"
            min={1}
            max={20}
            step={0.5}
            value={threshold}
            onChange={(e) => setThreshold(parseFloat(e.target.value))}
            className="w-full accent-emerald-500"
          />
          <p className="text-[10px] text-slate-600 mt-1">Only suggest trades for positions drifting more than this from target.</p>
        </div>
        <div className="flex justify-end">
          <button
            onClick={handleRun}
            disabled={loading}
            className="px-6 py-2 bg-emerald-600 hover:bg-emerald-500 disabled:opacity-50 text-white rounded-lg text-sm font-medium"
          >
            {loading ? "Analyzing..." : "Compute Rebalancing"}
          </button>
        </div>
      </div>

      {error && <div className="glass-card p-4 text-center"><p className="text-rose-300 text-sm">{error}</p></div>}

      {result?.error && <div className="glass-card p-8 text-center"><p className="text-amber-300 text-sm">{result.error}</p></div>}

      {result && !result.error && (
        <>
          {/* Summary */}
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
            <div className="glass-card p-3">
              <div className="text-xs text-slate-500">Portfolio Value</div>
              <div className="text-lg font-bold text-slate-200 tabular-nums">
                ₹{result.total_value.toLocaleString("en-IN")}
              </div>
            </div>
            <div className="glass-card p-3">
              <div className="text-xs text-slate-500">Max Drift</div>
              <div className={`text-lg font-bold tabular-nums ${result.max_drift_pct >= threshold ? "text-rose-400" : "text-emerald-400"}`}>
                {result.max_drift_pct.toFixed(1)}%
              </div>
            </div>
            <div className="glass-card p-3">
              <div className="text-xs text-slate-500">Buy Value</div>
              <div className="text-lg font-bold text-emerald-400 tabular-nums">
                ₹{result.total_buy_value.toLocaleString("en-IN")}
              </div>
            </div>
            <div className="glass-card p-3">
              <div className="text-xs text-slate-500">Sell Value</div>
              <div className="text-lg font-bold text-rose-400 tabular-nums">
                ₹{result.total_sell_value.toLocaleString("en-IN")}
              </div>
            </div>
          </div>

          {/* Verdict */}
          <div className={`glass-card p-4 text-center ${result.needs_rebalancing ? "border-amber-700/40" : "border-emerald-700/40"}`}>
            <span className={`text-sm font-semibold ${result.needs_rebalancing ? "text-amber-400" : "text-emerald-400"}`}>
              {result.needs_rebalancing
                ? `Rebalancing needed — ${result.trades.length} trades to reach ${result.method.replace("_", " ")} target`
                : "Portfolio is within threshold — no rebalancing needed"}
            </span>
            {result.needs_rebalancing && (
              <div className="text-xs text-slate-500 mt-1">
                Net trade value: ₹{result.net_trade_value.toLocaleString("en-IN")}
              </div>
            )}
          </div>

          {/* Trade Suggestions */}
          {result.trades.length > 0 && (
            <div className="glass-card overflow-x-auto">
              <div className="text-sm font-semibold text-slate-300 p-4 pb-2">Suggested Trades</div>
              <table className="w-full text-xs">
                <thead>
                  <tr className="text-slate-500 border-b border-slate-800">
                    <th className="px-3 py-2 text-left font-medium">Symbol</th>
                    <th className="px-3 py-2 text-left font-medium">Action</th>
                    <th className="px-3 py-2 text-right font-medium">Shares</th>
                    <th className="px-3 py-2 text-right font-medium">Value</th>
                    <th className="px-3 py-2 text-right font-medium">Current Weight</th>
                    <th className="px-3 py-2 text-right font-medium">Target Weight</th>
                    <th className="px-3 py-2 text-right font-medium">Drift</th>
                  </tr>
                </thead>
                <tbody>
                  {result.trades.map((t) => (
                    <tr key={t.symbol} className="border-b border-slate-800/40 hover:bg-slate-800/30">
                      <td className="px-3 py-2.5 text-slate-200 font-medium">{t.symbol}</td>
                      <td className={`px-3 py-2.5 font-semibold ${t.action === "buy" ? "text-emerald-400" : "text-rose-400"}`}>
                        {t.action.toUpperCase()}
                      </td>
                      <td className="px-3 py-2.5 text-right tabular-nums text-slate-300">{t.shares}</td>
                      <td className="px-3 py-2.5 text-right tabular-nums text-slate-300">
                        ₹{t.value.toLocaleString("en-IN")}
                      </td>
                      <td className="px-3 py-2.5 text-right tabular-nums text-slate-400">{t.current_weight.toFixed(1)}%</td>
                      <td className="px-3 py-2.5 text-right tabular-nums text-slate-300">{t.target_weight.toFixed(1)}%</td>
                      <td className={`px-3 py-2.5 text-right tabular-nums font-semibold ${t.drift_pct >= 0 ? "text-emerald-400" : "text-rose-400"}`}>
                        {t.drift_pct >= 0 ? "+" : ""}{t.drift_pct.toFixed(1)}%
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}

          {/* Full Position Breakdown */}
          <div className="glass-card overflow-x-auto">
            <div className="text-sm font-semibold text-slate-300 p-4 pb-2">All Positions</div>
            <table className="w-full text-xs">
              <thead>
                <tr className="text-slate-500 border-b border-slate-800">
                  <th className="px-3 py-2 text-left font-medium">Symbol</th>
                  <th className="px-3 py-2 text-right font-medium">Value</th>
                  <th className="px-3 py-2 text-right font-medium">Current</th>
                  <th className="px-3 py-2 text-right font-medium">Target</th>
                  <th className="px-3 py-2 text-right font-medium">Drift</th>
                  <th className="px-3 py-2 text-left font-medium">Action</th>
                </tr>
              </thead>
              <tbody>
                {result.positions.map((p) => (
                  <tr key={p.symbol} className={`border-b border-slate-800/40 ${p.needs_rebalance ? "bg-amber-900/5" : ""}`}>
                    <td className="px-3 py-2.5 text-slate-200 font-medium">{p.symbol}</td>
                    <td className="px-3 py-2.5 text-right tabular-nums text-slate-300">
                      ₹{p.current_value.toLocaleString("en-IN")}
                    </td>
                    <td className="px-3 py-2.5 text-right tabular-nums text-slate-400">
                      {(p.current_weight * 100).toFixed(1)}%
                    </td>
                    <td className="px-3 py-2.5 text-right tabular-nums text-slate-300">
                      {(p.target_weight * 100).toFixed(1)}%
                    </td>
                    <td className={`px-3 py-2.5 text-right tabular-nums font-semibold ${p.needs_rebalance ? "text-amber-400" : "text-slate-500"}`}>
                      {p.drift_pct >= 0 ? "+" : ""}{p.drift_pct.toFixed(1)}%
                    </td>
                    <td className="px-3 py-2.5">
                      {p.needs_rebalance ? (
                        <span className={`text-xs font-medium ${p.action === "buy" ? "text-emerald-400" : "text-rose-400"}`}>
                          {p.action.toUpperCase()} {p.trade_shares} shares
                        </span>
                      ) : (
                        <span className="text-xs text-slate-600">OK</span>
                      )}
                    </td>
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
