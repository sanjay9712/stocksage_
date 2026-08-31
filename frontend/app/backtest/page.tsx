"use client";

import { useState } from "react";
import { runBacktest, type BacktestResult, type BacktestRequest } from "@/lib/api";

const STRATEGIES = [
  { value: "ema_crossover", label: "EMA Crossover", params: [
    { key: "fast_period", label: "Fast EMA", default: 9, min: 3, max: 50 },
    { key: "slow_period", label: "Slow EMA", default: 21, min: 10, max: 100 },
  ]},
  { value: "rsi_reversion", label: "RSI Mean Reversion", params: [
    { key: "rsi_period", label: "RSI Period", default: 14, min: 5, max: 30 },
    { key: "oversold", label: "Oversold", default: 30, min: 10, max: 45 },
    { key: "overbought", label: "Overbought", default: 70, min: 55, max: 90 },
  ]},
  { value: "bollinger", label: "Bollinger Bands", params: [
    { key: "bb_period", label: "BB Period", default: 20, min: 10, max: 50 },
    { key: "bb_std", label: "Std Dev", default: 2.0, min: 1, max: 3, step: 0.5 },
  ]},
  { value: "breakout", label: "Donchian Breakout", params: [
    { key: "lookback", label: "Lookback", default: 20, min: 5, max: 55 },
  ]},
];

export default function BacktestPage() {
  const [symbol, setSymbol] = useState("SPY");
  const [strategy, setStrategy] = useState("ema_crossover");
  const [days, setDays] = useState(365);
  const [capital, setCapital] = useState(100000);
  const [params, setParams] = useState<Record<string, number>>({ fast_period: 9, slow_period: 21 });
  const [result, setResult] = useState<BacktestResult | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleStrategyChange = (s: string) => {
    setStrategy(s);
    const strat = STRATEGIES.find((x) => x.value === s);
    if (strat) {
      const newParams: Record<string, number> = {};
      strat.params.forEach((p) => { newParams[p.key] = p.default; });
      setParams(newParams);
    }
  };

  const handleRun = async () => {
    setLoading(true);
    setError(null);
    setResult(null);
    try {
      const req: BacktestRequest = {
        symbol: symbol.toUpperCase(),
        strategy: strategy as BacktestRequest["strategy"],
        days,
        initial_capital: capital,
        params,
      };
      const res = await runBacktest(req);
      setResult(res);
    } catch (e: any) {
      setError(e.message || "Failed to run backtest");
    } finally {
      setLoading(false);
    }
  };

  const selectedStrategy = STRATEGIES.find((s) => s.value === strategy);
  const equityMax = result ? Math.max(...result.equity_curve.map((e) => e.equity)) : 0;
  const equityMin = result ? Math.min(...result.equity_curve.map((e) => e.equity)) : 0;

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-xl font-bold text-slate-100">Backtesting Engine</h1>
        <p className="text-sm text-slate-500 mt-1">
          Test trading strategies on historical data — EMA crossover, RSI reversion, Bollinger bands, breakout.
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
            <label className="text-xs text-slate-500 block mb-1">Strategy</label>
            <select
              value={strategy}
              onChange={(e) => handleStrategyChange(e.target.value)}
              className="w-full px-3 py-2 bg-slate-800 text-slate-100 rounded-lg text-sm border border-slate-700"
            >
              {STRATEGIES.map((s) => (
                <option key={s.value} value={s.value}>{s.label}</option>
              ))}
            </select>
          </div>
          <div>
            <label className="text-xs text-slate-500 block mb-1">Period (days)</label>
            <select
              value={days}
              onChange={(e) => setDays(parseInt(e.target.value))}
              className="w-full px-3 py-2 bg-slate-800 text-slate-100 rounded-lg text-sm border border-slate-700"
            >
              <option value={90}>3 months</option>
              <option value={180}>6 months</option>
              <option value={365}>1 year</option>
              <option value={730}>2 years</option>
            </select>
          </div>
        </div>

        {/* Strategy params */}
        {selectedStrategy && (
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
            {selectedStrategy.params.map((p) => (
              <div key={p.key}>
                <label className="text-xs text-slate-500 block mb-1">{p.label}</label>
                <input
                  type="number"
                  value={params[p.key] ?? p.default}
                  min={p.min}
                  max={p.max}
                  step={p.step || 1}
                  onChange={(e) => setParams({ ...params, [p.key]: parseFloat(e.target.value) })}
                  className="w-full px-3 py-2 bg-slate-800 text-slate-100 rounded-lg text-sm border border-slate-700"
                />
              </div>
            ))}
          </div>
        )}

        <div className="flex items-center gap-3">
          <div className="flex-1">
            <label className="text-xs text-slate-500 block mb-1">Initial Capital</label>
            <input
              type="number"
              value={capital}
              onChange={(e) => setCapital(parseFloat(e.target.value) || 100000)}
              className="w-full sm:w-48 px-3 py-2 bg-slate-800 text-slate-100 rounded-lg text-sm border border-slate-700"
            />
          </div>
          <button
            onClick={handleRun}
            disabled={loading}
            className="self-end px-6 py-2 bg-emerald-600 hover:bg-emerald-500 disabled:opacity-50 text-white rounded-lg text-sm font-medium"
          >
            {loading ? "Running..." : "Run Backtest"}
          </button>
        </div>
      </div>

      {error && (
        <div className="glass-card p-4 text-center">
          <p className="text-rose-300 text-sm">{error}</p>
        </div>
      )}

      {result && !result.error && (
        <>
          {/* Summary metrics */}
          <div className="grid grid-cols-2 sm:grid-cols-4 lg:grid-cols-6 gap-3">
            <div className="glass-card p-3">
              <div className="text-xs text-slate-500">Total Return</div>
              <div className={`text-lg font-bold tabular-nums ${result.total_return_pct >= 0 ? "text-emerald-400" : "text-rose-400"}`}>
                {result.total_return_pct >= 0 ? "+" : ""}{result.total_return_pct.toFixed(1)}%
              </div>
            </div>
            <div className="glass-card p-3">
              <div className="text-xs text-slate-500">CAGR</div>
              <div className={`text-lg font-bold tabular-nums ${result.cagr_pct >= 0 ? "text-emerald-400" : "text-rose-400"}`}>
                {result.cagr_pct >= 0 ? "+" : ""}{result.cagr_pct.toFixed(1)}%
              </div>
            </div>
            <div className="glass-card p-3">
              <div className="text-xs text-slate-500">Max Drawdown</div>
              <div className="text-lg font-bold text-rose-400 tabular-nums">{result.max_drawdown_pct.toFixed(1)}%</div>
            </div>
            <div className="glass-card p-3">
              <div className="text-xs text-slate-500">Sharpe</div>
              <div className="text-lg font-bold text-slate-200 tabular-nums">{result.sharpe_ratio.toFixed(2)}</div>
            </div>
            <div className="glass-card p-3">
              <div className="text-xs text-slate-500">Win Rate</div>
              <div className="text-lg font-bold text-amber-400 tabular-nums">{result.win_rate.toFixed(0)}%</div>
            </div>
            <div className="glass-card p-3">
              <div className="text-xs text-slate-500">Trades</div>
              <div className="text-lg font-bold text-slate-200 tabular-nums">{result.num_trades}</div>
            </div>
          </div>

          {/* vs Buy & Hold */}
          <div className="glass-card p-4 space-y-2 text-sm">
            <div className="flex justify-between">
              <span className="text-slate-500">Strategy Return</span>
              <span className={`tabular-nums font-medium ${result.total_return_pct >= 0 ? "text-emerald-400" : "text-rose-400"}`}>
                {result.total_return_pct >= 0 ? "+" : ""}{result.total_return_pct.toFixed(2)}%
              </span>
            </div>
            <div className="flex justify-between">
              <span className="text-slate-500">Buy & Hold Return</span>
              <span className={`tabular-nums font-medium ${result.buy_hold_return_pct >= 0 ? "text-emerald-400" : "text-rose-400"}`}>
                {result.buy_hold_return_pct >= 0 ? "+" : ""}{result.buy_hold_return_pct.toFixed(2)}%
              </span>
            </div>
            <div className="flex justify-between">
              <span className="text-slate-500">Outperformance</span>
              <span className={`tabular-nums font-bold ${result.outperformance_pct >= 0 ? "text-emerald-400" : "text-rose-400"}`}>
                {result.outperformance_pct >= 0 ? "+" : ""}{result.outperformance_pct.toFixed(2)}%
              </span>
            </div>
            <div className="flex justify-between">
              <span className="text-slate-500">Final Equity</span>
              <span className="text-slate-200 tabular-nums font-medium">₹{result.final_equity.toLocaleString("en-IN", { maximumFractionDigits: 0 })}</span>
            </div>
            <div className="flex justify-between">
              <span className="text-slate-500">Volatility (ann.)</span>
              <span className="text-slate-200 tabular-nums">{result.volatility_pct.toFixed(1)}%</span>
            </div>
            <div className="flex justify-between">
              <span className="text-slate-500">Avg Trade</span>
              <span className={`tabular-nums ${result.avg_trade_pct >= 0 ? "text-emerald-400" : "text-rose-400"}`}>
                {result.avg_trade_pct >= 0 ? "+" : ""}{result.avg_trade_pct.toFixed(1)}% ({result.avg_bars_held.toFixed(0)} bars)
              </span>
            </div>
          </div>

          {/* Equity curve */}
          <div className="glass-card p-4">
            <div className="text-sm font-semibold text-slate-300 mb-3">Equity Curve</div>
            <div className="flex items-end gap-px h-48 overflow-x-auto">
              {result.equity_curve.map((e, i) => {
                const heightPct = equityMax > equityMin ? ((e.equity - equityMin) / (equityMax - equityMin)) * 100 : 50;
                const isProfit = e.equity >= result.initial_capital;
                return (
                  <div
                    key={i}
                    className={`w-1 min-w-[2px] ${isProfit ? "bg-emerald-600/60" : "bg-rose-600/60"}`}
                    style={{ height: `${Math.max(heightPct, 2)}%` }}
                    title={`${e.date}: ₹${e.equity.toFixed(0)}`}
                  />
                );
              })}
            </div>
          </div>

          {/* Trade log */}
          {result.trades.length > 0 && (
            <div className="glass-card overflow-x-auto">
              <div className="text-sm font-semibold text-slate-300 p-4 pb-2">Trade Log ({result.trades.length} trades)</div>
              <table className="w-full text-xs">
                <thead>
                  <tr className="text-slate-500 border-b border-slate-800">
                    <th className="px-3 py-2 text-left font-medium">Entry</th>
                    <th className="px-3 py-2 text-left font-medium">Exit</th>
                    <th className="px-3 py-2 text-right font-medium">Entry ₹</th>
                    <th className="px-3 py-2 text-right font-medium">Exit ₹</th>
                    <th className="px-3 py-2 text-right font-medium">P&L</th>
                    <th className="px-3 py-2 text-right font-medium">P&L %</th>
                    <th className="px-3 py-2 text-right font-medium">Bars</th>
                  </tr>
                </thead>
                <tbody>
                  {result.trades.map((t, i) => (
                    <tr key={i} className="border-b border-slate-800/40 hover:bg-slate-800/30">
                      <td className="px-3 py-2 text-slate-400">{t.entry_date}</td>
                      <td className="px-3 py-2 text-slate-400">{t.exit_date}</td>
                      <td className="px-3 py-2 text-right tabular-nums text-slate-300">{t.entry_price.toFixed(2)}</td>
                      <td className="px-3 py-2 text-right tabular-nums text-slate-300">{t.exit_price.toFixed(2)}</td>
                      <td className={`px-3 py-2 text-right tabular-nums ${t.pnl >= 0 ? "text-emerald-400" : "text-rose-400"}`}>
                        {t.pnl >= 0 ? "+" : ""}{t.pnl.toFixed(0)}
                      </td>
                      <td className={`px-3 py-2 text-right tabular-nums ${t.pnl_pct >= 0 ? "text-emerald-400" : "text-rose-400"}`}>
                        {t.pnl_pct >= 0 ? "+" : ""}{t.pnl_pct.toFixed(1)}%
                      </td>
                      <td className="px-3 py-2 text-right tabular-nums text-slate-500">{t.bars_held}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </>
      )}

      {result?.error && (
        <div className="glass-card p-8 text-center">
          <p className="text-amber-300 text-sm">{result.error}</p>
        </div>
      )}
    </div>
  );
}
