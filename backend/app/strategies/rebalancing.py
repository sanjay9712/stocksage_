"""Portfolio rebalancing suggestions.

Analyzes the user's current holdings against a target allocation and
generates buy/sell suggestions to rebalance. Supports:
- Equal-weight rebalancing
- Custom target weights
- Risk-parity (inverse volatility) allocation
- Drift calculation and rebalancing trade generation
"""
from __future__ import annotations

import asyncio
import logging
import math
from typing import Any

import numpy as np
import pandas as pd

from app.providers.base import DataProvider

log = logging.getLogger("rebalancing")

TRADING_DAYS = 252


async def compute_rebalancing(
    provider: DataProvider,
    holdings: list[dict],
    target_allocation: dict[str, float] | None = None,
    method: str = "equal_weight",
    threshold_pct: float = 5.0,
) -> dict[str, Any]:
    """Compute rebalancing suggestions for a portfolio.

    Args:
        provider: Data provider for price data
        holdings: List of {symbol, quantity, avg_price} dicts
        target_allocation: Optional dict of {symbol: target_weight}
        method: "equal_weight", "custom", or "risk_parity"
        threshold_pct: Minimum drift to trigger rebalancing (default 5%)
    """
    if not holdings:
        return {"error": "No holdings to rebalance"}

    holdings = [h for h in holdings if h.get("quantity", 0) > 0]
    if not holdings:
        return {"error": "No active holdings"}

    # Fetch current prices
    sem = asyncio.Semaphore(8)

    async def _get_price(symbol: str) -> float:
        async with sem:
            try:
                df = await provider.get_daily_history(symbol, 5)
                if not df.empty:
                    return float(df["Close"].iloc[-1])
            except Exception:
                pass
        return 0.0

    symbols = [h["symbol"] for h in holdings]
    prices = await asyncio.gather(*[_get_price(s) for s in symbols])
    price_map = dict(zip(symbols, prices))

    # Compute current values
    positions = []
    total_value = 0.0
    for h in holdings:
        sym = h["symbol"]
        price = price_map.get(sym, h.get("avg_price", 0))
        value = price * h["quantity"]
        total_value += value
        positions.append({
            "symbol": sym,
            "quantity": h["quantity"],
            "current_price": round(price, 2),
            "current_value": round(value, 2),
        })

    if total_value <= 0:
        return {"error": "Portfolio has zero value"}

    # Current weights
    for p in positions:
        p["current_weight"] = round(p["current_value"] / total_value, 4)

    # Compute target weights
    if method == "custom" and target_allocation:
        # Use provided targets, normalize to sum to 1
        total_target = sum(target_allocation.values())
        if total_target > 0:
            for sym in symbols:
                p = next((x for x in positions if x["symbol"] == sym), None)
                if p:
                    p["target_weight"] = round(target_allocation.get(sym, 0) / total_target, 4)
                else:
                    positions.append({
                        "symbol": sym,
                        "quantity": 0,
                        "current_price": price_map.get(sym, 0),
                        "current_value": 0,
                        "current_weight": 0,
                        "target_weight": round(target_allocation.get(sym, 0) / total_target, 4),
                    })
        else:
            method = "equal_weight"

    if method == "risk_parity":
        # Fetch volatility for each position
        async def _get_vol(symbol: str) -> float:
            async with sem:
                try:
                    df = await provider.get_daily_history(symbol, 60)
                    if not df.empty and len(df) >= 20:
                        returns = df["Close"].pct_change().dropna()
                        return float(returns.std() * math.sqrt(TRADING_DAYS))
                except Exception:
                    pass
            return 0.20  # default 20% vol

        vols = await asyncio.gather(*[_get_vol(s) for s in symbols])
        vol_map = dict(zip(symbols, vols))

        # Inverse volatility weighting
        inv_vols = {s: 1 / max(v, 0.01) for s, v in vol_map.items()}
        total_inv_vol = sum(inv_vols.values())
        for p in positions:
            p["target_weight"] = round(inv_vols.get(p["symbol"], 0) / total_inv_vol, 4)
            p["volatility"] = round(vol_map.get(p["symbol"], 0.20) * 100, 2)

    if method == "equal_weight" or not any("target_weight" in p for p in positions):
        n = len(positions)
        for p in positions:
            p["target_weight"] = round(1.0 / n, 4)

    # Compute drift and rebalancing trades
    trades = []
    total_buy = 0.0
    total_sell = 0.0

    for p in positions:
        current_w = p["current_weight"]
        target_w = p["target_weight"]
        drift = target_w - current_w
        drift_pct = drift * 100

        target_value = total_value * target_w
        trade_value = target_value - p["current_value"]
        price = p["current_price"]

        trade_shares = int(trade_value / price) if price > 0 else 0
        action = "buy" if trade_value > 0 else "sell" if trade_value < 0 else "hold"
        needs_rebalance = abs(drift_pct) >= threshold_pct

        p["drift_pct"] = round(drift_pct, 2)
        p["target_value"] = round(target_value, 2)
        p["trade_value"] = round(abs(trade_value), 2)
        p["trade_shares"] = abs(trade_shares)
        p["action"] = action
        p["needs_rebalance"] = needs_rebalance

        if needs_rebalance and action != "hold":
            trades.append({
                "symbol": p["symbol"],
                "action": action,
                "shares": abs(trade_shares),
                "value": round(abs(trade_value), 2),
                "current_weight": round(current_w * 100, 2),
                "target_weight": round(target_w * 100, 2),
                "drift_pct": round(drift_pct, 2),
            })
            if action == "buy":
                total_buy += abs(trade_value)
            else:
                total_sell += abs(trade_value)

    # Max drift for summary
    max_drift = max(abs(p["drift_pct"]) for p in positions) if positions else 0
    avg_drift = sum(abs(p["drift_pct"]) for p in positions) / len(positions) if positions else 0
    needs_rebalancing = any(p["needs_rebalance"] for p in positions)

    # Sort positions by drift magnitude
    positions.sort(key=lambda x: abs(x["drift_pct"]), reverse=True)
    trades.sort(key=lambda x: abs(x["drift_pct"]), reverse=True)

    return {
        "total_value": round(total_value, 2),
        "num_positions": len(positions),
        "method": method,
        "threshold_pct": threshold_pct,
        "needs_rebalancing": needs_rebalancing,
        "max_drift_pct": round(max_drift, 2),
        "avg_drift_pct": round(avg_drift, 2),
        "total_buy_value": round(total_buy, 2),
        "total_sell_value": round(total_sell, 2),
        "net_trade_value": round(total_buy - total_sell, 2),
        "trades": trades,
        "positions": positions,
    }
