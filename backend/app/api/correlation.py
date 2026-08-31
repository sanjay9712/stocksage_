"""Correlation matrix — show which ETFs/stocks overlap so you don't duplicate exposure.

Computes pairwise correlation of daily returns for a set of securities.
High correlation (> 0.8) means you're effectively doubling up on the same
exposure; low/negative correlation means diversification benefit.
"""
from __future__ import annotations

import asyncio
import logging
from typing import Any

import pandas as pd
from fastapi import APIRouter, Depends

from app.api.auth import require_token
from app.api.cache import cached
from app.market_hours import is_nse_open, is_us_open, screen_cache_ttl
from app.providers.factory import get_provider
from app.universe import ETF_UNIVERSE, US_ETF_UNIVERSE, NIFTY_50, get_us_stocks

log = logging.getLogger("correlation")
router = APIRouter()


async def _fetch_returns(provider, symbols: list[str], days: int = 90) -> pd.DataFrame:
    """Fetch daily returns for multiple symbols, aligned by date."""
    sem = asyncio.Semaphore(8)
    returns_dict: dict[str, pd.Series] = {}

    async def _fetch_one(sym: str):
        async with sem:
            try:
                daily = await provider.get_daily_history(sym, days)
                if daily.empty or len(daily) < 30:
                    return
                rets = daily["Close"].pct_change().dropna()
                returns_dict[sym] = rets
            except Exception as e:
                log.warning("Failed to fetch %s: %s", sym, e)

    await asyncio.gather(*[_fetch_one(s) for s in symbols])

    if not returns_dict:
        return pd.DataFrame()

    df = pd.DataFrame(returns_dict)
    return df


@router.get("/correlation/nse")
async def nse_correlation(_t=Depends(require_token)):
    """Correlation matrix for NSE ETFs + top Nifty 50 stocks."""
    etf_symbols = [e["symbol"] for e in ETF_UNIVERSE]
    stock_symbols = list(NIFTY_50[:10])  # top 10 for manageable matrix
    symbols = etf_symbols + stock_symbols

    async def _fetch():
        provider = get_provider()
        df = await _fetch_returns(provider, symbols, 90)
        if df.empty:
            return {"symbols": [], "matrix": [], "clusters": []}

        corr = df.corr()

        # Build matrix as list of lists
        sym_list = list(corr.columns)
        matrix = []
        for i in range(len(sym_list)):
            row = []
            for j in range(len(sym_list)):
                val = corr.iloc[i, j]
                row.append(round(float(val), 3) if not pd.isna(val) else None)
            matrix.append(row)

        # Find high-correlation pairs (excluding diagonal)
        high_corr_pairs = []
        for i in range(len(sym_list)):
            for j in range(i + 1, len(sym_list)):
                val = corr.iloc[i, j]
                if not pd.isna(val) and abs(val) >= 0.7:
                    high_corr_pairs.append({
                        "a": sym_list[i],
                        "b": sym_list[j],
                        "correlation": round(float(val), 3),
                        "warning": "High overlap — consider consolidating" if val > 0.8 else "Moderate overlap",
                    })

        return {
            "symbols": sym_list,
            "matrix": matrix,
            "high_correlation_pairs": sorted(high_corr_pairs, key=lambda d: abs(d["correlation"]), reverse=True),
        }

    return await cached("nse_correlation", screen_cache_ttl(is_nse_open()), _fetch)


@router.get("/correlation/us")
async def us_correlation(_t=Depends(require_token)):
    """Correlation matrix for US ETFs + top US stocks."""
    etf_symbols = [e["symbol"] for e in US_ETF_UNIVERSE]
    stock_symbols = get_us_stocks()[:10]
    symbols = etf_symbols + stock_symbols

    async def _fetch():
        provider = get_provider()
        df = await _fetch_returns(provider, symbols, 90)
        if df.empty:
            return {"symbols": [], "matrix": [], "clusters": []}

        corr = df.corr()

        sym_list = list(corr.columns)
        matrix = []
        for i in range(len(sym_list)):
            row = []
            for j in range(len(sym_list)):
                val = corr.iloc[i, j]
                row.append(round(float(val), 3) if not pd.isna(val) else None)
            matrix.append(row)

        high_corr_pairs = []
        for i in range(len(sym_list)):
            for j in range(i + 1, len(sym_list)):
                val = corr.iloc[i, j]
                if not pd.isna(val) and abs(val) >= 0.7:
                    high_corr_pairs.append({
                        "a": sym_list[i],
                        "b": sym_list[j],
                        "correlation": round(float(val), 3),
                        "warning": "High overlap — consider consolidating" if val > 0.8 else "Moderate overlap",
                    })

        return {
            "symbols": sym_list,
            "matrix": matrix,
            "high_correlation_pairs": sorted(high_corr_pairs, key=lambda d: abs(d["correlation"]), reverse=True),
        }

    return await cached("us_correlation", screen_cache_ttl(is_us_open()), _fetch)
