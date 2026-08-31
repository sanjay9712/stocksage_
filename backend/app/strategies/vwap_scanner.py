"""VWAP premium/discount scanner.

Scans the stock universe for stocks trading at a significant premium or
discount to their intraday VWAP. This helps identify:

- **Premium stocks** (price > VWAP): overbought intraday, potential
  mean-reversion short or momentum continuation.
- **Discount stocks** (price < VWAP): oversold intraday, potential
  mean-reversion long or breakdown continuation.

The scanner computes VWAP deviation %, RSI, volume ratio, and classifies
each stock into a trading signal.
"""
from __future__ import annotations

import asyncio
import logging
from typing import Any

import pandas as pd

from app import indicators as ind
from app.providers.base import DataProvider
from app.universe import (
    NIFTY_50,
    NIFTY_NEXT_50,
    US_STOCKS,
    US_STOCK_NAMES,
)

log = logging.getLogger("vwap_scanner")

NSE_VWAP_UNIVERSE = list(dict.fromkeys(NIFTY_50 + NIFTY_NEXT_50))
US_VWAP_UNIVERSE = list(US_STOCKS)


async def scan_vwap(
    provider: DataProvider, symbol: str, name: str, market: str
) -> dict[str, Any] | None:
    """Scan one symbol for VWAP premium/discount.

    Returns None if data is insufficient.
    """
    try:
        intraday = await provider.get_intraday(symbol, "5m", 1)
    except Exception:
        return None

    if intraday.empty or len(intraday) < 5:
        return None

    close = intraday["Close"]
    current_price = float(close.iloc[-1])
    if current_price <= 0:
        return None

    vwap_series = ind.vwap(intraday)
    if vwap_series.empty:
        return None

    vwap_val = float(vwap_series.iloc[-1])
    if vwap_val <= 0:
        return None

    deviation_pct = round(((current_price - vwap_val) / vwap_val) * 100, 2)

    # RSI for context
    rsi_series = ind.rsi(close, 14)
    rsi_val = (
        round(float(rsi_series.iloc[-1]), 1)
        if not rsi_series.empty and not pd.isna(rsi_series.iloc[-1])
        else 50.0
    )

    # Volume ratio: last bar vs average
    volume = intraday["Volume"]
    avg_vol = float(volume.iloc[:-1].tail(20).mean()) if len(volume) > 1 else 0.0
    last_vol = float(volume.iloc[-1]) if len(volume) >= 1 else 0.0
    vol_ratio = round(last_vol / avg_vol, 2) if avg_vol > 0 else 0.0

    # Day range
    day_high = float(intraday["High"].max())
    day_low = float(intraday["Low"].min())
    day_range_pct = round(((day_high - day_low) / day_low) * 100, 2) if day_low > 0 else 0.0

    # Position within day range (0 = at low, 1 = at high)
    range_pos = round((current_price - day_low) / (day_high - day_low), 4) if day_high > day_low else 0.5

    # Classify signal
    if deviation_pct > 1.5 and rsi_val > 70:
        signal = "overbought_premium"
        action = "Potential reversal — overbought above VWAP"
    elif deviation_pct > 1.0:
        signal = "premium"
        action = "Trading at premium to VWAP — momentum long or fade"
    elif deviation_pct < -1.5 and rsi_val < 30:
        signal = "oversold_discount"
        action = "Potential bounce — oversold below VWAP"
    elif deviation_pct < -1.0:
        signal = "discount"
        action = "Trading at discount to VWAP — mean-reversion long or breakdown"
    else:
        signal = "neutral"
        action = "Near VWAP — wait for breakout"

    currency = "$" if market == "us" else "₹"

    return {
        "symbol": symbol,
        "name": name,
        "market": market,
        "current_price": round(current_price, 2),
        "vwap": round(vwap_val, 2),
        "deviation_pct": deviation_pct,
        "deviation_dir": "premium" if deviation_pct > 0 else "discount" if deviation_pct < 0 else "neutral",
        "rsi": rsi_val,
        "volume_ratio": vol_ratio,
        "day_high": round(day_high, 2),
        "day_low": round(day_low, 2),
        "day_range_pct": day_range_pct,
        "range_position": range_pos,
        "signal": signal,
        "action": action,
        "currency": currency,
    }


async def scan_all_vwap(
    provider: DataProvider,
    symbols: list[str],
    market: str,
    min_deviation: float = 0.5,
) -> list[dict[str, Any]]:
    """Scan all symbols in parallel for VWAP deviations."""
    sem = asyncio.Semaphore(10)
    name_map = US_STOCK_NAMES if market == "us" else {}

    async def _scan(sym: str) -> dict[str, Any] | None:
        async with sem:
            try:
                name = name_map.get(sym, sym)
                return await scan_vwap(provider, sym, name, market)
            except Exception as e:
                log.warning("Failed to scan VWAP for %s: %s", sym, e)
                return None

    results = await asyncio.gather(*[_scan(s) for s in symbols])
    filtered = [r for r in results if r is not None and abs(r["deviation_pct"]) >= min_deviation]
    filtered.sort(key=lambda d: abs(d["deviation_pct"]), reverse=True)
    return filtered
