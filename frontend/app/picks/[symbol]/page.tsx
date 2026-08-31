"use client";

import Link from "next/link";
import useSWR from "swr";
import { fetchPick } from "@/lib/api";
import ExplanationPanel from "@/components/ExplanationPanel";
import MiniChart from "@/components/MiniChart";

export default function PickDetail({ params }: { params: { symbol: string } }) {
  const symbol = params.symbol;
  const { data: pick, error, isLoading } = useSWR(["pick", symbol], () => fetchPick(symbol));

  if (isLoading) {
    return (
      <div className="glass-card p-8 text-center">
        <div className="shimmer h-6 w-40 mx-auto rounded mb-4" />
        <div className="shimmer h-4 w-24 mx-auto rounded" />
      </div>
    );
  }

  if (error || !pick) {
    return (
      <div className="space-y-4">
        <Link href="/" className="text-sky-400 text-sm hover:underline">← back</Link>
        <div className="glass-card p-8 text-center">
          <p className="text-slate-400 text-sm">No pick for {symbol} today.</p>
        </div>
      </div>
    );
  }

  const confPct = Math.round(pick.confidence * 100);

  return (
    <div className="space-y-5 fade-in">
      <div className="flex items-center justify-between">
        <Link href="/" className="text-sky-400 text-sm hover:underline">← back to picks</Link>
        <span className="text-xs text-slate-600">{pick.date}</span>
      </div>

      {/* Pick header card */}
      <div className="glass-card p-5">
        <div className="flex items-center justify-between flex-wrap gap-4">
          <div>
            <div className="flex items-center gap-3">
              <h1 className="text-2xl font-bold text-slate-100">{pick.symbol}</h1>
              <span className={`text-xs font-medium rounded border px-2 py-0.5 ${
                pick.side === "long"
                  ? "bg-emerald-500/15 text-emerald-400 border-emerald-500/30"
                  : "bg-rose-500/15 text-rose-400 border-rose-500/30"
              }`}>
                {pick.side.toUpperCase()}
              </span>
              {pick.expiry_day && (
                <span className="text-[10px] uppercase rounded bg-amber-500/15 text-amber-400 border border-amber-500/30 px-1.5 py-0.5">
                  expiry
                </span>
              )}
            </div>
            <p className="text-xs text-slate-400 mt-1">
              Confidence {confPct}% {pick.expiry_day ? "· expiry day" : ""}
            </p>
          </div>
          <div className="flex items-center gap-6">
            <div className="text-center">
              <div className="text-[10px] uppercase tracking-wide text-slate-400">Entry</div>
              <div className="text-lg font-bold tabular-nums text-sky-300">₹{pick.entry.toFixed(2)}</div>
            </div>
            <div className="text-center">
              <div className="text-[10px] uppercase tracking-wide text-slate-400">Stop-Loss</div>
              <div className="text-lg font-bold tabular-nums text-rose-300">₹{pick.stop_loss.toFixed(2)}</div>
            </div>
            <div className="text-center">
              <div className="text-[10px] uppercase tracking-wide text-slate-400">Target 1</div>
              <div className="text-lg font-bold tabular-nums text-emerald-300">₹{pick.target1.toFixed(2)}</div>
            </div>
            <div className="text-center">
              <div className="text-[10px] uppercase tracking-wide text-slate-400">Target 2</div>
              <div className="text-lg font-bold tabular-nums text-emerald-300">₹{pick.target2.toFixed(2)}</div>
            </div>
          </div>
        </div>
      </div>

      {/* Chart + Explanation */}
      <div className="grid gap-5 lg:grid-cols-2">
        <MiniChart pick={pick} />
        <ExplanationPanel explanation={pick.explanation} />
      </div>
    </div>
  );
}
