"""ETF invest screener.

Pulls ~2 years of daily data, computes risk/return metrics, classifies a
suggested investment horizon, and surfaces the risks/issues for each ETF.
Also computes entry/stop-loss/target levels and estimated expense ratio.
This is a SLOW-INVEST screener, not intraday.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, asdict, field

import pandas as pd
import yfinance as yf

from app import indicators as ind
from app.providers.base import DataProvider
from app.strategies.invest_levels import compute_invest_levels

log = logging.getLogger("etf_screener")

# SEBI-capped expense ratio estimates by category (direct/growth plans).
# These are HONEST APPROXIMATIONS — verify on the AMC's fact sheet.
_EXPENSE_ESTIMATES = {
    "broad-index": {"low": 0.05, "high": 0.50, "note": "Index ETFs: SEBI cap ~0.50%"},
    "gold": {"low": 0.50, "high": 1.00, "note": "Gold ETFs: typically 0.50-1.00%"},
    "silver": {"low": 0.50, "high": 1.00, "note": "Silver ETFs: typically 0.50-1.00%"},
    "sector-bank": {"low": 0.50, "high": 1.20, "note": "Sector ETFs: 0.50-1.20%"},
    "sector-it": {"low": 0.50, "high": 1.20, "note": "Sector ETFs: 0.50-1.20%"},
    "sector-psu": {"low": 0.50, "high": 1.00, "note": "Sector ETFs: 0.50-1.00%"},
    "midcap": {"low": 0.50, "high": 1.00, "note": "Midcap ETFs: 0.50-1.00%"},
    "liquid": {"low": 0.05, "high": 0.20, "note": "Liquid ETFs: very low expense"},
}

# US ETF expense ratio estimates by category (SEC-regulated, generally lower).
_US_EXPENSE_ESTIMATES = {
    "broad-index": {"low": 0.03, "high": 0.20, "note": "US broad index ETFs: 0.03-0.20%"},
    "gold": {"low": 0.17, "high": 0.40, "note": "US gold ETFs: 0.17-0.40%"},
    "sector-tech": {"low": 0.08, "high": 0.75, "note": "US sector ETFs: 0.08-0.75%"},
    "sector-finance": {"low": 0.08, "high": 0.75, "note": "US sector ETFs: 0.08-0.75%"},
    "sector-energy": {"low": 0.08, "high": 0.75, "note": "US sector ETFs: 0.08-0.75%"},
    "sector-health": {"low": 0.08, "high": 0.75, "note": "US sector ETFs: 0.08-0.75%"},
    "sector-utility": {"low": 0.08, "high": 0.75, "note": "US sector ETFs: 0.08-0.75%"},
    "sector-psu": {"low": 0.08, "high": 0.75, "note": "US sector ETFs: 0.08-0.75%"},
    "sector-bank": {"low": 0.08, "high": 0.75, "note": "US sector ETFs: 0.08-0.75%"},
    "sector-it": {"low": 0.08, "high": 0.75, "note": "US sector ETFs: 0.08-0.75%"},
    "midcap": {"low": 0.10, "high": 0.25, "note": "US midcap ETFs: 0.10-0.25%"},
    "bond": {"low": 0.03, "high": 0.20, "note": "US bond ETFs: 0.03-0.20%"},
    "silver": {"low": 0.17, "high": 0.40, "note": "US silver ETFs: 0.17-0.40%"},
}


def _estimate_expense(category: str, market: str = "in") -> dict:
    table = _US_EXPENSE_ESTIMATES if market == "us" else _EXPENSE_ESTIMATES
    est = table.get(category, {"low": 0.30, "high": 1.00, "note": "Estimated"})
    mid = (est["low"] + est["high"]) / 2
    verify_msg = "SEC prospectus" if market == "us" else "AMC fact sheet"
    return {
        "expense_ratio_est": round(mid, 2),
        "expense_ratio_range": f"{est['low']:.2f}%-{est['high']:.2f}%",
        "expense_ratio_note": f"Estimated ({est['note']}). Verify on {verify_msg}.",
    }


def _get_amc_name_sync(symbol: str) -> str:
    """Extract AMC name from yfinance prevName field. Sync — runs in thread pool."""
    try:
        ticker = yf.Ticker(f"{symbol}.NS")
        info = ticker.info or {}
        prev = info.get("prevName", "")
        if prev:
            # prevName is like "Nippon India Mutual Fund - Nippon India ETF Nifty BeES"
            return prev.split(" - ")[0].strip()
    except Exception:
        pass
    return ""


async def _get_amc_name(symbol: str) -> str:
    """Extract AMC name from yfinance prevName field (non-blocking)."""
    import asyncio
    return await asyncio.to_thread(_get_amc_name_sync, symbol)


@dataclass
class EtfScreen:
    symbol: str
    name: str
    category: str
    horizon_hint: str
    last_price: float
    volatility: float
    cagr: float
    max_drawdown: float
    sharpe: float
    suggested_horizon: str
    risk_level: str
    risks: list[str]
    verdict: str
    # New fields
    prev_close: float | None = None
    change_pct: float | None = None
    amc_name: str = ""
    cagr: float
    max_drawdown: float
    sharpe: float
    suggested_horizon: str
    risk_level: str
    risks: list[str]
    verdict: str
    # New fields
    amc_name: str = ""
    expense_ratio_est: float = 0.0
    expense_ratio_range: str = ""
    expense_ratio_note: str = ""
    entry: float = 0.0
    stop_loss: float = 0.0
    target: float = 0.0
    risk_reward: float = 0.0
    trend: str = ""
    ema50: float = 0.0
    ema200: float = 0.0
    atr14: float = 0.0
    high_52w: float = 0.0
    low_52w: float = 0.0
    invest_explanation: str = ""
    invest_caveats: list[str] = field(default_factory=list)


async def screen_etf(provider: DataProvider, symbol: str, name: str, category: str, horizon_hint: str, market: str = "in") -> EtfScreen:
    daily = await provider.get_daily_history(symbol, 504)  # ~2 trading years
    if daily.empty or len(daily) < 60:
        return EtfScreen(
            symbol=symbol, name=name, category=category, horizon_hint=horizon_hint,
            last_price=0.0, prev_close=None, change_pct=None,
            volatility=0.0, cagr=0.0, max_drawdown=0.0, sharpe=0.0,
            suggested_horizon=horizon_hint, risk_level="unknown",
            risks=["Insufficient history to evaluate."],
            verdict="Not enough data to screen.",
        )
    close = daily["Close"]
    m = ind.risk_metrics(close)
    last_price = float(close.iloc[-1])

    # Fetch live quote for prev_close and intraday change.
    prev_close = None
    change_pct = None
    try:
        quote = await provider.get_quote(symbol)
        if quote and quote.price > 0:
            last_price = quote.price
            prev_close = quote.prev_close
            if prev_close and prev_close > 0:
                change_pct = round((quote.price - prev_close) / prev_close * 100, 2)
    except Exception:
        pass

    vol = m["volatility"]
    mdd = m["max_drawdown"]
    sharpe = m["sharpe"]
    cagr_val = m["cagr"]

    # Risk classification by volatility + drawdown.
    if vol < 0.12 and mdd > -0.15:
        risk_level = "low"
    elif vol < 0.22 and mdd > -0.30:
        risk_level = "moderate"
    else:
        risk_level = "high"

    # Suggested horizon from volatility regime.
    if risk_level == "low":
        suggested_horizon = "short (6m+)" if horizon_hint != "short" else "short (6m+)"
    elif risk_level == "moderate":
        suggested_horizon = "medium (1-3y)"
    else:
        suggested_horizon = "long (3y+)"

    risks: list[str] = []
    if category.startswith("sector"):
        risks.append(f"Concentrated sector exposure ({category}); higher single-sector risk than broad index.")
    if category == "gold" or category == "silver":
        risks.append("Commodity-only exposure; no underlying earnings. Sensitive to USD/INR and real yields.")
    if category == "midcap":
        risks.append("Mid/small-cap volatility; can drawdown sharply in corrections.")
    if category == "liquid":
        risks.append("Low return; meant for parking cash, not wealth creation.")
    if mdd < -0.30:
        risks.append(f"Historical max drawdown was {mdd*100:.1f}% — be prepared to hold through deep dips.")
    if sharpe < 0.4:
        risks.append(f"Low risk-adjusted return (Sharpe {sharpe:.2f}); prefer only if thesis is strong.")

    verdict = (
        f"{name}: {risk_level} risk, {cagr_val*100:.1f}% CAGR over ~2y, "
        f"Sharpe {sharpe:.2f}, max DD {mdd*100:.1f}%. "
        f"Suggested horizon: {suggested_horizon}."
    )

    # New: expense ratio estimate, AMC name, investment levels
    exp = _estimate_expense(category, market)
    amc = await _get_amc_name(symbol) if market == "in" else ""
    levels = compute_invest_levels(daily, symbol)

    return EtfScreen(
        symbol=symbol, name=name, category=category, horizon_hint=horizon_hint,
        last_price=round(last_price, 2),
        prev_close=round(prev_close, 2) if prev_close else None,
        change_pct=change_pct,
        volatility=round(vol, 4),
        cagr=round(cagr_val, 4), max_drawdown=round(mdd, 4),
        sharpe=round(sharpe, 2), suggested_horizon=suggested_horizon,
        risk_level=risk_level, risks=risks, verdict=verdict,
        amc_name=amc,
        expense_ratio_est=exp["expense_ratio_est"],
        expense_ratio_range=exp["expense_ratio_range"],
        expense_ratio_note=exp["expense_ratio_note"],
        entry=levels["entry"],
        stop_loss=levels["stop_loss"],
        target=levels["target"],
        risk_reward=levels["risk_reward"],
        trend=levels["trend"],
        ema50=levels["ema50"],
        ema200=levels["ema200"],
        atr14=levels["atr14"],
        high_52w=levels["52w_high"],
        low_52w=levels["52w_low"],
        invest_explanation=levels["explanation"],
        invest_caveats=levels["caveats"],
    )


def to_dict(s: EtfScreen) -> dict:
    return asdict(s)
