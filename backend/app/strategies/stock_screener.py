"""Stock screener — multi-factor screening for invest-quality stocks.

Fetches daily history + fundamentals for a universe of stocks, scores each
with the multi-factor system (momentum + quality + value), and returns only
the best investment candidates. Shared by both NSE and US market endpoints.
"""
from __future__ import annotations

import pandas as pd

from app import indicators as ind
from app.providers.base import DataProvider
from app.providers.fundamentals import get_stock_fundamentals
from app.strategies.invest_levels import compute_invest_levels
from app.strategies.multifactor import composite_score


async def screen_stock(
    provider: DataProvider,
    symbol: str,
    name: str,
    currency: str = "₹",
    rf_annual: float = 0.06,
    min_composite: float = 0.55,
    benchmark_close: pd.Series | None = None,
) -> dict | None:
    """Screen a single stock. Returns a dict if it passes, None if filtered out."""
    try:
        daily = await provider.get_daily_history(symbol, 252)
    except Exception:
        daily = pd.DataFrame()
    if daily.empty or len(daily) < 60:
        return None

    close = daily["Close"]
    m = ind.risk_metrics(close, rf_annual=rf_annual)
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

    # Relative strength vs benchmark
    rs_score = 0.0
    stock_beta = 1.0
    if benchmark_close is not None and len(benchmark_close) >= 2:
        rs_score = round(ind.relative_strength(close, benchmark_close), 4)
        stock_beta = ind.beta(close, benchmark_close)

    # Fast filters using only price data — skip the slow fundamentals fetch
    # for stocks that don't pass these cheap checks.
    ema50 = ind.ema(close, 50).iloc[-1] if len(close) >= 50 else last_price
    uptrend = last_price >= ema50

    if not uptrend:
        return None
    if m["sharpe"] <= 0:
        return None

    # Only fetch fundamentals for stocks that passed the price-based filters.
    # This eliminates ~50% of the slow yfinance .info calls.
    try:
        fundamentals = await get_stock_fundamentals(symbol)
    except Exception:
        fundamentals = {}

    scores = composite_score(daily, fundamentals)

    if scores["composite"] < min_composite:
        return None

    levels = compute_invest_levels(daily, symbol, currency=currency)

    return {
        "symbol": symbol,
        "name": name,
        "sector": fundamentals.get("sector"),
        "last_price": round(last_price, 2),
        "prev_close": round(prev_close, 2) if prev_close else None,
        "change_pct": change_pct,
        "cagr": round(m["cagr"], 4),
        "volatility": round(m["volatility"], 4),
        "max_drawdown": round(m["max_drawdown"], 4),
        "sharpe": round(m["sharpe"], 2),
        "composite": scores["composite"],
        "grade": scores["grade"],
        "momentum": scores["momentum"],
        "value": scores["value"],
        "quality": scores["quality"],
        "trailing_pe": fundamentals.get("trailing_pe"),
        "forward_pe": fundamentals.get("forward_pe"),
        "market_cap": fundamentals.get("market_cap"),
        "return_on_equity": fundamentals.get("return_on_equity"),
        "debt_to_equity": fundamentals.get("debt_to_equity"),
        "profit_margins": fundamentals.get("profit_margins"),
        "dividend_yield": fundamentals.get("dividend_yield"),
        "rs_score": rs_score,
        "beta": stock_beta,
        "trend": levels["trend"],
        "entry": levels["entry"],
        "stop_loss": levels["stop_loss"],
        "target": levels["target"],
        "risk_reward": levels["risk_reward"],
        "summary": scores["summary"],
    }
