"""Pre-market / opening gap scanner.

Scans the stock universe for significant gaps between the previous day's
close and the current/opening price. Gaps often signal news catalysts,
earnings reactions, or overnight sentiment shifts. Traders use gap scans
to find:

- **Gap-up plays**: buy continuation above the gap high, or fade (short)
  if the gap fills.
- **Gap-down plays**: short continuation below the gap low, or buy if
  the gap fills and reverses.

The scanner computes gap %, direction, volume ratio vs 20-day average,
ATR-based expected move, and previous day high/low for trade planning.
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
    get_us_stocks,
)

log = logging.getLogger("gap_scanner")


# ---------------------------------------------------------------------------
# Universes
# ---------------------------------------------------------------------------

NSE_GAP_UNIVERSE = list(dict.fromkeys(NIFTY_50 + NIFTY_NEXT_50))  # dedupe
US_GAP_UNIVERSE = list(US_STOCKS)


# ---------------------------------------------------------------------------
# Single-symbol gap scan
# ---------------------------------------------------------------------------

async def scan_gap(
    provider: DataProvider, symbol: str, name: str, market: str
) -> dict[str, Any] | None:
    """Scan one symbol for gap statistics.

    Returns None if data is insufficient.
    """
    # Fetch 22 days of daily history for volume average + ATR + prev close.
    daily = await provider.get_daily_history(symbol, 22)
    if daily.empty or len(daily) < 2:
        return None

    close = daily["Close"]
    high = daily["High"]
    low = daily["Low"]
    volume = daily["Volume"]

    prev_close = round(float(close.iloc[-2]), 2)
    prev_high = round(float(high.iloc[-2]), 2)
    prev_low = round(float(low.iloc[-2]), 2)
    prev_volume = float(volume.iloc[-2]) if len(volume) >= 2 else 0.0

    # Current price: try quote first, fall back to last daily close.
    current_price = None
    try:
        quote = await provider.get_quote(symbol)
        current_price = quote.price
    except Exception:
        pass

    if current_price is None or current_price <= 0:
        current_price = round(float(close.iloc[-1]), 2)

    if prev_close <= 0:
        return None

    gap_pct = round(((current_price - prev_close) / prev_close) * 100, 2)
    gap_dir = "up" if gap_pct > 0 else "down" if gap_pct < 0 else "flat"

    # Volume ratio: current volume vs 20-day average.
    avg_vol_20 = float(volume.iloc[:-1].tail(20).mean()) if len(volume) > 1 else 0.0
    current_vol = float(volume.iloc[-1]) if len(volume) >= 1 else 0.0
    vol_ratio = round(current_vol / avg_vol_20, 2) if avg_vol_20 > 0 else 0.0

    # ATR for expected move.
    atr_series = ind.atr(daily, 14)
    atr_val = round(float(atr_series.iloc[-1]), 2) if not atr_series.empty and not pd.isna(atr_series.iloc[-1]) else 0.0
    expected_move_pct = round((atr_val / current_price) * 100, 2) if current_price > 0 else 0.0

    # Gap fill target (previous close) and gap range.
    gap_high = max(current_price, prev_close)
    gap_low = min(current_price, prev_close)

    # Strategy suggestion based on gap direction and magnitude.
    abs_gap = abs(gap_pct)
    if gap_dir == "up":
        if abs_gap >= 3:
            strategy = "Strong gap-up — watch for continuation above ${:.2f} or reversal to fill gap at {:.2f}".format(gap_high, prev_close)
            play = "continuation_long"
        else:
            strategy = "Mild gap-up — watch VWAP for direction"
            play = "watch"
    elif gap_dir == "down":
        if abs_gap >= 3:
            strategy = "Strong gap-down — watch for breakdown below {:.2f} or bounce to fill gap at {:.2f}".format(gap_low, prev_close)
            play = "continuation_short"
        else:
            strategy = "Mild gap-down — watch VWAP for direction"
            play = "watch"
    else:
        strategy = "No significant gap"
        play = "none"

    # Classify gap magnitude.
    if abs_gap >= 5:
        magnitude = "extreme"
    elif abs_gap >= 3:
        magnitude = "large"
    elif abs_gap >= 1:
        magnitude = "moderate"
    elif abs_gap >= 0.3:
        magnitude = "small"
    else:
        magnitude = "none"

    currency = "$" if market == "us" else "₹"

    return {
        "symbol": symbol,
        "name": name,
        "market": market,
        "current_price": current_price,
        "prev_close": prev_close,
        "prev_high": prev_high,
        "prev_low": prev_low,
        "gap_pct": gap_pct,
        "gap_dir": gap_dir,
        "magnitude": magnitude,
        "volume_ratio": vol_ratio,
        "atr": atr_val,
        "expected_move_pct": expected_move_pct,
        "gap_high": round(gap_high, 2),
        "gap_low": round(gap_low, 2),
        "play": play,
        "strategy": strategy,
        "currency": currency,
    }


# ---------------------------------------------------------------------------
# Batch scan
# ---------------------------------------------------------------------------

async def scan_all_gaps(
    provider: DataProvider,
    symbols: list[str],
    market: str,
    min_gap_pct: float = 0.5,
) -> list[dict[str, Any]]:
    """Scan all symbols in parallel for gaps, filtered by minimum gap %.

    Returns sorted list (largest absolute gap first), excluding no-gap stocks.
    """
    sem = asyncio.Semaphore(10)

    # Build name lookup.
    name_map = US_STOCK_NAMES if market == "us" else {}

    async def _scan(sym: str) -> dict[str, Any] | None:
        async with sem:
            try:
                name = name_map.get(sym, sym)
                return await scan_gap(provider, sym, name, market)
            except Exception as e:
                log.warning("Failed to scan gap for %s: %s", sym, e)
                return None

    results = await asyncio.gather(*[_scan(s) for s in symbols])
    # Filter out None and insignificant gaps.
    filtered = [r for r in results if r is not None and abs(r["gap_pct"]) >= min_gap_pct]
    # Sort by absolute gap descending.
    filtered.sort(key=lambda d: abs(d["gap_pct"]), reverse=True)
    return filtered
