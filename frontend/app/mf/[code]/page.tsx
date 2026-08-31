"use client";

import Link from "next/link";
import useSWR from "swr";
import { fetchMfDetail } from "@/lib/api";

function pct(v: number | undefined) { return v != null ? `${(v * 100).toFixed(1)}%` : "—"; }

export default function MfDetailPage({ params }: { params: { code: string } }) {
  const code = params.code;
  const { data, isLoading, error } = useSWR(`mf-${code}`, () => fetchMfDetail(code));

  if (isLoading) {
    return (
      <div className="glass-card p-8 text-center">
        <div className="shimmer h-6 w-40 mx-auto rounded mb-4" />
        <div className="shimmer h-4 w-24 mx-auto rounded" />
        <p className="text-xs text-slate-500 mt-3">Loading fund details… (first load fetches NAV history, ~60s)</p>
      </div>
    );
  }

  if (error || !data) {
    return (
      <div className="space-y-4">
        <Link href="/mf" className="text-sky-400 text-sm hover:underline">← back to funds</Link>
        <div className="glass-card p-8 text-center">
          <p className="text-rose-400 text-sm">Failed to load {code}.</p>
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-5 fade-in">
      <Link href="/mf" className="text-sky-400 text-sm hover:underline">← back to funds</Link>

      {/* Header */}
      <div className="glass-card p-5">
        <h1 className="text-xl font-bold text-slate-100">{data.name}</h1>
        <div className="flex items-center gap-3 mt-1">
          <span className="text-xs bg-slate-800 px-2 py-0.5 rounded text-slate-400">{data.category}</span>
          {data.fund_house && <span className="text-xs text-slate-500">{data.fund_house}</span>}
          {data.scheme_type && <span className="text-xs text-slate-500">{data.scheme_type}</span>}
        </div>
        <div className="flex items-center gap-6 mt-3">
          <div>
            <span className="text-xs text-slate-500">NAV</span>
            <div className="text-xl font-bold tabular-nums text-slate-100">₹{data.last_nav.toFixed(2)}</div>
          </div>
          <div>
            <span className="text-xs text-slate-500">Horizon</span>
            <div className="text-sm text-slate-300">{data.suggested_horizon}</div>
          </div>
        </div>
      </div>

      {/* Key metrics */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
        <Metric label="CAGR" value={pct(data.cagr)} />
        <Metric label="Volatility" value={pct(data.volatility)} />
        <Metric label="Max Drawdown" value={pct(data.max_drawdown)} color="text-rose-300" />
        <Metric label="Sharpe" value={data.sharpe.toFixed(2)} color="text-emerald-300" />
        <Metric label="Risk Level" value={data.risk_level} />
        {data.expense_ratio_est != null && (
          <Metric label="Expense Ratio (est)" value={`${data.expense_ratio_est.toFixed(2)}%`} />
        )}
        {data.exit_load && <Metric label="Exit Load" value={data.exit_load} />}
      </div>

      {/* Strategy */}
      {(data.entry_strategy || data.exit_strategy) && (
        <div className="glass-card p-4">
          <h2 className="section-title mb-3">Investment Strategy</h2>
          {data.entry_strategy && (
            <div className="mb-2">
              <div className="text-[10px] uppercase tracking-wide text-sky-400 mb-0.5">Entry</div>
              <p className="text-xs text-slate-300">{data.entry_strategy}</p>
            </div>
          )}
          {data.exit_strategy && (
            <div>
              <div className="text-[10px] uppercase tracking-wide text-rose-400 mb-0.5">Exit</div>
              <p className="text-xs text-slate-300">{data.exit_strategy}</p>
              <p className="text-xs text-slate-300">{data.exit_strategy}</p>
            </div>
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
