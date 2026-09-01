"""Opening Range Breakout scanner — OR-5, OR-15, OR-30 variants.

Scans the stock universe for stocks breaking out of their opening range
(first 5, 15, or 30 minutes of trading). The opening range breakout (ORB)
is a classic intraday strategy:

- **Long breakout**: price closes above the OR high on above-average volume.
- **Short breakdown**: price closes below the OR low on above-average volume.

Supports both NSE (09:15 IST open) and US (09:30 ET open) markets with
proper timezone handling.
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

log = logging.getLogger("or_scanner")

NSE_OR_UNIVERSE = list(dict.fromkeys(NIFTY_50 + NIFTY_NEXT_50))
US_OR_UNIVERSE = list(US_STOCKS)

# Market open times and timezone for OR computation
MARKET_CONFIG = {
    "in": {"open": "09:15", "tz": "Asia/Kolkata"},
    "us": {"open": "09:30", "tz": "US/Eastern"},
}

# OR duration in minutes → (start_time, end_time) per market
OR_DURATIONS = {
    5: 5,
    15: 15,
    30: 30,
}


def _get_or_window(intraday: pd.DataFrame, market: str, or_minutes: int) -> tuple[float, float, pd.DataFrame] | None:
    """Extract the opening range high/low for the given duration.

    Returns (or_high, or_low, after_or_bars) or None if the OR window
    hasn't completed yet.
    """
    if intraday.empty:
        return None

    cfg = MARKET_CONFIG.get(market, MARKET_CONFIG["in"])
    tz = cfg["tz"]
    open_time = cfg["open"]

    # Convert to local timezone
    local_idx = intraday.index
    if hasattr(local_idx, "tz_convert"):
        local_idx = local_idx.tz_convert(tz)
    else:
        return None

    times = local_idx.time
    open_t = pd.to_datetime(open_time, format="%H:%M").time()
    end_minutes = int(open_time.split(":")[0]) * 60 + int(open_time.split(":")[1]) + or_minutes
    end_t = pd.to_datetime(f"{end_minutes // 60:02d}:{end_minutes % 60:02d}", format="%H:%M").time()

    # OR window: from market open to open + or_minutes
    time_series = pd.Series(times, index=intraday.index)
    or_mask = time_series.apply(lambda t: open_t <= t < end_t)
    or_bars = intraday[or_mask]

    if or_bars.empty:
        return None

    or_high = float(or_bars["High"].max())
    or_low = float(or_bars["Low"].min())

    # Bars after the OR window
    after_mask = time_series.apply(lambda t: t >= end_t)
    after_bars = intraday[after_mask]

    return or_high, or_low, after_bars


def _detect_breakout(
    after_bars: pd.DataFrame,
    or_high: float,
    or_low: float,
    avg_vol: float,
    vol_ratio_min: float = 1.5,
) -> dict | None:
    """Find the first breakout bar after the OR window.

    Detects both long (close > or_high) and short (close < or_low) breakouts
    on volume >= vol_ratio_min * avg_vol.
    """
    if after_bars.empty or avg_vol <= 0:
        return None

    for ts, bar in after_bars.iterrows():
        vol_ratio = float(bar["Volume"]) / avg_vol if avg_vol > 0 else 0.0
        if vol_ratio < vol_ratio_min:
            continue

        if float(bar["Close"]) > or_high:
            return {
                "ts": str(ts),
                "side": "long",
                "close": float(bar["Close"]),
                "high": float(bar["High"]),
                "low": float(bar["Low"]),
                "volume": float(bar["Volume"]),
                "volume_ratio": round(vol_ratio, 2),
            }
        if float(bar["Close"]) < or_low:
            return {
                "ts": str(ts),
                "side": "short",
                "close": float(bar["Close"]),
                "high": float(bar["High"]),
                "low": float(bar["Low"]),
                "volume": float(bar["Volume"]),
                "volume_ratio": round(vol_ratio, 2),
            }

    return None


async def scan_opening_range(
    provider: DataProvider,
    symbol: str,
    name: str,
    market: str,
    or_minutes: int,
) -> dict[str, Any] | None:
    """Scan one symbol for opening range breakout.

    Returns None if insufficient data or no breakout detected.
    """
    try:
        intraday = await provider.get_intraday(symbol, "5m", 1)
        daily = await provider.get_daily_history(symbol, 22)
    except Exception:
        return None

    if intraday.empty or len(intraday) < 3:
        return None

    or_result = _get_or_window(intraday, market, or_minutes)
    if or_result is None:
        return None

    or_high, or_low, after_bars = or_result
    avg_vol = ind.avg_volume(intraday, 20) if not intraday.empty and len(intraday) >= 20 else (ind.avg_volume(daily, 20) if not daily.empty else 0.0)

    breakout = _detect_breakout(after_bars, or_high, or_low, avg_vol)
    if breakout is None:
        return None

    # Compute ATR for stop/target
    atr_val = 0.0
    if not daily.empty and len(daily) >= 15:
        atr_series = ind.atr(daily, 14)
        if not atr_series.empty and not pd.isna(atr_series.iloc[-1]):
            atr_val = float(atr_series.iloc[-1])

    current_price = float(intraday["Close"].iloc[-1])
    or_range_pct = round(((or_high - or_low) / or_low) * 100, 2) if or_low > 0 else 0.0

    if breakout["side"] == "long":
        entry = or_high
        stop_loss = or_low
        target1 = round(entry + atr_val, 2) if atr_val > 0 else round(entry * 1.01, 2)
        target2 = round(entry + 2 * atr_val, 2) if atr_val > 0 else round(entry * 1.02, 2)
        risk_reward = round((target1 - entry) / (entry - stop_loss), 2) if entry > stop_loss else 0.0
    else:
        entry = or_low
        stop_loss = or_high
        target1 = round(entry - atr_val, 2) if atr_val > 0 else round(entry * 0.99, 2)
        target2 = round(entry - 2 * atr_val, 2) if atr_val > 0 else round(entry * 0.98, 2)
        risk_reward = round((entry - target1) / (stop_loss - entry), 2) if stop_loss > entry else 0.0

    # Trend filter
    trend_up = True
    if not daily.empty and len(daily) >= 20:
        ema20 = ind.ema(daily["Close"], 20)
        trend_up = bool(daily["Close"].iloc[-1] > ema20.iloc[-1])

    confidence = round(
        min(breakout["volume_ratio"] / 3.0, 1.0) * 0.5 +
        (1.0 if (breakout["side"] == "long" and trend_up) or (breakout["side"] == "short" and not trend_up) else 0.3) * 0.5,
        3,
    )

    currency = "$" if market == "us" else "₹"

    return {
        "symbol": symbol,
        "name": name,
        "market": market,
        "or_minutes": or_minutes,
        "or_high": round(or_high, 2),
        "or_low": round(or_low, 2),
        "or_range_pct": or_range_pct,
        "side": breakout["side"],
        "entry": round(entry, 2),
        "stop_loss": round(stop_loss, 2),
        "target1": target1,
        "target2": target2,
        "risk_reward": risk_reward,
        "current_price": round(current_price, 2),
        "breakout_time": breakout["ts"],
        "breakout_price": round(breakout["close"], 2),
        "volume_ratio": breakout["volume_ratio"],
        "atr": round(atr_val, 2),
        "trend_up": trend_up,
        "confidence": confidence,
        "currency": currency,
    }


async def scan_all_opening_range(
    provider: DataProvider,
    symbols: list[str],
    market: str,
    or_minutes: int,
) -> list[dict[str, Any]]:
    """Scan all symbols for OR breakouts in parallel."""
    sem = asyncio.Semaphore(10)
    name_map = US_STOCK_NAMES if market == "us" else {}

    async def _scan(sym: str) -> dict[str, Any] | None:
        async with sem:
            try:
                name = name_map.get(sym, sym)
                return await scan_opening_range(provider, sym, name, market, or_minutes)
            except Exception as e:
                log.warning("Failed to scan OR for %s: %s", sym, e)
                return None

    results = await asyncio.gather(*[_scan(s) for s in symbols])
    filtered = [r for r in results if r is not None]
    filtered.sort(key=lambda d: d["confidence"], reverse=True)
    return filtered
