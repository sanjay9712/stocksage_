"use client";

import Link from "next/link";

export default function UsMarketsHub() {
  return (
    <div className="space-y-5">
      <div>
        <h1 className="text-lg font-semibold text-slate-100">US Markets</h1>
        <p className="text-xs text-slate-400 mt-0.5">US stocks & ETFs via yfinance · delayed ~15 min · not advice</p>
      </div>

      <div className="grid gap-4 sm:grid-cols-2">
        <Link href="/us-markets/stocks" className="glass-card-hover p-6 group">
          <div className="flex items-center gap-3 mb-3">
            <div className="w-10 h-10 rounded-xl bg-sky-500/15 border border-sky-500/30 flex items-center justify-center">
              <svg className="w-5 h-5 text-sky-400" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                <path d="M3 17l6-6 4 4 8-8" />
                <path d="M21 7v4h-4" />
              </svg>
            </div>
            <div>
              <h2 className="text-base font-semibold text-slate-100 group-hover:text-sky-300 transition-colors">US Stocks</h2>
              <p className="text-xs text-slate-500">Browse & search popular large-cap stocks</p>
            </div>
          </div>
          <div className="flex items-center justify-between">
            <span className="text-xs text-slate-400">AAPL, MSFT, NVDA, TSLA & 40+ more</span>
            <svg className="w-4 h-4 text-slate-500 group-hover:text-sky-400 transition-colors" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <path d="M9 18l6-6-6-6" />
            </svg>
          </div>
        </Link>

        <Link href="/us-markets/etfs" className="glass-card-hover p-6 group">
          <div className="flex items-center gap-3 mb-3">
            <div className="w-10 h-10 rounded-xl bg-emerald-500/15 border border-emerald-500/30 flex items-center justify-center">
              <svg className="w-5 h-5 text-emerald-400" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                <path d="M3 12h18M3 6h18M3 18h18" />
              </svg>
            </div>
            <div>
              <h2 className="text-base font-semibold text-slate-100 group-hover:text-emerald-300 transition-colors">US ETFs</h2>
              <p className="text-xs text-slate-500">Risk/return screener sorted by Sharpe</p>
            </div>
          </div>
          <div className="flex items-center justify-between">
            <span className="text-xs text-slate-400">SPY, QQQ, VTI, GLD & 15 total</span>
            <svg className="w-4 h-4 text-slate-500 group-hover:text-emerald-400 transition-colors" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <path d="M9 18l6-6-6-6" />
            </svg>
          </div>
        </Link>
      </div>

      <p className="text-xs text-slate-600 text-center">
        US market data via yfinance (delayed ~15 min). Not investment advice.
      </p>
    </div>
  );
}
