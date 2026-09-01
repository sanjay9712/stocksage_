"use client";

import Link from "next/link";
import useSWR from "swr";
import { fetchIpoDetail, type IpoData, type IpoFinancials, type IpoPeer, type IpoTimeline, type IpoRecommendation, type IpoCriteriaItem } from "@/lib/api";

function StatusPill({ status }: { status: string }) {
  const cls =
    status === "current" ? "text-emerald-400 border-emerald-500/30 bg-emerald-500/10"
    : status === "upcoming" ? "text-blue-400 border-blue-500/30 bg-blue-500/10"
    : "text-slate-500 border-slate-600/30 bg-slate-700/10";
  const label = status === "current" ? "OPEN" : status === "upcoming" ? "UPCOMING" : "LISTED";
  return <span className={`text-[10px] font-bold rounded border px-1.5 py-0.5 ${cls}`}>{label}</span>;
}

function ScoreBadge({ score }: { score: number | null }) {
  if (score == null) return <span className="text-slate-600">—</span>;
  const cls = score >= 60 ? "text-emerald-400 bg-emerald-500/10" : score >= 35 ? "text-amber-400 bg-amber-500/10" : "text-rose-400 bg-rose-500/10";
  return <span className={`tabular-nums font-bold rounded px-2 py-0.5 text-sm ${cls}`}>{score.toFixed(0)}/100</span>;
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
    <div className={`rounded-xl border ${s.bar} p-5`}>
      <div className="flex items-center gap-3 mb-3">
        <span className={`text-sm font-bold rounded border px-3 py-1.5 ${s.chip}`}>{s.label}</span>
        {score != null && <ScoreBadge score={score} />}
      </div>
      <p className="text-sm text-slate-300 mb-4">{rec.summary}</p>
      {rec.critical_flags.length > 0 && (
        <div className="flex flex-wrap gap-2 mb-3">
          {rec.critical_flags.map((f, i) => (
            <span key={i} className="text-xs text-rose-300 bg-rose-950/40 border border-rose-800/40 rounded px-2.5 py-1">
              ⚠ {f}
            </span>
          ))}
        </div>
      )}
      <div className="grid md:grid-cols-2 gap-4">
        {rec.pros.length > 0 && (
          <div>
            <div className="text-xs text-emerald-500 uppercase mb-2 font-semibold">Pros — Why to Invest</div>
            <ul className="space-y-1.5">
              {rec.pros.map((p, i) => (
                <li key={i} className="text-sm text-slate-400 flex gap-2">
                  <span className="text-emerald-500 shrink-0 mt-0.5">✓</span>
                  <span>{p}</span>
                </li>
              ))}
            </ul>
          </div>
        )}
        {rec.cons.length > 0 && (
          <div>
            <div className="text-xs text-rose-500 uppercase mb-2 font-semibold">Cons — Risks &amp; Concerns</div>
            <ul className="space-y-1.5">
              {rec.cons.map((c, i) => (
                <li key={i} className="text-sm text-slate-400 flex gap-2">
                  <span className="text-rose-500 shrink-0 mt-0.5">✗</span>
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

function CriteriaChecklistCard({ rec }: { rec: IpoRecommendation }) {
  if (!rec.criteria || rec.criteria.length === 0) return null;
  const metCount = rec.criteria.filter((c) => c.met).length;
  const totalCount = rec.criteria.length;
  return (
    <div className="glass-card p-5">
      <h2 className="section-title mb-3">
        Recommendation Criteria — Why {rec.verdict}? ({metCount}/{totalCount} met)
      </h2>
      <div className="space-y-2">
        {rec.criteria.map((c: IpoCriteriaItem, i: number) => (
          <div key={i} className="flex items-start gap-3 bg-slate-800/40 rounded-lg px-3 py-2.5">
            <span className={`shrink-0 mt-0.5 text-lg leading-none ${c.met ? "text-emerald-400" : "text-rose-400"}`}>
              {c.met ? "✓" : "✗"}
            </span>
            <div className="flex-1 min-w-0">
              <div className="flex items-center gap-2 flex-wrap">
                <span className="font-semibold text-slate-200 text-sm">{c.factor}</span>
                <span className="text-slate-400 tabular-nums text-sm">{c.value}</span>
              </div>
              <p className="text-xs text-slate-500 mt-0.5">{c.detail}</p>
              <p className="text-[10px] text-slate-600 mt-0.5">Threshold: {c.threshold}</p>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

function IssueStructureCard({ rec, ipo }: { rec: IpoRecommendation; ipo: IpoData }) {
  const s = rec.issue_structure;
  return (
    <div className="glass-card p-5">
      <h2 className="section-title mb-3">Issue Structure</h2>
      {(s.fresh_pct != null || s.ofs_pct != null) && (
        <div className="flex h-8 rounded-lg overflow-hidden border border-slate-700/50 mb-3">
          {s.fresh_pct != null && s.fresh_pct > 0 && (
            <div className="bg-emerald-600/60 flex items-center justify-center" style={{ width: `${s.fresh_pct}%` }}>
              <span className="text-xs font-bold text-white">Fresh {s.fresh_pct.toFixed(0)}%</span>
            </div>
          )}
          {s.ofs_pct != null && s.ofs_pct > 0 && (
            <div className="bg-amber-600/60 flex items-center justify-center" style={{ width: `${s.ofs_pct}%` }}>
              <span className="text-xs font-bold text-white">OFS {s.ofs_pct.toFixed(0)}%</span>
            </div>
          )}
        </div>
      )}
      <div className="grid grid-cols-2 gap-3 text-sm">
        <div className="stat-box">
          <div className="text-[10px] text-slate-500 uppercase">Total Issue Size</div>
          <div className="text-sm font-semibold tabular-nums text-slate-200">{ipo.issue_size_crs != null ? `₹${ipo.issue_size_crs.toFixed(0)} Cr` : "—"}</div>
        </div>
        <div className="stat-box">
          <div className="text-[10px] text-slate-500 uppercase">Fresh Issue</div>
          <div className="text-sm font-semibold tabular-nums text-emerald-300">{s.fresh_issue_crs != null ? `₹${s.fresh_issue_crs.toFixed(0)} Cr` : "—"}</div>
        </div>
        <div className="stat-box">
          <div className="text-[10px] text-slate-500 uppercase">Offer for Sale (OFS)</div>
          <div className="text-sm font-semibold tabular-nums text-amber-300">{s.ofs_amount_crs != null ? `₹${s.ofs_amount_crs.toFixed(0)} Cr` : "—"}</div>
        </div>
        <div className="stat-box">
          <div className="text-[10px] text-slate-500 uppercase">Face Value</div>
          <div className="text-sm font-semibold tabular-nums text-slate-200">{ipo.face_value != null ? `₹${ipo.face_value}` : "—"}</div>
        </div>
      </div>
      {s.promoter_exit_heavy && (
        <p className="text-xs text-amber-400 mt-3">
          ⚠ Promoter exit heavy — OFS exceeds 50% of the issue size. Existing shareholders are selling their stake rather than the company raising fresh capital.
        </p>
      )}
      <p className="text-[11px] text-slate-600 mt-2">
        Fresh Issue funds go to the company for growth, expansion, or debt reduction. OFS funds go to selling shareholders (promoters, PE investors).
      </p>
    </div>
  );
}

function ValuationCard({ rec }: { rec: IpoRecommendation }) {
  const v = rec.valuation;
  return (
    <div className="glass-card p-5">
      <h2 className="section-title mb-3">Valuation vs Peers</h2>
      <div className="grid grid-cols-3 gap-3 text-center">
        <div className="stat-box">
          <div className="text-[10px] text-slate-500 uppercase">IPO PE Ratio</div>
          <div className="text-lg font-bold tabular-nums text-slate-200">{v.ipo_pe?.toFixed(1) ?? "—"}</div>
        </div>
        <div className="stat-box">
          <div className="text-[10px] text-slate-500 uppercase">Peer Avg PE</div>
          <div className="text-lg font-bold tabular-nums text-slate-200">{v.peer_pe_avg?.toFixed(1) ?? "—"}</div>
        </div>
        <div className="stat-box">
          <div className="text-[10px] text-slate-500 uppercase">vs Peers</div>
          <div className={`text-lg font-bold tabular-nums ${v.discount_to_peers_pct != null ? (v.discount_to_peers_pct < 0 ? "text-emerald-400" : "text-rose-400") : "text-slate-400"}`}>
            {v.discount_to_peers_pct != null ? `${v.discount_to_peers_pct > 0 ? "+" : ""}${v.discount_to_peers_pct.toFixed(1)}%` : "—"}
          </div>
        </div>
      </div>
      {v.discount_to_peers_pct != null && (
        <p className="text-xs text-slate-500 mt-3">
          {v.discount_to_peers_pct < 0
            ? `Priced at a ${Math.abs(v.discount_to_peers_pct).toFixed(0)}% discount to peer average — potentially undervalued.`
            : `Priced at a ${v.discount_to_peers_pct.toFixed(0)}% premium to peer average — check if growth justifies the premium.`}
        </p>
      )}
    </div>
  );
}

function SubscriptionCard({ ipo }: { ipo: IpoData }) {
  const sub = ipo.subscription;
  if (!sub) return null;
  const subMax = Math.max(sub.qib ?? 0, sub.nii ?? 0, sub.rii ?? 0, sub.total ?? 0, 1);
  const bars = [
    { label: "QIB", value: sub.qib, desc: "Qualified Institutional Buyers" },
    { label: "NII", value: sub.nii, desc: "Non-Institutional Investors (HNIs)" },
    { label: "RII", value: sub.rii, desc: "Retail Individual Investors" },
    { label: "Total", value: sub.total, desc: "Overall subscription" },
  ];
  return (
    <div className="glass-card p-5">
      <h2 className="section-title mb-3">Subscription Details</h2>
      <div className="space-y-3">
        {bars.map((b) => {
          const pct = b.value != null ? Math.min((b.value / subMax) * 100, 100) : 0;
          return (
            <div key={b.label}>
              <div className="flex items-center justify-between text-xs mb-1">
                <div>
                  <span className="text-slate-300 font-medium">{b.label}</span>
                  <span className="text-slate-600 ml-2">{b.desc}</span>
                </div>
                <span className={`tabular-nums font-semibold ${b.value != null && b.value >= 10 ? "text-emerald-400" : "text-slate-300"}`}>
                  {b.value != null ? `${b.value.toFixed(2)}x` : "—"}
                </span>
              </div>
              <div className="h-2.5 bg-slate-800 rounded-full overflow-hidden">
                <div className="h-full bg-gradient-to-r from-emerald-500 to-teal-400 rounded-full" style={{ width: `${pct}%` }} />
              </div>
            </div>
          );
        })}
      </div>
      {ipo.quota_percent && Object.keys(ipo.quota_percent).length > 0 && (
        <div className="mt-4">
          <div className="text-[10px] text-slate-500 uppercase mb-2">Quota Allocation</div>
          <div className="flex flex-wrap gap-2">
            {Object.entries(ipo.quota_percent).map(([k, v]) => (
              <span key={k} className="text-xs text-slate-400 bg-slate-800/60 rounded px-2 py-1">
                {k}: <span className="text-slate-200 font-medium">{v}%</span>
              </span>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

function GmpCard({ ipo }: { ipo: IpoData }) {
  const gmp = ipo.gmp;
  const history = ipo.gmp_history;
  if (!gmp && !history) return null;
  return (
    <div className="glass-card p-5">
      <h2 className="section-title mb-3">Grey Market Premium (GMP)</h2>
      {gmp && (
        <div className="grid grid-cols-3 gap-3 text-center mb-4">
          <div className="stat-box">
            <div className="text-[10px] text-slate-500 uppercase">GMP (₹)</div>
            <div className={`text-lg font-bold tabular-nums ${gmp.premium != null && gmp.premium > 0 ? "text-emerald-400" : "text-rose-400"}`}>
              {gmp.premium != null ? `₹${gmp.premium}` : "—"}
            </div>
          </div>
          <div className="stat-box">
            <div className="text-[10px] text-slate-500 uppercase">GMP %</div>
            <div className={`text-lg font-bold tabular-nums ${gmp.premium_pct != null && gmp.premium_pct > 0 ? "text-emerald-400" : "text-rose-400"}`}>
              {gmp.premium_pct != null ? `${gmp.premium_pct > 0 ? "+" : ""}${gmp.premium_pct.toFixed(1)}%` : "—"}
            </div>
          </div>
          <div className="stat-box">
            <div className="text-[10px] text-slate-500 uppercase">Est. Listing</div>
            <div className="text-lg font-bold tabular-nums text-slate-200">
              {gmp.premium != null && ipo.price_high != null ? `₹${(ipo.price_high + gmp.premium).toFixed(0)}` : "—"}
            </div>
          </div>
        </div>
      )}
      {history && history.length > 0 && (
        <div className="overflow-x-auto">
          <div className="text-[10px] text-slate-500 uppercase mb-2">GMP History</div>
          <table className="w-full text-xs">
            <thead>
              <tr className="text-slate-500 border-b border-slate-800">
                <th className="px-2 py-1 text-left font-medium">Date</th>
                <th className="px-2 py-1 text-right font-medium">GMP (₹)</th>
                <th className="px-2 py-1 text-right font-medium">Subject to Sauda (₹)</th>
              </tr>
            </thead>
            <tbody>
              {history.slice(0, 10).map((h, i) => (
                <tr key={i} className="border-b border-slate-800/40">
                  <td className="px-2 py-1 text-slate-400">{h.date}</td>
                  <td className="px-2 py-1 text-right tabular-nums text-slate-300">{h.gmp != null ? `₹${h.gmp}` : "—"}</td>
                  <td className="px-2 py-1 text-right tabular-nums text-slate-300">{h.subject_to_sauda != null ? `₹${h.subject_to_sauda}` : "—"}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
      <p className="text-[11px] text-slate-600 mt-2">
        GMP is the unofficial premium at which IPO shares trade in the grey market before listing. It indicates market sentiment but is not guaranteed.
      </p>
    </div>
  );
}

function AnchorCard({ ipo }: { ipo: IpoData }) {
  const anchor = ipo.anchor_investors;
  if (!anchor) return null;
  const anchorPct = anchor.amount_crs && ipo.issue_size_crs && ipo.issue_size_crs > 0
    ? (anchor.amount_crs / ipo.issue_size_crs) * 100
    : null;
  return (
    <div className="glass-card p-5">
      <h2 className="section-title mb-3">Anchor Investors</h2>
      <div className="grid grid-cols-2 gap-3 text-sm">
        {anchor.bid_date && (
          <div className="stat-box">
            <div className="text-[10px] text-slate-500 uppercase">Bid Date</div>
            <div className="text-sm font-medium text-slate-200">{anchor.bid_date}</div>
          </div>
        )}
        {anchor.amount_crs != null && (
          <div className="stat-box">
            <div className="text-[10px] text-slate-500 uppercase">Anchor Amount</div>
            <div className="text-sm font-semibold tabular-nums text-emerald-300">₹{anchor.amount_crs.toFixed(0)} Cr</div>
          </div>
        )}
        {anchor.shares_offered && (
          <div className="stat-box">
            <div className="text-[10px] text-slate-500 uppercase">Shares Offered</div>
            <div className="text-sm font-medium text-slate-200">{anchor.shares_offered}</div>
          </div>
        )}
        {anchorPct != null && (
          <div className="stat-box">
            <div className="text-[10px] text-slate-500 uppercase">% of Issue</div>
            <div className="text-sm font-semibold tabular-nums text-emerald-300">{anchorPct.toFixed(1)}%</div>
          </div>
        )}
        {anchor.lock_in_50pct_date && (
          <div className="stat-box">
            <div className="text-[10px] text-slate-500 uppercase">50% Lock-in End</div>
            <div className="text-sm font-medium text-slate-200">{anchor.lock_in_50pct_date}</div>
          </div>
        )}
        {anchor.lock_in_90pct_date && (
          <div className="stat-box">
            <div className="text-[10px] text-slate-500 uppercase">90% Lock-in End</div>
            <div className="text-sm font-medium text-slate-200">{anchor.lock_in_90pct_date}</div>
          </div>
        )}
      </div>
      <p className="text-[11px] text-slate-600 mt-3">
        Anchor investors (FIIs, DIIs, mutual funds) commit funds one day before the IPO opens, with a mandatory 30/90-day lock-in. High anchor participation signals institutional confidence.
      </p>
    </div>
  );
}

function TimelineCard({ timeline }: { timeline: IpoTimeline | null }) {
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
    <div className="glass-card p-5">
      <h2 className="section-title mb-3">IPO Timeline</h2>
      <div className="flex flex-wrap gap-2">
        {entries.map(([k, v]) => (
          <div key={k} className="text-xs bg-slate-800/60 rounded-lg px-3 py-2">
            <div className="text-[10px] text-slate-500 uppercase">{labels[k] || k}</div>
            <div className="text-sm text-slate-200 font-medium mt-0.5">{v}</div>
          </div>
        ))}
      </div>
    </div>
  );
}

function FinTable({ title, data }: { title: string; data: IpoFinancials | null }) {
  if (!data) return null;
  const metrics = Object.keys(data);
  if (metrics.length === 0) return null;
  const years = Array.from(new Set(metrics.flatMap(m => Object.keys(data[m]))));
  return (
    <div className="glass-card p-5">
      <h2 className="section-title mb-3">{title}</h2>
      <div className="overflow-x-auto">
        <table className="w-full text-xs">
          <thead>
            <tr className="text-slate-500 border-b border-slate-800">
              <th className="px-3 py-2 text-left font-medium">Metric</th>
              {years.map(y => <th key={y} className="px-3 py-2 text-right font-medium whitespace-nowrap">{y}</th>)}
            </tr>
          </thead>
          <tbody>
            {metrics.map(m => (
              <tr key={m} className="border-b border-slate-800/40">
                <td className="px-3 py-2 text-slate-400">{m}</td>
                {years.map(y => {
                  const v = data[m][y];
                  return <td key={y} className="px-3 py-2 text-right tabular-nums text-slate-300">{v != null ? v : "—"}</td>;
                })}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

function PeerTable({ peers }: { peers: IpoPeer[] | null }) {
  if (!peers || peers.length === 0) return null;
  const cols = peers.length > 0 ? Object.keys(peers[0]).filter(k => k !== "company") : [];
  return (
    <div className="glass-card p-5">
      <h2 className="section-title mb-3">Peer Comparison</h2>
      <div className="overflow-x-auto">
        <table className="w-full text-xs">
          <thead>
            <tr className="text-slate-500 border-b border-slate-800">
              <th className="px-3 py-2 text-left font-medium">Company</th>
              {cols.map(c => <th key={c} className="px-3 py-2 text-right font-medium whitespace-nowrap">{c}</th>)}
            </tr>
          </thead>
          <tbody>
            {peers.map((p, i) => (
              <tr key={i} className={`border-b border-slate-800/40 ${i === 0 ? "bg-emerald-900/10" : ""}`}>
                <td className="px-3 py-2 text-slate-300 font-medium">{p.company}</td>
                {cols.map(c => {
                  const v = p[c];
                  return <td key={c} className="px-3 py-2 text-right tabular-nums text-slate-400">{v != null ? v : "—"}</td>;
                })}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

function ScoreCard({ ipo }: { ipo: IpoData }) {
  const factors = ipo.score_factors;
  const score = ipo.selection_score;
  if (!factors || score == null) return null;
  return (
    <div className="glass-card p-5">
      <h2 className="section-title mb-3">Selection Score Breakdown ({score.toFixed(0)}/100)</h2>
      <div className="space-y-2">
        {Object.entries(factors).map(([k, v]) => {
          const maxVals: Record<string, number> = {
            subscription: 25, gmp: 20, pricing: 15, issue_size: 10, freshness: 10,
            registrar: 5, board: 5, market_maker: 5, financials: 5, completeness: 5,
          };
          const max = maxVals[k] ?? 10;
          const pct = (v / max) * 100;
          return (
            <div key={k}>
              <div className="flex items-center justify-between text-xs mb-1">
                <span className="text-slate-400 capitalize">{k.replace(/_/g, " ")}</span>
                <span className="text-slate-300 tabular-nums">{v.toFixed(1)}/{max}</span>
              </div>
              <div className="h-2 bg-slate-800 rounded-full overflow-hidden">
                <div className="h-full bg-gradient-to-r from-emerald-500 to-teal-400 rounded-full" style={{ width: `${pct}%` }} />
              </div>
            </div>
          );
        })}
      </div>
      <div className="flex flex-wrap gap-3 mt-4 text-xs">
        <span className="flex items-center gap-1.5">
          <span className="w-3 h-3 rounded bg-emerald-500/30 border border-emerald-500/50" />
          <span className="text-slate-400">≥60 Strong</span>
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
    </div>
  );
}

export default function IpoDetailPage({ params }: { params: { symbol: string } }) {
  // Next.js may pass the param still URL-encoded in some cases.
  const symbol = (() => {
    try { return decodeURIComponent(params.symbol); } catch { return params.symbol; }
  })();
  const { data: ipo, error, isLoading, mutate } = useSWR(["ipo-detail", symbol], () => fetchIpoDetail(symbol), {
    refreshInterval: 300000, // 5 min — GMP/subscription can update during live IPO
    keepPreviousData: true,
  });

  if (isLoading) {
    return (
      <div className="space-y-4">
        <div className="shimmer h-8 w-64 rounded-lg" />
        <div className="glass-card p-8">
          <div className="shimmer h-6 w-48 mx-auto rounded mb-4" />
          <div className="shimmer h-4 w-32 mx-auto rounded" />
        </div>
      </div>
    );
  }

  if (error || !ipo) {
    return (
      <div className="space-y-4">
        <Link href="/ipo" className="text-sky-400 text-sm hover:underline">← back to IPO Center</Link>
        <div className="glass-card p-8 text-center">
          <p className="text-rose-300 text-sm mb-1">Failed to load IPO data for &ldquo;{symbol}&rdquo;.</p>
          <p className="text-xs text-slate-600 mt-1 mb-4">The IPO may have been removed or the data source is temporarily unavailable.</p>
          <button onClick={() => mutate()} className="px-4 py-2 bg-emerald-600 hover:bg-emerald-500 text-white rounded-lg text-sm">
            Retry
          </button>
        </div>
      </div>
    );
  }

  const rec = ipo.recommendation;
  const gmp = ipo.gmp;

  return (
    <div className="space-y-5 fade-in">
      <Link href="/ipo" className="text-sky-400 text-sm hover:underline inline-flex items-center gap-1">
        <svg className="w-4 h-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
          <path d="M19 12H5M12 19l-7-7 7-7" />
        </svg>
        back to IPO Center
      </Link>

      {/* Header card */}
      <div className="glass-card p-5">
        <div className="flex items-start justify-between flex-wrap gap-4">
          <div>
            <div className="flex items-center gap-3">
              <h1 className="text-2xl font-bold text-slate-100">{ipo.company_name}</h1>
              <StatusPill status={ipo.status} />
              <span className={`text-xs font-medium rounded border px-2 py-0.5 ${
                ipo.board === "mainboard"
                  ? "bg-sky-500/15 text-sky-400 border-sky-500/30"
                  : "bg-amber-500/15 text-amber-400 border-amber-500/30"
              }`}>
                {ipo.board === "mainboard" ? "MAINBOARD" : "SME"}
              </span>
            </div>
            {ipo.symbol && ipo.symbol !== ipo.company_name && (
              <p className="text-xs text-slate-500 mt-1">{ipo.symbol}</p>
            )}
          </div>
          <div className="flex items-center gap-6 flex-wrap">
            <div className="text-center">
              <div className="text-[10px] uppercase tracking-wide text-slate-400">Price Band</div>
              <div className="text-lg font-bold tabular-nums text-slate-200">{ipo.price_band || "—"}</div>
            </div>
            <div className="text-center">
              <div className="text-[10px] uppercase tracking-wide text-slate-400">Issue Size</div>
              <div className="text-lg font-bold tabular-nums text-slate-200">{ipo.issue_size_crs != null ? `₹${ipo.issue_size_crs.toFixed(0)} Cr` : "—"}</div>
            </div>
            <div className="text-center">
              <div className="text-[10px] uppercase tracking-wide text-slate-400">Lot Size</div>
              <div className="text-lg font-bold tabular-nums text-slate-200">{ipo.lot_size ?? "—"}</div>
            </div>
            {gmp?.premium != null && (
              <div className="text-center">
                <div className="text-[10px] uppercase tracking-wide text-slate-400">GMP</div>
                <div className={`text-lg font-bold tabular-nums ${gmp.premium > 0 ? "text-emerald-400" : "text-rose-400"}`}>
                  ₹{gmp.premium}
                </div>
              </div>
            )}
          </div>
        </div>
        {(ipo.open_date || ipo.close_date) && (
          <div className="mt-3 flex items-center gap-4 text-sm">
            {ipo.open_date && (
              <span className="text-slate-400">Open: <span className="text-slate-200">{ipo.open_date}</span></span>
            )}
            {ipo.close_date && (
              <span className="text-slate-400">Close: <span className="text-slate-200">{ipo.close_date}</span></span>
            )}
            {ipo.listing_at && (
              <span className="text-slate-400">Listing at: <span className="text-slate-200">{ipo.listing_at}</span></span>
            )}
          </div>
        )}
      </div>

      {/* Recommendation verdict */}
      {rec && <VerdictBanner rec={rec} score={ipo.selection_score} />}
      {rec && <CriteriaChecklistCard rec={rec} />}

      {/* Issue details quick stats */}
      <div className="glass-card p-5">
        <h2 className="section-title mb-3">Issue Details</h2>
        <div className="grid grid-cols-2 md:grid-cols-4 gap-3 text-sm">
          <div><span className="text-slate-500">Fresh Issue: </span><span className="text-slate-300">{ipo.fresh_issue_crs != null ? `₹${ipo.fresh_issue_crs} Cr` : "—"}</span></div>
          <div><span className="text-slate-500">OFS: </span><span className="text-slate-300">{ipo.offer_for_sale || "—"}</span></div>
          <div><span className="text-slate-500">Face Value: </span><span className="text-slate-300">{ipo.face_value != null ? `₹${ipo.face_value}` : "—"}</span></div>
          <div><span className="text-slate-500">Lot Value: </span><span className="text-slate-300">{ipo.lot_value != null ? `₹${ipo.lot_value.toLocaleString()}` : "—"}</span></div>
          <div><span className="text-slate-500">Registrar: </span><span className="text-slate-300">{ipo.registrar || "—"}</span></div>
          <div><span className="text-slate-500">Market Maker: </span><span className="text-slate-300">{ipo.market_maker || "—"}</span></div>
          {ipo.lead_manager && <div><span className="text-slate-500">Lead Manager: </span><span className="text-slate-300">{ipo.lead_manager}</span></div>}
          {ipo.listing_return_pct != null && (
            <div><span className="text-slate-500">Listing Return: </span>
              <span className={ipo.listing_return_pct > 0 ? "text-emerald-400" : "text-rose-400"}>
                {ipo.listing_return_pct > 0 ? "+" : ""}{ipo.listing_return_pct.toFixed(1)}%
              </span>
            </div>
          )}
        </div>
      </div>

      {/* Issue structure + Valuation */}
      <div className="grid gap-5 lg:grid-cols-2">
        {rec && <IssueStructureCard rec={rec} ipo={ipo} />}
        {rec && <ValuationCard rec={rec} />}
      </div>

      {/* Subscription + GMP */}
      <div className="grid gap-5 lg:grid-cols-2">
        <SubscriptionCard ipo={ipo} />
        <GmpCard ipo={ipo} />
      </div>

      {/* Anchor investors */}
      <AnchorCard ipo={ipo} />

      {/* Timeline */}
      <TimelineCard timeline={ipo.ipo_timeline} />

      {/* Financials */}
      <div className="grid gap-5 lg:grid-cols-2">
        <FinTable title="Financials (₹ Cr)" data={ipo.financials} />
        <FinTable title="Per-Share Metrics" data={ipo.per_share_metrics} />
      </div>
      <FinTable title="Return Ratios" data={ipo.return_ratios} />

      {/* Peer comparison */}
      <PeerTable peers={ipo.peer_comparison} />

      {/* Score breakdown */}
      <ScoreCard ipo={ipo} />

      {/* Disclaimer */}
      <div className="glass-card p-4">
        <p className="text-xs text-slate-600">
          This analysis is for educational purposes only and is not investment advice. IPO investments are subject to market risks.
          Always read the RHP/DRHP (Red Herring Prospectus) before investing. GMP is an unofficial indicator and not guaranteed.
        </p>
      </div>
    </div>
  );
}
