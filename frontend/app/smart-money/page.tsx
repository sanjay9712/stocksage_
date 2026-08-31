"use client";

import { useState } from "react";
import useSWR from "swr";
import {
  fetchFiiDii,
  fetchInstitutional,
  type FiiDiiRow,
  type InstitutionalData,
} from "@/lib/api";

function fmtCr(v: number): string {
  if (Math.abs(v) >= 1000) return `₹${(v / 1000).toFixed(1)}K Cr`;
  return `₹${v.toFixed(0)} Cr`;
}

function fmtUsd(v: number | null | undefined): string {
  if (v == null) return "—";
  if (v >= 1e9) return `$${(v / 1e9).toFixed(2)}B`;
  if (v >= 1e6) return `$${(v / 1e6).toFixed(1)}M`;
  return `$${v.toFixed(0)}`;
}

function fmtShares(v: number | null | undefined): string {
  if (v == null) return "—";
  if (v >= 1e6) return `${(v / 1e6).toFixed(2)}M`;
  if (v >= 1e3) return `${(v / 1e3).toFixed(1)}K`;
  return v.toString();
}

function FiiDiiTable({ rows }: { rows: FiiDiiRow[] }) {
  if (!rows.length) {
    return (
      <div className="glass-card p-8 text-center">
        <p className="text-amber-300 text-sm">
          FII/DII data unavailable — NSE may be blocking the request or market is closed.
        </p>
      </div>
    );
  }

  return (
    <div className="glass-card overflow-hidden">
      <table className="w-full text-sm">
        <thead>
          <tr className="border-b border-slate-800 text-slate-400 text-xs uppercase">
            <th className="text-left px-4 py-3">Category</th>
            <th className="text-right px-4 py-3">Buy (₹ Cr)</th>
            <th className="text-right px-4 py-3">Sell (₹ Cr)</th>
            <th className="text-right px-4 py-3">Net (₹ Cr)</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((r) => {
            const isFii = r.category.toLowerCase().includes("fii") || r.category.toLowerCase().includes("fpi");
            const isDii = r.category.toLowerCase().includes("dii");
            return (
              <tr key={r.category} className="border-b border-slate-800/50 hover:bg-slate-800/20">
                <td className="px-4 py-3 font-medium text-slate-200">
                  {r.category}
                  {isFii && <span className="ml-2 text-[10px] text-sky-400 bg-sky-950/40 px-1.5 py-0.5 rounded">FOREIGN</span>}
                  {isDii && <span className="ml-2 text-[10px] text-emerald-400 bg-emerald-950/40 px-1.5 py-0.5 rounded">DOMESTIC</span>}
                </td>
                <td className="text-right px-4 py-3 tabular-nums text-emerald-400">{r.buy_value.toFixed(0)}</td>
                <td className="text-right px-4 py-3 tabular-nums text-rose-400">{r.sell_value.toFixed(0)}</td>
                <td className={`text-right px-4 py-3 tabular-nums font-bold ${r.net_value > 0 ? "text-emerald-400" : r.net_value < 0 ? "text-rose-400" : "text-slate-400"}`}>
                  {r.net_value > 0 ? "+" : ""}{r.net_value.toFixed(0)}
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}

function InstitutionalLookup() {
  const [symbol, setSymbol] = useState("");
  const [searched, setSearched] = useState("");

  const { data, isLoading, error } = useSWR<InstitutionalData>(
    searched ? `institutional-${searched}` : null,
    () => fetchInstitutional(searched),
    { keepPreviousData: true }
  );

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (symbol.trim()) setSearched(symbol.trim().toUpperCase());
  }

  return (
    <div className="space-y-4">
      <form onSubmit={handleSubmit} className="flex gap-2">
        <input
          type="text"
          value={symbol}
          onChange={(e) => setSymbol(e.target.value)}
          placeholder="Enter US stock symbol (e.g. AAPL, MSFT, GOOGL)"
          className="flex-1 px-3 py-2 bg-slate-950 border border-slate-800 rounded-lg text-slate-100 focus:outline-none focus:border-emerald-500 text-sm"
        />
        <button
          type="submit"
          className="px-4 py-2 bg-emerald-600 hover:bg-emerald-500 text-white rounded-lg text-sm font-medium transition-colors"
        >
          Search
        </button>
      </form>

      {isLoading && (
        <div className="glass-card p-6">
          <div className="shimmer h-4 w-48 rounded mb-3" />
          <div className="shimmer h-3 w-full rounded mb-2" />
          <div className="shimmer h-3 w-2/3 rounded" />
        </div>
      )}

      {error && !isLoading && (
        <div className="glass-card p-6 text-center">
          <p className="text-rose-300 text-sm">Failed to load institutional data for {searched}.</p>
        </div>
      )}

      {data && !isLoading && (
        <div className="glass-card p-5 space-y-4 fade-in">
          <div className="flex items-center justify-between">
            <h3 className="text-lg font-semibold text-slate-100">{data.symbol}</h3>
            <div className="flex gap-3">
              {data.institutional_pct != null && (
                <div className="text-right">
                  <div className="text-[10px] text-slate-400 uppercase">Institutional</div>
                  <div className="text-lg font-bold text-sky-400 tabular-nums">{data.institutional_pct.toFixed(1)}%</div>
                </div>
              )}
              {data.insider_pct != null && (
                <div className="text-right">
                  <div className="text-[10px] text-slate-400 uppercase">Insider</div>
                  <div className="text-lg font-bold text-amber-400 tabular-nums">{data.insider_pct.toFixed(1)}%</div>
                </div>
              )}
            </div>
          </div>

          {/* Ownership bar */}
          {data.institutional_pct != null && data.insider_pct != null && (
            <div>
              <div className="flex h-3 rounded-full overflow-hidden bg-slate-800">
                <div className="bg-sky-500" style={{ width: `${data.institutional_pct}%` }} />
                <div className="bg-amber-500" style={{ width: `${data.insider_pct}%` }} />
              </div>
              <div className="flex justify-between mt-1 text-[10px] text-slate-500">
                <span>Institutional {data.institutional_pct.toFixed(1)}%</span>
                <span>Insider {data.insider_pct.toFixed(1)}%</span>
                <span>Public {(100 - data.institutional_pct - data.insider_pct).toFixed(1)}%</span>
              </div>
            </div>
          )}

          {/* Top holders */}
          {data.top_holders.length > 0 ? (
            <div>
              <h4 className="text-sm font-semibold text-slate-300 mb-2">Top Institutional Holders</h4>
              <div className="space-y-2">
                {data.top_holders.map((h, i) => (
                  <div key={i} className="flex items-center justify-between py-2 px-3 bg-slate-900/50 rounded-lg">
                    <div className="flex items-center gap-3 min-w-0">
                      <span className="text-xs font-mono text-slate-500">#{i + 1}</span>
                      <span className="text-sm text-slate-200 truncate">{h.holder}</span>
                    </div>
                    <div className="flex items-center gap-4 shrink-0 text-xs">
                      {h.shares != null && (
                        <div className="text-right">
                          <div className="text-slate-500">Shares</div>
                          <div className="text-slate-300 tabular-nums">{fmtShares(h.shares)}</div>
                        </div>
                      )}
                      {h.value != null && (
                        <div className="text-right">
                          <div className="text-slate-500">Value</div>
                          <div className="text-slate-300 tabular-nums">{fmtUsd(h.value)}</div>
                        </div>
                      )}
                      {h.pct_out != null && (
                        <div className="text-right">
                          <div className="text-slate-500">% Out</div>
                          <div className="text-emerald-400 tabular-nums font-medium">{h.pct_out.toFixed(2)}%</div>
                        </div>
                      )}
                    </div>
                  </div>
                ))}
              </div>
              <p className="text-[10px] text-slate-500 mt-2">Source: SEC 13F filings via Yahoo Finance. Updated quarterly.</p>
            </div>
          ) : (
            <p className="text-sm text-slate-500">No institutional holder data available for {data.symbol}.</p>
          )}
        </div>
      )}
    </div>
  );
}

export default function SmartMoneyPage() {
  const { data: fiiDii, isLoading: fiiLoading, error: fiiError } = useSWR("fii-dii", fetchFiiDii, {
    refreshInterval: 300000,
    keepPreviousData: true,
  });

  const totalNet = fiiDii?.reduce((sum, r) => sum + r.net_value, 0) ?? 0;
  const fiiNet = fiiDii?.filter(r => r.category.toLowerCase().includes("fii") || r.category.toLowerCase().includes("fpi")).reduce((s, r) => s + r.net_value, 0) ?? 0;
  const diiNet = fiiDii?.filter(r => r.category.toLowerCase().includes("dii")).reduce((s, r) => s + r.net_value, 0) ?? 0;

  return (
    <div className="space-y-8">
      <div>
        <h1 className="text-xl font-bold text-slate-100">Smart Money / Institutional Flow</h1>
        <p className="text-sm text-slate-500 mt-1">
          Track where institutions are putting their money — FII/DII for India, top holders for US stocks.
        </p>
      </div>

      {/* NSE: FII/DII */}
      <section>
        <h2 className="text-lg font-semibold text-slate-200 mb-4">NSE — FII / DII Cash Flow</h2>

        {/* Summary cards */}
        <div className="grid grid-cols-1 sm:grid-cols-3 gap-3 mb-4">
          <div className="glass-card p-4">
            <div className="text-[10px] text-slate-400 uppercase">FII Net</div>
            <div className={`text-2xl font-bold tabular-nums ${fiiNet > 0 ? "text-emerald-400" : fiiNet < 0 ? "text-rose-400" : "text-slate-400"}`}>
              {fiiLoading ? "—" : `${fiiNet > 0 ? "+" : ""}₹${fiiNet.toFixed(0)} Cr`}
            </div>
          </div>
          <div className="glass-card p-4">
            <div className="text-[10px] text-slate-400 uppercase">DII Net</div>
            <div className={`text-2xl font-bold tabular-nums ${diiNet > 0 ? "text-emerald-400" : diiNet < 0 ? "text-rose-400" : "text-slate-400"}`}>
              {fiiLoading ? "—" : `${diiNet > 0 ? "+" : ""}₹${diiNet.toFixed(0)} Cr`}
            </div>
          </div>
          <div className="glass-card p-4">
            <div className="text-[10px] text-slate-400 uppercase">Total Net</div>
            <div className={`text-2xl font-bold tabular-nums ${totalNet > 0 ? "text-emerald-400" : totalNet < 0 ? "text-rose-400" : "text-slate-400"}`}>
              {fiiLoading ? "—" : `${totalNet > 0 ? "+" : ""}₹${totalNet.toFixed(0)} Cr`}
            </div>
          </div>
        </div>

        {fiiLoading && !fiiDii && (
          <div className="glass-card p-8">
            <div className="shimmer h-4 w-full rounded mb-3" />
            <div className="shimmer h-4 w-2/3 rounded" />
          </div>
        )}

        {fiiDii && <FiiDiiTable rows={fiiDii} />}

        {fiiError && !fiiDii && (
          <div className="glass-card p-8 text-center">
            <p className="text-amber-300 text-sm">
              Could not fetch FII/DII data. NSE may be blocking requests. Try again later.
            </p>
          </div>
        )}
      </section>

      {/* US: Institutional holders */}
      <section>
        <h2 className="text-lg font-semibold text-slate-200 mb-4">US — Institutional Holders Lookup</h2>
        <InstitutionalLookup />
      </section>
    </div>
  );
}
