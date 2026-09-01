"use client";

import Link from "next/link";
import type { Pick } from "@/lib/api";

function sideBadge(side: string) {
  return side === "long"
    ? "bg-emerald-500/15 text-emerald-400 border-emerald-500/30"
    : "bg-rose-500/15 text-rose-400 border-rose-500/30";
}

function LevelPill({ label, value, color }: { label: string; value: number; color: string }) {
  return (
    <div className="flex flex-col items-center gap-0.5">
      <span className="text-[10px] uppercase tracking-wide text-slate-400">{label}</span>
      <span className={`text-sm font-semibold tabular-nums ${color}`}>₹{value.toFixed(2)}</span>
    </div>
  );
}

export default function PicksTable({ picks }: { picks: Pick[] }) {
  if (picks.length === 0) {
    return (
      <div className="glass-card p-10 text-center">
        <div className="text-slate-500 mb-2">
          <svg className="w-12 h-12 mx-auto opacity-40" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
            <path d="M21 21l-4.35-4.35M11 18a7 7 0 100-14 7 7 0 000 14z" />
          </svg>
        </div>
        <p className="text-slate-400 text-sm">No intraday picks yet.</p>
        <p className="text-slate-500 text-xs mt-1">
          The screener runs after the 09:30 IST opening range. Trigger a manual scan above.
        </p>
      </div>
    );
  }

  return (
    <div className="grid gap-3 sm:grid-cols-2 fade-in">
      {picks.map((p) => {
        const risk = p.entry - p.stop_loss;
        const rr1 = risk !== 0 ? ((p.target1 - p.entry) / risk).toFixed(1) : "—";
        const confPct = Math.round(p.confidence * 100);
        return (
          <Link
            key={p.symbol}
            href={`/picks/${p.symbol}`}
            className="glass-card-hover p-4 block group"
          >
            {/* Header row */}
            <div className="flex items-start justify-between mb-3">
              <div>
                <div className="flex items-center gap-2">
                  <span className="font-semibold text-slate-100 group-hover:text-emerald-400 transition-colors">
                    {p.symbol}
                  </span>
                  {p.expiry_day && (
                    <span className="text-[10px] uppercase rounded bg-amber-500/15 text-amber-400 border border-amber-500/30 px-1.5 py-0.5">
                      expiry
                    </span>
                  )}
                </div>
                <span className={`mt-1 inline-block text-xs font-medium rounded border px-2 py-0.5 ${sideBadge(p.side)}`}>
                  {p.side.toUpperCase()}
                </span>
              </div>
              <div className="text-right">
                <div className="text-xs text-slate-500">Last</div>
                <div className="text-sm font-semibold tabular-nums text-slate-200">
                  ₹{p.last_price ? p.last_price.toFixed(2) : "—"}
                </div>
              </div>
            </div>

            {/* Level pills */}
            <div className="grid grid-cols-4 gap-1 py-3 border-t border-b border-slate-800/50">
              <LevelPill label="Entry" value={p.entry} color="text-sky-300" />
              <LevelPill label="SL" value={p.stop_loss} color="text-rose-300" />
              <LevelPill label="T1" value={p.target1} color="text-emerald-300" />
              <LevelPill label="T2" value={p.target2} color="text-emerald-300" />
            </div>

            {/* Footer: confidence + R:R */}
            <div className="flex items-center justify-between mt-3">
              <div className="flex items-center gap-2">
                <div className="h-1.5 w-20 bg-slate-800 rounded-full overflow-hidden">
                  <div
                    className="h-full rounded-full bg-gradient-to-r from-emerald-500 to-teal-400"
                    style={{ width: `${confPct}%` }}
                  />
                </div>
                <span className="text-xs text-slate-400 tabular-nums">{confPct}%</span>
              </div>
              <span className="text-xs text-slate-500">
                R:R <span className="text-amber-300 font-medium tabular-nums">1:{rr1}</span>
              </span>
            </div>
          </Link>
        );
      })}
    </div>
  );
}
