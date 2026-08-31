// Types mirror the backend pydantic models (app/models.py).

export type Side = "long" | "short";
export type PickStatus = "active" | "hit-target1" | "stopped-out" | "expired";

// ---------------------------------------------------------------------------
// Auth types
// ---------------------------------------------------------------------------

export interface User {
  id: number;
  name: string;
  email: string;
  capital: number;
  is_guest: boolean;
  created_at: string | null;
}

export interface TokenResponse {
  token: string;
  user: User;
}

// The browser calls /api/* on its own origin. A server-side route handler
// (app/api/[...path]/route.ts) proxies to the backend, forwarding the JWT
// from localStorage in the Authorization header.
export function getToken(): string | null {
  if (typeof window === "undefined") return null;
  return localStorage.getItem("token");
}

export function setToken(token: string, user: User) {
  if (typeof window === "undefined") return;
  localStorage.setItem("token", token);
  localStorage.setItem("user", JSON.stringify(user));
  window.dispatchEvent(new Event("auth-change"));
}

export function clearToken() {
  if (typeof window === "undefined") return;
  localStorage.removeItem("token");
  localStorage.removeItem("user");
  window.dispatchEvent(new Event("auth-change"));
}

export function getStoredUser(): User | null {
  if (typeof window === "undefined") return null;
  const raw = localStorage.getItem("user");
  if (!raw) return null;
  try {
    return JSON.parse(raw) as User;
  } catch {
    return null;
  }
}

/** Error thrown by apiFetch when the server returns a non-OK status.
 *  Includes the HTTP status code so callers can distinguish 401 (token
 *  invalid — log out) from 500/network errors (transient — keep session). */
export class ApiError extends Error {
  status: number;
  constructor(message: string, status: number) {
    super(message);
    this.name = "ApiError";
    this.status = status;
  }
}

async function apiFetch<T>(path: string, init?: RequestInit): Promise<T> {
  const token = getToken();
  const res = await fetch(path, {
    ...init,
    headers: {
      "Content-Type": "application/json",
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
      ...(init?.headers || {}),
    },
  });
  if (!res.ok) {
    const text = await res.text().catch(() => res.statusText);
    let message = text;
    try {
      const json = JSON.parse(text);
      message = json.detail || json.error || text;
    } catch {
      // not JSON, use raw text
    }
    throw new ApiError(message, res.status);
  }
  return res.json() as Promise<T>;
}

// ---------------------------------------------------------------------------
// Auth API functions
// ---------------------------------------------------------------------------

export async function registerUser(name: string, email: string, password: string, capital: number): Promise<TokenResponse> {
  const res = await apiFetch<TokenResponse>("/api/auth/register", {
    method: "POST",
    body: JSON.stringify({ name, email, password, capital }),
  });
  setToken(res.token, res.user);
  return res;
}

export async function loginUser(email: string, password: string): Promise<TokenResponse> {
  const res = await apiFetch<TokenResponse>("/api/auth/login", {
    method: "POST",
    body: JSON.stringify({ email, password }),
  });
  setToken(res.token, res.user);
  return res;
}

export async function fetchMe(): Promise<User> {
  return apiFetch<User>("/api/auth/me");
}

export async function guestLogin(): Promise<TokenResponse> {
  const res = await apiFetch<TokenResponse>("/api/auth/guest", { method: "POST" });
  setToken(res.token, res.user);
  return res;
}

export function logout() {
  clearToken();
}

export interface FormulaStep {
  label: string;
  formula: string;
  substituted: string;
  result: number;
}

export interface Explanation {
  summary: string;
  inputs: Record<string, number | string>;
  formula_trace: FormulaStep[];
  verification: string[];
  caveats: string[];
}

export interface Pick {
  date: string;
  symbol: string;
  side: Side;
  entry: number;
  stop_loss: number;
  target1: number;
  target2: number;
  confidence: number;
  last_price: number;
  name: string;
  expiry_day: boolean;
  status: PickStatus;
  explanation: Explanation;
}

export interface DayStatus {
  date: string;
  market_open: boolean;
  no_trade: boolean;
  reason: string | null;
  expiry_day: boolean;
  picks_count: number;
}

export const fetchPicks = () => apiFetch<Pick[]>("/api/picks/today");
export const fetchPick = (symbol: string) => apiFetch<Pick>(`/api/picks/${symbol}`);
export const fetchDayStatus = () => apiFetch<DayStatus>("/api/day/status");
export const triggerScan = () => apiFetch<Pick[]>("/api/picks/scan", { method: "POST" });

// Commodities
export interface CommodityPick {
  name: string;
  symbol: string;
  side: "long" | "short" | null;
  entry: number | null;
  stop_loss: number | null;
  target1: number | null;
  target2: number | null;
  confidence: number;
  atr: number;
  pdh: number;
  pdl: number;
  explanation: Explanation;
}
export const fetchCommodities = () => apiFetch<CommodityPick[]>("/api/commodities/today");

// Day events
export interface DayEvents {
  date: string;
  events_today: string[];
  known_recurring: string[];
}
export const fetchDayEvents = () => apiFetch<DayEvents>("/api/day/events");

// ETF screener
export interface EtfScreen {
  symbol: string;
  name: string;
  category: string;
  horizon_hint: string;
  last_price: number;
  prev_close?: number | null;
  change_pct?: number | null;
  volatility: number;
  cagr: number;
  max_drawdown: number;
  sharpe: number;
  suggested_horizon: string;
  risk_level: "low" | "moderate" | "high" | "unknown";
  risks: string[];
  verdict: string;
  amc_name?: string;
  expense_ratio_est?: number;
  expense_ratio_range?: string;
  expense_ratio_note?: string;
  entry?: number;
  stop_loss?: number;
  target?: number;
  risk_reward?: number;
  trend?: string;
  ema50?: number;
  ema200?: number;
  atr14?: number;
  high_52w?: number;
  low_52w?: number;
  invest_explanation?: string;
  invest_caveats?: string[];
}
export const fetchEtfScreen = () => apiFetch<EtfScreen[]>("/api/etf/screener");

// US market
export interface UsStockSuggestion {
  symbol: string;
  name: string;
}
export interface UsStockSearchResult {
  symbol: string;
  found: boolean;
  message: string;
  quote: {
    price: number;
    prev_close: number | null;
    day_high: number | null;
    day_low: number | null;
    volume: number | null;
  } | null;
  pick: Pick | null;
  fundamentals?: {
    company_name: string | null;
    sector: string | null;
    industry: string | null;
    trailing_pe: number | null;
    forward_pe: number | null;
    market_cap: number | null;
    description: string | null;
  } | null;
}
export const fetchUsEtfScreen = () => apiFetch<EtfScreen[]>("/api/us-etf/screener");
export const fetchUsStockList = () =>
  apiFetch<{ stocks: UsStockSuggestion[] }>("/api/us-stock/list");

export interface UsStockScreen {
  symbol: string;
  name: string;
  sector: string | null;
  last_price: number;
  prev_close: number | null;
  change_pct: number | null;
  cagr: number;
  volatility: number;
  max_drawdown: number;
  sharpe: number;
  composite: number;
  grade: string;
  momentum: number;
  value: number;
  quality: number;
  trailing_pe: number | null;
  forward_pe: number | null;
  market_cap: number | null;
  return_on_equity: number | null;
  debt_to_equity: number | null;
  profit_margins: number | null;
  dividend_yield: number | null;
  rs_score: number;
  beta: number;
  trend: string;
  entry: number;
  stop_loss: number;
  target: number;
  risk_reward: number;
  summary: string;
}
export interface ScreenResponse<T> {
  stocks: T[];
  refreshed_at: string;
  market_open: boolean;
  market_status: string;
}
export const fetchUsStockScreen = () => apiFetch<ScreenResponse<UsStockScreen>>("/api/us-stock/screen");
export const refreshUsStockScreen = () =>
  apiFetch<{ ok: boolean }>("/api/us-stock/screen/refresh", { method: "POST" });
export const fetchUsEtfDetail = (symbol: string) =>
  apiFetch<EtfDetail>(`/api/us-etf/${symbol}/details`);
export const fetchUsStockDetail = (symbol: string) =>
  apiFetch<StockDetail>(`/api/us-stock/${symbol}/details`);
export const fetchUsStockSuggest = (q: string) =>
  apiFetch<{ results: UsStockSuggestion[] }>(`/api/us-stock/search/suggest?q=${encodeURIComponent(q)}`);
export const fetchUsStockSearch = (q: string) =>
  apiFetch<UsStockSearchResult>(`/api/us-stock/search?q=${encodeURIComponent(q)}`);

// Mutual fund screener
export interface MfScreen {
  code: string;
  name: string;
  category: string;
  horizon_hint: string;
  last_nav: number;
  volatility: number;
  cagr: number;
  max_drawdown: number;
  sharpe: number;
  suggested_horizon: string;
  risk_level: "low" | "moderate" | "high" | "unknown";
  risks: string[];
  verdict: string;
}
export const fetchMfScreen = () => apiFetch<MfScreen[]>("/api/mf/screener");

// Holdings review
export interface Holding {
  symbol: string;
  quantity: number;
  avg_price: number;
  current_price: number;
  product: string;
  pnl: number;
}
export interface HoldingReview {
  symbol: string;
  quantity: number;
  avg_price: number;
  current_price: number;
  pnl: number;
  pnl_pct: number;
  trend: string;
  ema20: number;
  ema50: number;
  atr: number;
  drawdown_from_peak: number;
  verdict: "hold" | "review" | "caution" | "wrong-pick";
  rationale: string;
  actions: string[];
}
export interface BrokerStatus {
  broker: string;
  connected: boolean;
  message: string;
}
export const fetchHoldings = () => apiFetch<Holding[]>("/api/holdings");
export const fetchHoldingsReview = () => apiFetch<HoldingReview[]>("/api/holdings/review");

// Live NSE market status (directly from nseindia.com)
export interface MarketIndex {
  name: string;
  last: number;
  change: number;
  pct_change: number;
}
export interface MarketLive {
  status: {
    market_open: boolean;
    status_text: string;
    trade_date: string;
    nifty_last: number;
    nifty_change: number;
    nifty_pct_change: number;
    source: string;
  };
  indices: MarketIndex[];
}
export const fetchMarketLive = () => apiFetch<MarketLive>("/api/market/live");

// Stock search
export interface StockSuggestion {
  symbol: string;
  name: string;
}
export interface StockSearchResult {
  symbol: string;
  found: boolean;
  message: string;
  quote: {
    price: number;
    prev_close: number | null;
    day_high: number | null;
    day_low: number | null;
    volume: number | null;
  } | null;
  pick: Pick | null;
  fundamentals?: {
    company_name: string | null;
    sector: string | null;
    industry: string | null;
    trailing_pe: number | null;
    forward_pe: number | null;
    market_cap: number | null;
    description: string | null;
  } | null;
}
export const searchStockSuggest = (q: string) =>
  apiFetch<{ results: StockSuggestion[] }>(`/api/search/suggest?q=${encodeURIComponent(q)}`);
export const searchStock = (q: string) =>
  apiFetch<StockSearchResult>(`/api/search?q=${encodeURIComponent(q)}`);

// Candlestick patterns
export interface CandlestickPattern {
  name: string;
  bias: "bullish" | "bearish" | "neutral";
  strength: "weak" | "moderate" | "strong";
  bar_index: number;
  description: string;
}
export interface CandlestickResult {
  symbol: string;
  patterns: CandlestickPattern[];
  net_bias: "bullish" | "bearish" | "neutral";
  bars_scanned: number;
  message?: string;
}
export const fetchCandlestick = (symbol: string) =>
  apiFetch<CandlestickResult>(`/api/stock/${symbol}/candlestick`);

// Multi-factor score
export interface MultiFactorScore {
  symbol: string;
  momentum: number;
  value: number;
  quality: number;
  composite: number;
  grade: string;
  weights: Record<string, number>;
  summary: string;
}
export const fetchMultiFactor = (symbol: string) =>
  apiFetch<MultiFactorScore>(`/api/stock/${symbol}/multifactor`);

// Scalping signals
export interface ScalpPattern {
  name: string;
  bias: "bullish" | "bearish" | "neutral";
  strength: "weak" | "moderate" | "strong";
  description: string;
}
export interface ScalpSignal {
  symbol: string;
  side: "long" | "short";
  entry: number;
  stop_loss: number;
  target: number;
  risk_reward: number;
  confidence: number;
  last_price: number;
  atr: number;
  volume_ratio: number;
  trend: string;
  patterns: ScalpPattern[];
  pattern_bias: string;
  explanation: string;
  caveats: string[];
  // Murphy confirmation indicators (enhanced scalping).
  stochastic_k?: number;
  stochastic_signal?: string;
  macd_histogram?: number;
  adx_value?: number;
}
export interface ScalpingResponse {
  signals: ScalpSignal[];
  count: number;
}
export const fetchScalping = () => apiFetch<ScalpingResponse>("/api/scalping");
export const fetchScalpSignal = (symbol: string) =>
  apiFetch<{ symbol: string; signal: ScalpSignal | null; message?: string }>(`/api/scalping/${symbol}`);

// Advanced strategies (VWAP pullback, Bollinger squeeze, PPO momentum)
export interface StrategySignal {
  symbol: string;
  side: "long" | "short";
  entry: number;
  stop_loss: number;
  target?: number;
  target1?: number;
  target2?: number;
  risk_reward: number;
  confidence: number;
  last_price: number;
  trend: string;
  volume_ratio: number;
  explanation: string;
  caveats: string[];
  glossary?: Record<string, string>;
  // VWAP-specific
  vwap?: number;
  ema9?: number;
  ema21?: number;
  pullback_low?: number;
  // Bollinger-specific
  upper_band?: number;
  lower_band?: number;
  middle_band?: number;
  bandwidth?: number;
  squeeze_pct?: number;
  // PPO-specific
  ppo_value?: number;
  signal_value?: number;
  histogram?: number;
  swing_extreme?: number;
  // Scalp-specific
  atr?: number;
  patterns?: ScalpPattern[];
  pattern_bias?: string;
}
export interface StrategyResponse {
  signals: StrategySignal[];
  count: number;
  glossary?: Record<string, string>;
}
export const fetchVwapSignals = () => apiFetch<StrategyResponse>("/api/strategies/vwap");
export const fetchBollingerSignals = () => apiFetch<StrategyResponse>("/api/strategies/bollinger");
export const fetchPpoSignals = () => apiFetch<StrategyResponse>("/api/strategies/ppo");
export const fetchMaTrendSignals = () => apiFetch<StrategyResponse>("/api/strategies/ma-trend");
export const fetchGapAndGoSignals = () => apiFetch<StrategyResponse>("/api/strategies/gap-and-go");
export const fetchSrReversalSignals = () => apiFetch<StrategyResponse>("/api/strategies/sr-reversal");
export const fetchMomentumBreakoutSignals = () => apiFetch<StrategyResponse>("/api/strategies/momentum-breakout");
export const fetchAbcdSignals = () => apiFetch<StrategyResponse>("/api/strategies/abcd");
export const fetchAllStrategies = (symbol: string) =>
  apiFetch<{ symbol: string; signals: Record<string, StrategySignal | null> }>(`/api/strategies/all/${symbol}`);

// Glossary
export const fetchGlossary = () =>
  apiFetch<{ terms: Record<string, string>; count: number }>("/api/strategies/glossary");

// Paper trading
export interface PaperTrade {
  id: number;
  date: string;
  symbol: string;
  market: string;
  strategy: string;
  side: string;
  entry: number;
  stop_loss: number;
  target: number;
  confidence: number;
  status: string;
  entry_time: string | null;
  exit_time: string | null;
  exit_price: number | null;
  pnl_pct: number | null;
  explanation: Record<string, unknown> | null;
  created_at: string | null;
}
export interface PaperTradeStats {
  total_signals: number;
  open: number;
  resolved: number;
  wins: number;
  losses: number;
  win_rate: number;
  avg_pnl_pct: number;
  total_pnl_pct: number;
  best_trade_pct: number | null;
  worst_trade_pct: number | null;
  by_strategy: Record<string, Record<string, number>>;
  capital: number;
  position_size: number;
  total_pnl_rupees: number;
  portfolio_value: number;
}
export const fetchPaperSignals = (strategy?: string, status?: string, market?: string) => {
  const params = new URLSearchParams();
  if (strategy) params.set("strategy", strategy);
  if (status) params.set("status", status);
  if (market) params.set("market", market);
  const qs = params.toString();
  return apiFetch<{ signals: PaperTrade[]; count: number }>(
    `/api/paper/signals${qs ? `?${qs}` : ""}`
  );
};
export const fetchPaperStats = (market?: string) =>
  apiFetch<PaperTradeStats>(`/api/paper/stats${market ? `?market=${market}` : ""}`);
export const resolvePaperSignal = (id: number, exitPrice: number, status: string) =>
  apiFetch<PaperTrade>(`/api/paper/resolve/${id}`, {
    method: "POST",
    body: JSON.stringify({ exit_price: exitPrice, status }),
  });
export const paperScan = (market: string = "nse") =>
  apiFetch<{ new_signals: number; resolved: number; resolve_details: any[]; signals: PaperTrade[] }>(
    `/api/paper/scan?market=${market}`, { method: "POST" }
  );
export const paperAutoResolve = () =>
  apiFetch<{ resolved: number; details: any[] }>("/api/paper/auto-resolve", { method: "POST" });
export const paperExpire = () =>
  apiFetch<{ expired: number; details: any[] }>("/api/paper/expire", { method: "POST" });
export interface PaperDayHistory {
  date: string;
  total_signals: number;
  open: number;
  resolved: number;
  wins: number;
  losses: number;
  win_rate: number;
  pnl_pct: number;
  avg_pnl_pct: number;
}
export const fetchPaperHistory = (market?: string) =>
  apiFetch<{ history: PaperDayHistory[]; count: number }>(`/api/paper/history${market ? `?market=${market}` : ""}`);

// Stock screener (NSE)
export interface NseStockScreen {
  symbol: string;
  name: string;
  sector: string | null;
  last_price: number;
  prev_close: number | null;
  change_pct: number | null;
  cagr: number;
  volatility: number;
  max_drawdown: number;
  sharpe: number;
  composite: number;
  grade: string;
  momentum: number;
  value: number;
  quality: number;
  trailing_pe: number | null;
  forward_pe: number | null;
  market_cap: number | null;
  return_on_equity: number | null;
  debt_to_equity: number | null;
  profit_margins: number | null;
  dividend_yield: number | null;
  rs_score: number;
  beta: number;
  trend: string;
  entry: number;
  stop_loss: number;
  target: number;
  risk_reward: number;
  summary: string;
}
export const fetchNseStockScreen = () => apiFetch<ScreenResponse<NseStockScreen>>("/api/stock/screen");
export const refreshNseStockScreen = () =>
  apiFetch<{ ok: boolean }>("/api/stock/screen/refresh", { method: "POST" });

// Stock detail page
export interface StockFundamentals {
  symbol: string;
  company_name: string | null;
  sector: string | null;
  industry: string | null;
  description: string | null;
  website: string | null;
  employees: number | null;
  trailing_pe: number | null;
  forward_pe: number | null;
  market_cap: number | null;
  enterprise_value: number | null;
  profit_margins: number | null;
  operating_margins: number | null;
  return_on_equity: number | null;
  total_revenue: number | null;
  total_debt: number | null;
  total_cash: number | null;
  debt_to_equity: number | null;
  dividend_yield: number | null;
  beta: number | null;
  "52w_high": number | null;
  "52w_low": number | null;
  [key: string]: number | string | null;
}

export interface Financials {
  income_statement: Record<string, Record<string, number | null>>;
  balance_sheet: Record<string, Record<string, number | null>>;
}

export interface Recommendations {
  periods: { period: string; strong_buy: number; buy: number; hold: number; sell: number; strong_sell: number; total: number }[];
  consensus: string;
}

export interface InvestLevels {
  symbol: string;
  last_price: number;
  entry: number;
  entry_label: string;
  stop_loss: number;
  stop_loss_label: string;
  target: number;
  target_label: string;
  risk_reward: number;
  trend: string;
  ema50: number;
  ema200: number;
  atr14: number;
  "52w_high": number;
  "52w_low": number;
  explanation: string;
  caveats: string[];
}

export interface LiveQuote {
  price: number;
  prev_close: number | null;
  change: number | null;
  change_pct: number | null;
  day_high: number | null;
  day_low: number | null;
  volume: number | null;
}

export interface StockDetail {
  symbol: string;
  fundamentals: StockFundamentals;
  financials: Financials;
  recommendations: Recommendations;
  invest_levels: InvestLevels;
  live_quote: LiveQuote | null;
  intraday_pick: Pick | null;
}
export const fetchStockDetail = (symbol: string) =>
  apiFetch<StockDetail>(`/api/stock/${symbol}/details`);

// ETF detail
export interface EtfDetail extends EtfScreen {
  amc_name?: string;
  expense_ratio_est?: number;
  expense_ratio_range?: string;
  expense_ratio_note?: string;
  entry?: number;
  stop_loss?: number;
  target?: number;
  risk_reward?: number;
  trend?: string;
  ema50?: number;
  ema200?: number;
  atr14?: number;
  high_52w?: number;
  low_52w?: number;
  invest_explanation?: string;
  invest_caveats?: string[];
  yf_fundamentals?: Record<string, number | null>;
}
export const fetchEtfDetail = (symbol: string) =>
  apiFetch<EtfDetail>(`/api/etf/${symbol}/details`);

// MF detail
export interface MfDetail extends MfScreen {
  fund_house?: string;
  scheme_type?: string;
  expense_ratio_est?: number;
  expense_ratio_note?: string;
  exit_load?: string;
  entry_strategy?: string;
  exit_strategy?: string;
}
export const fetchMfDetail = (code: string) =>
  apiFetch<MfDetail>(`/api/mf/${code}/details`);

// ---------------------------------------------------------------------------
// Sector rotation heatmap
// ---------------------------------------------------------------------------
export interface SectorRotation {
  symbol: string;
  name: string;
  market: "in" | "us";
  last_price: number;
  return_1d: number;
  return_1w: number;
  return_1m: number;
  return_3m: number;
  rsi: number;
  trend: "bullish" | "bearish" | "neutral";
  sharpe: number;
  rotation: "accelerating" | "strengthening" | "weakening" | "decelerating" | "bearish";
  momentum_score: number;
}

export interface SectorRotationResponse {
  nse: SectorRotation[];
  us: SectorRotation[];
  refreshed_at: string;
  nse_market: { market_open: boolean; market_status: string; exchange: string; timezone: string };
  us_market: { market_open: boolean; market_status: string; exchange: string; timezone: string };
}

export const fetchSectorRotation = () =>
  apiFetch<SectorRotationResponse>("/api/sector-rotation");
export const refreshSectorRotation = () =>
  apiFetch<{ invalidated: boolean }>("/api/sector-rotation/refresh", { method: "POST" });

// ---------------------------------------------------------------------------
// Institutional flow (FII/DII + US institutional holders)
// ---------------------------------------------------------------------------
export interface FiiDiiRow {
  category: string;
  buy_value: number;
  sell_value: number;
  net_value: number;
}

export interface InstitutionalHolder {
  holder: string;
  shares: number | null;
  value: number | null;
  pct_out: number | null;
  date_reported: string;
}

export interface InstitutionalData {
  symbol: string;
  institutional_pct: number | null;
  insider_pct: number | null;
  top_holders: InstitutionalHolder[];
}

export const fetchFiiDii = () =>
  apiFetch<FiiDiiRow[]>("/api/fii-dii/cash-flow");
export const fetchInstitutional = (symbol: string) =>
  apiFetch<InstitutionalData>(`/api/institutional/${encodeURIComponent(symbol)}`);

// ---------------------------------------------------------------------------
// Dividend calendar
// ---------------------------------------------------------------------------
export interface DividendData {
  symbol: string;
  dividend_yield: number | null;
  dividend_rate: number | null;
  payout_ratio: number | null;
  ex_dividend_date: string | null;
  next_dividend_date: string | null;
  dividend_history: { date: string; amount: number }[];
}

export const fetchNseDividends = () =>
  apiFetch<DividendData[]>("/api/dividends/nse");
export const fetchUsDividends = () =>
  apiFetch<DividendData[]>("/api/dividends/us");
export const fetchDividendDetail = (symbol: string) =>
  apiFetch<DividendData>(`/api/dividends/${encodeURIComponent(symbol)}`);

// ---------------------------------------------------------------------------
// SIP / STP calculator
// ---------------------------------------------------------------------------
export interface SipResult {
  symbol: string;
  amount: number;
  months: number;
  volatility: number;
  cagr: number;
  max_drawdown: number;
  regime: "low" | "moderate" | "high";
  recommendation: string;
  rationale: string;
  lump_sum_pct: number;
  sip_months: number;
  backtest: {
    lump_sum_pnl_pct: number;
    sip_pnl_pct: number;
    better: "lump_sum" | "sip";
    advantage_pct: number;
    period_months: number;
  };
  error?: string;
}

export const calculateSip = (symbol: string, amount: number, months: number) =>
  apiFetch<SipResult>("/api/sip/calculate", {
    method: "POST",
    body: JSON.stringify({ symbol, amount, months }),
  });

// ---------------------------------------------------------------------------
// Tax-loss harvesting
// ---------------------------------------------------------------------------
export interface TaxHarvestOpportunity {
  symbol: string;
  quantity: number;
  avg_price: number;
  current_price: number;
  unrealized_loss: number;
  loss_pct: number;
  estimated_tax_saving: number;
  replacement_symbol: string;
  wash_sale_period: string;
  action: string;
}

export interface TaxHarvestResult {
  total_holdings: number;
  losing_positions: number;
  gaining_positions: number;
  total_unrealized_losses: number;
  total_unrealized_gains: number;
  net_taxable_gain: number;
  offsettable_losses: number;
  estimated_tax_saving_from_offset: number;
  opportunities: TaxHarvestOpportunity[];
  summary: string;
}

export const fetchTaxHarvest = () =>
  apiFetch<TaxHarvestResult>("/api/tax-harvest");

// ---------------------------------------------------------------------------
// Correlation matrix
// ---------------------------------------------------------------------------
export interface CorrelationPair {
  a: string;
  b: string;
  correlation: number;
  warning: string;
}

export interface CorrelationResult {
  symbols: string[];
  matrix: (number | null)[][];
  high_correlation_pairs: CorrelationPair[];
}

export const fetchNseCorrelation = () =>
  apiFetch<CorrelationResult>("/api/correlation/nse");
export const fetchUsCorrelation = () =>
  apiFetch<CorrelationResult>("/api/correlation/us");

// ---------------------------------------------------------------------------
// Momentum rotation (Jegadeesh-Titman 12-1)
// ---------------------------------------------------------------------------

export interface MomentumRotationEntry {
  symbol: string;
  name: string;
  market: "in" | "us";
  type: "stock" | "etf";
  last_price: number;
  momentum_12_1: number;
  return_1m: number;
  return_3m: number;
  return_6m: number;
  return_12m: number;
  rsi: number;
  sharpe: number;
  volatility: number;
  trend: "bullish" | "bearish" | "neutral";
  signal: "bullish" | "overbought" | "recovering" | "bearish" | "weakening" | "neutral";
  tier: "Strong Buy" | "Accumulate" | "Hold" | "Reduce" | "Avoid";
  rank_percentile: number;
  rank: number;
}

export interface MomentumRotationResponse {
  nse: MomentumRotationEntry[];
  us: MomentumRotationEntry[];
  refreshed_at: string;
  nse_market: { market_open: boolean; market_status: string; exchange: string; timezone: string };
  us_market: { market_open: boolean; market_status: string; exchange: string; timezone: string };
}

export const fetchMomentumRotation = () =>
  apiFetch<MomentumRotationResponse>("/api/momentum-rotation");
export const refreshMomentumRotation = () =>
  apiFetch<{ invalidated: boolean }>("/api/momentum-rotation/refresh", { method: "POST" });

// ---------------------------------------------------------------------------
// Pre-market gap scanner
// ---------------------------------------------------------------------------

export interface GapScanEntry {
  symbol: string;
  name: string;
  market: "in" | "us";
  current_price: number;
  prev_close: number;
  prev_high: number;
  prev_low: number;
  gap_pct: number;
  gap_dir: "up" | "down" | "flat";
  magnitude: "extreme" | "large" | "moderate" | "small" | "none";
  volume_ratio: number;
  atr: number;
  expected_move_pct: number;
  gap_high: number;
  gap_low: number;
  play: "continuation_long" | "continuation_short" | "watch" | "none";
  strategy: string;
  currency: string;
}

export interface GapScanResponse {
  market: string;
  gaps: GapScanEntry[];
  gap_ups: GapScanEntry[];
  gap_downs: GapScanEntry[];
  total: number;
  refreshed_at: string;
  market_status: { market_open: boolean; market_status: string; exchange: string; timezone: string };
}

export const fetchGapScanner = (market: "nse" | "us", minGapPct: number = 0.5) =>
  apiFetch<GapScanResponse>(`/api/gap-scanner?market=${market}&min_gap_pct=${minGapPct}`);
export const refreshGapScanner = () =>
  apiFetch<{ invalidated: boolean }>("/api/gap-scanner/refresh", { method: "POST" });

// ---------------------------------------------------------------------------
// Volume Profile / POC
// ---------------------------------------------------------------------------

export interface VolumeProfileRow {
  price_low: number;
  price_high: number;
  price_mid: number;
  volume: number;
  pct: number;
  is_poc: boolean;
  in_value_area: boolean;
}

export interface VolumeProfileResponse {
  symbol: string;
  rows: VolumeProfileRow[];
  poc_price: number;
  vah: number;
  val: number;
  total_volume: number;
  hvn: number[];
  lvn: number[];
  current_price: number;
  vwap: number;
  prev_close: number;
  days: number;
}

export const fetchVolumeProfile = (symbol: string, days: number = 5, bins: number = 50) =>
  apiFetch<VolumeProfileResponse>(`/api/volume-profile/${symbol}?days=${days}&bins=${bins}`);

// ---------------------------------------------------------------------------
// VWAP premium/discount scanner
// ---------------------------------------------------------------------------

export interface VwapScanEntry {
  symbol: string;
  name: string;
  market: "in" | "us";
  current_price: number;
  vwap: number;
  deviation_pct: number;
  deviation_dir: "premium" | "discount" | "neutral";
  rsi: number;
  volume_ratio: number;
  day_high: number;
  day_low: number;
  day_range_pct: number;
  range_position: number;
  signal: string;
  action: string;
  currency: string;
}

export interface VwapScanResponse {
  market: string;
  results: VwapScanEntry[];
  premiums: VwapScanEntry[];
  discounts: VwapScanEntry[];
  total: number;
  refreshed_at: string;
  market_status: { market_open: boolean; market_status: string; exchange: string; timezone: string };
}

export const fetchVwapScanner = (market: "nse" | "us", minDeviation: number = 0.5) =>
  apiFetch<VwapScanResponse>(`/api/vwap-scanner?market=${market}&min_deviation=${minDeviation}`);
export const refreshVwapScanner = () =>
  apiFetch<{ invalidated: boolean }>("/api/vwap-scanner/refresh", { method: "POST" });

// ---------------------------------------------------------------------------
// Opening Range Breakout scanner (OR-5 / OR-15 / OR-30)
// ---------------------------------------------------------------------------

export interface ORScanEntry {
  symbol: string;
  name: string;
  market: "in" | "us";
  or_minutes: number;
  or_high: number;
  or_low: number;
  or_range_pct: number;
  side: "long" | "short";
  entry: number;
  stop_loss: number;
  target1: number;
  target2: number;
  risk_reward: number;
  current_price: number;
  breakout_time: string;
  breakout_price: number;
  volume_ratio: number;
  atr: number;
  trend_up: boolean;
  confidence: number;
  currency: string;
}

export interface ORScanResponse {
  market: string;
  or_minutes: number;
  signals: ORScanEntry[];
  longs: ORScanEntry[];
  shorts: ORScanEntry[];
  total: number;
  refreshed_at: string;
  market_status: { market_open: boolean; market_status: string; exchange: string; timezone: string };
}

export const fetchORScanner = (market: "nse" | "us", orMinutes: number = 15) =>
  apiFetch<ORScanResponse>(`/api/or-scanner?market=${market}&or_minutes=${orMinutes}`);
export const refreshORScanner = () =>
  apiFetch<{ invalidated: boolean }>("/api/or-scanner/refresh", { method: "POST" });

// ---------------------------------------------------------------------------
// Options OI support/resistance
// ---------------------------------------------------------------------------

export interface OILevel {
  strike: number;
  call_oi?: number;
  put_oi?: number;
  type: string;
}

export interface OIProfileRow {
  strike: number;
  call_oi: number;
  put_oi: number;
  call_vol: number;
  put_vol: number;
}

export interface OptionsOIResponse {
  symbol: string;
  error?: string;
  calls: Record<string, number>[];
  puts: Record<string, number>[];
  expiries: string[];
  expiry: string | null;
  max_pain: number;
  pcr: number;
  sentiment: string;
  total_call_oi: number;
  total_put_oi: number;
  resistance_levels: OILevel[];
  support_levels: OILevel[];
  oi_profile: OIProfileRow[];
  current_price: number;
}

export const fetchOptionsOI = (symbol: string, expiry?: string) =>
  apiFetch<OptionsOIResponse>(`/api/options-oi/${symbol}${expiry ? `?expiry=${expiry}` : ""}`);

// ---------------------------------------------------------------------------
// Backtesting engine
// ---------------------------------------------------------------------------

export interface BacktestTrade {
  entry_date: string;
  entry_price: number;
  exit_date: string;
  exit_price: number;
  shares: number;
  pnl: number;
  pnl_pct: number;
  bars_held: number;
}

export interface BacktestResult {
  symbol: string;
  strategy: string;
  error?: string;
  params: Record<string, number | string>;
  initial_capital: number;
  final_equity: number;
  total_return_pct: number;
  cagr_pct: number;
  max_drawdown_pct: number;
  sharpe_ratio: number;
  volatility_pct: number;
  win_rate: number;
  num_trades: number;
  avg_trade_pct: number;
  avg_bars_held: number;
  trades: BacktestTrade[];
  equity_curve: { date: string; equity: number }[];
  buy_hold_return_pct: number;
  outperformance_pct: number;
}

export interface BacktestRequest {
  symbol: string;
  strategy: "ema_crossover" | "rsi_reversion" | "bollinger" | "breakout";
  days: number;
  initial_capital: number;
  params: Record<string, number>;
}

export const runBacktest = (req: BacktestRequest) =>
  apiFetch<BacktestResult>("/api/backtest", {
    method: "POST",
    body: JSON.stringify(req),
  });

// ---------------------------------------------------------------------------
// Walk-forward optimization
// ---------------------------------------------------------------------------

export interface WalkForwardWindow {
  window: number;
  in_sample_start: string;
  in_sample_end: string;
  out_of_sample_start: string;
  out_of_sample_end: string;
  best_params: Record<string, number>;
  in_sample_return: number;
  in_sample_sharpe: number;
  in_sample_trades: number;
  out_of_sample_return: number;
  out_of_sample_sharpe: number;
  out_of_sample_trades: number;
  out_of_sample_max_dd: number;
}

export interface WalkForwardSummary {
  avg_in_sample_return: number;
  avg_out_of_sample_return: number;
  walk_forward_efficiency: number;
  profitable_windows: number;
  total_windows: number;
  consistency_pct: number;
  verdict: "robust" | "moderate" | "fragile" | "overfit";
}

export interface WalkForwardResult {
  symbol: string;
  strategy: string;
  error?: string;
  num_windows: number;
  in_sample_pct: number;
  windows: WalkForwardWindow[];
  summary: WalkForwardSummary;
}

export interface WalkForwardRequest {
  symbol: string;
  strategy: "ema_crossover" | "rsi_reversion" | "bollinger" | "breakout";
  days: number;
  in_sample_pct: number;
  num_windows: number;
  initial_capital: number;
}

export const runWalkForward = (req: WalkForwardRequest) =>
  apiFetch<WalkForwardResult>("/api/walk-forward", {
    method: "POST",
    body: JSON.stringify(req),
  });

// ---------------------------------------------------------------------------
// Portfolio simulation
// ---------------------------------------------------------------------------

export interface PortfolioStrategyResult {
  strategy: string;
  label: string;
  params: Record<string, number>;
  initial_capital: number;
  final_equity: number;
  total_return_pct: number;
  cagr_pct: number;
  max_drawdown_pct: number;
  sharpe_ratio: number;
  win_rate: number;
  num_trades: number;
}

export interface PortfolioSimResult {
  symbol: string;
  error?: string;
  initial_capital: number;
  final_equity: number;
  total_return_pct: number;
  cagr_pct: number;
  max_drawdown_pct: number;
  sharpe_ratio: number;
  volatility_pct: number;
  buy_hold_return_pct: number;
  outperformance_pct: number;
  diversification_benefit: number;
  num_strategies: number;
  strategies: PortfolioStrategyResult[];
  equity_curve: { date: string; equity: number }[];
}

export interface PortfolioStrategyConfig {
  strategy: "ema_crossover" | "rsi_reversion" | "bollinger" | "breakout";
  label?: string;
  params?: Record<string, number>;
}

export interface PortfolioSimRequest {
  symbol: string;
  strategies: PortfolioStrategyConfig[];
  days: number;
  initial_capital: number;
}

export const runPortfolioSim = (req: PortfolioSimRequest) =>
  apiFetch<PortfolioSimResult>("/api/portfolio-sim", {
    method: "POST",
    body: JSON.stringify(req),
  });

// ---------------------------------------------------------------------------
// Position sizing (Kelly Criterion)
// ---------------------------------------------------------------------------

export interface PositionSizingResult {
  symbol: string;
  strategy: string;
  capital: number;
  entry_price: number;
  stop_price: number;
  risk_per_share: number;
  win_rate: number;
  avg_win_pct: number;
  avg_loss_pct: number;
  payoff_ratio: number;
  kelly_fraction: number;
  sizing_methods: {
    full_kelly_pct: number;
    half_kelly_pct: number;
    quarter_kelly_pct: number;
    fixed_fractional_pct: number;
    inverse_volatility_pct: number;
  };
  recommended: {
    method: string;
    pct_of_capital: number;
    shares: number;
    dollar_amount: number;
  };
  risk: {
    risk_dollar: number;
    risk_pct_of_capital: number;
  };
  estimates: {
    annual_growth_pct: number;
    max_drawdown_pct: number;
  };
  historical: {
    trades: number;
    sharpe: number;
    return_pct: number;
    volatility_pct: number;
  };
  error?: string;
}

export interface PositionSizingRequest {
  symbol: string;
  strategy: "ema_crossover" | "rsi_reversion" | "bollinger" | "breakout";
  capital: number;
  entry_price: number;
  stop_price: number;
  risk_pct: number;
  days: number;
  params?: Record<string, number>;
}

export const computePositionSize = (req: PositionSizingRequest) =>
  apiFetch<PositionSizingResult>("/api/position-sizing", {
    method: "POST",
    body: JSON.stringify(req),
  });

// ---------------------------------------------------------------------------
// Price alerts
// ---------------------------------------------------------------------------

export interface PriceAlert {
  id: number;
  symbol: string;
  condition: "above" | "below" | "cross_up" | "cross_down";
  target_price: number;
  note: string | null;
  status: "active" | "triggered" | "deleted";
  created_at: string;
  triggered_at: string | null;
  triggered_price: number | null;
}

export interface PriceAlertListResponse {
  alerts: PriceAlert[];
}

export interface PriceAlertCheckResponse {
  checked: number;
  triggered: PriceAlert[];
  prices: Record<string, number>;
}

export interface CreateAlertRequest {
  symbol: string;
  condition: "above" | "below" | "cross_up" | "cross_down";
  target_price: number;
  note?: string;
}

export const fetchPriceAlerts = () =>
  apiFetch<PriceAlertListResponse>("/api/price-alerts");

export const createPriceAlert = (req: CreateAlertRequest) =>
  apiFetch<PriceAlert>("/api/price-alerts", {
    method: "POST",
    body: JSON.stringify(req),
  });

export const deletePriceAlert = (id: number) =>
  apiFetch<{ deleted: boolean; id: number }>(`/api/price-alerts/${id}`, {
    method: "DELETE",
  });

export const checkPriceAlerts = () =>
  apiFetch<PriceAlertCheckResponse>("/api/price-alerts/check", {
    method: "POST",
  });

// ---------------------------------------------------------------------------
// Signal alerts
// ---------------------------------------------------------------------------

export interface SignalAlertEntry {
  symbol: string;
  name: string;
  market: string;
  signal_type: string;
  side: "long" | "short" | "watch";
  price: number;
  rsi?: number;
  volume_ratio?: number;
  entry: number | null;
  stop_loss: number | null;
  target: number | null;
  confidence: number;
  description: string;
}

export interface SignalAlertsResponse {
  market: string;
  signals: SignalAlertEntry[];
  total: number;
  refreshed_at: string;
  market_status: { market_open: boolean; market: string };
}

export const fetchSignalAlerts = (market: "nse" | "us", signal_types?: string) =>
  apiFetch<SignalAlertsResponse>(
    `/api/signal-alerts?market=${market}${signal_types ? `&signal_types=${signal_types}` : ""}`
  );

export const refreshSignalAlerts = (market: "nse" | "us") =>
  apiFetch<{ invalidated: boolean; market: string }>(
    `/api/signal-alerts/refresh?market=${market}`,
    { method: "POST" }
  );

// ---------------------------------------------------------------------------
// Daily digest
// ---------------------------------------------------------------------------

export interface DigestSummary {
  id: number;
  date: string;
  subject: string;
  emailed: boolean;
  created_at: string;
}

export interface DigestDetail extends DigestSummary {
  data: Record<string, any>;
  html: string;
  error?: string;
}

export const generateDigest = (targetDate?: string) =>
  apiFetch<{ id: number; date: string; subject: string; emailed: boolean; data: Record<string, any> }>(
    `/api/daily-digest/generate${targetDate ? `?target_date=${targetDate}` : ""}`,
    { method: "POST" }
  );

export const fetchDigests = (limit: number = 7) =>
  apiFetch<{ digests: DigestSummary[] }>(`/api/daily-digest?limit=${limit}`);

export const fetchDigest = (id: number) =>
  apiFetch<DigestDetail>(`/api/daily-digest/${id}`);

// ---------------------------------------------------------------------------
// Notifications (Telegram/Discord)
// ---------------------------------------------------------------------------

export interface NotificationChannel {
  id: number;
  channel_type: "telegram" | "discord";
  config: Record<string, string>;
  enabled: boolean;
  created_at: string;
}

export interface CreateChannelRequest {
  channel_type: "telegram" | "discord";
  config: Record<string, string>;
}

export const fetchChannels = () =>
  apiFetch<{ channels: NotificationChannel[] }>("/api/notifications/channels");

export const createChannel = (req: CreateChannelRequest) =>
  apiFetch<NotificationChannel>("/api/notifications/channels", {
    method: "POST",
    body: JSON.stringify(req),
  });

export const deleteChannel = (id: number) =>
  apiFetch<{ deleted: boolean; id: number }>(`/api/notifications/channels/${id}`, {
    method: "DELETE",
  });

export const testNotification = (message?: string) =>
  apiFetch<{ sent: number; total: number; results: any[] }>("/api/notifications/test", {
    method: "POST",
    body: JSON.stringify({ message: message || "Test notification" }),
  });

// ---------------------------------------------------------------------------
// Broker trading (Fyers)
// ---------------------------------------------------------------------------

export interface BrokerStatus {
  broker: string;
  connected: boolean;
  message: string;
}

export interface BrokerPosition {
  symbol: string;
  quantity: number;
  side: string;
  avg_price: number;
  current_price: number;
  product: string;
  pnl: number;
}

export interface BrokerFunds {
  available_balance?: number;
  used_margin?: number;
  total_balance?: number;
  error?: string;
}

export interface PlaceOrderRequest {
  symbol: string;
  side: "buy" | "sell";
  quantity: number;
  order_type?: "MARKET" | "LIMIT" | "SL" | "SL-M";
  product?: "CNC" | "MIS" | "NRML";
  limit_price?: number;
  stop_price?: number;
  validity?: string;
}

export interface OrderResult {
  status: string;
  order_id?: string;
  message: string;
  symbol: string;
  side: string;
  quantity: number;
}

export const fetchBrokerStatus = () =>
  apiFetch<BrokerStatus>("/api/broker/status");

export const fetchPositions = () =>
  apiFetch<{ positions: BrokerPosition[]; total: number }>("/api/broker/positions");

export const fetchOrders = () =>
  apiFetch<{ orders: any[]; total: number }>("/api/broker/orders");

export const fetchFunds = () =>
  apiFetch<BrokerFunds>("/api/broker/funds");

export const placeOrder = (req: PlaceOrderRequest) =>
  apiFetch<OrderResult>("/api/broker/place-order", {
    method: "POST",
    body: JSON.stringify(req),
  });

export const cancelOrder = (orderId: string) =>
  apiFetch<{ cancelled: boolean; order_id: string }>(`/api/broker/cancel-order/${orderId}`, {
    method: "DELETE",
  });

// ---------------------------------------------------------------------------
// Portfolio risk analytics
// ---------------------------------------------------------------------------

export interface PositionRisk {
  symbol: string;
  weight: number;
  value: number;
  volatility: number;
  marginal_var: number;
  contribution_to_risk: number;
}

export interface RiskAnalyticsResult {
  total_value: number;
  num_positions: number;
  volatility_pct: number;
  var_95: number;
  var_99: number;
  cvar_95: number;
  sharpe_ratio: number;
  max_drawdown_pct: number;
  beta: number;
  alpha_annual: number;
  correlation_to_benchmark: number;
  herfindahl_index: number;
  effective_positions: number;
  diversification_ratio: number;
  avg_correlation: number;
  positions: PositionRisk[];
  error?: string;
}

export const fetchRiskAnalytics = (benchmark?: string, days?: number) =>
  apiFetch<RiskAnalyticsResult>(
    `/api/risk-analytics?${benchmark ? `benchmark=${benchmark}` : ""}${days ? `&days=${days}` : ""}`
  );

// ---------------------------------------------------------------------------
// Rebalancing suggestions
// ---------------------------------------------------------------------------

export interface RebalancingTrade {
  symbol: string;
  action: "buy" | "sell";
  shares: number;
  value: number;
  current_weight: number;
  target_weight: number;
  drift_pct: number;
}

export interface RebalancingPosition {
  symbol: string;
  quantity: number;
  current_price: number;
  current_value: number;
  current_weight: number;
  target_weight: number;
  drift_pct: number;
  target_value: number;
  trade_value: number;
  trade_shares: number;
  action: string;
  needs_rebalance: boolean;
  volatility?: number;
}

export interface RebalancingResult {
  total_value: number;
  num_positions: number;
  method: string;
  threshold_pct: number;
  needs_rebalancing: boolean;
  max_drift_pct: number;
  avg_drift_pct: number;
  total_buy_value: number;
  total_sell_value: number;
  net_trade_value: number;
  trades: RebalancingTrade[];
  positions: RebalancingPosition[];
  error?: string;
}

export interface RebalancingRequest {
  method: "equal_weight" | "custom" | "risk_parity";
  target_allocation?: Record<string, number>;
  threshold_pct?: number;
}

export const computeRebalancing = (req: RebalancingRequest) =>
  apiFetch<RebalancingResult>("/api/rebalancing", {
    method: "POST",
    body: JSON.stringify(req),
  });

// ---------------------------------------------------------------------------
// IPO center — current, recent, upcoming IPOs with GMP and selection scores
// ---------------------------------------------------------------------------
export interface IpoSubscription {
  rii: number | null;
  nii: number | null;
  qib: number | null;
  total: number | null;
}

export interface IpoGmp {
  premium: number | null;
  premium_pct: number | null;
  last_updated: string | null;
}

export interface IpoData {
  company_name: string;
  symbol: string;
  board: "mainboard" | "sme";
  status: "current" | "recent" | "upcoming";
  price_band: string | null;
  price_low: number | null;
  price_high: number | null;
  face_value: number | null;
  issue_size_crs: number | null;
  lot_size: number | null;
  open_date: string | null;
  close_date: string | null;
  allotment_date: string | null;
  listing_date: string | null;
  listing_at: string | null;
  registrar: string | null;
  market_maker: string | null;
  lead_manager: string | null;
  subscription: IpoSubscription | null;
  gmp: IpoGmp | null;
  selection_score: number | null;
  score_factors: Record<string, number> | null;
}

export interface IpoBoardData {
  current: IpoData[];
  recent: IpoData[];
  upcoming: IpoData[];
}

export interface IpoResponse {
  mainboard: IpoBoardData;
  sme: IpoBoardData;
  refreshed_at?: string;
  error?: string;
}

export const fetchIpoAll = () => apiFetch<IpoResponse>("/api/ipo/all");
export const fetchIpoCurrent = () => apiFetch<IpoResponse>("/api/ipo/current");
export const fetchIpoUpcoming = () => apiFetch<IpoResponse>("/api/ipo/upcoming");
export const fetchIpoDetail = (symbol: string) =>
  apiFetch<IpoData | null>(`/api/ipo/${encodeURIComponent(symbol)}`);

// ---------------------------------------------------------------------------
// Daily Top-5 Picks — Murphy multi-indicator analysis
// ---------------------------------------------------------------------------

export interface MurphyFactors {
  trend: number;
  momentum: number;
  volume: number;
  support_resistance: number;
}

export interface MurphyAnalysis {
  symbol: string;
  name: string;
  last_price: number;
  // Trend
  trend_score: number;
  trend_direction: string;
  ema_alignment: string;
  adx_value: number;
  adx_strength: string;
  supertrend_dir: string;
  // Momentum
  momentum_score: number;
  rsi_value: number;
  rsi_signal: string;
  stochastic_k: number;
  stochastic_signal: string;
  macd_histogram: number;
  macd_signal: string;
  williams_r_value: number;
  williams_r_signal: string;
  // Volume
  volume_score: number;
  obv_trend: string;
  volume_ratio: number;
  // Support / Resistance
  fibonacci_levels: Record<string, number>;
  nearest_support: number;
  nearest_resistance: number;
  pivot_levels: Record<string, number>;
  price_vs_support: string;
  // Composite
  composite_score: number;
  verdict: string;
  // Entry / Exit
  entry: number;
  stop_loss: number;
  target1: number;
  target2: number;
  risk_reward: number;
  atr_value: number;
  // Breakdown
  factors: MurphyFactors;
  explanation: string;
  caveats: string[];
}

export interface DailyPick extends MurphyAnalysis {
  rank: number;
}

export interface DailyPicksResponse {
  picks: DailyPick[];
  total_scanned: number;
  refreshed_at: string;
  market_status: string;
}

export interface DailyBacktestTrade {
  date: string;
  symbol: string;
  name: string;
  verdict: string;
  composite_score: number;
  entry: number;
  stop_loss: number;
  target1: number;
  target2: number;
  exit_price: number;
  exit_date: string;
  outcome: string;
  pnl_pct: number;
  pnl_rupees: number;
  hold_days: number;
}

export interface DailyBacktestDay {
  date: string;
  picks: Record<string, unknown>[];
  day_pnl_pct: number;
}

export interface DailyBacktestResult {
  days: DailyBacktestDay[];
  summary: {
    total_trades: number;
    wins: number;
    losses: number;
    win_rate: number;
    avg_return_pct: number;
  };
  all_trades: DailyBacktestTrade[];
}

export const fetchDailyPicks = () => apiFetch<DailyPicksResponse>("/api/daily-picks");
export const refreshDailyPicks = () => apiFetch<DailyPicksResponse>("/api/daily-picks/refresh");
export const fetchMurphyDetail = (symbol: string) =>
  apiFetch<{ symbol: string; analysis: MurphyAnalysis | null; message?: string }>(
    `/api/daily-picks/${encodeURIComponent(symbol)}`
  );
export const fetchDailyBacktest = (days: number = 30) =>
  apiFetch<DailyBacktestResult>(`/api/daily-picks/backtest?days=${days}`);

// ---------------------------------------------------------------------------
// Autonomous Trading Bot API
// ---------------------------------------------------------------------------

export interface BotStatus {
  last_scan: string | null;
  today: string;
  total_signals: number;
  open: number;
  resolved: number;
  by_strategy: Record<string, Record<string, number>>;
  has_recommendation: boolean;
}

export interface BotDecision {
  id: number;
  scan_time: string | null;
  date: string;
  symbol: string;
  market: string;
  strategy: string;
  side: string;
  entry: number;
  stop_loss: number;
  target: number;
  confidence: number;
  risk_reward: number;
  composite_score: number | null;
  verdict: string | null;
  status: string;
  exit_price: number | null;
  pnl_pct: number | null;
  explanation: Record<string, any> | null;
}

export interface StrategyRanking {
  rank: number;
  strategy: string;
  total_signals: number;
  resolved: number;
  wins: number;
  losses: number;
  win_rate: number;
  avg_pnl_pct: number;
  total_pnl_pct: number;
  best_trade_pct: number | null;
  worst_trade_pct: number | null;
  wfe_score: number | null;
  wfe_verdict: string | null;
  recommendation: string;
}

export interface DailyRecommendationData {
  found: boolean;
  date: string;
  symbol?: string;
  name?: string;
  strategy?: string;
  side?: string;
  entry?: number;
  stop_loss?: number;
  target?: number;
  confidence?: number;
  risk_reward?: number;
  composite_score?: number | null;
  explanation?: string;
  caveats?: string[];
  alternatives?: { symbol: string; strategy: string; rank: number; entry: number; stop_loss: number; target: number; confidence: number }[];
  message?: string;
}

export const fetchBotStatus = () => apiFetch<BotStatus>("/api/bot/status");
export const fetchBotDecisions = (strategy?: string, status?: string, limit = 100) => {
  const params = new URLSearchParams();
  if (strategy) params.set("strategy", strategy);
  if (status) params.set("status", status);
  params.set("limit", String(limit));
  const qs = params.toString();
  return apiFetch<{ decisions: BotDecision[]; count: number }>(`/api/bot/decisions?${qs}`);
};
export const fetchStrategyRankings = (date?: string) =>
  apiFetch<{ date: string; rankings: StrategyRanking[]; count: number }>(
    `/api/bot/rankings${date ? `?date=${date}` : ""}`
  );
export const fetchDailyRecommendation = (date?: string) =>
  apiFetch<DailyRecommendationData>(`/api/bot/recommendation${date ? `?date=${date}` : ""}`);
export const fetchBotHistory = (limit = 30) =>
  apiFetch<{ history: PaperDayHistory[]; count: number }>(`/api/bot/history?limit=${limit}`);
export const triggerBotScan = (market = "nse") =>
  apiFetch<{ new_signals: number; resolved: number; by_strategy: Record<string, number>; scan_time: string }>(
    `/api/bot/scan?market=${market}`, { method: "POST" }
  );
export const fetchStrategyComparison = (days = 30) =>
  apiFetch<{ comparison: Record<string, any>; count: number }>(`/api/bot/strategy-comparison?days=${days}`);

