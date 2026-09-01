"use client";

import { useState } from "react";
import useSWR from "swr";
import { fetchSignalAlerts, refreshSignalAlerts, type SignalAlertEntry } from "@/lib/api";

const ALL_SIGNAL_TYPES = [
  { value: "rsi_oversold", label: "RSI Oversold" },
  { value: "rsi_overbought", label: "RSI Overbought" },
  { value: "ema_cross_up", label: "EMA Cross Up" },
  { value: "ema_cross_down", label: "EMA Cross Down" },
  { value: "bb_squeeze", label: "BB Squeeze" },
  { value: "volume_spike", label: "Volume Spike" },
  { value: "donchian_breakout", label: "Donchian Breakout" },
  { value: "macd_cross_up", label: "MACD Cross Up" },
];

const sideColors: Record<string, string> = {
  long: "bg-emerald-900/40 text-emerald-400",
  short: "bg-rose-900/40 text-rose-400",
  watch: "bg-amber-900/40 text-amber-400",
};

export default function SignalAlertsPage() {
  const [market, setMarket] = useState<"nse" | "us">("nse");
  const [selectedTypes, setSelectedTypes] = useState<string[]>([]);
  const [refreshing, setRefreshing] = useState(false);
  const [refreshError, setRefreshError] = useState<string | null>(null);

  const signalTypesParam = selectedTypes.length > 0 ? selectedTypes.join(",") : undefined;
  const { data, error, isLoading, mutate } = useSWR(
    ["signal-alerts", market, signalTypesParam],
    () => fetchSignalAlerts(market, signalTypesParam),
    { refreshInterval: 60000, keepPreviousData: true }
  );

  const toggleType = (value: string) => {
    setSelectedTypes((prev) =>
      prev.includes(value) ? prev.filter((t) => t !== value) : [...prev, value]
    );
  };

  const handleRefresh = async () => {
    setRefreshing(true);
    setRefreshError(null);
    try {
      await refreshSignalAlerts(market);
      await mutate();
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "Failed to refresh signals.";
      setRefreshError(msg);
    } finally {
      setRefreshing(false);
    }
  };

  const signals = data?.signals || [];
  const currency = market === "nse" ? "₹" : "$";

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-bold text-slate-100">Signal Alerts</h1>
          <p className="text-sm text-slate-500 mt-1">
            Technical signal scanner — RSI, EMA crossover, volume spikes, breakouts & more.
          </p>
        </div>
        <div className="flex items-center gap-2">
          {data?.market_status && (
            <span className={`text-xs px-2 py-1 rounded-full ${
              data.market_status.market_open ? "bg-emerald-900/40 text-emerald-400" : "bg-slate-800 text-slate-500"
            }`}>
              {data.market_status.market_open ? "LIVE" : "CLOSED"}
            </span>
          )}
          <button
            onClick={handleRefresh}
            disabled={refreshing}
            className="px-4 py-1.5 bg-slate-800 hover:bg-slate-700 text-slate-300 rounded-lg text-xs font-medium disabled:opacity-40"
          >
            {refreshing ? "Refreshing…" : "Refresh"}
          </button>
        </div>
      </div>

      {refreshError && (
        <div className="glass-card p-3 border-l-4 border-rose-500/50 flex items-start gap-2">
          <span className="text-rose-400 text-sm">⚠</span>
          <p className="text-sm text-rose-300 flex-1">{refreshError}</p>
          <button onClick={() => setRefreshError(null)} className="text-slate-500 hover:text-slate-300 text-xs">✕</button>
        </div>
      )}

      {error && !data && (
        <div className="text-center py-12">
          <p className="text-rose-300 mb-2">Failed to load signal alerts</p>
          <p className="text-xs text-slate-500 mb-4">{error instanceof Error ? error.message : "Unknown error"}</p>
          <button onClick={() => mutate()} className="px-4 py-2 bg-emerald-600 hover:bg-emerald-500 text-white rounded-lg text-sm">
            Retry
          </button>
        </div>
      )}

      {/* Market + Signal Type Filter */}
      <div className="glass-card p-4 space-y-3">
        <div className="flex gap-2">
          {(["nse", "us"] as const).map((m) => (
            <button
              key={m}
              onClick={() => setMarket(m)}
              className={`px-4 py-1.5 rounded-lg text-xs font-medium ${
                market === m ? "bg-emerald-600 text-white" : "bg-slate-800 text-slate-400"
              }`}
            >
              {m === "nse" ? "NSE (India)" : "US Markets"}
            </button>
          ))}
        </div>
        <div>
          <label className="text-xs text-slate-500 block mb-2">Signal Types (leave empty for all)</label>
          <div className="flex flex-wrap gap-2">
            {ALL_SIGNAL_TYPES.map((t) => {
              const active = selectedTypes.includes(t.value);
              return (
                <button
                  key={t.value}
                  onClick={() => toggleType(t.value)}
                  className={`px-2.5 py-1 rounded-lg text-xs font-medium transition-colors ${
                    active ? "bg-emerald-600 text-white" : "bg-slate-800 text-slate-400 hover:bg-slate-700"
                  }`}
                >
                  {t.label}
                </button>
              );
            })}
          </div>
        </div>
      </div>

      {/* Results */}
      {isLoading && !data && (
        <div className="glass-card p-8 text-center">
          <div className="shimmer h-5 w-48 rounded mx-auto mb-3" />
          <div className="shimmer h-3 w-full rounded mb-2" />
          <div className="shimmer h-3 w-2/3 rounded" />
          <p className="text-xs text-slate-500 mt-3">Scanning {market === "nse" ? "NSE" : "US"} universe for signals…</p>
        </div>
      )}

      {signals.length === 0 && !isLoading && (
        <div className="glass-card p-8 text-center">
          <p className="text-sm text-slate-500">
            {data ? "No signals triggered in the current scan." : "Loading signals..."}
          </p>
        </div>
      )}

      {signals.length > 0 && (
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
          {signals.map((s, i) => (
            <SignalCard key={`${s.symbol}-${s.signal_type}-${i}`} signal={s} market={market} />
          ))}
        </div>
      )}
    </div>
  );
}

function SignalCard({ signal, market }: { signal: SignalAlertEntry; market: "nse" | "us" }) {
  const currency = market === "nse" ? "₹" : "$";
  return (
    <div className="glass-card p-3 space-y-2">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <span className="font-semibold text-slate-100 text-sm">{signal.symbol}</span>
          <span className="text-[10px] text-slate-500">{signal.name}</span>
        </div>
        <div className="flex items-center gap-1.5">
          <span className={`text-[10px] px-2 py-0.5 rounded-full font-semibold ${sideColors[signal.side] || "bg-slate-800"}`}>
            {signal.side.toUpperCase()}
          </span>
          <span className="text-[10px] text-slate-500">
            {signal.confidence > 0.7 ? "High" : signal.confidence > 0.5 ? "Medium" : "Low"}
          </span>
        </div>
      </div>
      <div className="text-xs text-slate-400">{signal.description}</div>
      <div className="text-[10px] text-slate-600 uppercase tracking-wide">{signal.signal_type.replace(/_/g, " ")}</div>
      {signal.entry && (
        <div className="flex items-center gap-3 text-xs pt-1 border-t border-slate-800/50">
          <div>
            <span className="text-slate-600">Entry</span>
            <span className="ml-1 text-slate-300 tabular-nums">{currency}{signal.entry}</span>
          </div>
          {signal.stop_loss && (
            <div>
              <span className="text-slate-600">SL</span>
              <span className="ml-1 text-rose-400 tabular-nums">{currency}{signal.stop_loss}</span>
            </div>
          )}
          {signal.target && (
            <div>
              <span className="text-slate-600">Target</span>
              <span className="ml-1 text-emerald-400 tabular-nums">{currency}{signal.target}</span>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
