"use client";

import { useState } from "react";
import useSWR from "swr";
import {
  fetchNseDividends,
  fetchUsDividends,
  fetchDividendDetail,
  type DividendData,
} from "@/lib/api";

function DividendCard({ d, currency, onSelect }: { d: DividendData; currency: string; onSelect: (s: string) => void }) {
  const [expanded, setExpanded] = useState(false);
  const today = new Date().toISOString().split("T")[0];
  const isUpcoming = d.ex_dividend_date && d.ex_dividend_date >= today;

  return (
    <div
      className={`glass-card-hover p-4 cursor-pointer fade-in ${isUpcoming ? "ring-1 ring-amber-500/30" : ""}`}
      onClick={() => { setExpanded(!expanded); onSelect(d.symbol); }}
    >
      <div className="flex items-start justify-between mb-2">
        <div>
          <div className="flex items-center gap-2">
            <span className="font-semibold text-slate-100">{d.symbol}</span>
            {isUpcoming && (
              <span className="text-[10px] font-bold rounded border px-1.5 py-0.5 text-amber-400 border-amber-500/30 bg-amber-500/10">
                EX {d.ex_dividend_date}
              </span>
            )}
          </div>
        </div>
        {d.dividend_yield != null && (
          <div className="text-right">
            <div className="text-lg font-bold text-emerald-400 tabular-nums">{d.dividend_yield.toFixed(2)}%</div>
            <div className="text-[10px] text-slate-500">YIELD</div>
          </div>
        )}
      </div>

      <div className="grid grid-cols-3 gap-2 text-xs">
        {d.dividend_rate != null && (
          <div>
            <span className="text-slate-500">Rate: </span>
            <span className="text-slate-300 tabular-nums">{currency}{d.dividend_rate.toFixed(2)}</span>
          </div>
        )}
        {d.payout_ratio != null && (
          <div>
            <span className="text-slate-500">Payout: </span>
            <span className="text-slate-300 tabular-nums">{d.payout_ratio.toFixed(0)}%</span>
          </div>
        )}
        {d.ex_dividend_date && (
          <div>
            <span className="text-slate-500">Ex: </span>
            <span className="text-slate-300">{d.ex_dividend_date}</span>
          </div>
        )}
      </div>

      {expanded && d.dividend_history.length > 0 && (
        <div className="mt-3 pt-3 border-t border-slate-800/50">
          <div className="text-[10px] text-slate-400 uppercase mb-2">Recent Dividends</div>
          <div className="space-y-1">
            {d.dividend_history.slice(0, 6).map((h, i) => (
              <div key={i} className="flex justify-between text-xs">
                <span className="text-slate-400">{h.date}</span>
                <span className="text-slate-300 tabular-nums">{currency}{h.amount.toFixed(4)}</span>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

export default function DividendsPage() {
  const [tab, setTab] = useState<"nse" | "us">("nse");
  const [selected, setSelected] = useState<string | null>(null);

  const { data: nseData, isLoading: nseLoading } = useSWR(tab === "nse" ? "nse-dividends" : null, fetchNseDividends, {
    refreshInterval: 300000,
    keepPreviousData: true,
  });
  const { data: usData, isLoading: usLoading } = useSWR(tab === "us" ? "us-dividends" : null, fetchUsDividends, {
    refreshInterval: 300000,
    keepPreviousData: true,
  });

  const { data: detail } = useSWR(
    selected ? `dividend-${selected}` : null,
    () => fetchDividendDetail(selected!),
    { keepPreviousData: true }
  );

  const data = tab === "nse" ? nseData : usData;
  const loading = tab === "nse" ? nseLoading : usLoading;
  const currency = tab === "nse" ? "₹" : "$";

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-xl font-bold text-slate-100">Dividend Calendar</h1>
        <p className="text-sm text-slate-500 mt-1">
          Screen stocks and ETFs by dividend yield — find income opportunities and upcoming ex-dividend dates.
        </p>
      </div>

      {/* Tabs */}
      <div className="flex gap-2">
        <button
          onClick={() => setTab("nse")}
          className={`px-4 py-2 rounded-lg text-sm font-medium transition-colors ${
            tab === "nse" ? "bg-emerald-600 text-white" : "bg-slate-800 text-slate-400 hover:bg-slate-700"
          }`}
        >
          NSE / India
        </button>
        <button
          onClick={() => setTab("us")}
          className={`px-4 py-2 rounded-lg text-sm font-medium transition-colors ${
            tab === "us" ? "bg-emerald-600 text-white" : "bg-slate-800 text-slate-400 hover:bg-slate-700"
          }`}
        >
          US Markets
        </button>
      </div>

      {loading && !data && (
        <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
          {Array.from({ length: 6 }).map((_, i) => (
            <div key={i} className="glass-card p-4 h-24 shimmer" />
          ))}
        </div>
      )}

      {data && data.length === 0 && (
        <div className="glass-card p-8 text-center">
          <p className="text-amber-300 text-sm">No dividend-paying securities found.</p>
        </div>
      )}

      {data && data.length > 0 && (
        <>
          <div className="text-sm text-slate-400">
            {data.length} dividend-paying {tab === "nse" ? "NSE" : "US"} securities · sorted by yield
          </div>
          <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
            {data.map((d) => (
              <DividendCard key={d.symbol} d={d} currency={currency} onSelect={setSelected} />
            ))}
          </div>
        </>
      )}
    </div>
  );
}
