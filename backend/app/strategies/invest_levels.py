"""Investment entry/exit levels for stocks and ETFs.

Computes swing-trade and long-term entry/stop-loss/target levels from:
- 50-EMA and 200-EMA (trend + value entry zones)
- ATR(14) (for stop-loss placement)
- Floor pivots (P, R1, R2, S1, S2)
- 52-week high/low (target and support context)

These are INVESTMENT levels (days/weeks), not intraday scalping levels.
The intraday screener handles same-day entry/SL/target separately.
"""
from __future__ import annotations

import pandas as pd

from app import indicators as ind


def compute_invest_levels(daily: pd.DataFrame, symbol: str, high_52w: float | None = None,
                          low_52w: float | None = None, currency: str = "₹") -> dict:
    """Compute investment entry/SL/target for a stock or ETF.

    Args:
        daily: daily OHLCV DataFrame (at least 200 rows for 200-EMA).
        symbol: stock symbol for display.
        high_52w: 52-week high (optional, computed from daily if not given).
        low_52w: 52-week low (optional).
        currency: currency symbol for display strings ("₹" or "$").

    Returns dict with entry, stop_loss, target, risk_reward, and explanation.
    """
    if daily is None or daily.empty or len(daily) < 30:
        return _empty(symbol)

    close = daily["Close"].dropna()
    high = daily["High"].dropna()
    low = daily["Low"].dropna()

    if len(close) < 30:
        return _empty(symbol)

    # Indicators
    ema50 = ind.ema(close, 50)
    ema200 = ind.ema(close, 200) if len(close) >= 200 else ind.ema(close, min(len(close), 50))
    atr = ind.atr(daily, 14)
    piv = ind.pivots(
        float(high.iloc[-1]), float(low.iloc[-1]), float(close.iloc[-1])
    )

    last_price = float(close.iloc[-1])
    ema50_val = float(ema50.iloc[-1])
    ema200_val = float(ema200.iloc[-1]) if len(ema200) > 0 else ema50_val
    atr_val = float(atr.iloc[-1]) if atr is not None and len(atr) > 0 else 0.0

    # 52-week range
    if high_52w is None or low_52w is None:
        lookback = min(len(close), 252)
        high_52w = float(close.tail(lookback).max())
        low_52w = float(close.tail(lookback).min())

    # Swing low (20-bar low) for stop-loss
    swing_low = float(low.tail(20).min())
    swing_high = float(high.tail(20).max())

    # Entry zone: near 50-EMA (momentum entry) or 200-EMA (value entry)
    # If price is above 200-EMA, trend is up → entry near 50-EMA
    # If price is below 200-EMA, wait for reclaim
    trend_up = last_price > ema200_val

    if trend_up:
        entry = ema50_val  # momentum entry at 50-EMA pullback
        entry_label = "50-EMA (momentum pullback entry)"
    else:
        entry = ema200_val  # value entry near 200-EMA
        entry_label = "200-EMA (value entry — price below 200-EMA, wait for reclaim)"

    # Stop-loss: below recent swing low or 200-EMA − 1×ATR (whichever is tighter)
    sl_candidate_1 = swing_low
    sl_candidate_2 = ema200_val - atr_val
    stop_loss = min(sl_candidate_1, sl_candidate_2)

    # Target: pivot R2 or 52-week high (whichever is closer/achievable)
    target_candidate_1 = piv["r2"]
    target_candidate_2 = high_52w
    target = max(target_candidate_1, target_candidate_2)

    # Risk:reward
    risk = entry - stop_loss
    reward = target - entry
    rr = reward / risk if risk > 0 else 0.0

    return {
        "symbol": symbol.upper(),
        "last_price": round(last_price, 2),
        "entry": round(entry, 2),
        "entry_label": entry_label,
        "stop_loss": round(stop_loss, 2),
        "stop_loss_label": f"Below swing low {currency}{swing_low:.2f} or 200-EMA−ATR {currency}{sl_candidate_2:.2f}",
        "target": round(target, 2),
        "target_label": f"Pivot R2 {currency}{piv['r2']:.2f} or 52w-high {currency}{high_52w:.2f}",
        "risk_reward": round(rr, 2),
        "trend": "up" if trend_up else "down/below-200EMA",
        "ema50": round(ema50_val, 2),
        "ema200": round(ema200_val, 2),
        "atr14": round(atr_val, 2),
        "52w_high": round(high_52w, 2),
        "52w_low": round(low_52w, 2),
        "swing_low_20": round(swing_low, 2),
        "swing_high_20": round(swing_high, 2),
        "pivots": {k: round(v, 2) for k, v in piv.items()},
        "explanation": (
            f"{symbol.upper()} is {'above' if trend_up else 'below'} its 200-EMA ({currency}{ema200_val:.2f}). "
            f"{'Trend is up' if trend_up else 'Price below 200-EMA — cautious, wait for reclaim'}. "
            f"Entry zone: {currency}{entry:.2f} ({entry_label}). "
            f"Stop-loss: {currency}{stop_loss:.2f} (below 20-bar swing low). "
            f"Target: {currency}{target:.2f}. "
            f"Risk:reward = 1:{rr:.2f}."
        ),
        "caveats": [
            "These are investment levels (days/weeks), not intraday.",
            "Always verify on your charting platform before executing.",
            "If the stock gaps below stop-loss, exit — don't average down.",
            "Past performance does not guarantee future results.",
        ],
    }


def _empty(symbol: str) -> dict:
    return {
        "symbol": symbol.upper(),
        "last_price": 0.0,
        "entry": 0.0,
        "entry_label": "",
        "stop_loss": 0.0,
        "stop_loss_label": "",
        "target": 0.0,
        "target_label": "",
        "risk_reward": 0.0,
        "trend": "unknown",
        "ema50": 0.0,
        "ema200": 0.0,
        "atr14": 0.0,
        "52w_high": 0.0,
        "52w_low": 0.0,
        "swing_low_20": 0.0,
        "swing_high_20": 0.0,
        "pivots": {},
        "explanation": f"Insufficient data for {symbol}.",
        "caveats": [],
    }
