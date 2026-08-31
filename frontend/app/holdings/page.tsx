"use client";

import useSWR from "swr";
import { fetchHoldingsReview, fetchBrokerStatus } from "@/lib/api";
import StockSearch from "@/components/StockSearch";

const verdictColor: Record<string, string> = {
  hold: "text-emerald-400",
  review: "text-sky-300",
  caution: "text-amber-300",
  "wrong-pick": "text-rose-400",
};

const verdictBorder: Record<string, string> = {
  hold: "border-emerald-800/30",
  review: "border-sky-800/30",
  caution: "border-amber-800/30",
  "wrong-pick": "border-rose-800/40",
};

const verdictBadge: Record<string, string> = {
  hold: "bg-emerald-500/15 text-emerald-400 border-emerald-500/30",
  review: "bg-sky-500/15 text-sky-300 border-sky-500/30",
  caution: "bg-amber-500/15 text-amber-400 border-amber-500/30",
  "wrong-pick": "bg-rose-500/15 text-rose-400 border-rose-500/30",
};

export default function HoldingsPage() {
  const { data: status } = useSWR("broker-status", fetchBrokerStatus, { refreshInterval: 300000, keepPreviousData: true });
  const { data, isLoading, error, mutate } = useSWR("holdings-review", fetchHoldingsReview, { refreshInterval: 300000, keepPreviousData: true });

  const connected = status?.connected ?? false;

  if (isLoading) {
    return (
      <div className="glass-card p-8 text-center">
        <div className="shimmer h-6 w-48 mx-auto rounded mb-4" />
        <div className="shimmer h-4 w-32 mx-auto rounded" />
        <p className="text-xs text-slate-500 mt-3">Loading holdings review…</p>
      </div>
    );
  }

  if (error) {
    return (
      <div className="space-y-5">
        <Header />
        <div className="glass-card p-8 text-center">
          <p className="text-rose-300 text-sm">
            Failed to load holdings. Backend may be down or broker credentials missing.
          </p>
          <button
            onClick={() => mutate()}
            className="mt-3 rounded-lg bg-slate-800 hover:bg-slate-700 px-4 py-2 text-sm transition-colors"
          >
            Retry
          </button>
        </div>
      </div>
    );
  }

  const reviews = data || [];

  return (
    <div className="space-y-5">
      <Header />

      <StockSearch />

      {/* Broker connection banner */}
      {!connected && (
        <div className="glass-card p-5 border-amber-800/30">
          <div className="flex items-start gap-3">
            <span className="text-amber-300 text-xl mt-0.5">⚠</span>
            <div className="flex-1">
              <h3 className="text-sm font-semibold text-amber-300">
                Showing sample data — connect your broker to see real holdings
              </h3>
              <p className="text-xs text-slate-500 mt-1">
                The holdings below are mock data. To see YOUR real portfolio with
                live prices and wrong-pick alerts, connect Fyers:
              </p>
              <ol className="text-xs text-slate-500 mt-3 space-y-1 list-decimal list-inside">
                <li>Create a free Fyers API app at myapi.fyers.in</li>
                <li>Run: <code className="text-slate-300 bg-slate-800 px-1 rounded">python3 backend/scripts/fyers_auth.py --app-id YOUR_ID --secret-id YOUR_SECRET</code></li>
                <li>Set <code className="text-slate-300 bg-slate-800 px-1 rounded">APP_BROKER_PROVIDER=fyers</code> and <code className="text-slate-300 bg-slate-800 px-1 rounded">APP_FYERS_APP_ID</code> + <code className="text-slate-300 bg-slate-800 px-1 rounded">APP_FYERS_ACCESS_TOKEN</code> in backend/.env</li>
                <li>Restart the backend</li>
              </ol>
              <p className="text-xs text-slate-600 mt-2">
                The Fyers token expires daily — re-run the auth script each morning.
              </p>
            </div>
          </div>
        </div>
      )}
      {connected && (
        <div className="glass-card p-3 border-emerald-800/30 text-center">
          <span className="text-sm text-emerald-400">
            {status?.broker?.toUpperCase()} connected — showing your real holdings with live prices.
          </span>
        </div>
      )}

      <div className="flex items-center justify-between">
        <span className="text-xs text-slate-600">
          Each holding checked against trend (20/50-EMA) and the day&apos;s screener picks.
        </span>
        <button
          onClick={() => mutate()}
          className="flex items-center gap-2 rounded-lg bg-slate-800 hover:bg-slate-700 px-3 py-1.5 text-sm transition-colors"
        >
          <svg className="w-3.5 h-3.5" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <path d="M21 12a9 9 0 11-6.219-8.56" />
          </svg>
          Re-check
        </button>
      </div>

      {reviews.length === 0 ? (
        <div className="glass-card p-10 text-center">
          <p className="text-slate-400 text-sm">No holdings to review.</p>
        </div>
      ) : (
        <div className="grid gap-3 fade-in">
          {reviews.map((r) => (
            <div key={r.symbol} className={`glass-card-hover p-4 ${verdictBorder[r.verdict] || "border-slate-800/60"}`}>
              <div className="flex items-center justify-between flex-wrap gap-3">
                <div>
                  <div className="flex items-center gap-2">
                    <span className="font-semibold text-slate-100">{r.symbol}</span>
                    <span className={`text-[10px] uppercase rounded border px-1.5 py-0.5 ${verdictBadge[r.verdict]}`}>
                      {r.verdict}
                    </span>
                  </div>
                  <div className="text-xs text-slate-500 mt-0.5">
                    {r.quantity} @ ₹{r.avg_price.toFixed(2)} · now ₹{r.current_price.toFixed(2)} · trend {r.trend}
                  </div>
                </div>
                <div className="text-right">
                  <div className={`text-lg font-bold tabular-nums ${r.pnl >= 0 ? "text-emerald-400" : "text-rose-400"}`}>
                    {r.pnl >= 0 ? "+" : ""}{r.pnl.toFixed(2)}
                  </div>
                  <div className={`text-xs tabular-nums ${r.pnl >= 0 ? "text-emerald-400/70" : "text-rose-400/70"}`}>
                    {r.pnl >= 0 ? "+" : ""}{r.pnl_pct.toFixed(2)}%
                  </div>
                </div>
              </div>
              <p className="text-xs text-slate-400 mt-3 leading-relaxed">{r.rationale}</p>
              {r.actions.length > 0 && (
                <ul className="mt-2 text-xs text-slate-500 list-disc list-inside space-y-0.5">
                  {r.actions.map((a, i) => <li key={i}>{a}</li>)}
                </ul>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

function Header() {
  return (
    <div>
      <h1 className="text-lg font-semibold text-slate-100">Holdings Review — Wrong-Pick Alerts</h1>
      <p className="text-xs text-slate-500 mt-0.5">
        Intraday positions not in today&apos;s screen are flagged as untracked risk.
      </p>
    </div>
  );
}
