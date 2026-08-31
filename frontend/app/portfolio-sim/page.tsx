"use client";

import { useState } from "react";
import { runPortfolioSim, type PortfolioSimResult, type PortfolioStrategyConfig } from "@/lib/api";

const ALL_STRATEGIES = [
  { value: "ema_crossover", label: "EMA Crossover", defaultParams: { fast: 9, slow: 21 } },
  { value: "rsi_reversion", label: "RSI Mean Reversion", defaultParams: { period: 14, oversold: 30, overbought: 70 } },
  { value: "bollinger", label: "Bollinger Bands", defaultParams: { period: 20, std: 2.0 } },
  { value: "breakout", label: "Donchian Breakout", defaultParams: { period: 20 } },
] as const;

export default function PortfolioSimPage() {
  const [symbol, setSymbol] = useState("SPY");
  const [days, setDays] = useState(730);
  const [initialCapital, setInitialCapital] = useState(100000);
  const [selected, setSelected] = useState<string[]>(["ema_crossover", "rsi_reversion", "bollinger"]);
  const [result, setResult] = useState<PortfolioSimResult | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const toggleStrategy = (value: string) => {
    setSelected((prev) =>
      prev.includes(value) ? prev.filter((s) => s !== value) : [...prev, value]
    );
  };

  const handleRun = async () => {
    if (selected.length < 2) {
      setError("Select at least 2 strategies to see diversification benefit");
      return;
    }
    setLoading(true);
    setError(null);
    setResult(null);
    try {
      const strategies: PortfolioStrategyConfig[] = selected.map((s) => {
        const def = ALL_STRATEGIES.find((a) => a.value === s)!;
        return {
          strategy: s as PortfolioStrategyConfig["strategy"],
          label: def.label,
          params: { ...def.defaultParams } as Record<string, number>,
        };
      });
      const res = await runPortfolioSim({
        symbol: symbol.toUpperCase(),
        strategies,
        days,
        initial_capital: initialCapital,
      });
      setResult(res);
    } catch (e: any) {
      setError(e.message || "Failed to run portfolio simulation");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-xl font-bold text-slate-100">Multi-Strategy Portfolio Simulation</h1>
        <p className="text-sm text-slate-500 mt-1">
          Run multiple strategies on the same symbol with equal capital allocation. See how diversifying
          across strategies improves risk-adjusted returns vs any single strategy.
        </p>
      </div>

      {/* Config */}
      <div className="glass-card p-4 space-y-4">
        <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
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
            <label className="text-xs text-slate-500 block mb-1">Initial Capital</label>
            <input
              type="number"
              value={initialCapital}
              onChange={(e) => setInitialCapital(parseFloat(e.target.value) || 100000)}
              className="w-full px-3 py-2 bg-slate-800 text-slate-100 rounded-lg text-sm border border-slate-700 focus:border-emerald-500 focus:outline-none"
            />
          </div>
        </div>

        <div>
          <label className="text-xs text-slate-500 block mb-2">Strategies (select 2-6)</label>
          <div className="flex flex-wrap gap-2">
            {ALL_STRATEGIES.map((s) => {
              const active = selected.includes(s.value);
              return (
                <button
                  key={s.value}
                  onClick={() => toggleStrategy(s.value)}
                  className={`px-3 py-1.5 rounded-lg text-xs font-medium transition-colors ${
                    active
                      ? "bg-emerald-600 text-white"
                      : "bg-slate-800 text-slate-400 hover:bg-slate-700"
                  }`}
                >
                  {s.label}
                </button>
              );
            })}
          </div>
        </div>

        <div className="flex justify-end">
          <button
            onClick={handleRun}
            disabled={loading || selected.length < 2}
            className="px-6 py-2 bg-emerald-600 hover:bg-emerald-500 disabled:opacity-50 text-white rounded-lg text-sm font-medium"
          >
            {loading ? "Simulating..." : "Run Simulation"}
          </button>
        </div>
      </div>

      {error && <div className="glass-card p-4 text-center"><p className="text-rose-300 text-sm">{error}</p></div>}

      {result?.error && <div className="glass-card p-8 text-center"><p className="text-amber-300 text-sm">{result.error}</p></div>}

      {result && !result.error && (
        <>
          {/* Portfolio summary */}
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
            <div className="glass-card p-3">
              <div className="text-xs text-slate-500">Portfolio Return</div>
              <div className={`text-lg font-bold tabular-nums ${result.total_return_pct >= 0 ? "text-emerald-400" : "text-rose-400"}`}>
                {result.total_return_pct >= 0 ? "+" : ""}{result.total_return_pct.toFixed(1)}%
              </div>
            </div>
            <div className="glass-card p-3">
              <div className="text-xs text-slate-500">Sharpe Ratio</div>
              <div className="text-lg font-bold text-sky-400 tabular-nums">{result.sharpe_ratio.toFixed(2)}</div>
            </div>
            <div className="glass-card p-3">
              <div className="text-xs text-slate-500">Max Drawdown</div>
              <div className="text-lg font-bold text-rose-400 tabular-nums">{result.max_drawdown_pct.toFixed(1)}%</div>
            </div>
            <div className="glass-card p-3">
              <div className="text-xs text-slate-500">Diversification Benefit</div>
              <div className={`text-lg font-bold tabular-nums ${result.diversification_benefit >= 0 ? "text-emerald-400" : "text-rose-400"}`}>
                {result.diversification_benefit >= 0 ? "+" : ""}{result.diversification_benefit.toFixed(2)}
              </div>
            </div>
          </div>

          {/* Portfolio vs Buy & Hold */}
          <div className="glass-card p-4">
            <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
              <div>
                <div className="text-xs text-slate-500">Buy & Hold</div>
                <div className="text-sm font-semibold text-slate-300 tabular-nums">{result.buy_hold_return_pct.toFixed(1)}%</div>
              </div>
              <div>
                <div className="text-xs text-slate-500">Outperformance</div>
                <div className={`text-sm font-semibold tabular-nums ${result.outperformance_pct >= 0 ? "text-emerald-400" : "text-rose-400"}`}>
                  {result.outperformance_pct >= 0 ? "+" : ""}{result.outperformance_pct.toFixed(1)}%
                </div>
              </div>
              <div>
                <div className="text-xs text-slate-500">CAGR</div>
                <div className="text-sm font-semibold text-slate-300 tabular-nums">{result.cagr_pct.toFixed(1)}%</div>
              </div>
              <div>
                <div className="text-xs text-slate-500">Volatility</div>
                <div className="text-sm font-semibold text-slate-300 tabular-nums">{result.volatility_pct.toFixed(1)}%</div>
              </div>
            </div>
          </div>

          {/* Equity Curve */}
          {result.equity_curve.length > 0 && (
            <div className="glass-card p-4">
              <div className="text-sm font-semibold text-slate-300 mb-3">Combined Equity Curve</div>
              <EquityChart data={result.equity_curve} initial={result.initial_capital} />
            </div>
          )}

          {/* Per-strategy comparison */}
          <div className="glass-card overflow-x-auto">
            <div className="text-sm font-semibold text-slate-300 p-4 pb-2">Per-Strategy Breakdown</div>
            <table className="w-full text-xs">
              <thead>
                <tr className="text-slate-500 border-b border-slate-800">
                  <th className="px-3 py-2 text-left font-medium">Strategy</th>
                  <th className="px-3 py-2 text-right font-medium">Return</th>
                  <th className="px-3 py-2 text-right font-medium">CAGR</th>
                  <th className="px-3 py-2 text-right font-medium">Sharpe</th>
                  <th className="px-3 py-2 text-right font-medium">Max DD</th>
                  <th className="px-3 py-2 text-right font-medium">Win Rate</th>
                  <th className="px-3 py-2 text-right font-medium">Trades</th>
                  <th className="px-3 py-2 text-right font-medium">Final Equity</th>
                </tr>
              </thead>
              <tbody>
                <tr className="border-b-2 border-emerald-800/50 bg-emerald-900/10">
                  <td className="px-3 py-2.5 font-semibold text-emerald-400">PORTFOLIO (combined)</td>
                  <td className={`px-3 py-2.5 text-right tabular-nums font-bold ${result.total_return_pct >= 0 ? "text-emerald-400" : "text-rose-400"}`}>
                    {result.total_return_pct >= 0 ? "+" : ""}{result.total_return_pct.toFixed(1)}%
                  </td>
                  <td className="px-3 py-2.5 text-right tabular-nums text-slate-300">{result.cagr_pct.toFixed(1)}%</td>
                  <td className="px-3 py-2.5 text-right tabular-nums text-sky-400 font-bold">{result.sharpe_ratio.toFixed(2)}</td>
                  <td className="px-3 py-2.5 text-right tabular-nums text-rose-400">{result.max_drawdown_pct.toFixed(1)}%</td>
                  <td className="px-3 py-2.5 text-right tabular-nums text-slate-500">—</td>
                  <td className="px-3 py-2.5 text-right tabular-nums text-slate-500">—</td>
                  <td className="px-3 py-2.5 text-right tabular-nums text-slate-300">{result.final_equity.toLocaleString()}</td>
                </tr>
                {result.strategies.map((s) => (
                  <tr key={s.strategy} className="border-b border-slate-800/40 hover:bg-slate-800/30">
                    <td className="px-3 py-2.5 text-slate-300">
                      {s.label}
                      <span className="text-[10px] text-slate-600 ml-1">
                        ({Object.entries(s.params).map(([k, v]) => `${k}=${v}`).join(", ")})
                      </span>
                    </td>
                    <td className={`px-3 py-2.5 text-right tabular-nums ${s.total_return_pct >= 0 ? "text-emerald-400" : "text-rose-400"}`}>
                      {s.total_return_pct >= 0 ? "+" : ""}{s.total_return_pct.toFixed(1)}%
                    </td>
                    <td className="px-3 py-2.5 text-right tabular-nums text-slate-300">{s.cagr_pct.toFixed(1)}%</td>
                    <td className="px-3 py-2.5 text-right tabular-nums text-slate-300">{s.sharpe_ratio.toFixed(2)}</td>
                    <td className="px-3 py-2.5 text-right tabular-nums text-rose-400">{s.max_drawdown_pct.toFixed(1)}%</td>
                    <td className="px-3 py-2.5 text-right tabular-nums text-slate-400">{(s.win_rate * 100).toFixed(0)}%</td>
                    <td className="px-3 py-2.5 text-right tabular-nums text-slate-500">{s.num_trades}</td>
                    <td className="px-3 py-2.5 text-right tabular-nums text-slate-300">{s.final_equity.toLocaleString()}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          {/* Insight */}
          {result.diversification_benefit !== 0 && (
            <div className="glass-card p-4">
              <div className="text-sm font-semibold text-slate-300 mb-1">Diversification Insight</div>
              <p className="text-xs text-slate-400">
                {result.diversification_benefit > 0 ? (
                  <>The combined portfolio Sharpe is <span className="text-emerald-400 font-semibold">{result.sharpe_ratio.toFixed(2)}</span>,
                  which is <span className="text-emerald-400 font-semibold">+{result.diversification_benefit.toFixed(2)}</span> higher
                  than the average individual strategy Sharpe. Diversifying across strategies reduced risk while maintaining returns —
                  the classic &ldquo;free lunch&rdquo; of combining uncorrelated return streams.</>
                ) : (
                  <>The combined portfolio Sharpe is <span className="text-rose-400 font-semibold">{result.sharpe_ratio.toFixed(2)}</span>,
                  which is <span className="text-rose-400 font-semibold">{result.diversification_benefit.toFixed(2)}</span> vs the average
                  strategy. These strategies are highly correlated, so combining them offers little diversification benefit.</>
                )}
              </p>
            </div>
          )}
        </>
      )}
    </div>
  );
}

/** Simple SVG equity curve chart. */
function EquityChart({ data, initial }: { data: { date: string; equity: number }[]; initial: number }) {
  if (data.length < 2) return <div className="text-xs text-slate-500 py-4 text-center">No equity data</div>;

  const W = 800;
  const H = 200;
  const PAD = 40;

  const equities = data.map((d) => d.equity);
  const minE = Math.min(...equities, initial);
  const maxE = Math.max(...equities, initial);
  const range = maxE - minE || 1;

  const x = (i: number) => PAD + (i / (data.length - 1)) * (W - 2 * PAD);
  const y = (e: number) => H - PAD - ((e - minE) / range) * (H - 2 * PAD);

  const points = data.map((d, i) => `${x(i)},${y(d.equity)}`).join(" ");
  const initialY = y(initial);

  return (
    <svg viewBox={`0 0 ${W} ${H}`} className="w-full h-48">
      {/* Grid lines */}
      {[0.25, 0.5, 0.75].map((p) => (
        <line key={p} x1={PAD} y1={PAD + p * (H - 2 * PAD)} x2={W - PAD} y2={PAD + p * (H - 2 * PAD)}
          stroke="rgb(30 41 59)" strokeWidth="1" />
      ))}
      {/* Initial capital baseline */}
      <line x1={PAD} y1={initialY} x2={W - PAD} y2={initialY}
        stroke="rgb(100 116 139)" strokeWidth="1" strokeDasharray="4 4" />
      <text x={W - PAD} y={initialY - 4} textAnchor="end" className="fill-slate-500 text-[10px]">
        {initial.toLocaleString()}
      </text>
      {/* Equity curve */}
      <polyline points={points} fill="none" stroke="rgb(52 211 153)" strokeWidth="2" />
      {/* Area under curve */}
      <polygon
        points={`${PAD},${H - PAD} ${points} ${W - PAD},${H - PAD}`}
        fill="rgb(52 211 153 / 0.1)"
      />
      {/* Labels */}
      <text x={PAD} y={H - 10} className="fill-slate-600 text-[10px]">{data[0]?.date}</text>
      <text x={W - PAD} y={H - 10} textAnchor="end" className="fill-slate-600 text-[10px]">{data[data.length - 1]?.date}</text>
    </svg>
  );
}
