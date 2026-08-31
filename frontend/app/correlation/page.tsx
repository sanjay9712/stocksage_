"use client";

import { useState } from "react";
import useSWR from "swr";
import { fetchNseCorrelation, fetchUsCorrelation, type CorrelationResult } from "@/lib/api";

function corrColor(val: number | null): string {
  if (val == null) return "bg-slate-900/30";
  if (val >= 0.8) return "bg-rose-600/60";
  if (val >= 0.6) return "bg-rose-600/40";
  if (val >= 0.3) return "bg-amber-600/30";
  if (val >= -0.3) return "bg-slate-700/30";
  if (val >= -0.6) return "bg-sky-600/30";
  if (val >= -0.8) return "bg-sky-600/50";
  return "bg-emerald-600/60";
}

function CorrelationMatrix({ data }: { data: CorrelationResult }) {
  const { symbols, matrix } = data;

  if (!symbols.length) {
    return (
      <div className="glass-card p-8 text-center">
        <p className="text-amber-300 text-sm">No correlation data available.</p>
      </div>
    );
  }

  return (
    <div className="glass-card p-4 overflow-x-auto">
      <table className="text-xs">
        <thead>
          <tr>
            <th className="p-1"></th>
            {symbols.map((s) => (
              <th key={s} className="p-1 text-slate-400 font-medium whitespace-nowrap" style={{ writingMode: "vertical-rl", transform: "rotate(180deg)", maxHeight: "80px" }}>
                {s}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {matrix.map((row, i) => (
            <tr key={symbols[i]}>
              <td className="p-1 text-slate-400 font-medium whitespace-nowrap text-right">{symbols[i]}</td>
              {row.map((val, j) => (
                <td
                  key={j}
                  className={`${corrColor(val)} text-center tabular-nums border border-slate-800/30`}
                  title={val != null ? `${symbols[i]} vs ${symbols[j]}: ${val.toFixed(3)}` : "N/A"}
                  style={{ minWidth: "32px", height: "32px" }}
                >
                  {val != null ? val.toFixed(2) : "—"}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

export default function CorrelationPage() {
  const [tab, setTab] = useState<"nse" | "us">("nse");

  const { data: nseData, isLoading: nseLoading } = useSWR(tab === "nse" ? "nse-correlation" : null, fetchNseCorrelation, {
    refreshInterval: 300000,
    keepPreviousData: true,
  });
  const { data: usData, isLoading: usLoading } = useSWR(tab === "us" ? "us-correlation" : null, fetchUsCorrelation, {
    refreshInterval: 300000,
    keepPreviousData: true,
  });

  const data = tab === "nse" ? nseData : usData;
  const loading = tab === "nse" ? nseLoading : usLoading;

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-xl font-bold text-slate-100">Correlation Matrix</h1>
        <p className="text-sm text-slate-500 mt-1">
          Spot overlapping positions — high correlation means you're doubling up on the same exposure. Low/negative = good diversification.
        </p>
      </div>

      {/* Tabs */}
      <div className="flex gap-2">
        <button
          onClick={() => setTab("nse")}
          className={`px-4 py-2 rounded-lg text-sm font-medium transition-colors ${tab === "nse" ? "bg-emerald-600 text-white" : "bg-slate-800 text-slate-400 hover:bg-slate-700"}`}
        >
          NSE / India
        </button>
        <button
          onClick={() => setTab("us")}
          className={`px-4 py-2 rounded-lg text-sm font-medium transition-colors ${tab === "us" ? "bg-emerald-600 text-white" : "bg-slate-800 text-slate-400 hover:bg-slate-700"}`}
        >
          US Markets
        </button>
      </div>

      {/* Legend */}
      <div className="flex flex-wrap items-center gap-3 text-xs text-slate-500">
        <span>Correlation scale:</span>
        <div className="flex items-center gap-1"><div className="w-4 h-4 rounded bg-emerald-600/60" /><span>-1.0 (inverse)</span></div>
        <div className="flex items-center gap-1"><div className="w-4 h-4 rounded bg-slate-700/30" /><span>0 (uncorrelated)</span></div>
        <div className="flex items-center gap-1"><div className="w-4 h-4 rounded bg-rose-600/60" /><span>+1.0 (identical)</span></div>
      </div>

      {loading && !data && (
        <div className="glass-card p-8 shimmer" />
      )}

      {data && (
        <>
          <CorrelationMatrix data={data} />

          {/* High correlation warnings */}
          {data.high_correlation_pairs.length > 0 && (
            <div>
              <h2 className="text-sm font-semibold text-slate-400 mb-3">High Overlap Pairs (&gt;= 0.70)</h2>
              <div className="space-y-2">
                {data.high_correlation_pairs.map((pair, i) => (
                  <div key={i} className="glass-card p-3 flex items-center justify-between">
                    <div className="flex items-center gap-3">
                      <span className="text-sm font-medium text-slate-200">{pair.a}</span>
                      <svg className="w-4 h-4 text-slate-500" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M5 12h14M5 12l4-4M5 12l4 4" /></svg>
                      <span className="text-sm font-medium text-slate-200">{pair.b}</span>
                    </div>
                    <div className="flex items-center gap-3">
                      <span className="text-xs text-amber-300">{pair.warning}</span>
                      <span className={`text-sm font-bold tabular-nums ${pair.correlation > 0 ? "text-rose-400" : "text-emerald-400"}`}>
                        {pair.correlation > 0 ? "+" : ""}{pair.correlation.toFixed(3)}
                      </span>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}
        </>
      )}
    </div>
  );
}
