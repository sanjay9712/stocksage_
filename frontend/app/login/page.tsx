"use client";

import { useState, Suspense } from "react";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { loginUser, guestLogin } from "@/lib/api";

function LoginContent() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const guestMessage = searchParams.get("reason") === "guest";
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  const [guestLoading, setGuestLoading] = useState(false);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError("");
    setLoading(true);
    try {
      await loginUser(email, password);
      router.replace("/");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Login failed");
    } finally {
      setLoading(false);
    }
  }

  async function handleGuest() {
    setError("");
    setGuestLoading(true);
    try {
      await guestLogin();
      router.replace("/");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Guest login failed");
    } finally {
      setGuestLoading(false);
    }
  }

  return (
    <div className="max-w-md mx-auto pt-12">
      <div className="text-center mb-8">
        <div className="inline-flex items-center justify-center w-14 h-14 rounded-xl bg-gradient-to-br from-emerald-500 to-teal-600 shadow-lg shadow-emerald-900/30 mb-4">
          <svg className="w-8 h-8 text-white" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
            <path d="M3 17l6-6 4 4 8-8" />
            <path d="M14 7h7v7" />
          </svg>
        </div>
        <h1 className="text-2xl font-bold text-slate-100">Welcome back</h1>
        <p className="text-sm text-slate-500 mt-1">Log in to access your trading dashboard</p>
      </div>

      {guestMessage && (
        <div className="mb-4 text-sm text-amber-400 bg-amber-950/30 border border-amber-900/50 rounded-lg px-3 py-2">
          Advanced strategies, paper trading, and funds require a registered account. Please log in or register to continue.
        </div>
      )}

      <form onSubmit={handleSubmit} className="space-y-4 bg-slate-900/50 border border-slate-800 rounded-xl p-6">
        <div>
          <label className="block text-sm text-slate-400 mb-1">Email</label>
          <input
            type="email"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            required
            autoFocus
            className="w-full px-3 py-2 bg-slate-950 border border-slate-800 rounded-lg text-slate-100 focus:outline-none focus:border-emerald-500"
            placeholder="you@example.com"
          />
        </div>
        <div>
          <label className="block text-sm text-slate-400 mb-1">Password</label>
          <input
            type="password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            required
            className="w-full px-3 py-2 bg-slate-950 border border-slate-800 rounded-lg text-slate-100 focus:outline-none focus:border-emerald-500"
            placeholder="••••••••"
          />
        </div>

        {error && (
          <div className="text-sm text-red-400 bg-red-950/30 border border-red-900/50 rounded-lg px-3 py-2">
            {error}
          </div>
        )}

        <button
          type="submit"
          disabled={loading}
          className="w-full py-2.5 bg-emerald-600 hover:bg-emerald-500 disabled:opacity-50 text-white font-medium rounded-lg transition-colors"
        >
          {loading ? "Logging in…" : "Log In"}
        </button>

        <div className="flex items-center gap-3 py-1">
          <div className="flex-1 h-px bg-slate-800" />
          <span className="text-xs text-slate-600">or</span>
          <div className="flex-1 h-px bg-slate-800" />
        </div>

        <button
          type="button"
          onClick={handleGuest}
          disabled={guestLoading}
          className="w-full py-2.5 bg-slate-800 hover:bg-slate-700 disabled:opacity-50 text-slate-300 font-medium rounded-lg transition-colors"
        >
          {guestLoading ? "Starting guest session…" : "Continue as Guest"}
        </button>

        <p className="text-center text-sm text-slate-500">
          Don&apos;t have an account?{" "}
          <Link href="/register" className="text-emerald-400 hover:underline">
            Register here
          </Link>
        </p>
      </form>
    </div>
  );
}

export default function LoginPage() {
  return (
    <Suspense fallback={<div className="max-w-md mx-auto pt-12 text-center text-slate-500">Loading…</div>}>
      <LoginContent />
    </Suspense>
  );
}
