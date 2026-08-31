"use client";

import useSWR from "swr";
import { fetchTaxHarvest, type TaxHarvestOpportunity } from "@/lib/api";

export default function TaxHarvestPage() {
  const { data, isLoading, error, mutate } = useSWR("tax-harvest", fetchTaxHarvest, {
    refreshInterval: 300000,
    keepPreviousData: true,
  });

  if (isLoading && !data) {
    return (
      <div className="space-y-4">
        <h1 className="text-xl font-bold text-slate-100">Tax-Loss Harvesting</h1>
        <div className="glass-card p-8 shimmer" />
      </div>
    );
  }

  if (error && !data) {
    return (
      <div className="text-center py-12">
        <p className="text-rose-300 mb-4">Failed to load tax harvesting data</p>
        <button onClick={() => mutate()} className="px-4 py-2 bg-emerald-600 hover:bg-emerald-500 text-white rounded-lg text-sm">Retry</button>
      </div>
    );
  }

  if (!data) return null;

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-xl font-bold text-slate-100">Tax-Loss Harvesting</h1>
        <p className="text-sm text-slate-500 mt-1">
          Sell losing positions to offset gains and save taxes — while maintaining market exposure with replacement securities.
        </p>
      </div>

      {/* Summary cards */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
        <div className="glass-card p-4">
          <div className="text-[10px] text-slate-400 uppercase">Total Losses</div>
          <div className="text-lg font-bold text-rose-400 tabular-nums">₹{data.total_unrealized_losses.toLocaleString("en-IN")}</div>
        </div>
        <div className="glass-card p-4">
          <div className="text-[10px] text-slate-400 uppercase">Total Gains</div>
          <div className="text-lg font-bold text-emerald-400 tabular-nums">₹{data.total_unrealized_gains.toLocaleString("en-IN")}</div>
        </div>
        <div className="glass-card p-4">
          <div className="text-[10px] text-slate-400 uppercase">Offsettable</div>
          <div className="text-lg font-bold text-sky-400 tabular-nums">₹{data.offsettable_losses.toLocaleString("en-IN")}</div>
        </div>
        <div className="glass-card p-4">
          <div className="text-[10px] text-slate-400 uppercase">Tax Saving</div>
          <div className="text-lg font-bold text-emerald-400 tabular-nums">₹{data.estimated_tax_saving_from_offset.toLocaleString("en-IN")}</div>
        </div>
      </div>

      {/* Summary text */}
      <div className="glass-card p-4">
        <p className="text-sm text-slate-300">{data.summary}</p>
      </div>

      {/* Opportunities */}
      {data.opportunities.length > 0 ? (
        <div>
          <h2 className="text-sm font-semibold text-slate-400 mb-3">
            {data.opportunities.length} Harvesting Opportunities (sorted by loss amount)
          </h2>
          <div className="space-y-3">
            {data.opportunities.map((o: TaxHarvestOpportunity) => (
              <div key={o.symbol} className="glass-card p-4 fade-in">
                <div className="flex items-start justify-between mb-3">
                  <div>
                    <div className="flex items-center gap-2">
                      <span className="font-semibold text-slate-100">{o.symbol}</span>
                      <span className="text-xs text-slate-500">{o.quantity} shares</span>
                    </div>
                    <div className="text-xs text-slate-400 mt-0.5">
                      Avg: ₹{o.avg_price} → Current: ₹{o.current_price}
                    </div>
                  </div>
                  <div className="text-right">
                    <div className="text-lg font-bold text-rose-400 tabular-nums">₹{o.unrealized_loss.toLocaleString("en-IN")}</div>
                    <div className="text-xs text-rose-300 tabular-nums">{o.loss_pct.toFixed(1)}% loss</div>
                  </div>
                </div>

                <div className="grid grid-cols-2 gap-3 mb-3">
                  <div className="bg-slate-900/50 rounded-lg p-2 text-center">
                    <div className="text-[10px] text-slate-400 uppercase">Tax Saving</div>
                    <div className="text-sm font-bold text-emerald-400 tabular-nums">₹{o.estimated_tax_saving.toLocaleString("en-IN")}</div>
                  </div>
                  <div className="bg-slate-900/50 rounded-lg p-2 text-center">
                    <div className="text-[10px] text-slate-400 uppercase">Replace With</div>
                    <div className="text-sm font-bold text-sky-400">{o.replacement_symbol}</div>
                  </div>
                </div>

                <div className="flex items-start gap-2 text-xs text-amber-300 bg-amber-950/20 rounded-lg p-2">
                  <svg className="w-4 h-4 shrink-0 mt-0.5" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                    <path d="M12 9v4M12 17h.01M10.29 3.86L1.82 18a2 2 0 001.71 3h16.94a2 2 0 001.71-3L13.71 3.86a2 2 0 00-3.42 0z" />
                  </svg>
                  <span>{o.wash_sale_period}</span>
                </div>

                <p className="text-xs text-slate-400 mt-2">{o.action}</p>
              </div>
            ))}
          </div>
        </div>
      ) : (
        <div className="glass-card p-8 text-center">
          <p className="text-emerald-300 text-sm">No losing positions to harvest right now. Your portfolio is in good shape!</p>
        </div>
      )}

      <p className="text-xs text-slate-600 text-center">
        Tax calculations assume 15% STCG rate. Consult a tax advisor before making decisions. This is educational, not tax advice.
      </p>
    </div>
  );
}
