"use client";

import { useState } from "react";
import { calculateSip, type SipResult } from "@/lib/api";

export default function SipCalculatorPage() {
  const [symbol, setSymbol] = useState("");
  const [amount, setAmount] = useState(100000);
  const [months, setMonths] = useState(36);
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<SipResult | null>(null);
  const [error, setError] = useState("");

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!symbol.trim()) return;
    setLoading(true);
    setError("");
    setResult(null);
    try {
      const r = await calculateSip(symbol.trim().toUpperCase(), amount, months);
      setResult(r);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Calculation failed");
    } finally {
      setLoading(false);
    }
  }

  const regimeColor: Record<string, string> = {
    low: "text-emerald-400 border-emerald-500/30 bg-emerald-500/10",
    moderate: "text-amber-400 border-amber-500/30 bg-amber-500/10",
    high: "text-rose-400 border-rose-500/30 bg-rose-500/10",
  };

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-xl font-bold text-slate-100">SIP / STP Calculator</h1>
        <p className="text-sm text-slate-500 mt-1">
          Should you invest lump sum or stagger via SIP? Get a data-driven recommendation based on volatility regime.
        </p>
      </div>

      <form onSubmit={handleSubmit} className="glass-card p-5 space-y-4">
        <div>
          <label className="block text-sm text-slate-400 mb-1">Stock / ETF / MF Symbol</label>
          <input
            type="text"
            value={symbol}
            onChange={(e) => setSymbol(e.target.value)}
            required
            placeholder="e.g. NIFTYBEES, RELIANCE, SPY, AAPL"
            className="w-full px-3 py-2 bg-slate-950 border border-slate-800 rounded-lg text-slate-100 focus:outline-none focus:border-emerald-500"
          />
        </div>
        <div className="grid grid-cols-2 gap-4">
          <div>
            <label className="block text-sm text-slate-400 mb-1">Investment Amount (₹)</label>
            <input
              type="number"
              value={amount}
              onChange={(e) => setAmount(Number(e.target.value))}
              min={1000}
              step={1000}
              className="w-full px-3 py-2 bg-slate-950 border border-slate-800 rounded-lg text-slate-100 focus:outline-none focus:border-emerald-500"
            />
          </div>
          <div>
            <label className="block text-sm text-slate-400 mb-1">SIP Duration (months)</label>
            <input
              type="number"
              value={months}
              onChange={(e) => setMonths(Number(e.target.value))}
              min={1}
              max={120}
              className="w-full px-3 py-2 bg-slate-950 border border-slate-800 rounded-lg text-slate-100 focus:outline-none focus:border-emerald-500"
            />
          </div>
        </div>
        <button
          type="submit"
          disabled={loading}
          className="w-full py-2.5 bg-emerald-600 hover:bg-emerald-500 disabled:opacity-50 text-white font-medium rounded-lg transition-colors"
        >
          {loading ? "Analyzing..." : "Calculate"}
        </button>
      </form>

      {error && (
        <div className="glass-card p-4 text-sm text-rose-300">{error}</div>
      )}

      {result && (
        <div className="glass-card p-5 space-y-4 fade-in">
          {result.error ? (
            <p className="text-amber-300 text-sm">{result.error}</p>
          ) : (
            <>
              {/* Recommendation */}
              <div className="flex items-start justify-between">
                <div>
                  <div className="text-sm text-slate-400">Symbol</div>
                  <div className="text-lg font-bold text-slate-100">{result.symbol}</div>
                </div>
                <span className={`text-xs font-bold rounded border px-2 py-1 ${regimeColor[result.regime] || ""}`}>
                  {result.regime.toUpperCase()} VOL
                </span>
              </div>

              <div className="bg-slate-900/50 rounded-lg p-4">
                <div className="text-[10px] text-slate-400 uppercase mb-1">Recommendation</div>
                <div className="text-base font-semibold text-emerald-400">{result.recommendation}</div>
                <p className="text-xs text-slate-400 mt-2 leading-relaxed">{result.rationale}</p>
              </div>

              {/* Deployment plan */}
              <div className="grid grid-cols-2 gap-3">
                <div className="bg-slate-900/50 rounded-lg p-3 text-center">
                  <div className="text-[10px] text-slate-400 uppercase">Lump Sum Now</div>
                  <div className="text-lg font-bold text-sky-400 tabular-nums">{result.lump_sum_pct}%</div>
                </div>
                <div className="bg-slate-900/50 rounded-lg p-3 text-center">
                  <div className="text-[10px] text-slate-400 uppercase">STP Over</div>
                  <div className="text-lg font-bold text-amber-400 tabular-nums">{result.sip_months} months</div>
                </div>
              </div>

              {/* Risk metrics */}
              <div className="grid grid-cols-3 gap-2">
                <div className="text-center">
                  <div className="text-[10px] text-slate-400 uppercase">Volatility</div>
                  <div className="text-sm font-medium tabular-nums text-slate-300">{(result.volatility * 100).toFixed(1)}%</div>
                </div>
                <div className="text-center">
                  <div className="text-[10px] text-slate-400 uppercase">CAGR</div>
                  <div className="text-sm font-medium tabular-nums text-emerald-400">{(result.cagr * 100).toFixed(1)}%</div>
                </div>
                <div className="text-center">
                  <div className="text-[10px] text-slate-400 uppercase">Max DD</div>
                  <div className="text-sm font-medium tabular-nums text-rose-400">{(result.max_drawdown * 100).toFixed(1)}%</div>
                </div>
              </div>

              {/* Backtest comparison */}
              {result.backtest && (
                <div className="border-t border-slate-800/50 pt-4">
                  <h3 className="text-sm font-semibold text-slate-300 mb-3">
                    Backtest: Past {result.backtest.period_months} months
                  </h3>
                  <div className="grid grid-cols-2 gap-3">
                    <div className={`rounded-lg p-3 text-center border ${
                      result.backtest.better === "lump_sum"
                        ? "border-emerald-500/30 bg-emerald-500/10"
                        : "border-slate-700/50 bg-slate-900/50"
                    }`}>
                      <div className="text-[10px] text-slate-400 uppercase">Lump Sum P&L</div>
                      <div className={`text-lg font-bold tabular-nums ${result.backtest.lump_sum_pnl_pct >= 0 ? "text-emerald-400" : "text-rose-400"}`}>
                        {result.backtest.lump_sum_pnl_pct > 0 ? "+" : ""}{result.backtest.lump_sum_pnl_pct.toFixed(1)}%
                      </div>
                      {result.backtest.better === "lump_sum" && (
                        <div className="text-[10px] text-emerald-400 mt-1">WINNER</div>
                      )}
                    </div>
                    <div className={`rounded-lg p-3 text-center border ${
                      result.backtest.better === "sip"
                        ? "border-emerald-500/30 bg-emerald-500/10"
                        : "border-slate-700/50 bg-slate-900/50"
                    }`}>
                      <div className="text-[10px] text-slate-400 uppercase">SIP P&L</div>
                      <div className={`text-lg font-bold tabular-nums ${result.backtest.sip_pnl_pct >= 0 ? "text-emerald-400" : "text-rose-400"}`}>
                        {result.backtest.sip_pnl_pct > 0 ? "+" : ""}{result.backtest.sip_pnl_pct.toFixed(1)}%
                      </div>
                      {result.backtest.better === "sip" && (
                        <div className="text-[10px] text-emerald-400 mt-1">WINNER</div>
                      )}
                    </div>
                  </div>
                  <p className="text-[10px] text-slate-500 mt-2">
                    {result.backtest.better === "lump_sum" ? "Lump sum" : "SIP"} would have been better by {result.backtest.advantage_pct.toFixed(1)}% over this period. Past performance doesn't guarantee future results.
                  </p>
                </div>
              )}
            </>
          )}
        </div>
      )}
    </div>
  );
}
