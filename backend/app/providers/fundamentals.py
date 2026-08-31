"""Stock fundamentals via yfinance — company financials, valuation, analyst ratings.

Uses yfinance's .info (dict), .financials (income statement), .balance_sheet,
and .recommendations. Cached 1 hour since fundamentals change slowly.

IMPORTANT: yfinance uses synchronous `requests` under the hood. All .info,
.financials, .balance_sheet, and .recommendations calls are wrapped in
asyncio.to_thread() so they run in a thread pool and don't block the
FastAPI event loop. Without this, concurrent stock screens (100+ symbols)
execute their .info calls serially, taking 60+ seconds.

Data is delayed ~15 min (same as all yfinance data). This is fine for
fundamental analysis — P/E, revenue, debt etc. don't change intraday.
"""
from __future__ import annotations

import asyncio
import logging
import time

import yfinance as yf

from app.universe import is_us_symbol

log = logging.getLogger("fundamentals")

# In-process cache: {symbol: (timestamp, data)}
_cache: dict[str, tuple[float, dict]] = {}
_TTL = 3600  # 1 hour


def _suffix(symbol: str) -> str:
    if any(ch in symbol for ch in (".", "=", "^")):
        return symbol
    if is_us_symbol(symbol):
        return symbol  # US tickers need no suffix on yfinance
    return f"{symbol}.NS"


def _safe_float(v, default=None):
    try:
        return float(v)
    except (TypeError, ValueError):
        return default


def _fetch_info_sync(symbol: str) -> dict:
    """Synchronous yfinance .info call — runs in thread pool via to_thread."""
    ticker = yf.Ticker(_suffix(symbol))
    info = ticker.info or {}
    return info


def _fetch_financials_sync(symbol: str) -> dict:
    """Synchronous yfinance .financials + .balance_sheet — runs in thread pool."""
    ticker = yf.Ticker(_suffix(symbol))
    result: dict = {"income_statement": {}, "balance_sheet": {}}

    try:
        fin = ticker.financials
        if fin is not None and not fin.empty:
            for col in list(fin.columns)[:3]:
                year = str(col.year) if hasattr(col, "year") else str(col)[:4]
                result["income_statement"][year] = {
                    "revenue": _safe_float(fin.loc["Total Revenue", col]) if "Total Revenue" in fin.index else None,
                    "cost_of_revenue": _safe_float(fin.loc["Cost Of Revenue", col]) if "Cost Of Revenue" in fin.index else None,
                    "gross_profit": _safe_float(fin.loc["Gross Profit", col]) if "Gross Profit" in fin.index else None,
                    "operating_income": _safe_float(fin.loc["Operating Income", col]) if "Operating Income" in fin.index else None,
                    "net_income": _safe_float(fin.loc["Net Income", col]) if "Net Income" in fin.index else None,
                    "ebitda": _safe_float(fin.loc["EBITDA", col]) if "EBITDA" in fin.index else None,
                    "eps": _safe_float(fin.loc["Diluted EPS", col]) if "Diluted EPS" in fin.index else None,
                }
    except Exception as e:
        log.debug("financials fetch failed for %s: %s", symbol, e)

    try:
        bs = ticker.balance_sheet
        if bs is not None and not bs.empty:
            for col in list(bs.columns)[:3]:
                year = str(col.year) if hasattr(col, "year") else str(col)[:4]
                result["balance_sheet"][year] = {
                    "total_assets": _safe_float(bs.loc["Total Assets", col]) if "Total Assets" in bs.index else None,
                    "total_debt": _safe_float(bs.loc["Total Debt", col]) if "Total Debt" in bs.index else None,
                    "total_cash": _safe_float(bs.loc["Cash And Cash Equivalents", col]) if "Cash And Cash Equivalents" in bs.index else None,
                    "stockholders_equity": _safe_float(bs.loc["Stockholders Equity", col]) if "Stockholders Equity" in bs.index else None,
                    "retained_earnings": _safe_float(bs.loc["Retained Earnings", col]) if "Retained Earnings" in bs.index else None,
                    "net_debt": _safe_float(bs.loc["Net Debt", col]) if "Net Debt" in bs.index else None,
                    "working_capital": _safe_float(bs.loc["Working Capital", col]) if "Working Capital" in bs.index else None,
                }
    except Exception as e:
        log.debug("balance_sheet fetch failed for %s: %s", symbol, e)

    return result


def _fetch_recommendations_sync(symbol: str) -> dict:
    """Synchronous yfinance .recommendations — runs in thread pool."""
    ticker = yf.Ticker(_suffix(symbol))
    result: dict = {"periods": [], "consensus": "no data"}

    try:
        recs = ticker.recommendations
        if recs is not None and not recs.empty:
            for _, row in recs.tail(3).iterrows():
                period = str(row.get("period", ""))
                total = (row.get("strongBuy", 0) + row.get("buy", 0) +
                         row.get("hold", 0) + row.get("sell", 0) + row.get("strongSell", 0))
                result["periods"].append({
                    "period": period,
                    "strong_buy": int(row.get("strongBuy", 0)),
                    "buy": int(row.get("buy", 0)),
                    "hold": int(row.get("hold", 0)),
                    "sell": int(row.get("sell", 0)),
                    "strong_sell": int(row.get("strongSell", 0)),
                    "total": int(total),
                })
            if result["periods"]:
                latest = result["periods"][0]
                buys = latest["strong_buy"] + latest["buy"]
                sells = latest["sell"] + latest["strong_sell"]
                holds = latest["hold"]
                if buys > holds + sells:
                    result["consensus"] = "BUY" if buys > 2 * (holds + sells) else "ACCUMULATE"
                elif sells > buys + holds:
                    result["consensus"] = "REDUCE" if sells > 2 * (buys + holds) else "SELL"
                else:
                    result["consensus"] = "HOLD"
    except Exception as e:
        log.debug("recommendations fetch failed for %s: %s", symbol, e)

    return result


async def get_stock_fundamentals(symbol: str) -> dict:
    """Fetch company fundamentals from yfinance .info."""
    cached = _cache.get(f"info:{symbol}")
    if cached and (time.time() - cached[0]) < _TTL:
        return cached[1]

    info = await asyncio.to_thread(_fetch_info_sync, symbol)

    result = {
        "symbol": symbol.upper(),
        "company_name": info.get("longName") or info.get("shortName") or symbol.upper(),
        "sector": info.get("sector"),
        "industry": info.get("industry"),
        "description": info.get("longBusinessSummary"),
        "website": info.get("website"),
        "employees": info.get("fullTimeEmployees"),
        "country": info.get("country", "India"),

        # Valuation

        # Valuation
        "trailing_pe": _safe_float(info.get("trailingPE")),
        "forward_pe": _safe_float(info.get("forwardPE")),
        "market_cap": _safe_float(info.get("marketCap")),
        "enterprise_value": _safe_float(info.get("enterpriseValue")),
        "price_to_book": _safe_float(info.get("priceToBook")),
        "enterprise_to_revenue": _safe_float(info.get("enterpriseToRevenue")),
        "enterprise_to_ebitda": _safe_float(info.get("enterpriseToEbitda")),

        # Profitability
        "profit_margins": _safe_float(info.get("profitMargins")),
        "operating_margins": _safe_float(info.get("operatingMargins")),
        "return_on_equity": _safe_float(info.get("returnOnEquity")),
        "return_on_assets": _safe_float(info.get("returnOnAssets")),

        # Financials
        "total_revenue": _safe_float(info.get("totalRevenue")),
        "gross_profits": _safe_float(info.get("grossProfits")),
        "ebitda": _safe_float(info.get("ebitda")),
        "total_cash": _safe_float(info.get("totalCash")),
        "total_debt": _safe_float(info.get("totalDebt")),
        "debt_to_equity": _safe_float(info.get("debtToEquity")),
        "current_ratio": _safe_float(info.get("currentRatio")),
        "revenue_per_share": _safe_float(info.get("revenuePerShare")),
        "earnings_per_share": _safe_float(info.get("trailingEps")),

        # Dividends
        "dividend_yield": _safe_float(info.get("dividendYield")),
        "payout_ratio": _safe_float(info.get("payoutRatio")),

        # Growth (may not always be present)
        "revenue_growth": _safe_float(info.get("revenueGrowth")),
        "earnings_growth": _safe_float(info.get("earningsGrowth")),

        # Market data
        "beta": _safe_float(info.get("beta")),
        "52w_high": _safe_float(info.get("fiftyTwoWeekHigh")),
        "52w_low": _safe_float(info.get("fiftyTwoWeekLow")),
        "avg_volume": _safe_float(info.get("averageVolume")),
    }

    _cache[f"info:{symbol}"] = (time.time(), result)
    return result


async def get_stock_financials(symbol: str) -> dict:
    """Fetch annual income statement + balance sheet (last 3 years)."""
    cached = _cache.get(f"fin:{symbol}")
    if cached and (time.time() - cached[0]) < _TTL:
        return cached[1]

    result = await asyncio.to_thread(_fetch_financials_sync, symbol)
    _cache[f"fin:{symbol}"] = (time.time(), result)
    return result


async def get_analyst_recommendations(symbol: str) -> dict:
    """Fetch analyst recommendation consensus from yfinance."""
    cached = _cache.get(f"rec:{symbol}")
    if cached and (time.time() - cached[0]) < _TTL:
        return cached[1]

    result = await asyncio.to_thread(_fetch_recommendations_sync, symbol)
    _cache[f"rec:{symbol}"] = (time.time(), result)
    return result


async def get_stock_detail(symbol: str) -> dict:
    """Combined: fundamentals + financials + recommendations.
    All three yfinance calls run in parallel via asyncio.gather()."""
    fundamentals, financials, recommendations = await asyncio.gather(
        get_stock_fundamentals(symbol),
        get_stock_financials(symbol),
        get_analyst_recommendations(symbol),
    )
    return {
        "fundamentals": fundamentals,
        "financials": financials,
        "recommendations": recommendations,
    }
