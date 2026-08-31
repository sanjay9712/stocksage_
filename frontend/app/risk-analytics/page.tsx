"use client";

import useSWR from "swr";
import { fetchRiskAnalytics, type RiskAnalyticsResult } from "@/lib/api";

export default function RiskAnalyticsPage() {
  const { data, error } = useSWR("/api/risk-analytics", () => fetchRiskAnalytics(), {
    refreshInterval: 60000,
    keepPreviousData: true,
  });

  if (error) {
    return (
      <div className="glass-card p-8 text-center">
        <p className="text-rose-300 text-sm">{error.message || "Failed to load risk analytics"}</p>
      </div>
    );
  }

  if (!data) {
    return (
      <div className="glass-card p-8 text-center">
        <p className="text-sm text-slate-500">Loading risk analytics...</p>
      </div>
    );
  }

  if (data.error) {
    return (
      <div className="space-y-6">
        <div>
          <h1 className="text-xl font-bold text-slate-100">Portfolio Risk Analytics</h1>
          <p className="text-sm text-slate-500 mt-1">
            VaR, CVaR, beta, Sharpe ratio, drawdown, and concentration risk for your holdings.
          </p>
        </div>
        <div className="glass-card p-8 text-center">
          <p className="text-amber-300 text-sm">{data.error}</p>
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-xl font-bold text-slate-100">Portfolio Risk Analytics</h1>
        <p className="text-sm text-slate-500 mt-1">
          VaR, CVaR, beta, Sharpe ratio, drawdown, and concentration risk for your holdings.
        </p>
      </div>

      {/* Key Risk Metrics */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
        <div className="glass-card p-3">
          <div className="text-xs text-slate-500">Portfolio Value</div>
          <div className="text-lg font-bold text-slate-200 tabular-nums">
            ₹{data.total_value.toLocaleString("en-IN")}
          </div>
        </div>
        <div className="glass-card p-3">
          <div className="text-xs text-slate-500">VaR (95%)</div>
          <div className="text-lg font-bold text-rose-400 tabular-nums">
            ₹{data.var_95.toLocaleString("en-IN")}
          </div>
          <div className="text-[10px] text-slate-600">1-day, 95% confidence</div>
        </div>
        <div className="glass-card p-3">
          <div className="text-xs text-slate-500">VaR (99%)</div>
          <div className="text-lg font-bold text-rose-500 tabular-nums">
            ₹{data.var_99.toLocaleString("en-IN")}
          </div>
          <div className="text-[10px] text-slate-600">1-day, 99% confidence</div>
        </div>
        <div className="glass-card p-3">
          <div className="text-xs text-slate-500">CVaR (95%)</div>
          <div className="text-lg font-bold text-rose-500 tabular-nums">
            ₹{data.cvar_95.toLocaleString("en-IN")}
          </div>
          <div className="text-[10px] text-slate-600">Expected shortfall</div>
        </div>
      </div>

      {/* Performance Metrics */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
        <div className="glass-card p-3">
          <div className="text-xs text-slate-500">Sharpe Ratio</div>
          <div className="text-lg font-bold text-sky-400 tabular-nums">{data.sharpe_ratio.toFixed(2)}</div>
        </div>
        <div className="glass-card p-3">
          <div className="text-xs text-slate-500">Max Drawdown</div>
          <div className="text-lg font-bold text-rose-400 tabular-nums">{data.max_drawdown_pct.toFixed(1)}%</div>
        </div>
        <div className="glass-card p-3">
          <div className="text-xs text-slate-500">Volatility (Annual)</div>
          <div className="text-lg font-bold text-amber-400 tabular-nums">{data.volatility_pct.toFixed(1)}%</div>
        </div>
        <div className="glass-card p-3">
          <div className="text-xs text-slate-500">Beta vs NIFTY</div>
          <div className="text-lg font-bold text-slate-200 tabular-nums">{data.beta.toFixed(2)}</div>
        </div>
      </div>

      {/* Diversification Metrics */}
      <div className="glass-card p-4">
        <div className="text-sm font-semibold text-slate-300 mb-3">Diversification</div>
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
          <div>
            <div className="text-xs text-slate-500">Positions</div>
            <div className="text-sm font-semibold text-slate-200">{data.num_positions}</div>
          </div>
          <div>
            <div className="text-xs text-slate-500">Effective Positions</div>
            <div className="text-sm font-semibold text-slate-200">{data.effective_positions.toFixed(1)}</div>
            <div className="text-[10px] text-slate-600">Higher = more diversified</div>
          </div>
          <div>
            <div className="text-xs text-slate-500">Herfindahl Index</div>
            <div className="text-sm font-semibold text-slate-200">{data.herfindahl_index.toFixed(3)}</div>
            <div className="text-[10px] text-slate-600">Lower = more spread out</div>
          </div>
          <div>
            <div className="text-xs text-slate-500">Diversification Ratio</div>
            <div className="text-sm font-semibold text-emerald-400">{data.diversification_ratio.toFixed(2)}x</div>
            <div className="text-[10px] text-slate-600">Higher = better</div>
          </div>
        </div>
        <div className="mt-3 pt-3 border-t border-slate-800/50">
          <div className="flex items-center gap-4">
            <div>
              <span className="text-xs text-slate-500">Alpha (annual): </span>
              <span className={`text-sm font-semibold ${data.alpha_annual >= 0 ? "text-emerald-400" : "text-rose-400"}`}>
                {data.alpha_annual >= 0 ? "+" : ""}{data.alpha_annual.toFixed(1)}%
              </span>
            </div>
            <div>
              <span className="text-xs text-slate-500">Corr to NIFTY: </span>
              <span className="text-sm font-semibold text-slate-300">{data.correlation_to_benchmark.toFixed(2)}</span>
            </div>
            <div>
              <span className="text-xs text-slate-500">Avg Correlation: </span>
              <span className="text-sm font-semibold text-slate-300">{data.avg_correlation.toFixed(2)}</span>
            </div>
          </div>
        </div>
      </div>

      {/* Per-Position Risk */}
      {data.positions.length > 0 && (
        <div className="glass-card overflow-x-auto">
          <div className="text-sm font-semibold text-slate-300 p-4 pb-2">Per-Position Risk Breakdown</div>
          <table className="w-full text-xs">
            <thead>
              <tr className="text-slate-500 border-b border-slate-800">
                <th className="px-3 py-2 text-left font-medium">Symbol</th>
                <th className="px-3 py-2 text-right font-medium">Value</th>
                <th className="px-3 py-2 text-right font-medium">Weight</th>
                <th className="px-3 py-2 text-right font-medium">Volatility</th>
                <th className="px-3 py-2 text-right font-medium">Marginal VaR</th>
                <th className="px-3 py-2 text-right font-medium">Risk Contribution</th>
              </tr>
            </thead>
            <tbody>
              {data.positions.map((p) => (
                <tr key={p.symbol} className="border-b border-slate-800/40 hover:bg-slate-800/30">
                  <td className="px-3 py-2.5 text-slate-200 font-medium">{p.symbol}</td>
                  <td className="px-3 py-2.5 text-right tabular-nums text-slate-300">
                    ₹{p.value.toLocaleString("en-IN")}
                  </td>
                  <td className="px-3 py-2.5 text-right tabular-nums text-slate-400">
                    {(p.weight * 100).toFixed(1)}%
                  </td>
                  <td className="px-3 py-2.5 text-right tabular-nums text-amber-400">{p.volatility.toFixed(1)}%</td>
                  <td className="px-3 py-2.5 text-right tabular-nums text-rose-400">
                    ₹{p.marginal_var.toLocaleString("en-IN")}
                  </td>
                  <td className="px-3 py-2.5 text-right tabular-nums">
                    <div className="flex items-center justify-end gap-2">
                      <div className="w-16 h-1.5 bg-slate-800 rounded-full overflow-hidden">
                        <div
                          className="h-full bg-rose-400 rounded-full"
                          style={{ width: `${Math.min(100, p.contribution_to_risk)}%` }}
                        />
                      </div>
                      <span className="text-slate-400">{p.contribution_to_risk.toFixed(1)}%</span>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
