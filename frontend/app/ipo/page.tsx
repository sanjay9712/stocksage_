"use client";

import { useState, useMemo } from "react";
import Link from "next/link";
import useSWR from "swr";
import { fetchIpoAll, type IpoData, type IpoResponse, type IpoTimeline, type IpoRecommendation } from "@/lib/api";

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

function FinTable({ title, data }: { title: string; data: Record<string, Record<string, number | string>> | null }) {
  if (!data) return null;
  const metrics = Object.keys(data);
  if (metrics.length === 0) return null;
  const years = Array.from(new Set(metrics.flatMap(m => Object.keys(data[m]))));
  return (
    <div>
      <div className="text-[10px] text-slate-500 uppercase mb-2">{title}</div>
      <div className="overflow-x-auto">
        <table className="w-full text-[11px]">
          <thead>
            <tr className="text-slate-500 border-b border-slate-800">
              <th className="px-2 py-1 text-left font-medium">Metric</th>
              {years.map(y => <th key={y} className="px-2 py-1 text-right font-medium">{y}</th>)}
            </tr>
          </thead>
          <tbody>
            {metrics.map(m => (
              <tr key={m} className="border-b border-slate-800/40">
                <td className="px-2 py-1 text-slate-400">{m}</td>
                {years.map(y => {
                  const v = data[m][y];
                  return <td key={y} className="px-2 py-1 text-right tabular-nums text-slate-300">{v != null ? v : "—"}</td>;
                })}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

function GmpHistory({ history }: { history: { date: string; gmp: number | null; subject_to_sauda: number | null }[] | null }) {
  if (!history || history.length === 0) return null;
  const recent = history.slice(0, 7);
  return (
    <div>
      <div className="text-[10px] text-slate-500 uppercase mb-2">GMP History</div>
      <div className="overflow-x-auto">
        <table className="w-full text-[11px]">
          <thead>
            <tr className="text-slate-500 border-b border-slate-800">
              <th className="px-2 py-1 text-left font-medium">Date</th>
              <th className="px-2 py-1 text-right font-medium">GMP (₹)</th>
              <th className="px-2 py-1 text-right font-medium">Sauda (₹)</th>
            </tr>
          </thead>
          <tbody>
            {recent.map((h, i) => (
              <tr key={i} className="border-b border-slate-800/40">
                <td className="px-2 py-1 text-slate-400">{h.date}</td>
                <td className="px-2 py-1 text-right tabular-nums text-slate-300">{h.gmp != null ? `₹${h.gmp}` : "—"}</td>
                <td className="px-2 py-1 text-right tabular-nums text-slate-300">{h.subject_to_sauda != null ? `₹${h.subject_to_sauda}` : "—"}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

function PeerTable({ peers }: { peers: { company: string; [k: string]: number | string }[] | null }) {
  if (!peers || peers.length === 0) return null;
  const cols = peers.length > 0 ? Object.keys(peers[0]).filter(k => k !== "company") : [];
  return (
    <div>
      <div className="text-[10px] text-slate-500 uppercase mb-2">Peer Comparison</div>
      <div className="overflow-x-auto">
        <table className="w-full text-[11px]">
          <thead>
            <tr className="text-slate-500 border-b border-slate-800">
              <th className="px-2 py-1 text-left font-medium">Company</th>
              {cols.map(c => <th key={c} className="px-2 py-1 text-right font-medium whitespace-nowrap">{c}</th>)}
            </tr>
          </thead>
          <tbody>
            {peers.map((p, i) => (
              <tr key={i} className={`border-b border-slate-800/40 ${i === 0 ? "bg-emerald-900/10" : ""}`}>
                <td className="px-2 py-1 text-slate-300 font-medium">{p.company}</td>
                {cols.map(c => {
                  const v = p[c];
                  return <td key={c} className="px-2 py-1 text-right tabular-nums text-slate-400">{v != null ? v : "—"}</td>;
                })}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

function VerdictBanner({ rec, score }: { rec: IpoRecommendation; score: number | null }) {
  const styles: Record<string, { bar: string; chip: string; label: string }> = {
    Apply: { bar: "border-emerald-600/50 bg-emerald-950/20", chip: "text-emerald-300 bg-emerald-500/15 border-emerald-500/30", label: "APPLY" },
    Consider: { bar: "border-amber-600/50 bg-amber-950/20", chip: "text-amber-300 bg-amber-500/15 border-amber-500/30", label: "CONSIDER" },
    Avoid: { bar: "border-rose-600/50 bg-rose-950/20", chip: "text-rose-300 bg-rose-500/15 border-rose-500/30", label: "AVOID" },
    "Insufficient Data": { bar: "border-slate-600/50 bg-slate-900/20", chip: "text-slate-300 bg-slate-500/15 border-slate-500/30", label: "INSUFFICIENT DATA" },
  };
  const s = styles[rec.verdict] ?? styles["Insufficient Data"];
  return (
    <div className={`lg:col-span-2 rounded-xl border ${s.bar} p-4`}>
      <div className="flex items-center gap-3 mb-2">
        <span className={`text-sm font-bold rounded border px-2.5 py-1 ${s.chip}`}>{s.label}</span>
        {score != null && <span className="text-xs text-slate-500">Score: {score.toFixed(0)}/100</span>}
      </div>
      <p className="text-sm text-slate-300">{rec.summary}</p>
      {rec.critical_flags.length > 0 && (
        <div className="mt-2 flex flex-wrap gap-1.5">
          {rec.critical_flags.map((f, i) => (
            <span key={i} className="text-[11px] text-rose-300 bg-rose-950/40 border border-rose-800/40 rounded px-2 py-0.5">
              ⚠ {f}
            </span>
          ))}
        </div>
      )}
      <div className="grid sm:grid-cols-2 gap-4 mt-3">
        {rec.pros.length > 0 && (
          <div>
            <div className="text-[10px] text-emerald-500 uppercase mb-1.5 font-semibold">Pros</div>
            <ul className="space-y-1">
              {rec.pros.map((p, i) => (
                <li key={i} className="text-[11px] text-slate-400 flex gap-1.5">
                  <span className="text-emerald-500 shrink-0">+</span>
                  <span>{p}</span>
                </li>
              ))}
            </ul>
          </div>
        )}
        {rec.cons.length > 0 && (
          <div>
            <div className="text-[10px] text-rose-500 uppercase mb-1.5 font-semibold">Cons</div>
            <ul className="space-y-1">
              {rec.cons.map((c, i) => (
                <li key={i} className="text-[11px] text-slate-400 flex gap-1.5">
                  <span className="text-rose-500 shrink-0">−</span>
                  <span>{c}</span>
                </li>
              ))}
            </ul>
          </div>
        )}
      </div>
    </div>
  );
}

function IssueStructure({ rec }: { rec: IpoRecommendation }) {
  const s = rec.issue_structure;
  if (s.fresh_pct == null && s.ofs_pct == null) return null;
  return (
    <div>
      <div className="text-[10px] text-slate-500 uppercase mb-2">Issue Structure</div>
      <div className="flex h-6 rounded-lg overflow-hidden border border-slate-700/50">
        {s.fresh_pct != null && s.fresh_pct > 0 && (
          <div className="bg-emerald-600/60 flex items-center justify-center" style={{ width: `${s.fresh_pct}%` }}>
            <span className="text-[10px] font-bold text-white">Fresh {s.fresh_pct.toFixed(0)}%</span>
          </div>
        )}
        {s.ofs_pct != null && s.ofs_pct > 0 && (
          <div className="bg-amber-600/60 flex items-center justify-center" style={{ width: `${s.ofs_pct}%` }}>
            <span className="text-[10px] font-bold text-white">OFS {s.ofs_pct.toFixed(0)}%</span>
          </div>
        )}
      </div>
      <div className="grid grid-cols-2 gap-1 mt-2">
        <div><span className="text-slate-500">Fresh Issue: </span><span className="text-emerald-300">{s.fresh_issue_crs != null ? `₹${s.fresh_issue_crs.toFixed(0)} Cr` : "—"}</span></div>
        <div><span className="text-slate-500">OFS: </span><span className="text-amber-300">{s.ofs_amount_crs != null ? `₹${s.ofs_amount_crs.toFixed(0)} Cr` : "—"}</span></div>
      </div>
      {s.promoter_exit_heavy && (
        <p className="text-[10px] text-amber-400 mt-1.5">⚠ Promoter exit heavy — OFS exceeds 50% of the issue.</p>
      )}
    </div>
  );
}

function ValuationCard({ rec }: { rec: IpoRecommendation }) {
  const v = rec.valuation;
  if (v.ipo_pe == null && v.peer_pe_avg == null) return null;
  const discount = v.discount_to_peers_pct;
  return (
    <div>
      <div className="text-[10px] text-slate-500 uppercase mb-2">Valuation vs Peers</div>
      <div className="grid grid-cols-3 gap-2 text-center">
        <div className="stat-box">
          <div className="text-[10px] text-slate-500">IPO PE</div>
          <div className="text-sm font-semibold tabular-nums text-slate-200">{v.ipo_pe?.toFixed(1) ?? "—"}</div>
        </div>
        <div className="stat-box">
          <div className="text-[10px] text-slate-500">Peer Avg PE</div>
          <div className="text-sm font-semibold tabular-nums text-slate-200">{v.peer_pe_avg?.toFixed(1) ?? "—"}</div>
        </div>
        <div className="stat-box">
          <div className="text-[10px] text-slate-500">vs Peers</div>
          <div className={`text-sm font-semibold tabular-nums ${discount != null ? (discount < 0 ? "text-emerald-400" : "text-rose-400") : "text-slate-400"}`}>
            {discount != null ? `${discount > 0 ? "+" : ""}${discount.toFixed(1)}%` : "—"}
          </div>
        </div>
      </div>
      {discount != null && (
        <p className="text-[10px] text-slate-500 mt-1.5">
          {discount < 0
            ? `Priced ${Math.abs(discount).toFixed(0)}% below peer average — potentially undervalued.`
            : `Priced ${discount.toFixed(0)}% above peer average — check if growth justifies the premium.`}
        </p>
      )}
    </div>
  );
}

function TimelineView({ timeline }: { timeline: IpoTimeline | null }) {
  if (!timeline) return null;
  const entries = Object.entries(timeline).filter(([, v]) => v);
  if (entries.length === 0) return null;
  const labels: Record<string, string> = {
    open_date: "IPO Open",
    close_date: "IPO Close",
    allotment_date: "Allotment",
    refund_date: "Refund Initiation",
    demat_credit_date: "Demat Credit",
    listing_date: "Listing",
  };
  return (
    <div>
      <div className="text-[10px] text-slate-500 uppercase mb-2">IPO Timeline</div>
      <div className="flex flex-wrap gap-2">
        {entries.map(([k, v]) => (
          <div key={k} className="text-[11px] bg-slate-800/60 rounded px-2 py-1">
            <span className="text-slate-500">{labels[k] || k}: </span>
            <span className="text-slate-300">{v}</span>
          </div>
        ))}
      </div>
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
  const fin = ipo.financials;
  const metrics = ipo.per_share_metrics;
  const ratios = ipo.return_ratios;
  const peers = ipo.peer_comparison;
  const timeline = ipo.ipo_timeline;
  const anchor = ipo.anchor_investors;
  const gmpHistory = ipo.gmp_history;
  const rec = ipo.recommendation;

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
            <div className="grid lg:grid-cols-2 gap-4">
              {/* Recommendation verdict banner */}
              {rec && <VerdictBanner rec={rec} score={score} />}

              {/* Issue structure */}
              {rec && <IssueStructure rec={rec} />}

              {/* Valuation vs peers */}
              {rec && <ValuationCard rec={rec} />}

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

                {/* Quota percentages */}
                {ipo.quota_percent && Object.keys(ipo.quota_percent).length > 0 && (
                  <div className="mt-3">
                    <div className="text-[10px] text-slate-500 uppercase mb-1">Quota Allocation</div>
                    <div className="flex flex-wrap gap-1.5">
                      {Object.entries(ipo.quota_percent).map(([k, v]) => (
                        <span key={k} className="text-[10px] text-slate-400 bg-slate-800/60 rounded px-1.5 py-0.5">
                          {k}: <span className="text-slate-200">{v}%</span>
                        </span>
                      ))}
                    </div>
                  </div>
                )}
              </div>

              {/* Key details */}
              <div className="space-y-1 text-xs">
                <div className="text-[10px] text-slate-500 uppercase mb-2">Issue Details</div>
                <div className="grid grid-cols-2 gap-1">
                  <div><span className="text-slate-500">Fresh Issue: </span><span className="text-slate-300">{ipo.fresh_issue_crs != null ? `₹${ipo.fresh_issue_crs} Cr` : "—"}</span></div>
                  <div><span className="text-slate-500">OFS: </span><span className="text-slate-300">{ipo.offer_for_sale || "—"}</span></div>
                  <div><span className="text-slate-500">Face Value: </span><span className="text-slate-300">{ipo.face_value != null ? `₹${ipo.face_value}` : "—"}</span></div>
                  <div><span className="text-slate-500">Lot Value: </span><span className="text-slate-300">{ipo.lot_value != null ? `₹${ipo.lot_value.toLocaleString()}` : "—"}</span></div>
                  <div><span className="text-slate-500">Listing At: </span><span className="text-slate-300">{ipo.listing_at || "—"}</span></div>
                  <div><span className="text-slate-500">Allotment: </span><span className="text-slate-300">{ipo.allotment_date || "—"}</span></div>
                </div>
                <div className="mt-1"><span className="text-slate-500">Registrar: </span><span className="text-slate-300">{ipo.registrar || "—"}</span></div>
                <div><span className="text-slate-500">Market Maker: </span><span className="text-slate-300">{ipo.market_maker || "—"}</span></div>
                {ipo.lead_manager && <div><span className="text-slate-500">Lead Manager: </span><span className="text-slate-300">{ipo.lead_manager}</span></div>}
                {ipo.listing_return_pct != null && (
                  <div><span className="text-slate-500">Listing Return: </span>
                    <span className={ipo.listing_return_pct > 0 ? "text-emerald-400" : "text-rose-400"}>
                      {ipo.listing_return_pct > 0 ? "+" : ""}{ipo.listing_return_pct.toFixed(1)}%
                    </span>
                  </div>
                )}
                {gmp?.last_updated && <div><span className="text-slate-500">GMP Updated: </span><span className="text-slate-400">{new Date(gmp.last_updated).toLocaleString()}</span></div>}
              </div>

              {/* Anchor investors */}
              {anchor && (
                <div className="space-y-1 text-xs">
                  <div className="text-[10px] text-slate-500 uppercase mb-2">Anchor Investors</div>
                  <div className="grid grid-cols-2 gap-1">
                    {anchor.bid_date && <div><span className="text-slate-500">Bid Date: </span><span className="text-slate-300">{anchor.bid_date}</span></div>}
                    {anchor.amount_crs != null && <div><span className="text-slate-500">Amount: </span><span className="text-slate-300">₹{anchor.amount_crs} Cr</span></div>}
                    {anchor.shares_offered && <div><span className="text-slate-500">Shares: </span><span className="text-slate-300">{anchor.shares_offered}</span></div>}
                    {anchor.amount_crs != null && ipo.issue_size_crs && ipo.issue_size_crs > 0 && (
                      <div><span className="text-slate-500">% of Issue: </span>
                        <span className="text-emerald-300">{((anchor.amount_crs / ipo.issue_size_crs) * 100).toFixed(1)}%</span>
                      </div>
                    )}
                    {anchor.lock_in_50pct_date && <div><span className="text-slate-500">50% Lock-in End: </span><span className="text-slate-300">{anchor.lock_in_50pct_date}</span></div>}
                    {anchor.lock_in_90pct_date && <div><span className="text-slate-500">90% Lock-in End: </span><span className="text-slate-300">{anchor.lock_in_90pct_date}</span></div>}
                  </div>
                  {anchor.amount_crs && (
                    <p className="text-[10px] text-slate-600 mt-1.5">
                      Anchor investors (FIIs, DIIs, mutual funds) commit funds one day before IPO opens,
                      with a mandatory 30/90-day lock-in. High anchor participation signals institutional confidence.
                    </p>
                  )}
                </div>
              )}

              {/* Timeline */}
              <TimelineView timeline={timeline} />

              {/* Financials */}
              <FinTable title="Financials (₹ Cr)" data={fin} />
              <FinTable title="Per-Share Metrics" data={metrics} />
              <FinTable title="Return Ratios" data={ratios} />

              {/* GMP History */}
              <GmpHistory history={gmpHistory} />

              {/* Peer comparison */}
              <div className="lg:col-span-2">
                <PeerTable peers={peers} />
              </div>

              {/* Score breakdown */}
              {factors && (
                <div className="lg:col-span-2">
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

              {/* More details link */}
              <div className="lg:col-span-2 flex justify-end pt-1">
                <Link
                  href={`/ipo/${encodeURIComponent(ipo.symbol || ipo.company_name)}`}
                  onClick={(e) => e.stopPropagation()}
                  className="inline-flex items-center gap-1.5 rounded-lg bg-slate-800 hover:bg-slate-700 px-4 py-2 text-xs font-medium text-emerald-400 transition-colors"
                >
                  More Details
                  <svg className="w-3.5 h-3.5" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                    <path d="M5 12h14M12 5l7 7-7 7" />
                  </svg>
                </Link>
              </div>
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
          Current, upcoming, and recent IPOs with GMP, subscription, financials, peer comparison, and selection score.
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
          <p className="text-xs text-slate-600 mt-1">Fetching from ipocentral.in (~3-5s)</p>
        </div>
      )}

      {data?.error && (
        <div className="glass-card p-4 text-center">
          <p className="text-amber-300 text-sm">{data.error}</p>
          <p className="text-xs text-slate-600 mt-1">IPO data source may be temporarily unavailable. Data will retry on refresh.</p>
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
              Score factors: subscription (25), GMP (20), pricing (15), issue size (10), freshness (10),
              registrar (5), board (5), market maker (5), financials (5). Click a row for full details.
            </p>
          </div>
        </>
      )}
    </div>
  );
}
