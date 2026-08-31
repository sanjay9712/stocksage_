"use client";

import type { Pick } from "@/lib/api";

export default function MiniChart({ pick }: { pick: Pick }) {
  const levels = [
    { label: "Target 2", value: pick.target2, color: "#34d399" },
    { label: "Target 1", value: pick.target1, color: "#34d399" },
    { label: "Entry", value: pick.entry, color: "#38bdf8" },
    { label: "Stop-Loss", value: pick.stop_loss, color: "#fb7185" },
  ].sort((a, b) => b.value - a.value);

  const top = Math.max(pick.target2, pick.entry);
  const bottom = Math.min(pick.stop_loss, pick.entry);
  const pad = (top - bottom) * 0.15 || 1;
  const max = top + pad;
  const min = bottom - pad;
  const range = max - min || 1;
  const h = 240;
  const y = (v: number) => h - ((v - min) / range) * h;
  const rr = ((pick.target1 - pick.entry) / (pick.entry - pick.stop_loss)).toFixed(2);

  return (
    <div className="glass-card p-4">
      <h2 className="section-title mb-3">Trade Levels (Risk : Reward)</h2>
      <svg viewBox={`0 0 320 ${h}`} className="w-full h-60">
        {/* Background gradient */}
        <defs>
          <linearGradient id="rewardGrad" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor="#34d399" stopOpacity="0.15" />
            <stop offset="100%" stopColor="#34d399" stopOpacity="0" />
          </linearGradient>
          <linearGradient id="riskGrad" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor="#fb7185" stopOpacity="0" />
            <stop offset="100%" stopColor="#fb7185" stopOpacity="0.15" />
          </linearGradient>
        </defs>

        {/* Risk/reward shaded zones */}
        <rect x="150" y={y(pick.entry)} width="20" height={Math.abs(y(pick.stop_loss) - y(pick.entry))} fill="url(#riskGrad)" />
        <rect x="170" y={y(pick.target1)} width="20" height={Math.abs(y(pick.entry) - y(pick.target1))} fill="url(#rewardGrad)" />

        {/* Level lines */}
        {levels.map((l, i) => (
          <g key={i}>
            <line
              x1={20} x2={300}
              y1={y(l.value)} y2={y(l.value)}
              stroke={l.color} strokeWidth={1.5}
              strokeDasharray="4 3"
              opacity={0.8}
            />
            <text x={300} y={y(l.value) - 5} fontSize={10} fill={l.color} textAnchor="end" fontWeight="600">
              {l.label}
            </text>
            <text x={22} y={y(l.value) - 5} fontSize={10} fill="#cbd5e1" fontWeight="500">
              {l.value.toFixed(2)}
            </text>
          </g>
        ))}

        {/* Risk/reward bracket lines */}
        <line x1={150} x2={150} y1={y(pick.entry)} y2={y(pick.stop_loss)} stroke="#fb7185" strokeWidth={2.5} strokeLinecap="round" />
        <line x1={170} x2={170} y1={y(pick.entry)} y2={y(pick.target1)} stroke="#34d399" strokeWidth={2.5} strokeLinecap="round" />

        {/* Labels */}
        <text x={140} y={(y(pick.entry) + y(pick.stop_loss)) / 2 + 4} fontSize={10} fill="#fb7185" textAnchor="end" fontWeight="600">
          risk
        </text>
        <text x={180} y={(y(pick.entry) + y(pick.target1)) / 2 + 4} fontSize={10} fill="#34d399" fontWeight="600">
          reward
        </text>
      </svg>
      <div className="flex items-center justify-between mt-2 pt-2 border-t border-slate-800/50">
        <span className="text-xs text-slate-500">Reward : Risk to T1</span>
        <span className="text-sm font-semibold tabular-nums text-emerald-400">{rr} : 1</span>
      </div>
    </div>
  );
}
