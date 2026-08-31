"use client";

import { useState, useCallback, useEffect } from "react";
import useSWR from "swr";
import {
  fetchPriceAlerts,
  createPriceAlert,
  deletePriceAlert,
  checkPriceAlerts,
  type PriceAlert,
} from "@/lib/api";

const CONDITIONS = [
  { value: "above", label: "Price goes above", desc: "Trigger when price ≥ target" },
  { value: "below", label: "Price goes below", desc: "Trigger when price ≤ target" },
  { value: "cross_up", label: "Crosses above", desc: "Trigger when price crosses up through target" },
  { value: "cross_down", label: "Crosses below", desc: "Trigger when price crosses down through target" },
] as const;

export default function PriceAlertsPage() {
  const { data, mutate } = useSWR("/api/price-alerts", fetchPriceAlerts, { refreshInterval: 60000, keepPreviousData: true });
  const [symbol, setSymbol] = useState("SPY");
  const [condition, setCondition] = useState<string>("above");
  const [targetPrice, setTargetPrice] = useState("");
  const [note, setNote] = useState("");
  const [creating, setCreating] = useState(false);
  const [checking, setChecking] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [triggered, setTriggered] = useState<PriceAlert[]>([]);

  const alerts = data?.alerts || [];

  const handleCreate = async () => {
    const price = parseFloat(targetPrice);
    if (!price || price <= 0) {
      setError("Enter a valid target price");
      return;
    }
    setCreating(true);
    setError(null);
    try {
      await createPriceAlert({
        symbol: symbol.toUpperCase(),
        condition: condition as PriceAlert["condition"],
        target_price: price,
        note: note || undefined,
      });
      setTargetPrice("");
      setNote("");
      mutate();
    } catch (e: any) {
      setError(e.message || "Failed to create alert");
    } finally {
      setCreating(false);
    }
  };

  const handleDelete = async (id: number) => {
    try {
      await deletePriceAlert(id);
      mutate();
    } catch (e: any) {
      setError(e.message || "Failed to delete alert");
    }
  };

  const handleCheck = async () => {
    setChecking(true);
    setError(null);
    setTriggered([]);
    try {
      const res = await checkPriceAlerts();
      if (res.triggered.length > 0) {
        setTriggered(res.triggered);
      }
      mutate();
    } catch (e: any) {
      setError(e.message || "Failed to check alerts");
    } finally {
      setChecking(false);
    }
  };

  const activeAlerts = alerts.filter((a) => a.status === "active");
  const triggeredAlerts = alerts.filter((a) => a.status === "triggered");

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-bold text-slate-100">Price Alerts</h1>
          <p className="text-sm text-slate-500 mt-1">
            Set price thresholds and get notified when they hit.
          </p>
        </div>
        <button
          onClick={handleCheck}
          disabled={checking || activeAlerts.length === 0}
          className="px-4 py-2 bg-sky-600 hover:bg-sky-500 disabled:opacity-50 text-white rounded-lg text-sm font-medium"
        >
          {checking ? "Checking..." : "Check All"}
        </button>
      </div>

      {triggered.length > 0 && (
        <div className="glass-card p-4 border border-emerald-700/40">
          <div className="text-sm font-semibold text-emerald-400 mb-2">
            {triggered.length} Alert{triggered.length > 1 ? "s" : ""} Triggered!
          </div>
          <div className="space-y-1">
            {triggered.map((a) => (
              <div key={a.id} className="text-xs text-slate-300 flex items-center gap-2">
                <span className="text-emerald-400">▶</span>
                <span className="font-semibold">{a.symbol}</span>
                <span className="text-slate-500">{a.condition.replace("_", " ")}</span>
                <span className="text-slate-400">${a.target_price}</span>
                <span className="text-slate-500">→ hit at</span>
                <span className="text-emerald-400 font-semibold">${a.triggered_price}</span>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Create Alert */}
      <div className="glass-card p-4 space-y-3">
        <div className="text-sm font-semibold text-slate-300">Create New Alert</div>
        <div className="grid grid-cols-1 sm:grid-cols-4 gap-3">
          <div>
            <label className="text-xs text-slate-500 block mb-1">Symbol</label>
            <input
              type="text"
              value={symbol}
              onChange={(e) => setSymbol(e.target.value)}
              className="w-full px-3 py-2 bg-slate-800 text-slate-100 rounded-lg text-sm border border-slate-700 focus:border-emerald-500 focus:outline-none"
            />
          </div>
          <div>
            <label className="text-xs text-slate-500 block mb-1">Condition</label>
            <select
              value={condition}
              onChange={(e) => setCondition(e.target.value)}
              className="w-full px-3 py-2 bg-slate-800 text-slate-100 rounded-lg text-sm border border-slate-700"
            >
              {CONDITIONS.map((c) => <option key={c.value} value={c.value}>{c.label}</option>)}
            </select>
          </div>
          <div>
            <label className="text-xs text-slate-500 block mb-1">Target Price ($)</label>
            <input
              type="number"
              step="0.01"
              value={targetPrice}
              onChange={(e) => setTargetPrice(e.target.value)}
              className="w-full px-3 py-2 bg-slate-800 text-slate-100 rounded-lg text-sm border border-slate-700 focus:border-emerald-500 focus:outline-none"
              placeholder="450.00"
            />
          </div>
          <div>
            <label className="text-xs text-slate-500 block mb-1">Note (optional)</label>
            <input
              type="text"
              value={note}
              onChange={(e) => setNote(e.target.value)}
              className="w-full px-3 py-2 bg-slate-800 text-slate-100 rounded-lg text-sm border border-slate-700 focus:border-emerald-500 focus:outline-none"
              placeholder="Take profit"
            />
          </div>
        </div>
        <div className="flex justify-end">
          <button
            onClick={handleCreate}
            disabled={creating}
            className="px-6 py-2 bg-emerald-600 hover:bg-emerald-500 disabled:opacity-50 text-white rounded-lg text-sm font-medium"
          >
            {creating ? "Creating..." : "Add Alert"}
          </button>
        </div>
      </div>

      {error && <div className="glass-card p-4 text-center"><p className="text-rose-300 text-sm">{error}</p></div>}

      {/* Active Alerts */}
      <div>
        <div className="text-sm font-semibold text-slate-300 mb-2">Active Alerts ({activeAlerts.length})</div>
        {activeAlerts.length === 0 ? (
          <div className="glass-card p-8 text-center">
            <p className="text-sm text-slate-500">No active alerts. Create one above to get started.</p>
          </div>
        ) : (
          <div className="space-y-2">
            {activeAlerts.map((a) => (
              <div key={a.id} className="glass-card p-3 flex items-center gap-3">
                <div className="flex-1">
                  <div className="flex items-center gap-2">
                    <span className="font-semibold text-slate-100">{a.symbol}</span>
                    <span className={`text-xs px-2 py-0.5 rounded-full ${
                      a.condition === "above" || a.condition === "cross_up"
                        ? "bg-emerald-900/40 text-emerald-400"
                        : "bg-rose-900/40 text-rose-400"
                    }`}>
                      {a.condition.replace("_", " ")} ${a.target_price}
                    </span>
                  </div>
                  {a.note && <div className="text-xs text-slate-500 mt-1">{a.note}</div>}
                  <div className="text-[10px] text-slate-600 mt-0.5">
                    Created {new Date(a.created_at).toLocaleDateString()}
                  </div>
                </div>
                <button
                  onClick={() => handleDelete(a.id)}
                  className="text-xs text-slate-500 hover:text-rose-400 px-2 py-1"
                >
                  Delete
                </button>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Triggered Alerts */}
      {triggeredAlerts.length > 0 && (
        <div>
          <div className="text-sm font-semibold text-slate-300 mb-2">Triggered ({triggeredAlerts.length})</div>
          <div className="space-y-2">
            {triggeredAlerts.map((a) => (
              <div key={a.id} className="glass-card p-3 flex items-center gap-3 opacity-70">
                <div className="flex-1">
                  <div className="flex items-center gap-2">
                    <span className="font-semibold text-slate-100">{a.symbol}</span>
                    <span className="text-xs text-emerald-400">
                      {a.condition.replace("_", " ")} ${a.target_price}
                    </span>
                    <span className="text-xs text-slate-500">→</span>
                    <span className="text-xs text-emerald-400 font-semibold">${a.triggered_price}</span>
                  </div>
                  {a.note && <div className="text-xs text-slate-500 mt-1">{a.note}</div>}
                  {a.triggered_at && (
                    <div className="text-[10px] text-slate-600 mt-0.5">
                      Triggered {new Date(a.triggered_at).toLocaleString()}
                    </div>
                  )}
                </div>
                <button
                  onClick={() => handleDelete(a.id)}
                  className="text-xs text-slate-500 hover:text-rose-400 px-2 py-1"
                >
                  Delete
                </button>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
