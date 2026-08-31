"""Advanced scalping strategy API endpoints.

Exposes the VWAP pullback, Bollinger squeeze, PPO momentum, MA Trend Scalp,
Gap-and-Go, S/R Reversal, Momentum Breakout, and ABCD Pattern strategies.
Every signal includes a plain-English explanation and beginner-mode glossary
terms so a complete beginner can understand every part of a pick.

GET /api/strategies/vwap               — VWAP pullback signals across the universe
GET /api/strategies/vwap/{symbol}      — VWAP pullback signal for one symbol
GET /api/strategies/bollinger           — Bollinger squeeze breakout signals
GET /api/strategies/bollinger/{symbol}  — squeeze signal for one symbol
GET /api/strategies/ppo                 — PPO momentum signals
GET /api/strategies/ppo/{symbol}        — PPO momentum signal for one symbol
GET /api/strategies/ma-trend             — MA Trend Scalp signals
GET /api/strategies/ma-trend/{symbol}    — MA Trend Scalp signal for one symbol
GET /api/strategies/gap-and-go           — Gap-and-Go signals
GET /api/strategies/gap-and-go/{symbol}  — Gap-and-Go signal for one symbol
GET /api/strategies/sr-reversal           — S/R Reversal signals
GET /api/strategies/sr-reversal/{symbol}  — S/R Reversal signal for one symbol
GET /api/strategies/momentum-breakout     — Momentum Breakout signals
GET /api/strategies/momentum-breakout/{symbol} — Momentum Breakout signal for one symbol
GET /api/strategies/abcd                  — ABCD Pattern signals
GET /api/strategies/abcd/{symbol}         — ABCD Pattern signal for one symbol
GET /api/strategies/all/{symbol}          — merged view of all eight strategies
GET /api/strategies/glossary              — full glossary of all trading terms
"""
from __future__ import annotations

import asyncio

from fastapi import APIRouter, Depends

from app.api.auth import require_token
from app.api.cache import cached
from app.config import settings
from app.explain.glossary import GLOSSARY, get_relevant_terms
from app.market_hours import is_nse_open, screen_cache_ttl
from app.providers.factory import get_provider
from app.strategies import vwap_pullback as vwap_strat
from app.strategies import bollinger_squeeze as bollinger_strat
from app.strategies import ppo_momentum as ppo_strat
from app.strategies import ma_trend_scalp as ma_trend_strat
from app.strategies import gap_and_go as gap_go_strat
from app.strategies import sr_reversal as sr_reversal_strat
from app.strategies import momentum_breakout as momentum_breakout_strat
from app.strategies import abcd_pattern as abcd_strat
from app.universe import get_universe

router = APIRouter()

# Terms each strategy uses, for the beginner-mode glossary enrichment.
_STRATEGY_TERMS = {
    "vwap": ["long", "short", "entry", "stop_loss", "target1", "target2",
             "risk_reward", "confidence", "vwap", "ema", "ema9", "ema21",
             "trend", "uptrend", "downtrend", "sideways", "pullback",
             "volume_ratio", "volume", "scalp", "candle", "bullish", "bearish"],
    "bollinger": ["long", "short", "entry", "stop_loss", "target",
                  "risk_reward", "confidence", "bollinger_bands", "upper_band",
                  "lower_band", "middle_band", "bandwidth", "squeeze", "pct_b",
                  "breakout", "volume_ratio", "volume", "trend", "uptrend",
                  "downtrend", "scalp", "bullish", "bearish"],
    "ppo": ["long", "short", "entry", "stop_loss", "target",
            "risk_reward", "confidence", "ppo", "signal_line", "histogram",
            "trend", "uptrend", "downtrend", "momentum", "volume_ratio",
            "volume", "scalp", "bullish", "bearish", "atr"],
    "ma_trend": ["long", "short", "entry", "stop_loss", "target",
                 "risk_reward", "confidence", "ema9", "ema21", "ema50",
                 "trend", "uptrend", "downtrend", "crossover", "momentum",
                 "volume_ratio", "volume", "scalp", "bullish", "bearish", "atr"],
    "gap_and_go": ["long", "short", "entry", "stop_loss", "target1", "target2",
                   "risk_reward", "confidence", "gap", "gap_pct", "opening_range",
                   "or_high", "or_low", "breakout", "volume_ratio", "volume",
                   "momentum", "bullish", "bearish"],
    "sr_reversal": ["long", "short", "entry", "stop_loss", "target1", "target2",
                    "risk_reward", "confidence", "support", "resistance", "pivot",
                    "fibonacci", "reversal", "level_type", "trend", "uptrend",
                    "downtrend", "sideways", "volume_ratio", "volume",
                    "bullish", "bearish", "atr"],
    "momentum_breakout": ["long", "short", "entry", "stop_loss", "target1", "target2",
                          "risk_reward", "confidence", "rsi", "opening_range",
                          "or_high", "or_low", "breakout", "momentum",
                          "volume_profile", "poc_price", "vah", "val",
                          "volume_ratio", "volume", "bullish", "bearish"],
    "abcd": ["long", "short", "entry", "stop_loss", "target",
             "risk_reward", "confidence", "fibonacci", "retracement",
             "swing", "point_a", "point_b", "point_c", "point_d",
             "symmetry", "projection", "bullish", "bearish", "atr"],
}


# ---------------------------------------------------------------------------
# Shared data fetch + per-strategy evaluation helper.
# ---------------------------------------------------------------------------

async def _fetch_data(symbol: str):
    provider = get_provider()
    try:
        daily = await provider.get_daily_history(symbol, 60)
        intraday = await provider.get_intraday(symbol, settings.intraday_interval, 5)
    except Exception:
        return None, None
    # Drop the last bar if it's a partial/forming bar (volume < 5% of average).
    # yfinance returns partial bars for the current 5-min interval with very
    # low volume, which skews volume-based strategy signals.
    if intraday is not None and not intraday.empty and len(intraday) > 20:
        avg_vol = intraday["Volume"].iloc[-21:-1].mean()
        last_vol = intraday["Volume"].iloc[-1]
        if avg_vol > 0 and last_vol < 0.05 * avg_vol:
            intraday = intraday.iloc[:-1]
    return daily, intraday


async def _get_name_map() -> dict[str, str]:
    """Fetch the NSE symbol→name map (cached 24h)."""
    try:
        from app.providers.nse_list import get_nse_stocks
        nse_stocks = await get_nse_stocks()
        return {s["symbol"]: s.get("name", s["symbol"]) for s in nse_stocks}
    except Exception:
        return {}


async def _scan_universe(strategy_fn, strategy_name: str, cache_ttl: int | None = None):
    """Scan the configured universe for signals from `strategy_fn`."""
    symbols = get_universe(settings.universe)
    sem = asyncio.Semaphore(20)

    # Build company name lookup once for all symbols.
    name_map = await _get_name_map()

    async def _eval(symbol: str):
        async with sem:
            daily, intraday = await _fetch_data(symbol)
            if daily is None or daily.empty or intraday is None or intraday.empty:
                return None
            return strategy_fn(symbol, daily, intraday)

    results = await asyncio.gather(*[_eval(s) for s in symbols])
    signals = [r for r in results if r is not None]
    signals.sort(key=lambda s: s.confidence, reverse=True)
    return {
        "signals": [_to_dict(s, strategy_name, name_map) for s in signals],
        "count": len(signals),
        "glossary": get_relevant_terms(_STRATEGY_TERMS.get(strategy_name, [])),
    }


def _to_dict(signal, strategy_name: str | None = None, name_map: dict[str, str] | None = None) -> dict:
    """Serialize a strategy signal dataclass to a dict for the API response.

    If strategy_name is provided, attaches the relevant glossary terms so a
    beginner can look up every term used in the explanation.
    """
    d = {k: getattr(signal, k) for k in signal.__dataclass_fields__}
    # Add company name from the NSE stock list.
    if name_map:
        d["name"] = name_map.get(signal.symbol, signal.symbol)
    else:
        d["name"] = signal.symbol
    if strategy_name and strategy_name in _STRATEGY_TERMS:
        d["glossary"] = get_relevant_terms(_STRATEGY_TERMS[strategy_name])
    return d


# ---------------------------------------------------------------------------
# VWAP pullback.
# ---------------------------------------------------------------------------

@router.get("/strategies/vwap")
async def vwap_signals(_t: str = Depends(require_token)):
    """Scan the universe for VWAP + 9 EMA pullback signals."""
    ttl = screen_cache_ttl(is_nse_open())
    return await cached("strat:vwap:all", ttl, lambda: _scan_universe(vwap_strat.evaluate_vwap_pullback, "vwap"))


@router.get("/strategies/vwap/{symbol}")
async def vwap_signal(symbol: str, _t: str = Depends(require_token)):
    """VWAP pullback signal for a single symbol."""
    symbol = symbol.strip().upper().replace(".NS", "").replace("NSE:", "")

    async def _fetch():
        daily, intraday = await _fetch_data(symbol)
        if daily is None or daily.empty or intraday is None or intraday.empty:
            return {"symbol": symbol, "signal": None, "message": "No data available."}
        signal = vwap_strat.evaluate_vwap_pullback(symbol, daily, intraday)
        if signal is None:
            return {"symbol": symbol, "signal": None,
                    "message": "No VWAP pullback signal right now."}
        return {"symbol": symbol, "signal": _to_dict(signal, "vwap", await _get_name_map())}

    return await cached(f"strat:vwap:{symbol}", 120, _fetch)


# ---------------------------------------------------------------------------
# Bollinger squeeze.
# ---------------------------------------------------------------------------

@router.get("/strategies/bollinger")
async def bollinger_signals(_t: str = Depends(require_token)):
    """Scan the universe for Bollinger squeeze breakout signals."""
    ttl = screen_cache_ttl(is_nse_open())
    return await cached("strat:bollinger:all", ttl, lambda: _scan_universe(bollinger_strat.evaluate_squeeze, "bollinger"))


@router.get("/strategies/bollinger/{symbol}")
async def bollinger_signal(symbol: str, _t: str = Depends(require_token)):
    """Bollinger squeeze signal for a single symbol."""
    symbol = symbol.strip().upper().replace(".NS", "").replace("NSE:", "")

    async def _fetch():
        daily, intraday = await _fetch_data(symbol)
        if daily is None or daily.empty or intraday is None or intraday.empty:
            return {"symbol": symbol, "signal": None, "message": "No data available."}
        signal = bollinger_strat.evaluate_squeeze(symbol, daily, intraday)
        if signal is None:
            return {"symbol": symbol, "signal": None,
                    "message": "No Bollinger squeeze breakout right now."}
        return {"symbol": symbol, "signal": _to_dict(signal, "bollinger", await _get_name_map())}

    return await cached(f"strat:bollinger:{symbol}", 120, _fetch)


# ---------------------------------------------------------------------------
# PPO momentum.
# ---------------------------------------------------------------------------

@router.get("/strategies/ppo")
async def ppo_signals(_t: str = Depends(require_token)):
    """Scan the universe for PPO momentum signals."""
    ttl = screen_cache_ttl(is_nse_open())
    return await cached("strat:ppo:all", ttl, lambda: _scan_universe(ppo_strat.evaluate_ppo, "ppo"))


@router.get("/strategies/ppo/{symbol}")
async def ppo_signal(symbol: str, _t: str = Depends(require_token)):
    """PPO momentum signal for a single symbol."""
    symbol = symbol.strip().upper().replace(".NS", "").replace("NSE:", "")

    async def _fetch():
        daily, intraday = await _fetch_data(symbol)
        if daily is None or daily.empty or intraday is None or intraday.empty:
            return {"symbol": symbol, "signal": None, "message": "No data available."}
        signal = ppo_strat.evaluate_ppo(symbol, daily, intraday)
        if signal is None:
            return {"symbol": symbol, "signal": None,
                    "message": "No PPO momentum signal right now."}
        return {"symbol": symbol, "signal": _to_dict(signal, "ppo", await _get_name_map())}

    return await cached(f"strat:ppo:{symbol}", 120, _fetch)


# ---------------------------------------------------------------------------
# MA Trend Scalp (EMA crossover).
# ---------------------------------------------------------------------------

@router.get("/strategies/ma-trend")
async def ma_trend_signals(_t: str = Depends(require_token)):
    """Scan the universe for MA Trend Scalp (EMA crossover) signals."""
    ttl = screen_cache_ttl(is_nse_open())
    return await cached("strat:ma_trend:all", ttl, lambda: _scan_universe(ma_trend_strat.evaluate_ma_trend_scalp, "ma_trend"))


@router.get("/strategies/ma-trend/{symbol}")
async def ma_trend_signal(symbol: str, _t: str = Depends(require_token)):
    """MA Trend Scalp signal for a single symbol."""
    symbol = symbol.strip().upper().replace(".NS", "").replace("NSE:", "")

    async def _fetch():
        daily, intraday = await _fetch_data(symbol)
        if daily is None or daily.empty or intraday is None or intraday.empty:
            return {"symbol": symbol, "signal": None, "message": "No data available."}
        signal = ma_trend_strat.evaluate_ma_trend_scalp(symbol, daily, intraday)
        if signal is None:
            return {"symbol": symbol, "signal": None,
                    "message": "No MA Trend Scalp signal right now."}
        return {"symbol": symbol, "signal": _to_dict(signal, "ma_trend", await _get_name_map())}

    return await cached(f"strat:ma_trend:{symbol}", 120, _fetch)


# ---------------------------------------------------------------------------
# Gap-and-Go.
# ---------------------------------------------------------------------------

@router.get("/strategies/gap-and-go")
async def gap_and_go_signals(_t: str = Depends(require_token)):
    """Scan the universe for Gap-and-Go signals."""
    ttl = screen_cache_ttl(is_nse_open())
    return await cached("strat:gap_and_go:all", ttl, lambda: _scan_universe(gap_go_strat.evaluate_gap_and_go, "gap_and_go"))


@router.get("/strategies/gap-and-go/{symbol}")
async def gap_and_go_signal(symbol: str, _t: str = Depends(require_token)):
    """Gap-and-Go signal for a single symbol."""
    symbol = symbol.strip().upper().replace(".NS", "").replace("NSE:", "")

    async def _fetch():
        daily, intraday = await _fetch_data(symbol)
        if daily is None or daily.empty or intraday is None or intraday.empty:
            return {"symbol": symbol, "signal": None, "message": "No data available."}
        signal = gap_go_strat.evaluate_gap_and_go(symbol, daily, intraday)
        if signal is None:
            return {"symbol": symbol, "signal": None,
                    "message": "No Gap-and-Go signal right now."}
        return {"symbol": symbol, "signal": _to_dict(signal, "gap_and_go", await _get_name_map())}

    return await cached(f"strat:gap_and_go:{symbol}", 120, _fetch)


# ---------------------------------------------------------------------------
# S/R Reversal.
# ---------------------------------------------------------------------------

@router.get("/strategies/sr-reversal")
async def sr_reversal_signals(_t: str = Depends(require_token)):
    """Scan the universe for Support/Resistance Reversal signals."""
    ttl = screen_cache_ttl(is_nse_open())
    return await cached("strat:sr_reversal:all", ttl, lambda: _scan_universe(sr_reversal_strat.evaluate_sr_reversal, "sr_reversal"))


@router.get("/strategies/sr-reversal/{symbol}")
async def sr_reversal_signal(symbol: str, _t: str = Depends(require_token)):
    """S/R Reversal signal for a single symbol."""
    symbol = symbol.strip().upper().replace(".NS", "").replace("NSE:", "")

    async def _fetch():
        daily, intraday = await _fetch_data(symbol)
        if daily is None or daily.empty or intraday is None or intraday.empty:
            return {"symbol": symbol, "signal": None, "message": "No data available."}
        signal = sr_reversal_strat.evaluate_sr_reversal(symbol, daily, intraday)
        if signal is None:
            return {"symbol": symbol, "signal": None,
                    "message": "No S/R Reversal signal right now."}
        return {"symbol": symbol, "signal": _to_dict(signal, "sr_reversal", await _get_name_map())}

    return await cached(f"strat:sr_reversal:{symbol}", 120, _fetch)


# ---------------------------------------------------------------------------
# Momentum Breakout (Range Expansion with RSI + Volume Profile).
# ---------------------------------------------------------------------------

@router.get("/strategies/momentum-breakout")
async def momentum_breakout_signals(_t: str = Depends(require_token)):
    """Scan the universe for Momentum Breakout signals."""
    ttl = screen_cache_ttl(is_nse_open())
    return await cached("strat:momentum_breakout:all", ttl, lambda: _scan_universe(momentum_breakout_strat.evaluate_momentum_breakout, "momentum_breakout"))


@router.get("/strategies/momentum-breakout/{symbol}")
async def momentum_breakout_signal(symbol: str, _t: str = Depends(require_token)):
    """Momentum Breakout signal for a single symbol."""
    symbol = symbol.strip().upper().replace(".NS", "").replace("NSE:", "")

    async def _fetch():
        daily, intraday = await _fetch_data(symbol)
        if daily is None or daily.empty or intraday is None or intraday.empty:
            return {"symbol": symbol, "signal": None, "message": "No data available."}
        signal = momentum_breakout_strat.evaluate_momentum_breakout(symbol, daily, intraday)
        if signal is None:
            return {"symbol": symbol, "signal": None,
                    "message": "No Momentum Breakout signal right now."}
        return {"symbol": symbol, "signal": _to_dict(signal, "momentum_breakout", await _get_name_map())}

    return await cached(f"strat:momentum_breakout:{symbol}", 120, _fetch)


# ---------------------------------------------------------------------------
# ABCD Pattern.
# ---------------------------------------------------------------------------

@router.get("/strategies/abcd")
async def abcd_signals(_t: str = Depends(require_token)):
    """Scan the universe for ABCD Pattern signals."""
    ttl = screen_cache_ttl(is_nse_open())
    return await cached("strat:abcd:all", ttl, lambda: _scan_universe(abcd_strat.evaluate_abcd_pattern, "abcd"))


@router.get("/strategies/abcd/{symbol}")
async def abcd_signal(symbol: str, _t: str = Depends(require_token)):
    """ABCD Pattern signal for a single symbol."""
    symbol = symbol.strip().upper().replace(".NS", "").replace("NSE:", "")

    async def _fetch():
        daily, intraday = await _fetch_data(symbol)
        if daily is None or daily.empty or intraday is None or intraday.empty:
            return {"symbol": symbol, "signal": None, "message": "No data available."}
        signal = abcd_strat.evaluate_abcd_pattern(symbol, daily, intraday)
        if signal is None:
            return {"symbol": symbol, "signal": None,
                    "message": "No ABCD Pattern signal right now."}
        return {"symbol": symbol, "signal": _to_dict(signal, "abcd", await _get_name_map())}

    return await cached(f"strat:abcd:{symbol}", 120, _fetch)


# ---------------------------------------------------------------------------
# Merged view: all eight strategies for one symbol.
# ---------------------------------------------------------------------------

@router.get("/strategies/all/{symbol}")
async def all_strategies(symbol: str, _t: str = Depends(require_token)):
    """Run all eight advanced strategies on a single symbol."""
    symbol = symbol.strip().upper().replace(".NS", "").replace("NSE:", "")

    async def _fetch():
        daily, intraday = await _fetch_data(symbol)
        if daily is None or daily.empty or intraday is None or intraday.empty:
            return {"symbol": symbol, "signals": {}, "message": "No data available."}
        name_map = await _get_name_map()
        vwap_sig = vwap_strat.evaluate_vwap_pullback(symbol, daily, intraday)
        bollinger_sig = bollinger_strat.evaluate_squeeze(symbol, daily, intraday)
        ppo_sig = ppo_strat.evaluate_ppo(symbol, daily, intraday)
        ma_trend_sig = ma_trend_strat.evaluate_ma_trend_scalp(symbol, daily, intraday)
        gap_go_sig = gap_go_strat.evaluate_gap_and_go(symbol, daily, intraday)
        sr_rev_sig = sr_reversal_strat.evaluate_sr_reversal(symbol, daily, intraday)
        mom_brk_sig = momentum_breakout_strat.evaluate_momentum_breakout(symbol, daily, intraday)
        abcd_sig = abcd_strat.evaluate_abcd_pattern(symbol, daily, intraday)
        return {
            "symbol": symbol,
            "signals": {
                "vwap": _to_dict(vwap_sig, "vwap", name_map) if vwap_sig else None,
                "bollinger": _to_dict(bollinger_sig, "bollinger", name_map) if bollinger_sig else None,
                "ppo": _to_dict(ppo_sig, "ppo", name_map) if ppo_sig else None,
                "ma_trend": _to_dict(ma_trend_sig, "ma_trend", name_map) if ma_trend_sig else None,
                "gap_and_go": _to_dict(gap_go_sig, "gap_and_go", name_map) if gap_go_sig else None,
                "sr_reversal": _to_dict(sr_rev_sig, "sr_reversal", name_map) if sr_rev_sig else None,
                "momentum_breakout": _to_dict(mom_brk_sig, "momentum_breakout", name_map) if mom_brk_sig else None,
                "abcd": _to_dict(abcd_sig, "abcd", name_map) if abcd_sig else None,
            },
        }

    return await cached(f"strat:all:{symbol}", 120, _fetch)


# ---------------------------------------------------------------------------
# Glossary endpoint (beginner mode).
# ---------------------------------------------------------------------------

@router.get("/strategies/glossary")
async def glossary(_t: str = Depends(require_token)):
    """Full glossary of all trading terms used by the strategies.

    Every term a beginner might encounter in a signal explanation is defined
    here in plain English. No prior stock-market knowledge required.
    """
    return {"terms": GLOSSARY, "count": len(GLOSSARY)}
