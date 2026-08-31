"use client";

import { useState, useCallback } from "react";
import useSWR from "swr";
import { fetchOptionsOI, type OIProfileRow } from "@/lib/api";

function OIBar({ row, maxOI, currentPrice }: { row: OIProfileRow; maxOI: number; currentPrice: number }) {
  const callWidth = maxOI > 0 ? (row.call_oi / maxOI) * 50 : 0;
  const putWidth = maxOI > 0 ? (row.put_oi / maxOI) * 50 : 0;
  const isNearPrice = currentPrice >= row.strike - 1 && currentPrice <= row.strike + 1;

  return (
    <div className="flex items-center text-xs h-5">
      {/* Call OI (left side, growing left) */}
      <div className="w-1/2 flex justify-end">
        <div
          className="h-4 rounded-l-sm bg-rose-600/40 flex items-center justify-end pr-1"
          style={{ width: `${callWidth}%` }}
          title={`Call OI: ${(row.call_oi / 1000).toFixed(0)}k`}
        >
          {callWidth > 15 && <span className="text-[9px] text-rose-200">{(row.call_oi / 1000).toFixed(0)}k</span>}
        </div>
      </div>
      {/* Strike */}
      <div className={`w-16 text-center tabular-nums ${isNearPrice ? "text-sky-400 font-bold" : "text-slate-500"}`}>
        {row.strike.toFixed(0)}
      </div>
      {/* Put OI (right side, growing right) */}
      <div className="w-1/2">
        <div
          className="h-4 rounded-r-sm bg-emerald-600/40 flex items-center pl-1"
          style={{ width: `${putWidth}%` }}
          title={`Put OI: ${(row.put_oi / 1000).toFixed(0)}k`}
        >
          {putWidth > 15 && <span className="text-[9px] text-emerald-200">{(row.put_oi / 1000).toFixed(0)}k</span>}
        </div>
      </div>
    </div>
  );
}

function sentimentColor(s: string): string {
  switch (s) {
    case "bullish": return "text-emerald-400";
    case "slightly_bullish": return "text-emerald-300";
    case "bearish": return "text-rose-400";
    case "slightly_bearish": return "text-rose-300";
    default: return "text-slate-400";
  }
}

export default function OptionsOIPage() {
  const [symbol, setSymbol] = useState("SPY");
  const [inputSymbol, setInputSymbol] = useState("SPY");
  const [expiry, setExpiry] = useState<string | undefined>(undefined);

  const { data, error, isLoading, mutate } = useSWR(
    symbol ? ["options-oi", symbol, expiry] : null,
    () => fetchOptionsOI(symbol, expiry),
    { refreshInterval: 300000, keepPreviousData: true }
  );

  const handleSearch = useCallback(
    (e: React.FormEvent) => {
      e.preventDefault();
      if (inputSymbol.trim()) {
        setSymbol(inputSymbol.trim().toUpperCase());
        setExpiry(undefined);
      }
    },
    [inputSymbol]
  );

  const maxOI = data ? Math.max(...data.oi_profile.map((r) => Math.max(r.call_oi, r.put_oi)), 1) : 1;

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-xl font-bold text-slate-100">Options OI Analysis</h1>
        <p className="text-sm text-slate-500 mt-1">
          Open Interest by strike — max pain, support/resistance from high OI, and PCR sentiment.
        </p>
      </div>

      {/* Search */}
      <form onSubmit={handleSearch} className="flex gap-2 flex-wrap items-center">
        <input
          type="text"
          value={inputSymbol}
          onChange={(e) => setInputSymbol(e.target.value)}
          placeholder="Symbol (SPY, AAPL, RELIANCE...)"
          className="px-3 py-2 bg-slate-800 text-slate-100 rounded-lg text-sm border border-slate-700 focus:border-emerald-500 focus:outline-none w-48"
        />
        {data && data.expiries.length > 0 && (
          <select
            value={expiry ?? ""}
            onChange={(e) => setExpiry(e.target.value || undefined)}
            className="px-3 py-2 bg-slate-800 text-slate-100 rounded-lg text-sm border border-slate-700"
          >
            <option value="">Nearest</option>
            {data.expiries.map((d) => (
              <option key={d} value={d}>{d}</option>
            ))}
          </select>
        )}
        <button type="submit" className="px-4 py-2 bg-emerald-600 hover:bg-emerald-500 text-white rounded-lg text-sm font-medium">
          Analyze
        </button>
      </form>

      {isLoading && !data && <div className="glass-card h-64 shimmer" />}

      {error && !data && (
        <div className="text-center py-12">
          <p className="text-rose-300 mb-4">Failed to load options data for {symbol}</p>
          <button onClick={() => mutate()} className="px-4 py-2 bg-emerald-600 hover:bg-emerald-500 text-white rounded-lg text-sm">
            Retry
          </button>
        </div>
      )}

      {data && data.error && (
        <div className="glass-card p-8 text-center">
          <p className="text-amber-300 text-sm">{data.error}</p>
        </div>
      )}

      {data && !data.error && data.oi_profile.length > 0 && (
        <>
          {/* Key levels */}
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
            <div className="glass-card p-3">
              <div className="text-xs text-slate-500">Max Pain</div>
              <div className="text-lg font-bold text-amber-400 tabular-nums">{data.max_pain.toFixed(2)}</div>
            </div>
            <div className="glass-card p-3">
              <div className="text-xs text-slate-500">Current Price</div>
              <div className="text-lg font-bold text-sky-400 tabular-nums">{data.current_price.toFixed(2)}</div>
            </div>
            <div className="glass-card p-3">
              <div className="text-xs text-slate-500">PCR (Put/Call)</div>
              <div className={`text-lg font-bold tabular-nums ${data.pcr > 1 ? "text-emerald-400" : "text-rose-400"}`}>
                {data.pcr.toFixed(2)}
              </div>
            </div>
            <div className="glass-card p-3">
              <div className="text-xs text-slate-500">Sentiment</div>
              <div className={`text-lg font-bold capitalize ${sentimentColor(data.sentiment)}`}>
                {data.sentiment.replace(/_/g, " ")}
              </div>
            </div>
          </div>

          {/* OI Summary */}
          <div className="glass-card p-4 space-y-2 text-sm">
            <div className="flex justify-between">
              <span className="text-slate-500">Expiry</span>
              <span className="text-slate-200 font-medium">{data.expiry ?? "—"}</span>
            </div>
            <div className="flex justify-between">
              <span className="text-slate-500">Total Call OI</span>
              <span className="text-rose-400 tabular-nums">{(data.total_call_oi / 1_000_000).toFixed(2)}M</span>
            </div>
            <div className="flex justify-between">
              <span className="text-slate-500">Total Put OI</span>
              <span className="text-emerald-400 tabular-nums">{(data.total_put_oi / 1_000_000).toFixed(2)}M</span>
            </div>
            <div className="flex justify-between">
              <span className="text-slate-500">Price vs Max Pain</span>
              <span className={`font-medium ${data.current_price >= data.max_pain ? "text-emerald-400" : "text-rose-400"}`}>
                {data.current_price >= data.max_pain ? "Above Max Pain" : "Below Max Pain"}
              </span>
            </div>
          </div>

          {/* Support / Resistance */}
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            <div className="glass-card p-4">
              <div className="text-sm font-semibold text-rose-400 mb-2">Resistance (High Call OI)</div>
              <div className="space-y-1">
                {data.resistance_levels.map((r, i) => (
                  <div key={i} className="flex justify-between text-xs">
                    <span className="text-slate-400">Strike {r.strike.toFixed(2)}</span>
                    <span className="text-rose-300 tabular-nums">{(r.call_oi! / 1000).toFixed(0)}k OI</span>
                  </div>
                ))}
                {data.resistance_levels.length === 0 && <span className="text-slate-500 text-xs">No data</span>}
              </div>
            </div>
            <div className="glass-card p-4">
              <div className="text-sm font-semibold text-emerald-400 mb-2">Support (High Put OI)</div>
              <div className="space-y-1">
                {data.support_levels.map((s, i) => (
                  <div key={i} className="flex justify-between text-xs">
                    <span className="text-slate-400">Strike {s.strike.toFixed(2)}</span>
                    <span className="text-emerald-300 tabular-nums">{(s.put_oi! / 1000).toFixed(0)}k OI</span>
                  </div>
                ))}
                {data.support_levels.length === 0 && <span className="text-slate-500 text-xs">No data</span>}
              </div>
            </div>
          </div>

          {/* OI Histogram */}
          <div className="glass-card p-4">
            <div className="text-sm font-semibold text-slate-300 mb-3">
              OI by Strike — {data.symbol} ({data.expiry ?? "nearest"})
            </div>
            <div className="flex text-[10px] text-slate-500 mb-1">
              <div className="w-1/2 text-center">← Call OI (Resistance)</div>
              <div className="w-16 text-center">Strike</div>
              <div className="w-1/2 text-center">Put OI (Support) →</div>
            </div>
            <div className="space-y-0.5 max-h-96 overflow-y-auto">
              {data.oi_profile.map((row, i) => (
                <OIBar key={i} row={row} maxOI={maxOI} currentPrice={data.current_price} />
              ))}
            </div>
          </div>

          {/* Legend */}
          <div className="flex flex-wrap items-center gap-4 text-xs text-slate-500">
            <div className="flex items-center gap-1">
              <div className="w-4 h-4 rounded bg-rose-600/40" />
              <span>Call OI (Resistance)</span>
            </div>
            <div className="flex items-center gap-1">
              <div className="w-4 h-4 rounded bg-emerald-600/40" />
              <span>Put OI (Support)</span>
            </div>
            <div className="flex items-center gap-1">
              <span className="text-sky-400 font-bold">▶</span>
              <span>Current Price</span>
            </div>
          </div>
        </>
      )}

      {data && !data.error && data.oi_profile.length === 0 && (
        <div className="glass-card p-8 text-center">
          <p className="text-amber-300 text-sm">No option chain data available for {symbol}.</p>
        </div>
      )}
    </div>
  );
}
