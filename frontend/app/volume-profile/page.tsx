"use client";

import { useState, useCallback } from "react";
import useSWR from "swr";
import { fetchVolumeProfile, type VolumeProfileRow } from "@/lib/api";

function ProfileRow({
  row,
  maxVolume,
  currentPrice,
}: {
  row: VolumeProfileRow;
  maxVolume: number;
  currentPrice: number;
}) {
  const widthPct = maxVolume > 0 ? (row.volume / maxVolume) * 100 : 0;
  const isNearPrice = currentPrice >= row.price_low && currentPrice <= row.price_high;

  return (
    <div className="flex items-center text-xs h-5">
      <div className="w-20 text-right pr-2 tabular-nums text-slate-500 truncate">
        {row.price_mid.toFixed(2)}
      </div>
      <div className="flex-1 relative">
        <div
          className={`h-4 rounded-sm flex items-center ${
            row.is_poc
              ? "bg-amber-600/60"
              : row.in_value_area
              ? "bg-emerald-600/30"
              : "bg-slate-700/30"
          }`}
          style={{ width: `${Math.max(widthPct, 2)}%` }}
        >
          {row.is_poc && <span className="ml-1 text-[9px] text-amber-200 font-bold">POC</span>}
        </div>
        {isNearPrice && (
          <div className="absolute right-0 top-0 bottom-0 flex items-center pr-1">
            <span className="text-[9px] text-sky-400 font-bold">▶</span>
          </div>
        )}
      </div>
      <div className="w-16 text-right pl-2 tabular-nums text-slate-500">
        {(row.volume / 1000).toFixed(0)}k
      </div>
    </div>
  );
}

export default function VolumeProfilePage() {
  const [symbol, setSymbol] = useState("RELIANCE");
  const [days, setDays] = useState(5);
  const [inputSymbol, setInputSymbol] = useState("RELIANCE");

  const { data, error, isLoading, mutate } = useSWR(
    symbol ? ["volume-profile", symbol, days] : null,
    () => fetchVolumeProfile(symbol, days, 50),
    { refreshInterval: 300000, keepPreviousData: true }
  );

  const handleSearch = useCallback(
    (e: React.FormEvent) => {
      e.preventDefault();
      if (inputSymbol.trim()) {
        setSymbol(inputSymbol.trim().toUpperCase());
      }
    },
    [inputSymbol]
  );

  const maxVolume = data ? Math.max(...data.rows.map((r) => r.volume), 1) : 1;

  return (
    <div className="space-y-6">
      {/* Header */}
      <div>
        <h1 className="text-xl font-bold text-slate-100">Volume Profile</h1>
        <p className="text-sm text-slate-500 mt-1">
          Volume-by-price histogram — POC, Value Area, and high/low volume nodes for support/resistance.
        </p>
      </div>

      {/* Search */}
      <form onSubmit={handleSearch} className="flex gap-2 flex-wrap items-center">
        <input
          type="text"
          value={inputSymbol}
          onChange={(e) => setInputSymbol(e.target.value)}
          placeholder="Enter symbol (e.g. RELIANCE, AAPL)"
          className="px-3 py-2 bg-slate-800 text-slate-100 rounded-lg text-sm border border-slate-700 focus:border-emerald-500 focus:outline-none w-48"
        />
        <select
          value={days}
          onChange={(e) => setDays(parseInt(e.target.value))}
          className="px-3 py-2 bg-slate-800 text-slate-100 rounded-lg text-sm border border-slate-700"
        >
          <option value={1}>1 day</option>
          <option value={3}>3 days</option>
          <option value={5}>5 days</option>
          <option value={10}>10 days</option>
          <option value={20}>20 days</option>
        </select>
        <button
          type="submit"
          className="px-4 py-2 bg-emerald-600 hover:bg-emerald-500 text-white rounded-lg text-sm font-medium"
        >
          Analyze
        </button>
      </form>

      {isLoading && !data && (
        <div className="glass-card h-96 shimmer" />
      )}

      {error && !data && (
        <div className="text-center py-12">
          <p className="text-rose-300 mb-4">Failed to load volume profile for {symbol}</p>
          <button onClick={() => mutate()} className="px-4 py-2 bg-emerald-600 hover:bg-emerald-500 text-white rounded-lg text-sm">
            Retry
          </button>
        </div>
      )}

      {data && data.rows.length > 0 && (
        <>
          {/* Key levels */}
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
            <div className="glass-card p-3">
              <div className="text-xs text-slate-500">POC (Point of Control)</div>
              <div className="text-lg font-bold text-amber-400 tabular-nums">{data.poc_price.toFixed(2)}</div>
            </div>
            <div className="glass-card p-3">
              <div className="text-xs text-slate-500">Value Area High</div>
              <div className="text-lg font-bold text-emerald-400 tabular-nums">{data.vah.toFixed(2)}</div>
            </div>
            <div className="glass-card p-3">
              <div className="text-xs text-slate-500">Value Area Low</div>
              <div className="text-lg font-bold text-rose-400 tabular-nums">{data.val.toFixed(2)}</div>
            </div>
            <div className="glass-card p-3">
              <div className="text-xs text-slate-500">Current Price</div>
              <div className={`text-lg font-bold tabular-nums ${data.current_price >= data.poc_price ? "text-emerald-400" : "text-rose-400"}`}>
                {data.current_price.toFixed(2)}
              </div>
            </div>
          </div>

          {/* VWAP & position */}
          <div className="glass-card p-4 space-y-2 text-sm">
            <div className="flex justify-between">
              <span className="text-slate-500">VWAP</span>
              <span className="text-slate-200 tabular-nums font-medium">{data.vwap.toFixed(2)}</span>
            </div>
            <div className="flex justify-between">
              <span className="text-slate-500">Prev Close</span>
              <span className="text-slate-200 tabular-nums">{data.prev_close.toFixed(2)}</span>
            </div>
            <div className="flex justify-between">
              <span className="text-slate-500">Price vs POC</span>
              <span className={`font-medium ${data.current_price >= data.poc_price ? "text-emerald-400" : "text-rose-400"}`}>
                {data.current_price >= data.poc_price ? "Above POC (bullish)" : "Below POC (bearish)"}
              </span>
            </div>
            <div className="flex justify-between">
              <span className="text-slate-500">In Value Area</span>
              <span className={`font-medium ${data.current_price >= data.val && data.current_price <= data.vah ? "text-emerald-400" : "text-amber-400"}`}>
                {data.current_price >= data.val && data.current_price <= data.vah ? "Yes" : "No"}
              </span>
            </div>
            <div className="flex justify-between">
              <span className="text-slate-500">Total Volume</span>
              <span className="text-slate-200 tabular-nums">{(data.total_volume / 1_000_000).toFixed(2)}M</span>
            </div>
          </div>

          {/* Histogram */}
          <div className="glass-card p-4">
            <div className="text-sm font-semibold text-slate-300 mb-3">
              Volume Profile — {data.symbol} ({data.days}d)
            </div>
            <div className="space-y-0.5">
              {data.rows.map((row, i) => (
                <ProfileRow
                  key={i}
                  row={row}
                  maxVolume={maxVolume}
                  currentPrice={data.current_price}
                />
              ))}
            </div>
          </div>

          {/* HVN / LVN */}
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            {data.hvn.length > 0 && (
              <div className="glass-card p-4">
                <div className="text-sm font-semibold text-emerald-400 mb-2">High Volume Nodes (Support/Resistance)</div>
                <div className="flex flex-wrap gap-2">
                  {data.hvn.map((p, i) => (
                    <span key={i} className="px-2 py-1 bg-emerald-950/40 text-emerald-300 rounded text-xs tabular-nums border border-emerald-800/30">
                      {p.toFixed(2)}
                    </span>
                  ))}
                </div>
              </div>
            )}
            {data.lvn.length > 0 && (
              <div className="glass-card p-4">
                <div className="text-sm font-semibold text-amber-400 mb-2">Low Volume Nodes (Fast Moves)</div>
                <div className="flex flex-wrap gap-2">
                  {data.lvn.map((p, i) => (
                    <span key={i} className="px-2 py-1 bg-amber-950/30 text-amber-300 rounded text-xs tabular-nums border border-amber-800/30">
                      {p.toFixed(2)}
                    </span>
                  ))}
                </div>
              </div>
            )}
          </div>

          {/* Legend */}
          <div className="flex flex-wrap items-center gap-4 text-xs text-slate-500">
            <div className="flex items-center gap-1">
              <div className="w-4 h-4 rounded bg-amber-600/60" />
              <span>POC (highest volume)</span>
            </div>
            <div className="flex items-center gap-1">
              <div className="w-4 h-4 rounded bg-emerald-600/30" />
              <span>Value Area (70% of volume)</span>
            </div>
            <div className="flex items-center gap-1">
              <div className="w-4 h-4 rounded bg-slate-700/30" />
              <span>Outside Value Area</span>
            </div>
            <div className="flex items-center gap-1">
              <span className="text-sky-400">▶</span>
              <span>Current Price</span>
            </div>
          </div>
        </>
      )}

      {data && data.rows.length === 0 && (
        <div className="glass-card p-8 text-center">
          <p className="text-amber-300 text-sm">No volume data available for {symbol}.</p>
        </div>
      )}
    </div>
  );
}
