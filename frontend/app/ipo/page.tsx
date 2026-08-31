"use client";

import { useState, useMemo } from "react";
import useSWR from "swr";
import { fetchIpoAll, type IpoData, type IpoResponse } from "@/lib/api";

type Board = "mainboard" | "sme";
type StatusFilter = "all" | "current" | "upcoming" | "recent";

function ScoreBadge({ score }: { score: number | null }) {
  if (score == null) return <span className="text-slate-600">—</span>;
  const cls = score >= 60 ? "text-emerald-400 bg-emerald-500/10" : score >= 35 ? "text-amber-400 bg-amber-500/10" : "text-rose-400 bg-rose-500/10";
  return <span className={`tabular-nums font-bold rounded px-1.5 py-0.5 text-xs ${cls}`}>{score.toFixed(0)}</span>;
}

function StatusPill({ status }: { status: string }) {
  const cls =
    status === "current" ? "text-emerald-400 border-emerald-500/30 bg-emerald-500/10"
    : status === "upcoming" ? "text-blue-400 border-blue-500/30 bg-blue-500/10"
    : "text-slate-500 border-slate-600/30 bg-slate-700/10";
  const label = status === "current" ? "OPEN" : status === "upcoming" ? "UPCOMING" : "LISTED";
  return <span className={`text-[10px] font-bold rounded border px-1.5 py-0.5 ${cls}`}>{label}</span>;
}

function SubBar({ label, value, max }: { label: string; value: number | null; max: number }) {
  const v = value ?? 0;
  const pct = max > 0 ? Math.min((v / max) * 100, 100) : 0;
  return (
    <div className="flex items-center gap-2 text-xs">
      <span className="text-slate-500 w-8">{label}</span>
      <div className="flex-1 h-2 bg-slate-800 rounded overflow-hidden">
        <div className="h-full bg-emerald-500/60 rounded" style={{ width: `${pct}%` }} />
      </div>
      <span className="text-slate-300 tabular-nums w-12 text-right">{value != null ? `${value.toFixed(2)}x` : "—"}</span>
    </div>
  );
}

function IpoRow({ ipo }: { ipo: IpoData }) {
  const [expanded, setExpanded] = useState(false);
  const sub = ipo.subscription;
  const subMax = sub ? Math.max(sub.qib ?? 0, sub.nii ?? 0, sub.rii ?? 0, sub.total ?? 0, 1) : 1;
  const gmp = ipo.gmp;
  const score = ipo.selection_score;
  const factors = ipo.score_factors;

  return (
    <>
      <tr
        className={`border-b border-slate-800/40 hover:bg-slate-800/30 cursor-pointer ${ipo.status === "current" ? "bg-emerald-900/5" : ""}`}
        onClick={() => setExpanded(!expanded)}
      >
        <td className="px-3 py-2.5">
          <div className="flex items-center gap-2">
            <StatusPill status={ipo.status} />
            <span className="text-slate-200 font-medium">{ipo.company_name}</span>
          </div>
          {ipo.symbol && ipo.symbol !== ipo.company_name && (
            <span className="text-[10px] text-slate-600 ml-12">{ipo.symbol}</span>
          )}
        </td>
        <td className="px-3 py-2.5 text-right tabular-nums text-slate-300">{ipo.price_band || "—"}</td>
        <td className="px-3 py-2.5 text-right tabular-nums text-slate-400">
          {ipo.issue_size_crs != null ? `${ipo.issue_size_crs.toFixed(0)}` : "—"}
        </td>
        <td className="px-3 py-2.5 text-right tabular-nums text-slate-400">{ipo.lot_size ?? "—"}</td>
        <td className="px-3 py-2.5 text-right text-slate-400 text-xs">
          {ipo.open_date ? <div>{ipo.open_date}</div> : <div className="text-slate-600">—</div>}
          {ipo.close_date && <div className="text-slate-500">{ipo.close_date}</div>}
        </td>
        <td className="px-3 py-2.5 text-right tabular-nums">
          {sub?.total != null ? (
            <span className={sub.total >= 10 ? "text-emerald-400 font-semibold" : "text-slate-300"}>
              {sub.total.toFixed(1)}x
            </span>
          ) : (
            <span className="text-slate-600">—</span>
          )}
        </td>
        <td className="px-3 py-2.5 text-right tabular-nums">
          {gmp?.premium != null ? (
            <span className={gmp.premium > 0 ? "text-emerald-400 font-semibold" : "text-rose-400"}>
              ₹{gmp.premium}
            </span>
          ) : (
            <span className="text-slate-600">—</span>
          )}
        </td>
        <td className="px-3 py-2.5 text-right tabular-nums">
          {gmp?.premium_pct != null ? (
            <span className={gmp.premium_pct > 0 ? "text-emerald-400" : "text-rose-400"}>
              {gmp.premium_pct > 0 ? "+" : ""}{gmp.premium_pct.toFixed(1)}%
            </span>
          ) : (
            <span className="text-slate-600">—</span>
          )}
        </td>
        <td className="px-3 py-2.5 text-center"><ScoreBadge score={score} /></td>
      </tr>
      {expanded && (
        <tr className="border-b border-slate-800/40 bg-slate-900/40">
          <td colSpan={9} className="px-6 py-4">
            <div className="grid sm:grid-cols-2 gap-4">
              {/* Subscription breakdown */}
              <div>
                <div className="text-[10px] text-slate-500 uppercase mb-2">Subscription Breakdown</div>
                {sub ? (
                  <div className="space-y-1.5">
                    <SubBar label="QIB" value={sub.qib} max={subMax} />
                    <SubBar label="NII" value={sub.nii} max={subMax} />
                    <SubBar label="RII" value={sub.rii} max={subMax} />
                    <SubBar label="Total" value={sub.total} max={subMax} />
                  </div>
                ) : (
                  <p className="text-xs text-slate-600">No subscription data (may not have opened yet).</p>
                )}
              </div>

              {/* Key dates + details */}
              <div className="space-y-1 text-xs">
                <div className="text-[10px] text-slate-500 uppercase mb-2">Details</div>
                <div className="grid grid-cols-2 gap-1">
                  <div><span className="text-slate-500">Allotment: </span><span className="text-slate-300">{ipo.allotment_date || "—"}</span></div>
                  <div><span className="text-slate-500">Listing: </span><span className="text-slate-300">{ipo.listing_date || "—"}</span></div>
                  <div><span className="text-slate-500">Face Value: </span><span className="text-slate-300">{ipo.face_value != null ? `₹${ipo.face_value}` : "—"}</span></div>
                  <div><span className="text-slate-500">Listing At: </span><span className="text-slate-300">{ipo.listing_at || "—"}</span></div>
                </div>
                <div className="mt-1"><span className="text-slate-500">Registrar: </span><span className="text-slate-300">{ipo.registrar || "—"}</span></div>
                <div><span className="text-slate-500">Market Maker: </span><span className="text-slate-300">{ipo.market_maker || "—"}</span></div>
                {ipo.lead_manager && <div><span className="text-slate-500">Lead Manager: </span><span className="text-slate-300">{ipo.lead_manager}</span></div>}
                {gmp?.last_updated && <div><span className="text-slate-500">GMP Updated: </span><span className="text-slate-400">{new Date(gmp.last_updated).toLocaleString()}</span></div>}
              </div>

              {/* Score breakdown */}
              {factors && (
                <div className="sm:col-span-2">
                  <div className="text-[10px] text-slate-500 uppercase mb-2">Selection Score Breakdown ({score?.toFixed(0)}/100)</div>
                  <div className="flex flex-wrap gap-1.5">
                    {Object.entries(factors).map(([k, v]) => (
                      <span key={k} className="text-[10px] text-slate-400 bg-slate-800/60 rounded px-1.5 py-0.5">
                        {k}: <span className="text-slate-200 tabular-nums">{v.toFixed(1)}</span>
                      </span>
                    ))}
                  </div>
                </div>
              )}
            </div>
          </td>
        </tr>
      )}
    </>
  );
}

export default function IpoPage() {
  const [board, setBoard] = useState<Board>("mainboard");
  const [filter, setFilter] = useState<StatusFilter>("all");

  const { data, isLoading } = useSWR<IpoResponse>("ipo-all", fetchIpoAll, {
    refreshInterval: 300000,
    keepPreviousData: true,
  });

  const ipos = useMemo(() => {
    if (!data) return [];
    const boardData = data[board];
    if (!boardData) return [];
    let list: IpoData[] = [
      ...(boardData.current || []),
      ...(boardData.upcoming || []),
      ...(boardData.recent || []),
    ];
    if (filter !== "all") {
      list = list.filter((ipo) => ipo.status === filter);
    }
    // Sort: current > upcoming > recent, then by score descending.
    const statusOrder = { current: 0, upcoming: 1, recent: 2 };
    list.sort((a, b) => {
      const so = statusOrder[a.status] - statusOrder[b.status];
      if (so !== 0) return so;
      return (b.selection_score ?? 0) - (a.selection_score ?? 0);
    });
    return list;
  }, [data, board, filter]);

  const counts = useMemo(() => {
    if (!data) return { current: 0, upcoming: 0, recent: 0 };
    const b = data[board];
    return {
      current: (b?.current || []).length,
      upcoming: (b?.upcoming || []).length,
      recent: (b?.recent || []).length,
    };
  }, [data, board]);

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-xl font-bold text-slate-100">IPO Center</h1>
        <p className="text-sm text-slate-500 mt-1">
          Current, upcoming, and recent IPOs with grey market premium, subscription data, and a selection score.
        </p>
      </div>

      {/* Board tabs */}
      <div className="flex gap-2">
        <button
          onClick={() => setBoard("mainboard")}
          className={`px-4 py-2 rounded-lg text-sm font-medium transition-colors ${
            board === "mainboard" ? "bg-emerald-600 text-white" : "bg-slate-800 text-slate-400 hover:bg-slate-700"
          }`}
        >
          Main Board
        </button>
        <button
          onClick={() => setBoard("sme")}
          className={`px-4 py-2 rounded-lg text-sm font-medium transition-colors ${
            board === "sme" ? "bg-amber-600 text-white" : "bg-slate-800 text-slate-400 hover:bg-slate-700"
          }`}
        >
          SME
        </button>
      </div>

      {/* Status filter chips */}
      <div className="flex gap-2">
        {(["all", "current", "upcoming", "recent"] as StatusFilter[]).map((f) => (
          <button
            key={f}
            onClick={() => setFilter(f)}
            className={`px-3 py-1 rounded-lg text-xs font-medium capitalize transition-colors ${
              filter === f ? "bg-slate-700 text-slate-100" : "bg-slate-800/50 text-slate-500 hover:bg-slate-800"
            }`}
          >
            {f}
            {f !== "all" && counts[f] > 0 && <span className="ml-1 text-slate-500">({counts[f]})</span>}
          </button>
        ))}
      </div>

      {isLoading && !data && (
        <div className="glass-card p-8 text-center">
          <p className="text-slate-400 text-sm">Loading IPO data...</p>
          <p className="text-xs text-slate-600 mt-1">First load fetches from NSE + GMP sources (~2-3s)</p>
        </div>
      )}

      {data?.error && (
        <div className="glass-card p-4 text-center">
          <p className="text-amber-300 text-sm">{data.error}</p>
          <p className="text-xs text-slate-600 mt-1">NSE IPO API may be temporarily unavailable. Data will retry on refresh.</p>
        </div>
      )}

      {data && ipos.length === 0 && !data.error && (
        <div className="glass-card p-8 text-center">
          <p className="text-amber-300 text-sm">No {filter !== "all" ? filter + " " : ""}{board} IPOs found at this time.</p>
        </div>
      )}

      {ipos.length > 0 && (
        <>
          <div className="text-sm text-slate-400">
            {ipos.length} {board === "sme" ? "SME" : "Main Board"} IPO{ipos.length !== 1 ? "s" : ""}
            {data?.refreshed_at && (
              <span className="text-slate-600"> · Updated {new Date(data.refreshed_at).toLocaleTimeString()}</span>
            )}
          </div>

          <div className="glass-card overflow-x-auto">
            <table className="w-full text-xs">
              <thead>
                <tr className="text-slate-500 border-b border-slate-800">
                  <th className="px-3 py-2 text-left font-medium">Company</th>
                  <th className="px-3 py-2 text-right font-medium">Price Band</th>
                  <th className="px-3 py-2 text-right font-medium">Issue (Cr)</th>
                  <th className="px-3 py-2 text-right font-medium">Lot</th>
                  <th className="px-3 py-2 text-right font-medium">Open–Close</th>
                  <th className="px-3 py-2 text-right font-medium">Sub (Total)</th>
                  <th className="px-3 py-2 text-right font-medium">GMP</th>
                  <th className="px-3 py-2 text-right font-medium">GMP%</th>
                  <th className="px-3 py-2 text-center font-medium">Score</th>
                </tr>
              </thead>
              <tbody>
                {ipos.map((ipo, i) => (
                  <IpoRow key={`${ipo.symbol}-${i}`} ipo={ipo} />
                ))}
              </tbody>
            </table>
          </div>

          <div className="glass-card p-4">
            <div className="text-xs text-slate-500 mb-2">Score Legend</div>
            <div className="flex flex-wrap gap-3 text-xs">
              <span className="flex items-center gap-1.5">
                <span className="w-3 h-3 rounded bg-emerald-500/30 border border-emerald-500/50" />
                <span className="text-slate-400">≥60 Strong interest</span>
              </span>
              <span className="flex items-center gap-1.5">
                <span className="w-3 h-3 rounded bg-amber-500/30 border border-amber-500/50" />
                <span className="text-slate-400">35–59 Moderate</span>
              </span>
              <span className="flex items-center gap-1.5">
                <span className="w-3 h-3 rounded bg-rose-500/30 border border-rose-500/50" />
                <span className="text-slate-400">&lt;35 Caution</span>
              </span>
            </div>
            <p className="text-[10px] text-slate-600 mt-2">
              Score factors: subscription momentum (25), GMP signal (20), issue pricing (15), issue size (10),
              timeline freshness (10), registrar quality (5), board (5), market maker (5), data completeness (5).
              GMP from third-party sources may be unavailable — shown as "—".
            </p>
          </div>
        </>
      )}
    </div>
  );
}
