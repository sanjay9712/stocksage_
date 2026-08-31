"""Signal alerts — generates trading signals from technical conditions.

Scans the stock universe for configurable signal types:
- RSI oversold/overbought
- EMA crossover (golden/death cross on fast timeframe)
- Bollinger Band squeeze/breakout
- Volume spike (unusual volume)
- Donchian breakout (new highs/lows)
- MACD crossover

Each alert generates a signal with entry, stop, target, and confidence.
"""
from __future__ import annotations

import asyncio
import logging
from typing import Any

import numpy as np
import pandas as pd

from app import indicators as ind
from app.providers.base import DataProvider
from app.universe import NIFTY_50, NIFTY_NEXT_50, US_STOCKS, US_STOCK_NAMES

log = logging.getLogger("signal_alerts")

NSE_SIGNAL_UNIVERSE = list(dict.fromkeys(NIFTY_50 + NIFTY_NEXT_50))
US_SIGNAL_UNIVERSE = list(US_STOCKS)

SIGNAL_TYPES = [
    "rsi_oversold",
    "rsi_overbought",
    "ema_cross_up",
    "ema_cross_down",
    "bb_squeeze",
    "volume_spike",
    "donchian_breakout",
    "macd_cross_up",
]


async def scan_signal(
    provider: DataProvider,
    symbol: str,
    name: str,
    market: str,
    signal_types: list[str] | None = None,
) -> list[dict[str, Any]]:
    """Scan one symbol for all configured signal types.

    Returns a list of signal dicts (may be empty if no signals triggered).
    """
    signal_types = signal_types or SIGNAL_TYPES
    signals: list[dict[str, Any]] = []

    try:
        df = await provider.get_daily_history(symbol, 120)
    except Exception:
        return signals

    if df.empty or len(df) < 50:
        return signals

    df = df.dropna(subset=["Close"]).sort_index()
    close = df["Close"]
    volume = df.get("Volume", pd.Series(dtype=float))
    last_price = float(close.iloc[-1])

    # RSI signals
    if "rsi_oversold" in signal_types or "rsi_overbought" in signal_types:
        rsi = ind.rsi(close, 14)
        rsi_val = float(rsi.iloc[-1]) if not rsi.empty and not np.isnan(rsi.iloc[-1]) else 50.0

        if "rsi_oversold" in signal_types and rsi_val < 30:
            stop = last_price * 0.97
            target = last_price * 1.05
            signals.append({
                "symbol": symbol,
                "name": name,
                "market": market,
                "signal_type": "rsi_oversold",
                "side": "long",
                "price": round(last_price, 2),
                "rsi": round(rsi_val, 1),
                "entry": round(last_price, 2),
                "stop_loss": round(stop, 2),
                "target": round(target, 2),
                "confidence": min(0.9, (30 - rsi_val) / 30 + 0.5),
                "description": f"RSI oversold ({rsi_val:.1f}) — potential bounce",
            })

        if "rsi_overbought" in signal_types and rsi_val > 70:
            stop = last_price * 1.03
            target = last_price * 0.95
            signals.append({
                "symbol": symbol,
                "name": name,
                "market": market,
                "signal_type": "rsi_overbought",
                "side": "short",
                "price": round(last_price, 2),
                "rsi": round(rsi_val, 1),
                "entry": round(last_price, 2),
                "stop_loss": round(stop, 2),
                "target": round(target, 2),
                "confidence": min(0.9, (rsi_val - 70) / 30 + 0.5),
                "description": f"RSI overbought ({rsi_val:.1f}) — potential reversal",
            })

    # EMA crossover
    if "ema_cross_up" in signal_types or "ema_cross_down" in signal_types:
        ema9 = ind.ema(close, 9)
        ema21 = ind.ema(close, 21)
        if len(ema9) >= 2 and len(ema21) >= 2:
            curr_diff = float(ema9.iloc[-1] - ema21.iloc[-1])
            prev_diff = float(ema9.iloc[-2] - ema21.iloc[-2])

            if "ema_cross_up" in signal_types and prev_diff <= 0 < curr_diff:
                stop = last_price * 0.98
                target = last_price * 1.06
                signals.append({
                    "symbol": symbol,
                    "name": name,
                    "market": market,
                    "signal_type": "ema_cross_up",
                    "side": "long",
                    "price": round(last_price, 2),
                    "entry": round(last_price, 2),
                    "stop_loss": round(stop, 2),
                    "target": round(target, 2),
                    "confidence": 0.65,
                    "description": "EMA 9/21 bullish crossover",
                })

            if "ema_cross_down" in signal_types and prev_diff >= 0 > curr_diff:
                stop = last_price * 1.02
                target = last_price * 0.94
                signals.append({
                    "symbol": symbol,
                    "name": name,
                    "market": market,
                    "signal_type": "ema_cross_down",
                    "side": "short",
                    "price": round(last_price, 2),
                    "entry": round(last_price, 2),
                    "stop_loss": round(stop, 2),
                    "target": round(target, 2),
                    "confidence": 0.65,
                    "description": "EMA 9/21 bearish crossover",
                })

    # Bollinger Band squeeze
    if "bb_squeeze" in signal_types:
        bb = ind.bollinger_bands(close, 20, 2.0)
        bandwidth = (bb["upper"] - bb["lower"]) / bb["middle"]
        if len(bandwidth) >= 20:
            avg_bw = float(bandwidth.iloc[-20:].mean())
            curr_bw = float(bandwidth.iloc[-1])
            if avg_bw > 0 and curr_bw < avg_bw * 0.6:
                signals.append({
                    "symbol": symbol,
                    "name": name,
                    "market": market,
                    "signal_type": "bb_squeeze",
                    "side": "watch",
                    "price": round(last_price, 2),
                    "entry": None,
                    "stop_loss": None,
                    "target": None,
                    "confidence": 0.5,
                    "description": f"BB squeeze — bandwidth {curr_bw:.3f} vs avg {avg_bw:.3f}",
                })

    # Volume spike
    if "volume_spike" in signal_types and not volume.empty and len(volume) >= 20:
        avg_vol = float(volume.iloc[-20:].mean())
        curr_vol = float(volume.iloc[-1])
        if avg_vol > 0 and curr_vol > avg_vol * 2.5:
            vol_ratio = curr_vol / avg_vol
            rsi = ind.rsi(close, 14)
            rsi_val = float(rsi.iloc[-1]) if not rsi.empty else 50.0
            side = "long" if rsi_val > 50 else "short"
            stop = last_price * (0.97 if side == "long" else 1.03)
            target = last_price * (1.05 if side == "long" else 0.95)
            signals.append({
                "symbol": symbol,
                "name": name,
                "market": market,
                "signal_type": "volume_spike",
                "side": side,
                "price": round(last_price, 2),
                "volume_ratio": round(vol_ratio, 1),
                "entry": round(last_price, 2),
                "stop_loss": round(stop, 2),
                "target": round(target, 2),
                "confidence": min(0.85, 0.5 + (vol_ratio - 2.5) * 0.1),
                "description": f"Volume spike {vol_ratio:.1f}x average",
            })

    # Donchian breakout
    if "donchian_breakout" in signal_types:
        lookback = 20
        if len(close) >= lookback + 1:
            rolling_high = close.iloc[-(lookback+1):-1].max()
            rolling_low = close.iloc[-(lookback+1):-1].min()
            if last_price > rolling_high:
                stop = float(rolling_low)
                target = last_price * 1.10
                signals.append({
                    "symbol": symbol,
                    "name": name,
                    "market": market,
                    "signal_type": "donchian_breakout",
                    "side": "long",
                    "price": round(last_price, 2),
                    "entry": round(last_price, 2),
                    "stop_loss": round(stop, 2),
                    "target": round(target, 2),
                    "confidence": 0.7,
                    "description": f"Donchian breakout above {rolling_high:.2f}",
                })

    # MACD crossover
    if "macd_cross_up" in signal_types:
        ema12 = ind.ema(close, 12)
        ema26 = ind.ema(close, 26)
        macd = ema12 - ema26
        signal_line = ind.ema(macd, 9)
        if len(macd) >= 2 and len(signal_line) >= 2:
            curr_diff = float(macd.iloc[-1] - signal_line.iloc[-1])
            prev_diff = float(macd.iloc[-2] - signal_line.iloc[-2])
            if prev_diff <= 0 < curr_diff:
                stop = last_price * 0.97
                target = last_price * 1.05
                signals.append({
                    "symbol": symbol,
                    "name": name,
                    "market": market,
                    "signal_type": "macd_cross_up",
                    "side": "long",
                    "price": round(last_price, 2),
                    "entry": round(last_price, 2),
                    "stop_loss": round(stop, 2),
                    "target": round(target, 2),
                    "confidence": 0.6,
                    "description": "MACD bullish crossover",
                })

    return signals


async def scan_all_signals(
    provider: DataProvider,
    symbols: list[tuple[str, str]],
    market: str,
    signal_types: list[str] | None = None,
) -> list[dict[str, Any]]:
    """Scan all symbols in a universe for signal alerts.

    Args:
        provider: Data provider
        symbols: List of (symbol, name) tuples
        market: "in" or "us"
        signal_types: Filter for specific signal types
    """
    sem = asyncio.Semaphore(10)

    async def _scan(sym: str, name: str):
        async with sem:
            return await scan_signal(provider, sym, name, market, signal_types)

    results = await asyncio.gather(*[_scan(s, n) for s, n in symbols], return_exceptions=True)

    all_signals: list[dict[str, Any]] = []
    for result in results:
        if isinstance(result, list):
            all_signals.extend(result)

    # Sort by confidence descending
    all_signals.sort(key=lambda x: x.get("confidence", 0), reverse=True)
    return all_signals
