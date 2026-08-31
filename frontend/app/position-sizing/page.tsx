"use client";

import { useState } from "react";
import { computePositionSize, type PositionSizingResult } from "@/lib/api";

const STRATEGIES = [
  { value: "ema_crossover", label: "EMA Crossover", defaultParams: { fast_period: 9, slow_period: 21 } },
  { value: "rsi_reversion", label: "RSI Mean Reversion", defaultParams: { rsi_period: 14, oversold: 30, overbought: 70 } },
  { value: "bollinger", label: "Bollinger Bands", defaultParams: { bb_period: 20, bb_std: 2.0 } },
  { value: "breakout", label: "Donchian Breakout", defaultParams: { lookback: 20 } },
] as const;

const methodLabels: Record<string, string> = {
  half_kelly: "Half Kelly (Recommended)",
  inverse_volatility: "Inverse Volatility",
  fixed_fractional: "Fixed Fractional",
};

export default function PositionSizingPage() {
  const [symbol, setSymbol] = useState("SPY");
  const [strategy, setStrategy] = useState("ema_crossover");
  const [capital, setCapital] = useState(100000);
  const [entryPrice, setEntryPrice] = useState(450);
  const [stopPrice, setStopPrice] = useState(440);
  const [riskPct, setRiskPct] = useState(2.0);
  const [days, setDays] = useState(730);
  const [result, setResult] = useState<PositionSizingResult | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleRun = async () => {
    setLoading(true);
    setError(null);
    setResult(null);
    try {
      const def = STRATEGIES.find((s) => s.value === strategy)!;
      const res = await computePositionSize({
        symbol: symbol.toUpperCase(),
        strategy: strategy as PositionSizingResult["strategy"] extends never ? never : any,
        capital,
        entry_price: entryPrice,
        stop_price: stopPrice,
        risk_pct: riskPct,
        days,
        params: { ...def.defaultParams } as Record<string, number>,
      });
      setResult(res);
    } catch (e: any) {
      setError(e.message || "Failed to compute position size");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-xl font-bold text-slate-100">Position Sizing (Kelly Criterion)</h1>
        <p className="text-sm text-slate-500 mt-1">
          Calculate optimal position sizes based on your strategy&apos;s historical edge.
          Uses Kelly Criterion, fixed-fractional risk, and inverse-volatility methods.
        </p>
      </div>

      {/* Config */}
      <div className="glass-card p-4 space-y-4">
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
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
            <label className="text-xs text-slate-500 block mb-1">Capital ($)</label>
            <input
              type="number"
              value={capital}
              onChange={(e) => setCapital(parseFloat(e.target.value) || 100000)}
              className="w-full px-3 py-2 bg-slate-800 text-slate-100 rounded-lg text-sm border border-slate-700 focus:border-emerald-500 focus:outline-none"
            />
          </div>
          <div>
            <label className="text-xs text-slate-500 block mb-1">History (days)</label>
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
        </div>
        <div className="grid grid-cols-2 sm:grid-cols-3 gap-3">
          <div>
            <label className="text-xs text-slate-500 block mb-1">Entry Price</label>
            <input
              type="number"
              step="0.01"
              value={entryPrice}
              onChange={(e) => setEntryPrice(parseFloat(e.target.value) || 0)}
              className="w-full px-3 py-2 bg-slate-800 text-slate-100 rounded-lg text-sm border border-slate-700 focus:border-emerald-500 focus:outline-none"
            />
          </div>
          <div>
            <label className="text-xs text-slate-500 block mb-1">Stop Price</label>
            <input
              type="number"
              step="0.01"
              value={stopPrice}
              onChange={(e) => setStopPrice(parseFloat(e.target.value) || 0)}
              className="w-full px-3 py-2 bg-slate-800 text-slate-100 rounded-lg text-sm border border-slate-700 focus:border-emerald-500 focus:outline-none"
            />
          </div>
          <div>
            <label className="text-xs text-slate-500 block mb-1">Risk per Trade: {riskPct}%</label>
            <input
              type="range"
              min={0.5}
              max={10}
              step={0.5}
              value={riskPct}
              onChange={(e) => setRiskPct(parseFloat(e.target.value))}
              className="w-full accent-emerald-500"
            />
          </div>
        </div>
        <div className="flex justify-end">
          <button
            onClick={handleRun}
            disabled={loading}
            className="px-6 py-2 bg-emerald-600 hover:bg-emerald-500 disabled:opacity-50 text-white rounded-lg text-sm font-medium"
          >
            {loading ? "Calculating..." : "Calculate Position Size"}
          </button>
        </div>
      </div>

      {error && <div className="glass-card p-4 text-center"><p className="text-rose-300 text-sm">{error}</p></div>}

      {result?.error && <div className="glass-card p-8 text-center"><p className="text-amber-300 text-sm">{result.error}</p></div>}

      {result && !result.error && (
        <>
          {/* Recommended Position */}
          <div className="glass-card p-5 border border-emerald-700/40">
            <div className="flex items-center justify-between">
              <div>
                <div className="text-xs text-slate-500">Recommended Position</div>
                <div className="text-2xl font-bold text-emerald-400 tabular-nums">
                  {result.recommended.shares.toLocaleString()} shares
                </div>
                <div className="text-xs text-slate-400 mt-1">
                  {result.recommended.dollar_amount.toLocaleString()} invested · {result.recommended.pct_of_capital.toFixed(1)}% of capital
                </div>
              </div>
              <div className="text-right">
                <div className="text-xs text-slate-500">Method</div>
                <div className="text-sm font-semibold text-sky-400">
                  {methodLabels[result.recommended.method] || result.recommended.method}
                </div>
                <div className="text-xs text-slate-500 mt-2">Risk per Trade</div>
                <div className="text-sm text-slate-300">${result.risk.risk_dollar.toLocaleString()} ({result.risk.risk_pct_of_capital}%)</div>
              </div>
            </div>
          </div>

          {/* Kelly Stats */}
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
            <div className="glass-card p-3">
              <div className="text-xs text-slate-500">Win Rate</div>
              <div className="text-lg font-bold text-slate-200 tabular-nums">{(result.win_rate * 100).toFixed(1)}%</div>
            </div>
            <div className="glass-card p-3">
              <div className="text-xs text-slate-500">Payoff Ratio</div>
              <div className="text-lg font-bold text-slate-200 tabular-nums">{result.payoff_ratio.toFixed(2)}</div>
            </div>
            <div className="glass-card p-3">
              <div className="text-xs text-slate-500">Kelly Fraction</div>
              <div className="text-lg font-bold text-amber-400 tabular-nums">{(result.kelly_fraction * 100).toFixed(1)}%</div>
            </div>
            <div className="glass-card p-3">
              <div className="text-xs text-slate-500">Risk / Share</div>
              <div className="text-lg font-bold text-rose-400 tabular-nums">${result.risk_per_share.toFixed(2)}</div>
            </div>
          </div>

          {/* Sizing Methods Comparison */}
          <div className="glass-card overflow-x-auto">
            <div className="text-sm font-semibold text-slate-300 p-4 pb-2">Position Sizing Methods</div>
            <table className="w-full text-xs">
              <thead>
                <tr className="text-slate-500 border-b border-slate-800">
                  <th className="px-3 py-2 text-left font-medium">Method</th>
                  <th className="px-3 py-2 text-right font-medium">% of Capital</th>
                  <th className="px-3 py-2 text-right font-medium">Shares</th>
                  <th className="px-3 py-2 text-right font-medium">$ Invested</th>
                  <th className="px-3 py-2 text-right font-medium">Est. Annual Growth</th>
                  <th className="px-3 py-2 text-right font-medium">Est. Max DD</th>
                </tr>
              </thead>
              <tbody>
                {[
                  { name: "Full Kelly", pct: result.sizing_methods.full_kelly_pct, danger: true },
                  { name: "Half Kelly", pct: result.sizing_methods.half_kelly_pct, recommended: result.recommended.method === "half_kelly" },
                  { name: "Quarter Kelly", pct: result.sizing_methods.quarter_kelly_pct },
                  { name: "Fixed Fractional", pct: result.sizing_methods.fixed_fractional_pct, recommended: result.recommended.method === "fixed_fractional" },
                  { name: "Inverse Volatility", pct: result.sizing_methods.inverse_volatility_pct, recommended: result.recommended.method === "inverse_volatility" },
                ].map((m) => {
                  const dollar = capital * (m.pct / 100);
                  const shares = entryPrice > 0 ? Math.floor(dollar / entryPrice) : 0;
                  return (
                    <tr key={m.name} className={`border-b border-slate-800/40 hover:bg-slate-800/30 ${m.recommended ? "bg-emerald-900/10" : ""}`}>
                      <td className="px-3 py-2.5 text-slate-300">
                        {m.name}
                        {m.recommended && <span className="ml-2 text-[10px] text-emerald-400 font-semibold">RECOMMENDED</span>}
                        {m.danger && <span className="ml-2 text-[10px] text-rose-400">⚠ Aggressive</span>}
                      </td>
                      <td className="px-3 py-2.5 text-right tabular-nums text-slate-300">{m.pct.toFixed(1)}%</td>
                      <td className="px-3 py-2.5 text-right tabular-nums text-slate-300">{shares.toLocaleString()}</td>
                      <td className="px-3 py-2.5 text-right tabular-nums text-slate-300">${dollar.toLocaleString()}</td>
                      <td className="px-3 py-2.5 text-right tabular-nums text-emerald-400">~{result.estimates.annual_growth_pct.toFixed(1)}%</td>
                      <td className="px-3 py-2.5 text-right tabular-nums text-rose-400">~{result.estimates.max_drawdown_pct.toFixed(1)}%</td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>

          {/* Trade Statistics */}
          <div className="glass-card p-4">
            <div className="text-sm font-semibold text-slate-300 mb-3">Historical Trade Statistics</div>
            <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
              <div>
                <div className="text-xs text-slate-500">Avg Win</div>
                <div className="text-sm font-semibold text-emerald-400 tabular-nums">+{result.avg_win_pct.toFixed(1)}%</div>
              </div>
              <div>
                <div className="text-xs text-slate-500">Avg Loss</div>
                <div className="text-sm font-semibold text-rose-400 tabular-nums">-{result.avg_loss_pct.toFixed(1)}%</div>
              </div>
              <div>
                <div className="text-xs text-slate-500">Historical Sharpe</div>
                <div className="text-sm font-semibold text-sky-400 tabular-nums">{result.historical.sharpe.toFixed(2)}</div>
              </div>
              <div>
                <div className="text-xs text-slate-500">Total Trades</div>
                <div className="text-sm font-semibold text-slate-300 tabular-nums">{result.historical.trades}</div>
              </div>
            </div>
          </div>

          {/* Disclaimer */}
          <div className="glass-card p-3">
            <p className="text-xs text-slate-500 text-center">
              ⚠ Kelly estimates are based on historical backtest and assume future performance mirrors the past.
              Half-Kelly is recommended to reduce drawdowns. Never risk more than you can afford to lose.
            </p>
          </div>
        </>
      )}
    </div>
  );
}
