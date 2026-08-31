"use client";

import Link from "next/link";
import useSWR from "swr";
import { fetchEtfDetail } from "@/lib/api";

function pct(v: number | undefined) { return v != null ? `${(v * 100).toFixed(1)}%` : "—"; }

export default function EtfDetailPage({ params }: { params: { symbol: string } }) {
  const symbol = params.symbol.toUpperCase().replace(".NS", "");
  const { data, isLoading, error } = useSWR(`etf-${symbol}`, () => fetchEtfDetail(symbol));

  if (isLoading) {
    return (
      <div className="glass-card p-8 text-center">
        <div className="shimmer h-6 w-40 mx-auto rounded mb-4" />
        <div className="shimmer h-4 w-24 mx-auto rounded" />
      </div>
    );
  }

  if (error || !data) {
    return (
      <div className="space-y-4">
        <Link href="/etf" className="text-sky-400 text-sm hover:underline">← back to ETFs</Link>
        <div className="glass-card p-8 text-center">
          <p className="text-rose-400 text-sm">Failed to load {symbol}.</p>
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-5 fade-in">
      <Link href="/etf" className="text-sky-400 text-sm hover:underline">← back to ETFs</Link>

      {/* Header */}
      <div className="glass-card p-5">
        <div className="flex items-center gap-3 flex-wrap">
          <h1 className="text-xl font-bold text-slate-100">{data.symbol}</h1>
          <span className="text-xs bg-slate-800 px-2 py-0.5 rounded text-slate-400">{data.category}</span>
        </div>
        <p className="text-xs text-slate-500 mt-1">{data.name}</p>
        <div className="flex items-center gap-6 mt-3">
          <div>
            <span className="text-xs text-slate-500">Price</span>
            <div className="text-xl font-bold tabular-nums text-slate-100">₹{data.last_price.toFixed(2)}</div>
          </div>
          {data.amc_name && (
            <div>
              <span className="text-xs text-slate-500">AMC</span>
              <div className="text-sm text-slate-300">{data.amc_name}</div>
            </div>
          )}
        </div>
      </div>

      {/* Key metrics */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
        <Metric label="CAGR" value={pct(data.cagr)} />
        <Metric label="Volatility" value={pct(data.volatility)} />
        <Metric label="Max Drawdown" value={pct(data.max_drawdown)} color="text-rose-300" />
        <Metric label="Sharpe" value={data.sharpe.toFixed(2)} color="text-emerald-300" />
        <Metric label="Risk Level" value={data.risk_level} />
        <Metric label="Horizon" value={data.suggested_horizon} />
        {data.expense_ratio_est != null && (
          <Metric label="Expense Ratio (est)" value={`${data.expense_ratio_est.toFixed(2)}%`} />
        )}
        {data.high_52w != null && <Metric label="52W High" value={`₹${data.high_52w.toFixed(2)}`} />}
        {data.low_52w != null && <Metric label="52W Low" value={`₹${data.low_52w.toFixed(2)}`} />}
      </div>

      {/* Entry/exit levels */}
      {data.entry != null && (
        <div className="glass-card p-4 border-emerald-800/30">
          <h2 className="text-sm font-semibold text-emerald-400 mb-3">Investment Entry / Stop-Loss / Target</h2>
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 mb-3">
            <Metric label="Entry" value={`₹${data.entry}`} color="text-sky-300" />
            <Metric label="Stop-Loss" value={`₹${data.stop_loss}`} color="text-rose-300" />
            <Metric label="Target" value={`₹${data.target}`} color="text-emerald-300" />
            {data.risk_reward != null && <Metric label="Risk:Reward" value={`1:${data.risk_reward}`} color="text-amber-300" />}
          </div>
          {data.trend && <p className="text-xs text-slate-500 mb-2">Trend: {data.trend}</p>}
          {data.invest_explanation && <p className="text-xs text-slate-300">{data.invest_explanation}</p>}
          {data.invest_caveats && data.invest_caveats.length > 0 && (
            <ul className="mt-2 text-xs text-amber-300/70 list-disc list-inside space-y-0.5">
              {data.invest_caveats.map((c, i) => <li key={i}>{c}</li>)}
            </ul>
          )}
        </div>
      )}

      {/* Verdict */}
      <div className="glass-card p-4">
        <h2 className="section-title mb-2">Verdict</h2>
        <p className="text-xs text-slate-300">{data.verdict}</p>
        {data.risks.length > 0 && (
          <ul className="mt-2 text-xs text-amber-300/70 list-disc list-inside space-y-0.5">
            {data.risks.map((r, i) => <li key={i}>{r}</li>)}
          </ul>
        )}
      </div>

      {data.expense_ratio_note && (
        <p className="text-xs text-slate-600 text-center">{data.expense_ratio_note}</p>
      )}
    </div>
  );
}

function Metric({ label, value, color = "" }: { label: string; value: string; color?: string }) {
  return (
    <div className="stat-box">
      <div className="text-[10px] text-slate-400 uppercase tracking-wide">{label}</div>
      <div className={`text-sm font-medium tabular-nums ${color || "text-slate-200"}`}>{value}</div>
    </div>
  );
}
