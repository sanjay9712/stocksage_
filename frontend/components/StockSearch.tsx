"use client";

import { useState, useEffect, useRef } from "react";
import Link from "next/link";
import { searchStock, searchStockSuggest, type StockSearchResult, type StockSuggestion } from "@/lib/api";

export default function StockSearch() {
  const [query, setQuery] = useState("");
  const [suggestions, setSuggestions] = useState<StockSuggestion[]>([]);
  const [showDropdown, setShowDropdown] = useState(false);
  const [highlightIdx, setHighlightIdx] = useState(-1);
  const [result, setResult] = useState<StockSearchResult | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const debounceRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const containerRef = useRef<HTMLDivElement>(null);
  const selectingRef = useRef(false);

  // Debounced autocomplete
  useEffect(() => {
    if (debounceRef.current) clearTimeout(debounceRef.current);
    if (query.trim().length < 1) {
      setSuggestions([]);
      setShowDropdown(false);
      return;
    }
    // Skip the debounce if we just selected a suggestion (setQuery triggered this)
    if (selectingRef.current) {
      selectingRef.current = false;
      return;
    }
    debounceRef.current = setTimeout(async () => {
      try {
        const r = await searchStockSuggest(query.trim());
        setSuggestions(r.results);
        setShowDropdown(true);
        setHighlightIdx(-1);
      } catch {
        // Silent fail — suggestions are optional
      }
    }, 200);
    return () => {
      if (debounceRef.current) clearTimeout(debounceRef.current);
    };
  }, [query]);

  // Close dropdown on outside click
  useEffect(() => {
    function handleClick(e: MouseEvent) {
      if (containerRef.current && !containerRef.current.contains(e.target as Node)) {
        setShowDropdown(false);
      }
    }
    document.addEventListener("mousedown", handleClick);
    return () => document.removeEventListener("mousedown", handleClick);
  }, []);

  function selectSuggestion(s: StockSuggestion) {
    selectingRef.current = true;
    setQuery(s.symbol);
    setSuggestions([]);
    setShowDropdown(false);
    handleSearch(undefined, s.symbol);
  }

  async function handleSearch(e?: React.FormEvent, forcedSymbol?: string) {
    if (e) e.preventDefault();
    const sym = (forcedSymbol || query).trim();
    if (!sym) return;
    setLoading(true);
    setError("");
    setResult(null);
    setShowDropdown(false);
    try {
      const r = await searchStock(sym);
      setResult(r);
    } catch {
      setError("Search failed. Is the backend running?");
    } finally {
      setLoading(false);
    }
  }

  function handleKeyDown(e: React.KeyboardEvent) {
    if (!showDropdown || suggestions.length === 0) return;
    if (e.key === "ArrowDown") {
      e.preventDefault();
      setHighlightIdx((i) => Math.min(i + 1, suggestions.length - 1));
    } else if (e.key === "ArrowUp") {
      e.preventDefault();
      setHighlightIdx((i) => Math.max(i - 1, 0));
    } else if (e.key === "Enter" && highlightIdx >= 0) {
      e.preventDefault();
      selectSuggestion(suggestions[highlightIdx]);
    } else if (e.key === "Escape") {
      setShowDropdown(false);
    }
  }

  return (
    <div className="glass-card p-4 relative" ref={containerRef}>
      <form onSubmit={handleSearch}>
        <div className="flex gap-2 items-stretch">
          <div className="relative flex-1">
            <svg className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-500 pointer-events-none" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <path d="M21 21l-4.35-4.35M11 18a7 7 0 100-14 7 7 0 000 14z" />
            </svg>
            <input
              type="text"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              onKeyDown={handleKeyDown}
              onFocus={() => suggestions.length > 0 && setShowDropdown(true)}
              placeholder="Search any NSE stock — RELIANCE, TCS, INFY..."
              className="w-full rounded-lg bg-slate-800/60 border border-slate-700/50 pl-9 pr-3 py-2 text-sm placeholder:text-slate-600 focus:outline-none focus:border-emerald-600 focus:ring-1 focus:ring-emerald-600/30 transition-colors"
              autoComplete="off"
            />
          </div>
          <button
            type="submit"
            disabled={loading || !query.trim()}
            className="flex items-center gap-2 rounded-lg bg-gradient-to-r from-emerald-600 to-teal-600 hover:from-emerald-500 hover:to-teal-500 disabled:opacity-40 disabled:cursor-not-allowed px-5 py-2 text-sm font-medium shadow-lg shadow-emerald-900/20 transition-all shrink-0"
          >
            {loading ? (
              <svg className="w-4 h-4 animate-spin" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                <path d="M21 12a9 9 0 11-6.219-8.56" />
              </svg>
            ) : null}
            {loading ? "Searching" : "Search"}
          </button>
        </div>
      </form>

      {/* Autocomplete dropdown — separate from the form, positioned below it */}
      {showDropdown && suggestions.length > 0 && (
        <div className="relative z-30 h-0">
          <div className="absolute top-1 left-0 right-0 rounded-lg border border-slate-700 bg-slate-900 shadow-xl shadow-black/40 max-h-80 overflow-y-auto fade-in">
            {suggestions.map((s, i) => (
              <button
                key={s.symbol}
                type="button"
                onClick={() => selectSuggestion(s)}
                onMouseEnter={() => setHighlightIdx(i)}
                className={`w-full flex items-center justify-between gap-2 px-3 py-2 text-left transition-colors ${
                  i === highlightIdx ? "bg-slate-800" : "hover:bg-slate-800/50"
                }`}
              >
                <div className="min-w-0 flex-1">
                  <span className="text-sm font-medium text-slate-200">{s.symbol}</span>
                  <span className="ml-2 text-xs text-slate-500 truncate">{s.name}</span>
                </div>
                <svg className="w-3.5 h-3.5 text-slate-600 shrink-0" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                  <path d="M9 18l6-6-6-6" />
                </svg>
              </button>
            ))}
          </div>
        </div>
      )}

      {error && <p className="text-rose-400 text-sm mt-3">{error}</p>}

      {result && result.found && result.quote && (
        <div className={`p-4 rounded-lg border border-slate-800/60 bg-slate-800/30 fade-in space-y-3 ${showDropdown && suggestions.length > 0 ? "mt-[20.5rem]" : "mt-4"}`}>
          {/* Top row: name + price */}
          <div className="flex items-center justify-between">
            <div className="min-w-0">
              <div className="flex items-center gap-2 flex-wrap">
                <span className="font-semibold text-slate-100">{result.symbol}</span>
                {result.fundamentals?.company_name && (
                  <span className="text-xs text-slate-400 truncate">{result.fundamentals.company_name}</span>
                )}
                {result.fundamentals?.sector && (
                  <span className="text-xs bg-slate-800 px-1.5 py-0.5 rounded text-slate-400">{result.fundamentals.sector}</span>
                )}
              </div>
              {result.pick && (
                <Link href={`/picks/${result.symbol}`} className="mt-1 inline-block text-xs text-emerald-400 hover:underline">
                  In today&apos;s picks →
                </Link>
              )}
            </div>
            <div className="text-right shrink-0">
              <div className="text-2xl font-bold tabular-nums text-slate-100">
                ₹{result.quote.price?.toLocaleString()}
              </div>
              {result.quote.prev_close != null && result.quote.prev_close > 0 && (
                <div className={`text-sm tabular-nums font-medium ${
                  result.quote.price >= result.quote.prev_close ? "text-emerald-400" : "text-rose-400"
                }`}>
                  {result.quote.price >= result.quote.prev_close ? "▲" : "▼"} {Math.abs(((result.quote.price - result.quote.prev_close) / result.quote.prev_close) * 100).toFixed(2)}%
                </div>
              )}
            </div>
          </div>

          {/* Quote stats */}
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-2">
            {result.quote.prev_close != null && (
              <Stat label="Prev Close" value={`₹${result.quote.prev_close.toLocaleString()}`} />
            )}
            {result.quote.day_high != null && (
              <Stat label="Day High" value={`₹${result.quote.day_high.toLocaleString()}`} />
            )}
            {result.quote.day_low != null && (
              <Stat label="Day Low" value={`₹${result.quote.day_low.toLocaleString()}`} />
            )}
            {result.quote.volume != null && (
              <Stat label="Volume" value={result.quote.volume.toLocaleString()} />
            )}
          </div>

          {/* Fundamentals */}
          {result.fundamentals && (
            <div className="grid grid-cols-2 sm:grid-cols-4 gap-2">
              {result.fundamentals.trailing_pe != null && (
                <Stat label="P/E" value={result.fundamentals.trailing_pe.toFixed(2)} />
              )}
              {result.fundamentals.forward_pe != null && (
                <Stat label="Fwd P/E" value={result.fundamentals.forward_pe.toFixed(2)} />
              )}
              {result.fundamentals.market_cap != null && (
                <Stat label="Mkt Cap" value={
                  result.fundamentals.market_cap >= 1e12 ? `₹${(result.fundamentals.market_cap / 1e12).toFixed(1)}T` :
                  result.fundamentals.market_cap >= 1e7 ? `₹${(result.fundamentals.market_cap / 1e7).toFixed(0)}Cr` : "—"
                } />
              )}
            </div>
          )}

          <div className="flex items-center justify-between pt-1">
            <Link href={`/stock/${result.symbol}`} className="text-xs text-sky-400 hover:underline">
              View full details →
            </Link>
            <p className="text-xs text-slate-600">
              via {result.pick ? "broker" : "yfinance"} · may be delayed ~15 min
            </p>
          </div>
        </div>
      )}

      {result && !result.found && (
        <p className="text-amber-300 text-sm mt-3">{result.message}</p>
      )}
    </div>
  );
}

function Stat({ label, value }: { label: string; value: string }) {
  return (
    <div className="stat-box">
      <div className="text-[10px] text-slate-400 uppercase tracking-wide">{label}</div>
      <div className="text-sm font-medium tabular-nums text-slate-200">{value}</div>
    </div>
  );
}
