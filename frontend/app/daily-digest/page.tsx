"use client";

import { useState } from "react";
import useSWR from "swr";
import { fetchDigests, fetchDigest, generateDigest, type DigestSummary, type DigestDetail } from "@/lib/api";

export default function DailyDigestPage() {
  const [selectedId, setSelectedId] = useState<number | null>(null);
  const [generating, setGenerating] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const { data: listData, mutate } = useSWR("/api/daily-digest", () => fetchDigests(14), {
    refreshInterval: 60000,
    keepPreviousData: true,
  });
  const { data: digestDetail } = useSWR(
    selectedId ? `/api/daily-digest/${selectedId}` : null,
    () => fetchDigest(selectedId!),
    { revalidateOnFocus: false }
  );

  const digests = listData?.digests || [];

  const handleGenerate = async () => {
    setGenerating(true);
    setError(null);
    try {
      const result = await generateDigest();
      setSelectedId(result.id);
      mutate();
    } catch (e: any) {
      setError(e.message || "Failed to generate digest");
    } finally {
      setGenerating(false);
    }
  };

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-bold text-slate-100">Daily Digest</h1>
          <p className="text-sm text-slate-500 mt-1">
            Compiled market summary — picks, signals, gaps, and triggered alerts.
          </p>
        </div>
        <button
          onClick={handleGenerate}
          disabled={generating}
          className="px-4 py-2 bg-emerald-600 hover:bg-emerald-500 disabled:opacity-50 text-white rounded-lg text-sm font-medium"
        >
          {generating ? "Generating..." : "Generate Now"}
        </button>
      </div>

      {error && <div className="glass-card p-4 text-center"><p className="text-rose-300 text-sm">{error}</p></div>}

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
        {/* Digest list */}
        <div className="space-y-2">
          <div className="text-sm font-semibold text-slate-300 mb-1">Recent Digests</div>
          {digests.length === 0 ? (
            <div className="glass-card p-4 text-center">
              <p className="text-xs text-slate-500">No digests yet. Click &ldquo;Generate Now&rdquo; to create one.</p>
            </div>
          ) : (
            digests.map((d) => (
              <button
                key={d.id}
                onClick={() => setSelectedId(d.id)}
                className={`w-full text-left glass-card p-3 transition-colors ${
                  selectedId === d.id ? "border-emerald-700/50 bg-emerald-900/10" : ""
                }`}
              >
                <div className="flex items-center justify-between">
                  <span className="text-sm font-medium text-slate-200">{d.date}</span>
                  {d.emailed ? (
                    <span className="text-[10px] text-emerald-400 bg-emerald-900/30 px-1.5 py-0.5 rounded">Emailed</span>
                  ) : (
                    <span className="text-[10px] text-slate-500 bg-slate-800 px-1.5 py-0.5 rounded">Stored</span>
                  )}
                </div>
                <div className="text-[10px] text-slate-500 mt-1 truncate">{d.subject}</div>
              </button>
            ))
          )}
        </div>

        {/* Digest detail */}
        <div className="lg:col-span-2">
          {digestDetail && !digestDetail.error ? (
            <DigestView digest={digestDetail} />
          ) : (
            <div className="glass-card p-8 text-center">
              <p className="text-sm text-slate-500">
                {selectedId ? "Loading digest..." : "Select a digest to view details"}
              </p>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

function DigestView({ digest }: { digest: DigestDetail }) {
  const data = digest.data;
  const picks = data?.picks || [];
  const signals = data?.signals || [];
  const gaps = data?.gaps || [];
  const triggered = data?.triggered_alerts || [];

  return (
    <div className="space-y-4">
      {/* Header */}
      <div className="glass-card p-4">
        <div className="flex items-center justify-between">
          <div>
            <div className="text-sm font-bold text-slate-100">{digest.subject}</div>
            <div className="text-xs text-slate-500 mt-0.5">
              Generated {digest.created_at ? new Date(digest.created_at).toLocaleString() : ""}
              {digest.emailed && <span className="ml-2 text-emerald-400">· Emailed</span>}
            </div>
          </div>
        </div>
        {data?.market_status && (
          <div className="mt-2 text-xs text-slate-400">
            {data.market_status.status_text || "Market status unavailable"}
          </div>
        )}
      </div>

      {/* Picks */}
      {picks.length > 0 && (
        <div className="glass-card p-4">
          <div className="text-sm font-semibold text-slate-300 mb-2">Today&apos;s Picks ({picks.length})</div>
          <table className="w-full text-xs">
            <thead>
              <tr className="text-slate-500 border-b border-slate-800">
                <th className="px-2 py-1 text-left font-medium">Symbol</th>
                <th className="px-2 py-1 text-left font-medium">Side</th>
                <th className="px-2 py-1 text-right font-medium">Entry</th>
                <th className="px-2 py-1 text-right font-medium">SL</th>
                <th className="px-2 py-1 text-right font-medium">Target</th>
                <th className="px-2 py-1 text-right font-medium">Conf</th>
              </tr>
            </thead>
            <tbody>
              {picks.map((p: any, i: number) => (
                <tr key={i} className="border-b border-slate-800/40">
                  <td className="px-2 py-1.5 text-slate-200">{p.symbol}</td>
                  <td className={`px-2 py-1.5 ${p.side === "long" ? "text-emerald-400" : "text-rose-400"}`}>{p.side}</td>
                  <td className="px-2 py-1.5 text-right tabular-nums text-slate-300">{p.entry}</td>
                  <td className="px-2 py-1.5 text-right tabular-nums text-rose-400">{p.stop_loss}</td>
                  <td className="px-2 py-1.5 text-right tabular-nums text-emerald-400">{p.target1}</td>
                  <td className="px-2 py-1.5 text-right tabular-nums text-slate-300">{(p.confidence * 100).toFixed(0)}%</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {/* Signals */}
      {signals.length > 0 && (
        <div className="glass-card p-4">
          <div className="text-sm font-semibold text-slate-300 mb-2">Signal Alerts ({signals.length})</div>
          <div className="space-y-1">
            {signals.map((s: any, i: number) => (
              <div key={i} className="text-xs flex items-center gap-2 py-1 border-b border-slate-800/30">
                <span className="font-semibold text-slate-200">{s.symbol}</span>
                <span className={`text-[10px] px-1.5 py-0.5 rounded ${
                  s.side === "long" ? "bg-emerald-900/40 text-emerald-400" :
                  s.side === "short" ? "bg-rose-900/40 text-rose-400" :
                  "bg-amber-900/40 text-amber-400"
                }`}>{s.side.toUpperCase()}</span>
                <span className="text-slate-400 flex-1">{s.description}</span>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Gaps */}
      {gaps.length > 0 && (
        <div className="glass-card p-4">
          <div className="text-sm font-semibold text-slate-300 mb-2">Gap Scanner ({gaps.length})</div>
          <div className="space-y-1">
            {gaps.map((g: any, i: number) => (
              <div key={i} className="text-xs flex items-center gap-2 py-1 border-b border-slate-800/30">
                <span className="font-semibold text-slate-200">{g.symbol}</span>
                <span className={g.gap_pct >= 0 ? "text-emerald-400" : "text-rose-400"}>
                  gap {g.gap_pct >= 0 ? "+" : ""}{g.gap_pct?.toFixed(1)}%
                </span>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Triggered Alerts */}
      {triggered.length > 0 && (
        <div className="glass-card p-4">
          <div className="text-sm font-semibold text-slate-300 mb-2">Triggered Price Alerts ({triggered.length})</div>
          <div className="space-y-1">
            {triggered.map((a: any, i: number) => (
              <div key={i} className="text-xs flex items-center gap-2 py-1 border-b border-slate-800/30">
                <span className="font-semibold text-slate-200">{a.symbol}</span>
                <span className="text-slate-500">{a.condition.replace("_", " ")}</span>
                <span className="text-slate-400">₹{a.target_price}</span>
                <span className="text-slate-500">→</span>
                <span className="text-emerald-400 font-semibold">₹{a.triggered_price}</span>
              </div>
            ))}
          </div>
        </div>
      )}

      {picks.length === 0 && signals.length === 0 && gaps.length === 0 && triggered.length === 0 && (
        <div className="glass-card p-8 text-center">
          <p className="text-sm text-slate-500">No significant activity in this digest.</p>
        </div>
      )}
    </div>
  );
}
