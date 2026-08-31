"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useState, useRef, useEffect, useCallback } from "react";
import { useAuthContext } from "@/lib/auth-context";

interface SubItem {
  href: string;
  label: string;
  icon: string;
  section: string;
}

interface NavGroup {
  label: string;
  icon: string;
  items: SubItem[];
}

const SECTIONS = ["India \u00b7 NSE", "US Markets"] as const;

const NAV_GROUPS: NavGroup[] = [
  {
    label: "Markets",
    icon: "M3 13h2l3-9 4 18 3-9h6",
    items: [
      // India (NSE) — alphabetical
      { href: "/advanced", label: "Advanced", icon: "M12 2L2 7l10 5 10-5-10-5zM2 17l10 5 10-5M2 12l10 5 10-5", section: "India \u00b7 NSE" },
      { href: "/backtest", label: "Backtest", icon: "M3 3v18h18M9 3v18M3 9h18M3 15h18", section: "India \u00b7 NSE" },
      { href: "/bot", label: "Trading Bot", icon: "M12 2v20M5 7l7-5 7 5M5 17l7 5 7-5", section: "India \u00b7 NSE" },
      { href: "/broker", label: "Broker", icon: "M3 3h18v18H3zM3 9h18M9 21V9", section: "India \u00b7 NSE" },
      { href: "/commodities", label: "Commodities", icon: "M12 2v20M5 7l7-5 7 5M5 17l7 5 7-5", section: "India \u00b7 NSE" },
      { href: "/correlation", label: "Correlation", icon: "M3 3v18h18M7 14l4-4 4 4 4-6M3 3l18 18", section: "India \u00b7 NSE" },
      { href: "/daily-digest", label: "Digest", icon: "M3 8l4-4h10l4 4M3 8v10a2 2 0 002 2h14a2 2 0 002-2V8M3 8h18M9 12h6", section: "India \u00b7 NSE" },
      { href: "/dividends", label: "Dividends", icon: "M12 2v20M5 9h14M5 15h14", section: "India \u00b7 NSE" },
      { href: "/etf", label: "ETFs", icon: "M3 3v18h18M7 14l4-4 4 4 4-6", section: "India \u00b7 NSE" },
      { href: "/mf", label: "Funds", icon: "M4 6h16M4 12h16M4 18h10", section: "India \u00b7 NSE" },
      { href: "/gap-scanner", label: "Gap Scanner", icon: "M3 17l6-6 4 4 8-8M14 7h7v7", section: "India \u00b7 NSE" },
      { href: "/holdings", label: "Holdings", icon: "M20 7l-8-4-8 4v10l8 4 8-4V7zM4 7l8 4 8-4M12 11v10", section: "India \u00b7 NSE" },
      { href: "/", label: "Intraday", icon: "M3 13h2l3-9 4 18 3-9h6", section: "India \u00b7 NSE" },
      { href: "/ipo", label: "IPO", icon: "M3 3h18v18H3zM3 9h18M9 21V9M3 15h18M15 21V9", section: "India \u00b7 NSE" },
      { href: "/momentum-rotation", label: "Momentum", icon: "M3 17l6-6 4 4 8-8M14 7h7v7", section: "India \u00b7 NSE" },
      { href: "/notifications", label: "Notifications", icon: "M15 17h5l-1.5-9a6 6 0 00-12 0L4 17h5M9 17v1a3 3 0 006 0v-1M12 2v2", section: "India \u00b7 NSE" },
      { href: "/options-oi", label: "Options OI", icon: "M3 3v18h18M9 3v18M3 9h18M3 15h18", section: "India \u00b7 NSE" },
      { href: "/or-scanner", label: "OR Breakout", icon: "M3 3v18h18M9 3v18M3 9h18", section: "India \u00b7 NSE" },
      { href: "/portfolio-sim", label: "Portfolio Sim", icon: "M3 3v18h18M9 3v18M3 9h18M3 15h18M3 21h18M21 9h-6M21 15h-6", section: "India \u00b7 NSE" },
      { href: "/position-sizing", label: "Position Size", icon: "M12 2v20M5 7l7-5 7 5M5 17l7 5 7-5M12 7l5 5-5 5-5-5 5-5z", section: "India \u00b7 NSE" },
      { href: "/price-alerts", label: "Price Alerts", icon: "M15 17h5l-1.5-9a6 6 0 00-12 0L4 17h5M9 17v1a3 3 0 006 0v-1", section: "India \u00b7 NSE" },
      { href: "/rebalancing", label: "Rebalance", icon: "M3 12a9 9 0 1018 0 9 9 0 00-18 0zM12 3v9l6 6", section: "India \u00b7 NSE" },
      { href: "/risk-analytics", label: "Risk Analytics", icon: "M12 2L2 7l10 5 10-5-10-5zM2 17l10 5 10-5M2 12l10 5 10-5M9 12l3 3 3-3", section: "India \u00b7 NSE" },
      { href: "/sector-rotation", label: "Rotation", icon: "M4 4h16v16H4zM4 9h16M9 4v16", section: "India \u00b7 NSE" },
      { href: "/scalp", label: "Scalping", icon: "M13 2L3 14h9l-1 8 10-12h-9l1-8z", section: "India \u00b7 NSE" },
      { href: "/signal-alerts", label: "Signal Alerts", icon: "M13 2L3 14h9l-1 8 10-12h-9l1-8z", section: "India \u00b7 NSE" },
      { href: "/sip-calculator", label: "SIP Calc", icon: "M9 7h6m-6 4h6m-6 4h4M5 3v18M19 3v18", section: "India \u00b7 NSE" },
      { href: "/smart-money", label: "Smart Money", icon: "M12 2v20M5 7l7-5 7 5M5 17l7 5 7-5", section: "India \u00b7 NSE" },
      { href: "/stocks", label: "Stocks", icon: "M3 17l6-6 4 4 8-8M14 7h7v7", section: "India \u00b7 NSE" },
      { href: "/tax-harvest", label: "Tax Harvest", icon: "M12 2v20M5 7l7-5 7 5M5 17l7 5 7-5", section: "India \u00b7 NSE" },
      { href: "/daily-picks", label: "Top 5", icon: "M5 3h14a2 2 0 012 2v14a2 2 0 01-2 2H5a2 2 0 01-2-2V5a2 2 0 012-2zM9 7l3 3 5-5", section: "India \u00b7 NSE" },
      { href: "/volume-profile", label: "Vol Profile", icon: "M3 3v18h18M7 14l4-4 4 4 4-6", section: "India \u00b7 NSE" },
      { href: "/vwap-scanner", label: "VWAP Scan", icon: "M3 3v18h18M7 14l4-4 4 4 4-6M3 3l18 18", section: "India \u00b7 NSE" },
      { href: "/walk-forward", label: "Walk-Forward", icon: "M3 3v18h18M9 3v18M3 9h18M3 15h18M3 21h18", section: "India \u00b7 NSE" },
      // US
      { href: "/us-markets/etfs", label: "US ETFs", icon: "M3 3v18h18M7 14l4-4 4 4 4-6", section: "US Markets" },
      { href: "/us-markets/stocks", label: "US Stocks", icon: "M3 17l6-6 4 4 8-8M14 7h7v7", section: "US Markets" },
    ],
  },
];

/** Split an array into N roughly-equal chunks (column-major fill so each
 *  column reads top-to-bottom). */
function chunkColumns<T>(items: T[], cols: number): T[][] {
  const perCol = Math.ceil(items.length / cols);
  const out: T[][] = [];
  for (let c = 0; c < cols; c++) {
    out.push(items.slice(c * perCol, (c + 1) * perCol));
  }
  return out;
}

const RESTRICTED_HREFS = ["/mf", "/advanced"];

export default function NavDropdown() {
  const pathname = usePathname();
  const router = useRouter();
  const { user } = useAuthContext();
  const isGuest = user?.is_guest ?? false;
  const [openIdx, setOpenIdx] = useState<number | null>(null);
  const [lockedItem, setLockedItem] = useState<string | null>(null);
  const closeTimer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const navRef = useRef<HTMLElement>(null);

  const handleEnter = useCallback((idx: number) => {
    if (closeTimer.current) clearTimeout(closeTimer.current);
    setOpenIdx(idx);
  }, []);

  const handleLeave = useCallback(() => {
    closeTimer.current = setTimeout(() => setOpenIdx(null), 150);
  }, []);

  const closeNow = useCallback(() => {
    if (closeTimer.current) clearTimeout(closeTimer.current);
    setOpenIdx(null);
  }, []);

  // Close on Escape key.
  useEffect(() => {
    function onKey(e: KeyboardEvent) {
      if (e.key === "Escape") closeNow();
    }
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [closeNow]);

  // Close on click outside the nav.
  useEffect(() => {
    function onDown(e: MouseEvent) {
      if (navRef.current && !navRef.current.contains(e.target as Node)) closeNow();
    }
    document.addEventListener("mousedown", onDown);
    return () => document.removeEventListener("mousedown", onDown);
  }, [closeNow]);

  useEffect(() => {
    return () => {
      if (closeTimer.current) clearTimeout(closeTimer.current);
    };
  }, []);

  function isGroupActive(group: NavGroup) {
    return group.items.some((item) => {
      if (item.href === "/") return pathname === "/";
      return pathname.startsWith(item.href);
    });
  }

  return (
    <nav
      ref={navRef}
      className="flex items-center gap-0.5 text-sm"
      onMouseLeave={handleLeave}
    >
      {NAV_GROUPS.map((group, idx) => {
        const alignRight = idx === NAV_GROUPS.length - 1;
        // Group items by section, preserving SECTIONS order.
        const sections = SECTIONS.map((s) => ({
          name: s,
          items: group.items.filter((i) => i.section === s),
        })).filter((s) => s.items.length > 0);
        return (
          <div key={group.label} className="relative" onMouseEnter={() => handleEnter(idx)}>
            <button
              className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg whitespace-nowrap transition-colors ${
                openIdx === idx || isGroupActive(group)
                  ? "text-emerald-400 bg-slate-800/50"
                  : "text-slate-400 hover:text-emerald-400 hover:bg-slate-800/50"
              }`}
            >
              <svg className="w-4 h-4 shrink-0" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                <path d={group.icon} />
              </svg>
              <span className="hidden sm:inline">{group.label}</span>
              <svg className={`w-3 h-3 transition-transform ${openIdx === idx ? "rotate-180" : ""}`} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
                <path d="M6 9l6 6 6-6" />
              </svg>
            </button>

            {/* Dropdown menu */}
            {openIdx === idx && (
              <div className={`absolute top-full pt-1 z-30 ${alignRight ? "right-0" : "left-0"}`}>
                <div className="fade-in bg-slate-900/95 backdrop-blur-md border border-slate-800 rounded-xl shadow-2xl shadow-black/50 py-2 px-2 flex items-stretch gap-2">
                  {sections.map((sec, si) => {
                    const cols = sec.items.length > 14 ? 3 : sec.items.length > 8 ? 2 : 1;
                    const columns = chunkColumns(sec.items, cols);
                    return (
                      <div key={sec.name} className="flex items-stretch gap-1">
                        {si > 0 && <div className="w-px bg-slate-800" />}
                        <div className="flex flex-col gap-1">
                        <span className="px-1.5 text-[10px] font-semibold uppercase tracking-wider text-slate-500">
                          {sec.name}
                        </span>
                        <div className="flex gap-2">
                          {columns.map((col, ci) => (
                            <div key={ci} className="flex flex-col" style={{ minWidth: "124px" }}>
                              {col.map((item) => {
                                const isActive = item.href === "/" ? pathname === "/" : pathname.startsWith(item.href);
                                const restricted = isGuest && RESTRICTED_HREFS.includes(item.href);
                                const itemCls = `flex items-center gap-2 px-2.5 py-1.5 text-xs whitespace-nowrap rounded-lg transition-colors ${
                                  isActive
                                    ? "text-emerald-400 bg-slate-800/60"
                                    : "text-slate-300 hover:text-emerald-400 hover:bg-slate-800/40"
                                }`;
                                const icon = (
                                  <svg className="w-3.5 h-3.5 shrink-0 opacity-60" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                                    <path d={item.icon} />
                                  </svg>
                                );
                                const lockIcon = restricted && (
                                  <svg className="w-3 h-3 text-amber-400 ml-auto shrink-0" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                                    <rect x="3" y="11" width="18" height="11" rx="2" />
                                    <path d="M7 11V7a5 5 0 0110 0v4" />
                                  </svg>
                                );
                                if (restricted) {
                                  return (
                                    <button
                                      key={item.href}
                                      type="button"
                                      onClick={() => { closeNow(); setLockedItem(item.label); }}
                                      className={itemCls}
                                    >
                                      {icon}
                                      <span>{item.label}</span>
                                      {lockIcon}
                                    </button>
                                  );
                                }
                                return (
                                  <Link
                                    key={item.href}
                                    href={item.href}
                                    onClick={closeNow}
                                    className={itemCls}
                                  >
                                    {icon}
                                    <span>{item.label}</span>
                                  </Link>
                                );
                              })}
                            </div>
                          ))}
                        </div>
                        </div>
                      </div>
                    );
                  })}
                </div>
              </div>
            )}
          </div>
        );
      })}

      {/* Sign-in required modal for guest-restricted items */}
      {lockedItem && (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm fade-in"
          onMouseDown={(e) => { if (e.target === e.currentTarget) setLockedItem(null); }}
        >
          <div
            className="bg-slate-900 border border-slate-700 rounded-2xl shadow-2xl shadow-black/50 p-6 max-w-sm w-full mx-4"
            onMouseDown={(e) => e.stopPropagation()}
          >
            <div className="flex items-center gap-3 mb-4">
              <div className="flex items-center justify-center w-10 h-10 rounded-full bg-amber-500/15 shrink-0">
                <svg className="w-5 h-5 text-amber-400" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                  <rect x="3" y="11" width="18" height="11" rx="2" />
                  <path d="M7 11V7a5 5 0 0110 0v4" />
                </svg>
              </div>
              <div>
                <h3 className="text-base font-semibold text-slate-100">Sign in required</h3>
                <p className="text-xs text-slate-500">Guest accounts have limited access</p>
              </div>
            </div>
            <p className="text-sm text-slate-400 mb-5">
              <span className="text-slate-200 font-medium">{lockedItem}</span> requires a registered account.
              Please log in or create a free account to continue.
            </p>
            <div className="flex flex-col gap-2">
              <button
                onClick={() => { setLockedItem(null); router.push("/login"); }}
                className="w-full py-2.5 bg-emerald-600 hover:bg-emerald-500 text-white font-medium rounded-lg transition-colors text-sm"
              >
                Log In
              </button>
              <button
                onClick={() => { setLockedItem(null); router.push("/register"); }}
                className="w-full py-2.5 bg-slate-800 hover:bg-slate-700 text-slate-300 font-medium rounded-lg transition-colors text-sm"
              >
                Create Account
              </button>
              <button
                onClick={() => setLockedItem(null)}
                className="w-full py-2 text-slate-500 hover:text-slate-400 font-medium transition-colors text-sm"
              >
                Cancel
              </button>
            </div>
          </div>
        </div>
      )}
    </nav>
  );
}
