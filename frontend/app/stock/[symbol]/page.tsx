"use client";

import Link from "next/link";
import useSWR from "swr";
import {
  fetchStockDetail,
  fetchCandlestick,
  fetchMultiFactor,
  fetchMurphyDetail,
  fetchScalpSignal,
  fetchVolumeProfile,
  type StockDetail,
  type InvestLevels,
  type MurphyAnalysis,
  type MultiFactorScore,
  type CandlestickResult,
  type ScalpSignal,
  type VolumeProfileResponse,
} from "@/lib/api";

function fmtCr(v: number | null | undefined): string {
  if (v == null) return "—";
  if (v >= 1e12) return `₹${(v / 1e12).toFixed(2)}T`;
  if (v >= 1e7) return `₹${(v / 1e7).toFixed(0)}Cr`;
  if (v >= 1e5) return `₹${(v / 1e5).toFixed(1)}L`;
  return `₹${v.toFixed(0)}`;
}

function fmtPct(v: number | null | undefined): string {
  if (v == null) return "—";
  return `${(v * 100).toFixed(2)}%`;
}

function fmtNum(v: number | null | undefined, digits = 2): string {
  if (v == null) return "—";
  return v.toFixed(digits);
}

// ---------------------------------------------------------------------------
// Section components
// ---------------------------------------------------------------------------

function Metric({ label, value, color = "" }: { label: string; value: string; color?: string }) {
  return (
    <div className="stat-box">
      <div className="text-[10px] text-slate-400 uppercase tracking-wide">{label}</div>
      <div className={`text-sm font-medium tabular-nums ${color || "text-slate-200"}`}>{value}</div>
    </div>
  );
}

function VerdictBadge({ verdict }: { verdict: string }) {
  const v = verdict.toLowerCase();
  const cls = v.includes("buy") || v.includes("accumulate")
    ? "text-emerald-300 bg-emerald-500/15 border-emerald-500/30"
    : v.includes("sell") || v.includes("avoid")
    ? "text-rose-300 bg-rose-500/15 border-rose-500/30"
    : "text-amber-300 bg-amber-500/15 border-amber-500/30";
  return <span className={`text-sm font-bold rounded border px-3 py-1 ${cls}`}>{verdict.toUpperCase().replace(/_/g, " ")}</span>;
}

function OutlookCard({
  title,
  timeframe,
  verdict,
  entry,
  stopLoss,
  target1,
  target2,
  riskReward,
  what,
  why,
  when,
  factors,
}: {
  title: string;
  timeframe: string;
  verdict: string;
  entry?: number;
  stopLoss?: number;
  target1?: number;
  target2?: number;
  riskReward?: number;
  what: string;
  why: string;
  when: string;
  factors?: { label: string; value: number; max: number }[];
}) {
  return (
    <div className="glass-card p-5">
      <div className="flex items-center justify-between mb-3">
        <div>
          <h2 className="section-title">{title}</h2>
          <span className="text-[10px] text-slate-500">{timeframe}</span>
        </div>
        <VerdictBadge verdict={verdict} />
      </div>

      {(entry != null || stopLoss != null || target1 != null) && (
        <div className="grid grid-cols-2 sm:grid-cols-5 gap-2 mb-4">
          {entry != null && <Metric label="Entry" value={`₹${entry.toFixed(2)}`} color="text-sky-300" />}
          {stopLoss != null && <Metric label="Stop-Loss" value={`₹${stopLoss.toFixed(2)}`} color="text-rose-300" />}
          {target1 != null && <Metric label="Target 1" value={`₹${target1.toFixed(2)}`} color="text-emerald-300" />}
          {target2 != null && <Metric label="Target 2" value={`₹${target2.toFixed(2)}`} color="text-emerald-300" />}
          {riskReward != null && <Metric label="R:R" value={`1:${riskReward.toFixed(1)}`} color="text-amber-300" />}
        </div>
      )}

      {factors && factors.length > 0 && (
        <div className="space-y-2 mb-4">
          {factors.map((f, i) => (
            <div key={i}>
              <div className="flex items-center justify-between text-xs mb-1">
                <span className="text-slate-400 capitalize">{f.label.replace(/_/g, " ")}</span>
                <span className="text-slate-300 tabular-nums">{f.value.toFixed(0)}/{f.max}</span>
              </div>
              <div className="h-2 bg-slate-800 rounded-full overflow-hidden">
                <div
                  className={`h-full rounded-full ${f.value / f.max >= 0.6 ? "bg-emerald-500" : f.value / f.max >= 0.35 ? "bg-amber-500" : "bg-rose-500"}`}
                  style={{ width: `${(f.value / f.max) * 100}%` }}
                />
              </div>
            </div>
          ))}
        </div>
      )}

      <div className="space-y-2 text-sm">
        <div className="flex gap-2">
          <span className="text-[10px] font-bold text-slate-500 uppercase shrink-0 w-12 mt-0.5">What</span>
          <span className="text-slate-300">{what}</span>
        </div>
        <div className="flex gap-2">
          <span className="text-[10px] font-bold text-slate-500 uppercase shrink-0 w-12 mt-0.5">Why</span>
          <span className="text-slate-400">{why}</span>
        </div>
        <div className="flex gap-2">
          <span className="text-[10px] font-bold text-slate-500 uppercase shrink-0 w-12 mt-0.5">When</span>
          <span className="text-slate-400">{when}</span>
        </div>
      </div>
    </div>
  );
}

function TechnicalCard({ murphy }: { murphy: MurphyAnalysis }) {
  const rsi = murphy.rsi_value;
  const rsiSignal = murphy.rsi_signal;
  const macdHist = murphy.macd_histogram;
  const macdSignal = murphy.macd_signal;
  const stochK = murphy.stochastic_k;
  const stochSignal = murphy.stochastic_signal;
  const adx = murphy.adx_value;
  const adxStrength = murphy.adx_strength;
  const williams = murphy.williams_r_value;
  const williamsSignal = murphy.williams_r_signal;
  const obvTrend = murphy.obv_trend;
  const volRatio = murphy.volume_ratio;
  const supertrend = murphy.supertrend_dir;

  const indicators: { label: string; value: string; signal: string; bias: "bull" | "bear" | "neutral" }[] = [
    { label: "RSI (14)", value: fmtNum(rsi), signal: rsiSignal, bias: rsi < 30 ? "bull" : rsi > 70 ? "bear" : "neutral" },
    { label: "MACD Hist", value: fmtNum(macdHist), signal: macdSignal, bias: macdHist > 0 ? "bull" : macdHist < 0 ? "bear" : "neutral" },
    { label: "Stochastic %K", value: fmtNum(stochK), signal: stochSignal, bias: stochK < 20 ? "bull" : stochK > 80 ? "bear" : "neutral" },
    { label: "ADX", value: `${fmtNum(adx, 0)} (${adxStrength})`, signal: adxStrength, bias: adx > 25 ? "bull" : "neutral" },
    { label: "Williams %R", value: fmtNum(williams, 0), signal: williamsSignal, bias: williams < -80 ? "bull" : williams > -20 ? "bear" : "neutral" },
    { label: "Supertrend", value: supertrend.toUpperCase(), signal: supertrend, bias: supertrend === "bullish" ? "bull" : supertrend === "bearish" ? "bear" : "neutral" },
    { label: "OBV Trend", value: obvTrend, signal: obvTrend, bias: obvTrend === "up" ? "bull" : obvTrend === "down" ? "bear" : "neutral" },
    { label: "Volume Ratio", value: `${fmtNum(volRatio, 1)}x avg`, signal: volRatio > 1.5 ? "high" : "normal", bias: volRatio > 1.5 ? "bull" : "neutral" },
  ];

  const biasColor = (b: "bull" | "bear" | "neutral") =>
    b === "bull" ? "text-emerald-400" : b === "bear" ? "text-rose-400" : "text-slate-400";

  return (
    <div className="glass-card p-5">
      <h2 className="section-title mb-3">Technical Indicators</h2>
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
        {indicators.map((ind, i) => (
          <div key={i} className="stat-box">
            <div className="text-[10px] text-slate-500 uppercase">{ind.label}</div>
            <div className={`text-sm font-semibold tabular-nums ${biasColor(ind.bias)}`}>{ind.value}</div>
            <div className={`text-[10px] ${biasColor(ind.bias)}`}>{ind.signal}</div>
          </div>
        ))}
      </div>

      {/* Support / Resistance */}
      <div className="mt-4">
        <div className="text-[10px] text-slate-500 uppercase mb-2">Support &amp; Resistance</div>
        <div className="grid grid-cols-2 gap-4">
          <div>
            <div className="text-xs text-rose-400 mb-1">Support Levels</div>
            <div className="text-sm tabular-nums text-slate-300">Nearest: ₹{murphy.nearest_support?.toFixed(2)}</div>
            {murphy.fibonacci_levels && (
              <div className="text-[11px] text-slate-500 mt-1">
                {Object.entries(murphy.fibonacci_levels).filter(([k]) => k.includes("0.0") || k.includes("23.6") || k.includes("38.2")).slice(0, 3).map(([k, v]) => (
                  <span key={k} className="mr-2">Fib {k}: ₹{v.toFixed(2)}</span>
                ))}
              </div>
            )}
          </div>
          <div>
            <div className="text-xs text-emerald-400 mb-1">Resistance Levels</div>
            <div className="text-sm tabular-nums text-slate-300">Nearest: ₹{murphy.nearest_resistance?.toFixed(2)}</div>
            {murphy.pivot_levels && (
              <div className="text-[11px] text-slate-500 mt-1">
                R1: ₹{murphy.pivot_levels.r1?.toFixed(2)} · R2: ₹{murphy.pivot_levels.r2?.toFixed(2)}
              </div>
            )}
          </div>
        </div>
        <div className="text-[11px] text-slate-500 mt-2">Price position: {murphy.price_vs_support}</div>
      </div>
    </div>
  );
}

function VolumeProfileCard({ vp }: { vp: VolumeProfileResponse }) {
  const maxVol = Math.max(...vp.rows.map(r => r.volume), 1);
  const sortedRows = [...vp.rows].sort((a, b) => b.price_mid - a.price_mid);
  const visibleRows = sortedRows.slice(0, 20);
  return (
    <div className="glass-card p-5">
      <h2 className="section-title mb-3">Volume Profile ({vp.days}d)</h2>
      <div className="grid grid-cols-3 gap-3 mb-4">
        <Metric label="POC (High Vol)" value={`₹${vp.poc_price?.toFixed(2)}`} color="text-amber-300" />
        <Metric label="VAH" value={`₹${vp.vah?.toFixed(2)}`} color="text-emerald-300" />
        <Metric label="VAL" value={`₹${vp.val?.toFixed(2)}`} color="text-rose-300" />
      </div>
      <div className="space-y-0.5">
        {visibleRows.map((row, i) => (
          <div key={i} className="flex items-center gap-2 text-[10px]">
            <span className="text-slate-500 w-16 tabular-nums text-right">₹{row.price_mid.toFixed(0)}</span>
            <div className="flex-1 h-3.5 bg-slate-800/40 rounded-sm overflow-hidden relative">
              <div
                className={`h-full rounded-sm ${row.is_poc ? "bg-amber-500/60" : row.in_value_area ? "bg-emerald-500/30" : "bg-slate-600/30"}`}
                style={{ width: `${(row.volume / maxVol) * 100}%` }}
              />
            </div>
            <span className="text-slate-600 w-10 tabular-nums text-right">{row.pct.toFixed(1)}%</span>
          </div>
        ))}
      </div>
      <p className="text-[11px] text-slate-600 mt-2">
        POC = Point of Control (highest volume price). VAH/VAL = Value Area High/Low (70% of volume).
        Price above POC = bullish; below = bearish.
      </p>
    </div>
  );
}

function FactorBar({ label, value, weight }: { label: string; value: number; weight: number }) {
  return (
    <div>
      <div className="flex items-center justify-between mb-1">
        <span className="text-[10px] text-slate-400 uppercase tracking-wide">{label}</span>
        <span className="text-[10px] text-slate-500">{Math.round(weight * 100)}% wt</span>
      </div>
      <div className="h-2 bg-slate-800 rounded-full overflow-hidden">
        <div
          className={`h-full rounded-full ${value >= 0.7 ? "bg-emerald-500" : value >= 0.5 ? "bg-sky-500" : "bg-amber-500"}`}
          style={{ width: `${Math.round(value * 100)}%` }}
        />
      </div>
      <span className="text-xs text-slate-400 tabular-nums mt-0.5 block">{Math.round(value * 100)}%</span>
    </div>
  );
}

function renderFinRows(data: Record<string, Record<string, number | null>>, labels: [string, string][]) {
  const years = Object.keys(data).reverse();
  return labels.map(([key, label]) => (
    <tr key={key} className="border-t border-slate-800/50 hover:bg-slate-800/30 transition-colors">
      <td className="px-2 py-1.5 text-slate-400">{label}</td>
      {years.map(y => {
        const v = data[y]?.[key];
        return <td key={y} className="px-2 py-1.5 text-right tabular-nums text-slate-300">{v != null ? fmtCr(v) : "—"}</td>;
      })}
    </tr>
  ));
}

// ---------------------------------------------------------------------------
// Main page
// ---------------------------------------------------------------------------

export default function StockDetailPage({ params }: { params: { symbol: string } }) {
  const symbol = params.symbol.toUpperCase();

  // Auto-refreshing data sources
  const { data, isLoading, error } = useSWR(`stock-${symbol}`, () => fetchStockDetail(symbol), {
    refreshInterval: 5000,
    keepPreviousData: true,
  });
  const { data: candles } = useSWR(`candles-${symbol}`, () => fetchCandlestick(symbol), {
    refreshInterval: 30000,
    keepPreviousData: true,
  });
  const { data: multifactor } = useSWR(`mf-${symbol}`, () => fetchMultiFactor(symbol), {
    refreshInterval: 60000,
    keepPreviousData: true,
  });
  const { data: murphyData } = useSWR(`murphy-${symbol}`, () => fetchMurphyDetail(symbol), {
    refreshInterval: 30000,
    keepPreviousData: true,
  });
  const { data: scalpData } = useSWR(`scalp-${symbol}`, () => fetchScalpSignal(symbol), {
    refreshInterval: 15000,
    keepPreviousData: true,
  });
  const { data: vpData } = useSWR(`vp-${symbol}`, () => fetchVolumeProfile(symbol, 5, 30), {
    refreshInterval: 60000,
    keepPreviousData: true,
  });

  if (isLoading) {
    return (
      <div className="space-y-4">
        <div className="shimmer h-8 w-64 rounded-lg" />
        <div className="glass-card p-8">
          <div className="shimmer h-6 w-48 mx-auto rounded mb-4" />
          <div className="shimmer h-4 w-32 mx-auto rounded" />
        </div>
      </div>
    );
  }

  if (error || !data) {
    return (
      <div className="space-y-4">
        <Link href="/" className="text-sky-400 text-sm hover:underline">← back</Link>
        <div className="glass-card p-8 text-center">
          <p className="text-rose-400 text-sm">Failed to load {symbol}.</p>
          <p className="text-xs text-slate-500 mt-1">The stock may not be available on yfinance.</p>
        </div>
      </div>
    );
  }

  const f = data.fundamentals;
  const fin = data.financials;
  const rec = data.recommendations;
  const lv = data.invest_levels;
  const lq = data.live_quote;
  const murphy = murphyData?.analysis ?? null;
  const scalp = scalpData?.signal ?? null;
  const vp = vpData ?? null;
  const candlesData = candles ?? null;
  const mf = multifactor ?? null;

  const currentPrice = lq?.price ?? lv.last_price;
  const changePct = lq?.change_pct;
  const priceColor = changePct != null ? (changePct >= 0 ? "text-emerald-400" : "text-rose-400") : "text-slate-100";

  // Determine outlook verdicts
  const shortVerdict = scalp?.side === "long" ? "BUY" : scalp?.side === "short" ? "SELL" : murphy?.verdict ?? "HOLD";
  const longVerdict = mf?.grade?.startsWith("A") ? "ACCUMULATE" : mf?.grade === "B" ? "BUY" : mf?.grade === "C" ? "HOLD" : mf?.grade === "D" ? "REDUCE" : "HOLD";
  const longTrend = lv.trend === "up" ? "uptrend" : "downtrend (below 200-EMA)";

  return (
    <div className="space-y-5 fade-in">
      {/* Back link */}
      <Link href="/" className="text-sky-400 text-sm hover:underline inline-flex items-center gap-1">
        <svg className="w-4 h-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
          <path d="M19 12H5M12 19l-7-7 7-7" />
        </svg>
        back to dashboard
      </Link>

      {/* Header with live price */}
      <div className="glass-card p-5">
        <div className="flex items-start justify-between flex-wrap gap-4">
          <div>
            <div className="flex items-center gap-3 flex-wrap">
              <h1 className="text-2xl font-bold text-slate-100">{f.company_name || symbol}</h1>
              <span className="text-xs text-slate-500">{symbol}</span>
              {f.sector && <span className="text-xs bg-slate-800 px-2 py-0.5 rounded text-slate-400">{f.sector}</span>}
            </div>
            {f.industry && <p className="text-xs text-slate-500 mt-1">{f.industry}</p>}
            {data.intraday_pick && (
              <Link href={`/picks/${symbol}`} className="text-xs text-emerald-400 hover:underline mt-1 inline-block">
                In today&apos;s intraday picks →
              </Link>
            )}
          </div>
          <div className="text-right">
            <div className="flex items-center gap-3 justify-end">
              <span className="text-3xl font-bold tabular-nums text-slate-100">
                ₹{currentPrice.toFixed(2)}
              </span>
              <span className="inline-flex items-center gap-1 text-[10px] font-semibold text-emerald-400">
                <span className="inline-block w-1.5 h-1.5 rounded-full bg-emerald-400 animate-pulse" />
                LIVE
              </span>
            </div>
            {changePct != null && (
              <div className={`text-sm font-medium tabular-nums ${priceColor}`}>
                {changePct >= 0 ? "▲" : "▼"} {Math.abs(changePct).toFixed(2)}%
                {lq?.change != null && (
                  <span className="text-slate-500 ml-1">({lq.change >= 0 ? "+" : ""}{lq.change.toFixed(2)})</span>
                )}
              </div>
            )}
            {lq && (lq.day_high || lq.day_low) && (
              <div className="flex items-center gap-3 mt-1 text-xs text-slate-500 justify-end">
                {lq.day_high && <span>H: <span className="text-slate-400 tabular-nums">₹{lq.day_high.toFixed(2)}</span></span>}
                {lq.day_low && <span>L: <span className="text-slate-400 tabular-nums">₹{lq.day_low.toFixed(2)}</span></span>}
                {lq.prev_close && <span>Prev: <span className="text-slate-400 tabular-nums">₹{lq.prev_close.toFixed(2)}</span></span>}
              </div>
            )}
          </div>
        </div>
      </div>

      {/* Key metrics grid */}
      <div className="glass-card p-5">
        <h2 className="section-title mb-3">Key Metrics</h2>
        <div className="grid grid-cols-2 sm:grid-cols-4 lg:grid-cols-6 gap-3">
          <Metric label="P/E (trailing)" value={fmtNum(f.trailing_pe)} />
          <Metric label="P/E (forward)" value={fmtNum(f.forward_pe)} />
          <Metric label="Market Cap" value={fmtCr(f.market_cap)} />
          <Metric label="Revenue" value={fmtCr(f.total_revenue)} />
          <Metric label="Total Debt" value={fmtCr(f.total_debt)} />
          <Metric label="Cash" value={fmtCr(f.total_cash)} />
          <Metric label="Debt/Equity" value={fmtNum(f.debt_to_equity)} />
          <Metric label="Profit Margin" value={fmtPct(f.profit_margins)} />
          <Metric label="Op. Margin" value={fmtPct(f.operating_margins)} />
          <Metric label="ROE" value={fmtPct(f.return_on_equity)} />
          <Metric label="Div Yield" value={fmtPct(f.dividend_yield)} />
          <Metric label="Beta" value={fmtNum(f.beta, 3)} />
          <Metric label="52W Low" value={f["52w_low"] != null ? `₹${f["52w_low"]}` : "—"} />
          <Metric label="52W High" value={f["52w_high"] != null ? `₹${f["52w_high"]}` : "—"} />
          <Metric label="EPS" value={fmtNum(typeof f.earnings_per_share === "number" ? f.earnings_per_share : null)} />
          <Metric label="Employees" value={f.employees?.toLocaleString() || "—"} />
        </div>
      </div>

      {/* Short-term and Long-term outlook */}
      <div className="grid gap-5 lg:grid-cols-2">
        {/* Short-term outlook (Intraday / Swing) */}
        <OutlookCard
          title="Short-Term Outlook"
          timeframe="Intraday / Swing (1-5 days)"
          verdict={shortVerdict}
          entry={scalp?.entry ?? murphy?.entry}
          stopLoss={scalp?.stop_loss ?? murphy?.stop_loss}
          target1={murphy?.target1 ?? scalp?.target}
          target2={murphy?.target2}
          riskReward={scalp?.risk_reward ?? murphy?.risk_reward}
          what={
            scalp
              ? `Scalping signal: ${scalp.side.toUpperCase()} bias with ${Math.round(scalp.confidence * 100)}% confidence. Entry at ₹${scalp.entry.toFixed(2)}, target ₹${scalp.target.toFixed(2)}.`
              : murphy
              ? `Murphy multi-indicator composite score: ${murphy.composite_score}/100. Verdict: ${murphy.verdict.replace(/_/g, " ")}.`
              : "No short-term signal available for this stock."
          }
          why={
            murphy
              ? `Trend: ${murphy.trend_direction} (EMA: ${murphy.ema_alignment}, ADX: ${murphy.adx_value.toFixed(0)} — ${murphy.adx_strength}). Momentum: RSI ${murphy.rsi_value.toFixed(0)} (${murphy.rsi_signal}), MACD ${murphy.macd_histogram >= 0 ? "positive" : "negative"}, Stochastic ${murphy.stochastic_k.toFixed(0)}. Volume: ${murphy.volume_ratio.toFixed(1)}x avg, OBV ${murphy.obv_trend}.`
              : scalp
              ? scalp.explanation
              : "Insufficient data for short-term analysis."
          }
          when={
            scalp
              ? `Active during current market session. Valid for intraday only — exit by close if target not hit.`
              : `Based on daily candlestick analysis. Entry valid for 1-3 trading sessions. Review after each close.`
          }
          factors={murphy ? [
            { label: "trend", value: murphy.trend_score, max: 30 },
            { label: "momentum", value: murphy.momentum_score, max: 30 },
            { label: "volume", value: murphy.volume_score, max: 20 },
            { label: "support_resistance", value: murphy.factors.support_resistance, max: 20 },
          ] : undefined}
        />

        {/* Long-term outlook (Investment) */}
        <OutlookCard
          title="Long-Term Outlook"
          timeframe="Investment (weeks / months)"
          verdict={longVerdict}
          entry={lv.entry}
          stopLoss={lv.stop_loss}
          target1={lv.target}
          riskReward={lv.risk_reward}
          what={
            `${f.company_name || symbol} is in a ${longTrend}. ` +
            `Investment entry zone at ₹${lv.entry.toFixed(2)} (${lv.entry_label}). ` +
            `Target: ₹${lv.target.toFixed(2)} (${lv.target_label}).`
          }
          why={
            `Multi-factor grade: ${mf?.grade ?? "—"} (composite ${mf ? Math.round(mf.composite * 100) : "—"}%). ` +
            `${mf ? `Momentum ${Math.round(mf.momentum * 100)}%, Quality ${Math.round(mf.quality * 100)}%, Value ${Math.round(mf.value * 100)}%. ` : ""}` +
            `Fundamentals: P/E ${fmtNum(f.trailing_pe)}, ROE ${fmtPct(f.return_on_equity)}, ` +
            `Debt/Equity ${fmtNum(f.debt_to_equity)}, Margin ${fmtPct(f.profit_margins)}. ` +
            `Analyst consensus: ${rec.consensus}.`
          }
          when={
            `Entry valid while price is near ₹${lv.entry.toFixed(2)} (50-EMA in ${longTrend}). ` +
            `Stop-loss at ₹${lv.stop_loss.toFixed(2)}. Hold for weeks to months. ` +
            `Review at each quarterly earnings release.`
          }
        />
      </div>

      {/* Murphy explanation */}
      {murphy && (
        <div className="glass-card p-5">
          <h2 className="section-title mb-2">Murphy Analysis Summary</h2>
          <p className="text-sm text-slate-300 mb-2">{murphy.explanation}</p>
          {murphy.caveats.length > 0 && (
            <ul className="text-xs text-amber-300/70 list-disc list-inside space-y-0.5">
              {murphy.caveats.map((c, i) => <li key={i}>{c}</li>)}
            </ul>
          )}
        </div>
      )}

      {/* Invest levels explanation */}
      <div className="glass-card p-5 border-emerald-800/30">
        <h2 className="text-sm font-semibold text-emerald-400 mb-3">Investment Entry / Stop-Loss / Target</h2>
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 mb-3">
          <Metric label="Entry Zone" value={`₹${lv.entry}`} color="text-sky-300" />
          <Metric label="Stop-Loss" value={`₹${lv.stop_loss}`} color="text-rose-300" />
          <Metric label="Target" value={`₹${lv.target}`} color="text-emerald-300" />
          <Metric label="Risk:Reward" value={`1:${lv.risk_reward}`} color="text-amber-300" />
        </div>
        <div className="grid grid-cols-3 gap-3 mb-3">
          <Metric label="EMA-50" value={`₹${lv.ema50}`} />
          <Metric label="EMA-200" value={`₹${lv.ema200}`} />
          <Metric label="ATR(14)" value={`₹${lv.atr14}`} />
        </div>
        <p className="text-xs text-slate-300">{lv.explanation}</p>
        {lv.caveats.length > 0 && (
          <ul className="mt-2 text-xs text-amber-300/70 list-disc list-inside space-y-0.5">
            {lv.caveats.map((c, i) => <li key={i}>{c}</li>)}
          </ul>
        )}
      </div>

      {/* Technical indicators (from Murphy) */}
      {murphy && <TechnicalCard murphy={murphy} />}

      {/* Volume profile */}
      {vp && <VolumeProfileCard vp={vp} />}

      {/* Multi-factor score */}
      {mf && (
        <div className="glass-card p-5">
          <h2 className="section-title mb-3">Multi-Factor Score</h2>
          <div className="flex items-center gap-3 mb-3">
            <span className={`text-2xl font-bold ${
              mf.grade.startsWith("A") ? "text-emerald-400" :
              mf.grade === "B" ? "text-sky-400" :
              mf.grade === "C" ? "text-amber-400" : "text-rose-400"
            }`}>{mf.grade}</span>
            <div className="flex-1">
              <div className="h-2.5 bg-slate-800 rounded-full overflow-hidden">
                <div className="h-full rounded-full bg-gradient-to-r from-emerald-500 to-teal-400" style={{ width: `${Math.round(mf.composite * 100)}%` }} />
              </div>
              <span className="text-xs text-slate-500 mt-1 block tabular-nums">Composite {Math.round(mf.composite * 100)}%</span>
            </div>
          </div>
          <div className="grid grid-cols-3 gap-3 mb-2">
            <FactorBar label="Momentum" value={mf.momentum} weight={mf.weights.momentum} />
            <FactorBar label="Quality" value={mf.quality} weight={mf.weights.quality} />
            <FactorBar label="Value" value={mf.value} weight={mf.weights.value} />
          </div>
          <p className="text-xs text-slate-400 leading-relaxed">{mf.summary}</p>
        </div>
      )}

      {/* Candlestick patterns */}
      {candlesData && candlesData.patterns.length > 0 && (
        <div className="glass-card p-5">
          <h2 className="section-title mb-3">
            Candlestick Patterns{" "}
            <span className={`text-xs ${
              candlesData.net_bias === "bullish" ? "text-emerald-400" :
              candlesData.net_bias === "bearish" ? "text-rose-400" : "text-slate-500"
            }`}>
              net: {candlesData.net_bias}
            </span>
          </h2>
          <div className="space-y-2">
            {candlesData.patterns.map((p, i) => (
              <div key={i} className="flex items-start gap-2">
                <span className={`text-[10px] font-medium rounded border px-1.5 py-0.5 shrink-0 ${
                  p.bias === "bullish" ? "bg-emerald-500/15 text-emerald-400 border-emerald-500/30" :
                  p.bias === "bearish" ? "bg-rose-500/15 text-rose-400 border-rose-500/30" :
                  "bg-slate-700/40 text-slate-400 border-slate-600/30"
                }`}>
                  {p.strength}
                </span>
                <div className="min-w-0">
                  <span className="text-sm font-medium text-slate-200">{p.name}</span>
                  <p className="text-xs text-slate-400 leading-relaxed">{p.description}</p>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Analyst recommendations */}
      {rec.periods.length > 0 && (
        <div className="glass-card p-5">
          <h2 className="section-title mb-3">
            Analyst Recommendations —{" "}
            <span className={
              rec.consensus === "BUY" || rec.consensus === "ACCUMULATE" ? "text-emerald-400" :
              rec.consensus === "SELL" || rec.consensus === "REDUCE" ? "text-rose-400" :
              "text-amber-300"
            }>
              {rec.consensus}
            </span>
          </h2>
          {rec.periods.map((p, i) => (
            <div key={i} className="mb-3">
              <div className="text-xs text-slate-500 mb-1">{p.period} ({p.total} analysts)</div>
              <div className="flex h-6 rounded-lg overflow-hidden text-xs">
                <div className="bg-emerald-600 flex items-center justify-center" style={{ width: `${(p.strong_buy / p.total) * 100}%` }}>{p.strong_buy > 0 ? p.strong_buy : ""}</div>
                <div className="bg-emerald-500/60 flex items-center justify-center" style={{ width: `${(p.buy / p.total) * 100}%` }}>{p.buy > 0 ? p.buy : ""}</div>
                <div className="bg-amber-500/60 flex items-center justify-center" style={{ width: `${(p.hold / p.total) * 100}%` }}>{p.hold > 0 ? p.hold : ""}</div>
                <div className="bg-rose-500/60 flex items-center justify-center" style={{ width: `${(p.sell / p.total) * 100}%` }}>{p.sell > 0 ? p.sell : ""}</div>
                <div className="bg-rose-600 flex items-center justify-center" style={{ width: `${(p.strong_sell / p.total) * 100}%` }}>{p.strong_sell > 0 ? p.strong_sell : ""}</div>
              </div>
            </div>
          ))}
          <div className="flex gap-3 text-xs text-slate-500 flex-wrap">
            <span><span className="inline-block w-2 h-2 bg-emerald-600 rounded mr-1" />Strong Buy</span>
            <span><span className="inline-block w-2 h-2 bg-emerald-500/60 rounded mr-1" />Buy</span>
            <span><span className="inline-block w-2 h-2 bg-amber-500/60 rounded mr-1" />Hold</span>
            <span><span className="inline-block w-2 h-2 bg-rose-500/60 rounded mr-1" />Sell</span>
            <span><span className="inline-block w-2 h-2 bg-rose-600 rounded mr-1" />Strong Sell</span>
          </div>
        </div>
      )}

      {/* Financials table */}
      {Object.keys(fin.income_statement).length > 0 && (
        <div className="glass-card p-5">
          <h2 className="section-title mb-3">Financials (Annual)</h2>
          <div className="overflow-x-auto">
            <table className="w-full text-xs">
              <thead className="text-slate-500">
                <tr className="border-b border-slate-800">
                  <th className="px-2 py-1.5 text-left">Metric</th>
                  {Object.keys(fin.income_statement).reverse().map(y => <th key={y} className="px-2 py-1.5 text-right">{y}</th>)}
                </tr>
              </thead>
              <tbody>
                {renderFinRows(fin.income_statement, [
                  ["revenue", "Revenue"],
                  ["gross_profit", "Gross Profit"],
                  ["operating_income", "Operating Income"],
                  ["net_income", "Net Income"],
                  ["ebitda", "EBITDA"],
                  ["eps", "EPS"],
                ])}
              </tbody>
            </table>
          </div>
          {Object.keys(fin.balance_sheet).length > 0 && (
            <>
              <h3 className="text-xs text-slate-500 mt-4 mb-2">Balance Sheet</h3>
              <div className="overflow-x-auto">
                <table className="w-full text-xs">
                  <thead className="text-slate-500">
                    <tr className="border-b border-slate-800">
                      <th className="px-2 py-1.5 text-left">Metric</th>
                      {Object.keys(fin.balance_sheet).reverse().map(y => <th key={y} className="px-2 py-1.5 text-right">{y}</th>)}
                    </tr>
                  </thead>
                  <tbody>
                    {renderFinRows(fin.balance_sheet, [
                      ["total_assets", "Total Assets"],
                      ["total_debt", "Total Debt"],
                      ["total_cash", "Cash"],
                      ["stockholders_equity", "Equity"],
                      ["retained_earnings", "Retained Earnings"],
                      ["net_debt", "Net Debt"],
                    ])}
                  </tbody>
                </table>
              </div>
            </>
          )}
        </div>
      )}

      {/* Company description */}
      {f.description && (
        <div className="glass-card p-5">
          <h2 className="section-title mb-2">About {f.company_name || symbol}</h2>
          <p className="text-xs text-slate-400 leading-relaxed">{f.description}</p>
          {f.website && (
            <a href={f.website} target="_blank" rel="noreferrer" className="text-xs text-sky-400 hover:underline mt-2 inline-block">
              {f.website}
            </a>
          )}
        </div>
      )}

      {/* Disclaimer */}
      <div className="glass-card p-4">
        <p className="text-xs text-slate-600">
          Data via yfinance (delayed ~15 min). Technical analysis uses daily candlesticks and standard indicators (RSI, MACD, Stochastic, ADX, Bollinger, Fibonacci).
          Short-term outlook is for intraday/swing trading. Long-term outlook is for investment (weeks/months).
          Not investment advice. Always do your own research before trading.
        </p>
      </div>
    </div>
  );
}
