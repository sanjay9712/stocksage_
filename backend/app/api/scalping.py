"""Scalping + candlestick pattern API endpoints.

GET /api/scalping                  — today's scalp signals across the universe
GET /api/scalping/{symbol}         — scalp signal for a single symbol
GET /api/stock/{symbol}/candlestick — detected candlestick patterns on daily chart
GET /api/stock/{symbol}/multifactor — multi-factor score (momentum + value + quality)
"""
from __future__ import annotations

import asyncio

from fastapi import APIRouter, Depends

from app.api.auth import require_token
from app.api.cache import cached
from app.market_hours import is_nse_open, screen_cache_ttl
from app.providers.factory import get_provider
from app.providers.fundamentals import get_stock_fundamentals
from app.strategies import scalping as scalp_strat
from app.strategies import candlestick as candle
from app.strategies import multifactor as mf
from app.universe import get_universe
from app.config import settings

router = APIRouter()


@router.get("/scalping")
async def scalping_signals(_t: str = Depends(require_token)):
    """Scan the stock universe for scalping signals.

    Returns signals where a candlestick pattern aligned with the intraday
    trend and volume confirmation was detected. Cached 2 minutes (intraday data
    changes each bar but we don't want to hammer yfinance).
    """

    async def _fetch():
        provider = get_provider()
        symbols = get_universe(settings.universe)

        # Build company name lookup.
        name_map: dict[str, str] = {}
        try:
            from app.providers.nse_list import get_nse_stocks
            nse_stocks = await get_nse_stocks()
            for s in nse_stocks:
                name_map[s["symbol"]] = s.get("name", s["symbol"])
        except Exception:
            pass

        async def _eval(symbol: str):
            try:
                daily = await provider.get_daily_history(symbol, 60)
                intraday = await provider.get_intraday(symbol, settings.intraday_interval, 1)
            except Exception:
                return None, {"symbol": symbol, "reason": "Data fetch failed"}
            if daily.empty or intraday.empty:
                return None, {"symbol": symbol, "reason": "No data"}
            debug = scalp_strat.evaluate_scalp_debug(symbol, daily, intraday)
            if debug["signal"] is not None:
                signal = debug["signal"]
                return {
                    "symbol": signal.symbol,
                    "name": name_map.get(signal.symbol, signal.symbol),
                    "side": signal.side,
                    "entry": signal.entry,
                    "stop_loss": signal.stop_loss,
                    "target": signal.target,
                    "risk_reward": signal.risk_reward,
                    "confidence": signal.confidence,
                    "last_price": signal.last_price,
                    "atr": signal.atr,
                    "volume_ratio": signal.volume_ratio,
                    "trend": signal.trend,
                    "patterns": signal.patterns,
                    "pattern_bias": signal.pattern_bias,
                    "explanation": signal.explanation,
                    "caveats": signal.caveats,
                    "stochastic_k": signal.stochastic_k,
                    "stochastic_signal": signal.stochastic_signal,
                    "macd_histogram": signal.macd_histogram,
                    "adx_value": signal.adx_value,
                }, None
            # No signal — collect as near-miss with diagnostics.
            near_miss = {
                "symbol": symbol,
                "name": name_map.get(symbol, symbol),
                "reason": debug.get("reason", "Unknown"),
                "diagnostics": debug.get("diagnostics", {}),
            }
            return None, near_miss

        # Run scans concurrently (bounded to avoid rate limits).
        sem = asyncio.Semaphore(10)

        async def _bounded(symbol):
            async with sem:
                return await _eval(symbol)

        results = await asyncio.gather(*[_bounded(s) for s in symbols])
        signals = []
        near_misses = []
        data_errors = 0
        for sig, miss in results:
            if sig is not None:
                signals.append(sig)
            elif miss is not None:
                if "No data" in (miss.get("reason") or "") or "failed" in (miss.get("reason") or "").lower():
                    data_errors += 1
                else:
                    near_misses.append(miss)
        # Sort by confidence descending.
        signals.sort(key=lambda s: s["confidence"], reverse=True)
        # Sort near-misses: those with patterns found first.
        near_misses.sort(key=lambda m: len(m.get("diagnostics", {}).get("directional_patterns", [])), reverse=True)
        return {
            "signals": signals,
            "count": len(signals),
            "scan_summary": {
                "total_scanned": len(symbols),
                "signals_found": len(signals),
                "near_misses": len(near_misses),
                "data_errors": data_errors,
                "filters": scalp_strat.SCALP_FILTERS,
                "patterns_scanned": sorted(scalp_strat._DIRECITIONAL_PATTERNS),
            },
            "near_misses": near_misses[:15],  # top 15 near-misses for display
        }

    return await cached("scalping:signals", screen_cache_ttl(is_nse_open()), _fetch)


@router.get("/scalping/{symbol}")
async def scalping_signal(symbol: str, _t: str = Depends(require_token)):
    """Get a scalping signal for a single symbol."""
    symbol = symbol.strip().upper().replace(".NS", "").replace("NSE:", "")
    provider = get_provider()

    async def _fetch():
        daily = await provider.get_daily_history(symbol, 60)
        intraday = await provider.get_intraday(symbol, settings.intraday_interval, 1)
        if daily.empty or intraday.empty:
            return {"symbol": symbol, "signal": None, "message": "No data available."}
        signal = scalp_strat.evaluate_scalp(symbol, daily, intraday)
        if signal is None:
            return {
                "symbol": symbol,
                "signal": None,
                "message": "No scalping signal right now — no aligned candlestick pattern "
                           "with volume confirmation.",
            }
        # Look up company name.
        name = symbol
        try:
            from app.providers.nse_list import get_nse_stocks
            nse_stocks = await get_nse_stocks()
            for s in nse_stocks:
                if s["symbol"] == symbol:
                    name = s.get("name", symbol)
                    break
        except Exception:
            pass
        return {
            "symbol": symbol,
            "signal": {
                "symbol": signal.symbol,
                "name": name,
                "side": signal.side,
                "entry": signal.entry,
                "stop_loss": signal.stop_loss,
                "target": signal.target,
                "risk_reward": signal.risk_reward,
                "confidence": signal.confidence,
                "last_price": signal.last_price,
                "atr": signal.atr,
                "volume_ratio": signal.volume_ratio,
                "trend": signal.trend,
                "patterns": signal.patterns,
                "pattern_bias": signal.pattern_bias,
                "explanation": signal.explanation,
                "caveats": signal.caveats,
                "stochastic_k": signal.stochastic_k,
                "stochastic_signal": signal.stochastic_signal,
                "macd_histogram": signal.macd_histogram,
                "adx_value": signal.adx_value,
            },
        }

    return await cached(f"scalping:{symbol}", 120, _fetch)


@router.get("/stock/{symbol}/candlestick")
async def stock_candlestick(symbol: str, _t: str = Depends(require_token)):
    """Detect candlestick patterns on a stock's daily chart.

    Scans the last 5 daily bars for all Nison candlestick patterns.
    """
    symbol = symbol.strip().upper().replace(".NS", "").replace("NSE:", "")

    async def _fetch():
        provider = get_provider()
        daily = await provider.get_daily_history(symbol, 60)
        if daily.empty:
            return {"symbol": symbol, "patterns": [], "net_bias": "neutral",
                    "message": "No daily data available."}
        recent = daily.tail(5)
        hits = candle.detect_patterns(recent, lookback=5)
        return {
            "symbol": symbol,
            "patterns": [
                {
                    "name": h.name,
                    "bias": h.bias,
                    "strength": h.strength,
                    "bar_index": h.bar_index,
                    "description": h.description,
                }
                for h in hits
            ],
            "net_bias": candle.net_bias(hits),
            "bars_scanned": len(recent),
        }

    return await cached(f"candlestick:{symbol}", 300, _fetch)


@router.get("/stock/{symbol}/multifactor")
async def stock_multifactor(symbol: str, _t: str = Depends(require_token)):
    """Multi-factor score: momentum + value + quality composite."""
    symbol = symbol.strip().upper().replace(".NS", "").replace("NSE:", "")

    async def _fetch():
        provider = get_provider()
        daily = await provider.get_daily_history(symbol, 60)
        fundamentals = await get_stock_fundamentals(symbol)
        score = mf.composite_score(daily if not daily.empty else None, fundamentals)
        return {"symbol": symbol, **score}

    return await cached(f"multifactor:{symbol}", 600, _fetch)
