"use client";

import useSWR from "swr";
import { fetchCommodities, type CommodityPick } from "@/lib/api";
import StockSearch from "@/components/StockSearch";

export default function CommoditiesPage() {
  const { data, isLoading, error } = useSWR("commodities", fetchCommodities, {
    refreshInterval: 300000,
    keepPreviousData: true,
  });

  if (isLoading) {
    return (
      <div className="space-y-4">
        <Header />
        <StockSearch />
        <div className="grid gap-3 sm:grid-cols-2">
          {[1, 2, 3, 4].map((i) => (
            <div key={i} className="glass-card p-4">
              <div className="shimmer h-5 w-32 rounded mb-3" />
              <div className="shimmer h-3 w-full rounded mb-2" />
              <div className="shimmer h-3 w-2/3 rounded" />
            </div>
          ))}
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="space-y-4">
        <Header />
        <StockSearch />
        <div className="glass-card p-8 text-center">
          <p className="text-rose-300 text-sm">Failed to load commodity data. The free yfinance feed may be throttling.</p>
          <button onClick={() => window.location.reload()} className="mt-3 rounded-lg bg-slate-800 hover:bg-slate-700 px-4 py-2 text-sm transition-colors">Retry</button>
        </div>
      </div>
    );
  }

  const rows = data || [];
  const withBreakout = rows.filter((c) => c.side !== null);
  const degenerate = rows.length > 0 && rows.every(
    (c) => c.pdh > 0 && c.pdl > 0 && Math.abs(c.pdh - c.pdl) / c.pdh < 0.0005
  );

  return (
    <div className="space-y-5">
      <Header />

      <StockSearch />

      {degenerate && (
        <div className="glass-card p-4 border-amber-800/30 text-amber-300 text-sm">
          Market appears closed (weekend/holiday). Commodity levels shown below
          are stale placeholders — check back on a trading day for real breakout data.
        </div>
      )}

      {withBreakout.length > 0 && (
        <div>
          <h2 className="text-sm font-semibold text-emerald-400 mb-3 flex items-center gap-2">
            <span className="inline-block w-2 h-2 rounded-full bg-emerald-400 live-dot" />
            Breakouts Today ({withBreakout.length})
          </h2>
          <div className="grid gap-3 sm:grid-cols-2 fade-in">
            {withBreakout.map((c) => (
              <BreakoutCard key={c.symbol} c={c} />
            ))}
          </div>
        </div>
      )}

      <div>
        <h2 className="text-sm font-semibold text-slate-400 mb-3">All Commodities ({rows.length})</h2>
        <div className="grid gap-2 sm:grid-cols-2 fade-in">
          {rows.map((c) => {
            const note = c.explanation.caveats[0] || "";
            const status = c.side ? "BREAKOUT" : note ? "skip" : "no breakout";
            return (
              <div key={c.symbol} className="glass-card-hover p-3">
                <div className="flex items-center justify-between">
                  <div>
                    <div className="font-medium text-sm text-slate-200">{c.name}</div>
                    <div className="text-xs text-slate-500">{c.symbol}</div>
                  </div>
                  <span className={`text-xs font-medium px-2 py-0.5 rounded ${
                    c.side ? "bg-emerald-500/15 text-emerald-400" : "bg-slate-800 text-slate-400"
                  }`}>
                    {status}
                  </span>
                </div>
                <div className="grid grid-cols-3 gap-2 mt-2 pt-2 border-t border-slate-800/50">
                  <div className="text-center">
                    <div className="text-[10px] text-slate-400 uppercase">PDH</div>
                    <div className="text-sm tabular-nums text-slate-300">{fmt(c.pdh)}</div>
                  </div>
                  <div className="text-center">
                    <div className="text-[10px] text-slate-400 uppercase">PDL</div>
                    <div className="text-sm tabular-nums text-slate-300">{fmt(c.pdl)}</div>
                  </div>
                  <div className="text-center">
                    <div className="text-[10px] text-slate-400 uppercase">ATR</div>
                    <div className="text-sm tabular-nums text-slate-400">{fmt(c.atr)}</div>
                  </div>
                </div>
              </div>
            );
          })}
        </div>
        {withBreakout.length === 0 && (
          <p className="text-xs text-slate-400 mt-3">
            No breakouts above previous-day high on volume today. Levels above are
            reference; trade only on a confirmed breakout.
          </p>
        )}
      </div>
    </div>
  );
}

function BreakoutCard({ c }: { c: CommodityPick }) {
  return (
    <div className="glass-card-hover p-4 border-emerald-800/30">
      <div className="flex justify-between items-start">
        <div>
          <div className="font-semibold text-slate-100">{c.name}</div>
          <div className="text-xs text-slate-500">{c.symbol}</div>
        </div>
        <span className="text-xs font-medium rounded bg-emerald-500/15 text-emerald-400 border border-emerald-500/30 px-2 py-0.5">
          LONG
        </span>
      </div>
      <div className="grid grid-cols-4 gap-2 mt-3 pt-3 border-t border-slate-800/50">
        <Stat label="Entry" value={c.entry} color="text-sky-300" />
        <Stat label="SL" value={c.stop_loss} color="text-rose-300" />
        <Stat label="T1" value={c.target1} color="text-emerald-300" />
        <Stat label="T2" value={c.target2} color="text-emerald-300" />
      </div>
      <p className="text-xs text-slate-300 mt-3 leading-relaxed">{c.explanation.summary}</p>
    </div>
  );
}

function Header() {
  return (
    <div>
      <h1 className="text-lg font-semibold text-slate-100">Commodities — Intraday</h1>
      <p className="text-xs text-amber-300/80 mt-0.5">
        Data is a global USD futures proxy for MCX (free yfinance). Levels are reference, not INR tick data. Not advice.
      </p>
    </div>
  );
}

function Stat({ label, value, color }: { label: string; value: number | null; color: string }) {
  return (
    <div className="text-center">
      <div className="text-[10px] text-slate-400 uppercase">{label}</div>
      <div className={`text-sm font-semibold tabular-nums ${color}`}>{value != null ? value.toFixed(2) : "—"}</div>
    </div>
  );
}

function fmt(v: number) {
  return v != null ? v.toFixed(2) : "—";
}
