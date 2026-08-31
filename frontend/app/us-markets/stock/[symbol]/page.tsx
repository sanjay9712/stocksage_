"use client";

import useSWR from "swr";
import Link from "next/link";
import { fetchUsStockDetail, fetchCandlestick, fetchMultiFactor } from "@/lib/api";

function fmtUsd(v: number | null | undefined): string {
  if (v == null) return "—";
  if (v >= 1e12) return `$${(v / 1e12).toFixed(2)}T`;
  if (v >= 1e9) return `$${(v / 1e9).toFixed(1)}B`;
  if (v >= 1e6) return `$${(v / 1e6).toFixed(1)}M`;
  return `$${v.toFixed(0)}`;
}

function fmtPct(v: number | null | undefined): string {
  if (v == null) return "—";
  return `${(v * 100).toFixed(2)}%`;
}

export default function UsStockDetailPage({ params }: { params: { symbol: string } }) {
  const symbol = params.symbol.toUpperCase();
  const { data, isLoading, error } = useSWR(`us-stock-${symbol}`, () => fetchUsStockDetail(symbol), { refreshInterval: 2000, keepPreviousData: true });
  const { data: candles } = useSWR(`us-candles-${symbol}`, () => fetchCandlestick(symbol));
  const { data: multifactor } = useSWR(`us-mf-${symbol}`, () => fetchMultiFactor(symbol));

  if (isLoading) {
    return (
      <div className="glass-card p-8 text-center">
        <div className="shimmer h-6 w-48 mx-auto rounded mb-4" />
        <div className="shimmer h-4 w-32 mx-auto rounded" />
        <p className="text-xs text-slate-500 mt-3">Loading {symbol} details…</p>
      </div>
    );
  }
  if (error || !data) {
    return (
      <div className="space-y-4">
        <Link href="/us-markets" className="text-sky-400 text-sm hover:underline">← back to US Markets</Link>
        <div className="glass-card p-8 text-center">
          <p className="text-rose-400">Failed to load {symbol}.</p>
          <p className="text-xs text-slate-500 mt-1">The stock may not be available on yfinance.</p>
        </div>
      </div>
    );
  }

  const f = data.fundamentals;
  const fin = data.financials;
  const rec = data.recommendations;
  const lv = data.invest_levels;
  const lq = data.live_quote;

  return (
    <div className="space-y-5 fade-in">
      <Link href="/us-markets" className="text-sky-400 text-sm hover:underline">← back to US Markets</Link>

      {/* Header */}
      <div className="glass-card p-5">
        <div className="flex items-center gap-3 flex-wrap">
          <h1 className="text-xl font-bold text-slate-100">{f.company_name || symbol}</h1>
          {f.sector && <span className="text-xs bg-slate-800 px-2 py-0.5 rounded text-slate-400">{f.sector}</span>}
        </div>
        {f.industry && <p className="text-xs text-slate-500 mt-1">{f.industry}</p>}
        <div className="flex items-center gap-4 mt-3">
          <span className="text-2xl font-bold tabular-nums text-slate-100">
            ${(lq?.price ?? lv.last_price).toFixed(2)}
          </span>
          {lq?.change_pct != null && (
            <span className={`text-sm font-medium tabular-nums ${lq.change_pct >= 0 ? "text-emerald-400" : "text-rose-400"}`}>
              {lq.change_pct >= 0 ? "▲" : "▼"} {Math.abs(lq.change_pct).toFixed(2)}%
              {lq.change != null && (
                <span className="text-slate-500 ml-1">({lq.change >= 0 ? "+" : ""}{lq.change.toFixed(2)})</span>
              )}
            </span>
          )}
        </div>
        {lq && (lq.day_high || lq.day_low) && (
          <div className="flex items-center gap-4 mt-1 text-xs text-slate-500">
            {lq.day_high && <span>H: <span className="text-slate-400 tabular-nums">${lq.day_high.toFixed(2)}</span></span>}
            {lq.day_low && <span>L: <span className="text-slate-400 tabular-nums">${lq.day_low.toFixed(2)}</span></span>}
            {lq.prev_close && <span>Prev: <span className="text-slate-400 tabular-nums">${lq.prev_close.toFixed(2)}</span></span>}
          </div>
        )}
      </div>

      {/* Key metrics grid */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
        <Metric label="P/E (trailing)" value={f.trailing_pe?.toFixed(2) || "—"} />
        <Metric label="P/E (forward)" value={f.forward_pe?.toFixed(2) || "—"} />
        <Metric label="Market Cap" value={fmtUsd(f.market_cap)} />
        <Metric label="Revenue" value={fmtUsd(f.total_revenue)} />
        <Metric label="Total Debt" value={fmtUsd(f.total_debt)} />
        <Metric label="Cash" value={fmtUsd(f.total_cash)} />
        <Metric label="Debt/Equity" value={f.debt_to_equity?.toFixed(2) || "—"} />
        <Metric label="Profit Margin" value={fmtPct(f.profit_margins)} />
        <Metric label="Op. Margin" value={fmtPct(f.operating_margins)} />
        <Metric label="ROE" value={fmtPct(f.return_on_equity)} />
        <Metric label="Div Yield" value={fmtPct(f.dividend_yield)} />
        <Metric label="Beta" value={f.beta?.toFixed(3) || "—"} />
        <Metric label="52W Low" value={f["52w_low"] ? `$${f["52w_low"]}` : "—"} />
        <Metric label="52W High" value={f["52w_high"] ? `$${f["52w_high"]}` : "—"} />
        <Metric label="Employees" value={f.employees?.toLocaleString() || "—"} />
      </div>

      {/* Company description */}
      {f.description && (
        <div className="glass-card p-4">
          <h2 className="section-title mb-2">About</h2>
          <p className="text-xs text-slate-400 leading-relaxed">{f.description}</p>
          {f.website && (
            <a href={f.website} target="_blank" rel="noreferrer" className="text-xs text-sky-400 hover:underline mt-2 inline-block">
              {f.website}
            </a>
          )}
        </div>
      )}

      {/* Investment entry/exit levels */}
      <div className="glass-card p-4 border-emerald-800/30">
        <h2 className="text-sm font-semibold text-emerald-400 mb-3">Investment Entry / Stop-Loss / Target</h2>
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 mb-3">
          <Metric label="Entry Zone" value={`$${lv.entry}`} color="text-sky-300" />
          <Metric label="Stop-Loss" value={`$${lv.stop_loss}`} color="text-rose-300" />
          <Metric label="Target" value={`$${lv.target}`} color="text-emerald-300" />
          <Metric label="Risk:Reward" value={`1:${lv.risk_reward}`} color="text-amber-300" />
        </div>
        <div className="grid grid-cols-3 gap-3 mb-3">
          <Metric label="EMA-50" value={`$${lv.ema50}`} />
          <Metric label="EMA-200" value={`$${lv.ema200}`} />
          <Metric label="ATR(14)" value={`$${lv.atr14}`} />
        </div>
        <p className="text-xs text-slate-300">{lv.explanation}</p>
        {lv.caveats.length > 0 && (
          <ul className="mt-2 text-xs text-amber-300/70 list-disc list-inside space-y-0.5">
            {lv.caveats.map((c, i) => <li key={i}>{c}</li>)}
          </ul>
        )}
      </div>

      {/* Multi-factor score */}
      {multifactor && (
        <div className="glass-card p-4">
          <h2 className="section-title mb-3">Multi-Factor Score</h2>
          <div className="flex items-center gap-3 mb-3">
            <span className={`text-2xl font-bold ${
              multifactor.grade.startsWith("A") ? "text-emerald-400" :
              multifactor.grade === "B" ? "text-sky-400" :
              multifactor.grade === "C" ? "text-amber-400" : "text-rose-400"
            }`}>{multifactor.grade}</span>
            <div className="flex-1">
              <div className="h-2.5 bg-slate-800 rounded-full overflow-hidden">
                <div
                  className="h-full rounded-full bg-gradient-to-r from-emerald-500 to-teal-400"
                  style={{ width: `${Math.round(multifactor.composite * 100)}%` }}
                />
              </div>
              <span className="text-xs text-slate-500 mt-1 block tabular-nums">
                Composite {Math.round(multifactor.composite * 100)}%
              </span>
            </div>
          </div>
          <div className="grid grid-cols-3 gap-3 mb-2">
            <FactorBar label="Momentum" value={multifactor.momentum} weight={multifactor.weights.momentum} />
            <FactorBar label="Quality" value={multifactor.quality} weight={multifactor.weights.quality} />
            <FactorBar label="Value" value={multifactor.value} weight={multifactor.weights.value} />
          </div>
          <p className="text-xs text-slate-400 leading-relaxed">{multifactor.summary}</p>
        </div>
      )}

      {/* Candlestick patterns */}
      {candles && candles.patterns.length > 0 && (
        <div className="glass-card p-4">
          <h2 className="section-title mb-3">
            Candlestick Patterns{" "}
            <span className={`text-xs ${
              candles.net_bias === "bullish" ? "text-emerald-400" :
              candles.net_bias === "bearish" ? "text-rose-400" : "text-slate-500"
            }`}>
              net: {candles.net_bias}
            </span>
          </h2>
          <div className="space-y-2">
            {candles.patterns.map((p, i) => (
              <div key={i} className="flex items-start gap-2">
                <span className={`text-[10px] font-medium rounded border px-1.5 py-0.5 shrink-0 ${
                  p.bias === "bullish" ? "bg-emerald-500/15 text-emerald-400 border-emerald-500/30" :
                  p.bias === "bearish" ? "bg-rose-500/15 text-rose-400 border-rose-500/30" :
                  "bg-slate-700/40 text-slate-400 border-slate-600/30"
                }`}>
                  {p.strength}
                </span>
                <div className="min-w-0">
                  <span className="text-sm font-medium text-slate-200">{p.name}</span>
                  <p className="text-xs text-slate-400 leading-relaxed">{p.description}</p>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Analyst recommendations */}
      {rec.periods.length > 0 && (
        <div className="glass-card p-4">
          <h2 className="section-title mb-3">
            Analyst Recommendations —{" "}
            <span className={
              rec.consensus === "BUY" || rec.consensus === "ACCUMULATE" ? "text-emerald-400" :
              rec.consensus === "SELL" || rec.consensus === "REDUCE" ? "text-rose-400" :
              "text-amber-300"
            }>
              {rec.consensus}
            </span>
          </h2>
          {rec.periods.map((p, i) => (
            <div key={i} className="mb-3">
              <div className="text-xs text-slate-500 mb-1">{p.period} ({p.total} analysts)</div>
              <div className="flex h-6 rounded-lg overflow-hidden text-xs">
                <div className="bg-emerald-600 flex items-center justify-center" style={{ width: `${(p.strong_buy / p.total) * 100}%` }}>{p.strong_buy > 0 ? p.strong_buy : ""}</div>
                <div className="bg-emerald-500/60 flex items-center justify-center" style={{ width: `${(p.buy / p.total) * 100}%` }}>{p.buy > 0 ? p.buy : ""}</div>
                <div className="bg-amber-500/60 flex items-center justify-center" style={{ width: `${(p.hold / p.total) * 100}%` }}>{p.hold > 0 ? p.hold : ""}</div>
                <div className="bg-rose-500/60 flex items-center justify-center" style={{ width: `${(p.sell / p.total) * 100}%` }}>{p.sell > 0 ? p.sell : ""}</div>
                <div className="bg-rose-600 flex items-center justify-center" style={{ width: `${(p.strong_sell / p.total) * 100}%` }}>{p.strong_sell > 0 ? p.strong_sell : ""}</div>
              </div>
            </div>
          ))}
          <div className="flex gap-3 text-xs text-slate-500 flex-wrap">
            <span><span className="inline-block w-2 h-2 bg-emerald-600 rounded mr-1" />Strong Buy</span>
            <span><span className="inline-block w-2 h-2 bg-emerald-500/60 rounded mr-1" />Buy</span>
            <span><span className="inline-block w-2 h-2 bg-amber-500/60 rounded mr-1" />Hold</span>
            <span><span className="inline-block w-2 h-2 bg-rose-500/60 rounded mr-1" />Sell</span>
            <span><span className="inline-block w-2 h-2 bg-rose-600 rounded mr-1" />Strong Sell</span>
          </div>
        </div>
      )}

      {/* Financials table */}
      {Object.keys(fin.income_statement).length > 0 && (
        <div className="glass-card p-4">
          <h2 className="section-title mb-3">Financials (Annual)</h2>
          <div className="overflow-x-auto">
            <table className="w-full text-xs">
              <thead className="text-slate-500">
                <tr className="border-b border-slate-800">
                  <th className="px-2 py-1.5 text-left">Metric</th>
                  {Object.keys(fin.income_statement).reverse().map(y => <th key={y} className="px-2 py-1.5 text-right">{y}</th>)}
                </tr>
              </thead>
              <tbody>
                {renderFinRows(fin.income_statement, [
                  ["revenue", "Revenue"],
                  ["gross_profit", "Gross Profit"],
                  ["operating_income", "Operating Income"],
                  ["net_income", "Net Income"],
                  ["ebitda", "EBITDA"],
                  ["eps", "EPS"],
                ])}
              </tbody>
            </table>
          </div>
        </div>
      )}

      <p className="text-xs text-slate-600 text-center">
        Fundamentals via yfinance (delayed ~15 min). Investment levels from daily EMA/ATR/pivots. Not investment advice.
      </p>
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

function FactorBar({ label, value, weight }: { label: string; value: number; weight: number }) {
  return (
    <div>
      <div className="flex items-center justify-between mb-1">
        <span className="text-[10px] text-slate-400 uppercase tracking-wide">{label}</span>
        <span className="text-[10px] text-slate-500">{Math.round(weight * 100)}%</span>
      </div>
      <div className="h-1.5 bg-slate-800 rounded-full overflow-hidden">
        <div
          className={`h-full rounded-full ${
            value >= 0.7 ? "bg-emerald-500" : value >= 0.5 ? "bg-sky-500" : "bg-amber-500"
          }`}
          style={{ width: `${Math.round(value * 100)}%` }}
        />
      </div>
      <span className="text-xs text-slate-400 tabular-nums mt-0.5 block">{Math.round(value * 100)}%</span>
    </div>
  );
}

function renderFinRows(data: Record<string, Record<string, number | null>>, labels: [string, string][]) {
  const years = Object.keys(data).reverse();
  return labels.map(([key, label]) => (
    <tr key={key} className="border-t border-slate-800/50 hover:bg-slate-800/30 transition-colors">
      <td className="px-2 py-1.5 text-slate-400">{label}</td>
      {years.map(y => {
        const v = data[y]?.[key];
        return <td key={y} className="px-2 py-1.5 text-right tabular-nums text-slate-300">{v != null ? fmtUsd(v) : "—"}</td>;
      })}
    </tr>
  ));
}
