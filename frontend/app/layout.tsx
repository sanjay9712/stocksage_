import "./globals.css";
import type { Metadata } from "next";
import Link from "next/link";
import AuthGate from "@/components/AuthGate";
import HeaderUser from "@/components/HeaderUser";
import NavDropdown from "@/components/NavDropdown";
import Providers from "./providers";
import { AuthProvider } from "@/lib/auth-context";

export const metadata: Metadata = {
  title: "StockSage — NSE Screener",
  description: "Intraday picks, ETF/MF screening, and holdings review with explainable reasoning.",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body className="min-h-screen antialiased">
        <Providers>
        <AuthProvider>
        <AuthGate>
          <header className="border-b border-slate-800/60 bg-slate-950/70 backdrop-blur-md sticky top-0 z-20">
            <div className="mx-auto max-w-6xl px-4 py-3 flex items-center justify-between gap-4">
              <Link href="/" className="flex items-center gap-2 font-semibold tracking-tight whitespace-nowrap group">
                <div className="flex items-center justify-center w-8 h-8 rounded-lg bg-gradient-to-br from-emerald-500 to-teal-600 shadow-lg shadow-emerald-900/30 group-hover:scale-105 transition-transform">
                  <svg className="w-5 h-5 text-white" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
                    <path d="M3 17l6-6 4 4 8-8" />
                    <path d="M14 7h7v7" />
                  </svg>
                </div>
                <span className="text-slate-100">Stock<span className="text-emerald-400">Sage</span></span>
              </Link>
              <NavDropdown />
              <HeaderUser />
            </div>
          </header>
          <main className="mx-auto max-w-6xl px-4 py-6">{children}</main>
          <footer className="mx-auto max-w-6xl px-4 py-8 text-xs text-slate-600 border-t border-slate-800/40 mt-8">
            <p>Systematic screen for educational use. Data delayed ~15 min via Yahoo Finance. Not investment advice.</p>
          </footer>
        </AuthGate>
        </AuthProvider>
        </Providers>
      </body>
    </html>
  );
}
