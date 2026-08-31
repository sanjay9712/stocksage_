"use client";

import type { Explanation } from "@/lib/api";

export default function ExplanationPanel({ explanation }: { explanation: Explanation }) {
  const inputs = explanation.inputs || {};
  return (
    <div className="space-y-4">
      <section className="glass-card p-4">
        <h2 className="section-title mb-2">Summary</h2>
        <p className="text-sm leading-relaxed text-slate-300">{explanation.summary}</p>
      </section>

      <section className="glass-card p-4">
        <h2 className="section-title mb-3">Inputs</h2>
        <div className="grid grid-cols-2 sm:grid-cols-3 gap-2">
          {Object.entries(inputs).map(([k, v]) => (
            <div key={k} className="stat-box">
              <div className="text-[10px] text-slate-400 uppercase tracking-wide">{k}</div>
              <div className="text-sm font-medium tabular-nums text-slate-200">{String(v)}</div>
            </div>
          ))}
        </div>
      </section>

      <section className="glass-card p-4">
        <h2 className="section-title mb-3">How Each Level Was Calculated</h2>
        <ol className="space-y-3">
          {explanation.formula_trace.map((f, i) => (
            <li key={i} className="text-sm border-l-2 border-slate-700 pl-3">
              <div className="flex items-baseline justify-between">
                <span className="font-medium text-slate-200">{f.label}</span>
                <span className="tabular-nums text-emerald-400 font-semibold">{f.result.toFixed(2)}</span>
              </div>
              <p className="text-xs text-slate-500 mt-0.5">{f.formula}</p>
              <p className="text-xs text-slate-600 font-mono mt-0.5">{f.substituted}</p>
            </li>
          ))}
        </ol>
      </section>

      <section className="glass-card p-4">
        <h2 className="section-title mb-2">Verify It Yourself</h2>
        <ul className="space-y-1.5 text-sm text-slate-300">
          {explanation.verification.map((v, i) => (
            <li key={i} className="flex items-start gap-2">
              <svg className="w-4 h-4 text-emerald-400 shrink-0 mt-0.5" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                <path d="M9 12l2 2 4-4M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
              </svg>
              <span>{v}</span>
            </li>
          ))}
        </ul>
      </section>

      {explanation.caveats?.length > 0 && (
        <section className="glass-card p-4 border-amber-800/30">
          <h2 className="text-sm font-semibold text-amber-300 mb-2">Caveats</h2>
          <ul className="space-y-1 text-xs text-amber-200/80">
            {explanation.caveats.map((c, i) => (
              <li key={i} className="flex items-start gap-2">
                <span className="text-amber-500 shrink-0">⚠</span>
                <span>{c}</span>
              </li>
            ))}
          </ul>
        </section>
      )}
    </div>
  );
}
