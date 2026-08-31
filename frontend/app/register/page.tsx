"use client";

import { useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { registerUser } from "@/lib/api";

export default function RegisterPage() {
  const router = useRouter();
  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [capital, setCapital] = useState(500000);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError("");

    if (password !== confirmPassword) {
      setError("Passwords do not match");
      return;
    }
    if (password.length < 6) {
      setError("Password must be at least 6 characters");
      return;
    }

    setLoading(true);
    try {
      await registerUser(name, email, password, capital);
      router.replace("/");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Registration failed");
    } finally {
      setLoading(false);
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
        <h1 className="text-2xl font-bold text-slate-100">Create your account</h1>
        <p className="text-sm text-slate-500 mt-1">Start paper trading with virtual capital</p>
      </div>

      <form onSubmit={handleSubmit} className="space-y-4 bg-slate-900/50 border border-slate-800 rounded-xl p-6">
        <div>
          <label className="block text-sm text-slate-400 mb-1">Full Name</label>
          <input
            type="text"
            value={name}
            onChange={(e) => setName(e.target.value)}
            required
            autoFocus
            className="w-full px-3 py-2 bg-slate-950 border border-slate-800 rounded-lg text-slate-100 focus:outline-none focus:border-emerald-500"
            placeholder="Your Name"
          />
        </div>
        <div>
          <label className="block text-sm text-slate-400 mb-1">Email</label>
          <input
            type="email"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            required
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
            placeholder="At least 6 characters"
          />
        </div>
        <div>
          <label className="block text-sm text-slate-400 mb-1">Confirm Password</label>
          <input
            type="password"
            value={confirmPassword}
            onChange={(e) => setConfirmPassword(e.target.value)}
            required
            className="w-full px-3 py-2 bg-slate-950 border border-slate-800 rounded-lg text-slate-100 focus:outline-none focus:border-emerald-500"
            placeholder="Re-enter password"
          />
        </div>

        <div>
          <label className="block text-sm text-slate-400 mb-2">Virtual Capital for Paper Trading</label>
          <div className="grid grid-cols-2 gap-3">
            <button
              type="button"
              onClick={() => setCapital(500000)}
              className={`py-3 px-4 rounded-lg border text-center transition-colors ${
                capital === 500000
                  ? "border-emerald-500 bg-emerald-950/30 text-emerald-300"
                  : "border-slate-800 bg-slate-950 text-slate-400 hover:border-slate-700"
              }`}
            >
              <div className="text-lg font-bold">₹5 Lakh</div>
              <div className="text-xs opacity-70">₹50K per trade</div>
            </button>
            <button
              type="button"
              onClick={() => setCapital(1000000)}
              className={`py-3 px-4 rounded-lg border text-center transition-colors ${
                capital === 1000000
                  ? "border-emerald-500 bg-emerald-950/30 text-emerald-300"
                  : "border-slate-800 bg-slate-950 text-slate-400 hover:border-slate-700"
              }`}
            >
              <div className="text-lg font-bold">₹10 Lakh</div>
              <div className="text-xs opacity-70">₹1L per trade</div>
            </button>
          </div>
          <p className="text-xs text-slate-600 mt-2">Each trade uses 10% of your capital. You can track rupee P&L based on this amount.</p>
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
          {loading ? "Creating account…" : "Register"}
        </button>

        <p className="text-center text-sm text-slate-500">
          Already have an account?{" "}
          <Link href="/login" className="text-emerald-400 hover:underline">
            Log in
          </Link>
        </p>
      </form>
    </div>
  );
}
