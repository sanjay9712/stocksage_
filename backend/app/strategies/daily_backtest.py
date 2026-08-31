"""Daily backtest of the Murphy top-5 stock picker.

For each of the last N trading days:
  1. Slice daily OHLCV up to (but not including) that day.
  2. Run Murphy multi-indicator analysis on the universe.
  3. Pick the top 5 by composite_score (verdict must be buy or strong_buy).
  4. Simulate: entry = next day's open, exit = hit target1 or stop_loss,
     or close at that day's close if neither is hit.

This validates whether the Murphy system's picks would have been profitable.
"""
from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field, asdict
from datetime import datetime

import pandas as pd

from app.strategies.murphy_analysis import analyze_data, MurphyAnalysis

log = logging.getLogger("daily_backtest")


@dataclass
class DailyBacktestTrade:
    date: str               # YYYY-MM-DD — the day the pick was generated
    symbol: str
    name: str
    verdict: str
    composite_score: float
    entry: float            # next day's open
    stop_loss: float
    target1: float
    target2: float
    exit_price: float
    exit_date: str          # the day the trade was closed
    outcome: str            # "target_hit" | "stopped_out" | "time_exit"
    pnl_pct: float
    pnl_rupees: float       # per-share P&L
    hold_days: int


@dataclass
class DailyBacktestDay:
    date: str
    picks: list[dict]       # serialized trade info for each of the top 5
    day_pnl_pct: float      # average P&L % across the 5 trades


@dataclass
class DailyBacktestResult:
    days: list[DailyBacktestDay]
    summary: dict
    all_trades: list[DailyBacktestTrade] = field(default_factory=list)


def _simulate_trade(
    analysis: MurphyAnalysis,
    next_day: pd.Series,
    trade_date_str: str,
) -> DailyBacktestTrade | None:
    """Simulate a single trade: enter at next_day open, exit at target/SL/close.

    Args:
        analysis: Murphy analysis result (has entry, stop_loss, target1, etc.)
        next_day: the OHLCV row for the day AFTER the pick (execution day).
        trade_date_str: the date the pick was made (for logging).

    Returns:
        DailyBacktestTrade with outcome and P&L.
    """
    if next_day is None or next_day.empty:
        return None

    entry_price = float(next_day["Open"])
    if entry_price <= 0:
        return None

    stop = analysis.stop_loss
    target = analysis.target1

    high = float(next_day["High"])
    low = float(next_day["Low"])
    close = float(next_day["Close"])

    # Determine outcome — check both target and SL hit during the day.
    target_hit = high >= target
    stop_hit = low <= stop

    if target_hit and stop_hit:
        # Both hit in the same day — assume stop hit first (conservative).
        outcome = "stopped_out"
        exit_price = stop
    elif target_hit:
        outcome = "target_hit"
        exit_price = target
    elif stop_hit:
        outcome = "stopped_out"
        exit_price = stop
    else:
        # Neither hit — exit at close (time exit).
        outcome = "time_exit"
        exit_price = close

    pnl = exit_price - entry_price
    pnl_pct = (pnl / entry_price) * 100.0 if entry_price > 0 else 0.0

    return DailyBacktestTrade(
        date=trade_date_str,
        symbol=analysis.symbol,
        name=analysis.name,
        verdict=analysis.verdict,
        composite_score=analysis.composite_score,
        entry=round(entry_price, 2),
        stop_loss=round(stop, 2),
        target1=round(target, 2),
        target2=round(analysis.target2, 2),
        exit_price=round(exit_price, 2),
        exit_date=str(next_day.name.date()) if hasattr(next_day.name, "date") else trade_date_str,
        outcome=outcome,
        pnl_pct=round(pnl_pct, 2),
        pnl_rupees=round(pnl, 2),
        hold_days=1,
    )


async def backtest_daily_picks(
    provider,
    symbols: list[tuple[str, str]],
    market: str = "in",
    days: int = 30,
) -> DailyBacktestResult:
    """Backtest the Murphy top-5 system over the last N trading days.

    For each day, we:
      1. Fetch 300 days of daily history per symbol (enough for EMA-200 + 30-day backtest window).
      2. Slice the DataFrame to simulate "as of day D" (only data up to day D).
      3. Run Murphy analysis on the slice.
      4. Pick top 5 (verdict must be buy or strong_buy).
      5. Simulate trade on day D+1's OHLCV.

    Returns DailyBacktestResult with per-day breakdown + summary.
    """
    sem = asyncio.Semaphore(15)
    suffix = "" if market == "us" else ".NS"

    # Fetch daily history for all symbols in parallel.
    async def _fetch(sym: str, name: str) -> tuple[str, str, pd.DataFrame | None]:
        async with sem:
            try:
                ticker = f"{sym}{suffix}" if suffix else sym
                df = await provider.get_daily_history(ticker, 300)
                return sym, name, df
            except Exception as e:
                log.warning("Backtest fetch failed for %s: %s", sym, e)
                return sym, name, None

    fetched = await asyncio.gather(
        *[_fetch(s, n) for s, n in symbols],
        return_exceptions=True,
    )

    # Build a dict: symbol -> (name, DataFrame)
    data_map: dict[str, tuple[str, pd.DataFrame]] = {}
    for result in fetched:
        if isinstance(result, Exception) or result is None:
            continue
        sym, name, df = result
        if df is not None and not df.empty and len(df) >= 60:
            data_map[sym] = (name, df)

    if not data_map:
        return DailyBacktestResult(days=[], summary={
            "total_trades": 0, "wins": 0, "losses": 0,
            "win_rate": 0.0, "avg_return_pct": 0.0,
        })

    # Determine the backtest date range from the longest available DataFrame.
    longest_df = max(data_map.values(), key=lambda x: len(x[1]))[1]
    total_bars = len(longest_df)
    # Use the last N days for backtest, but need at least 60 bars for analysis.
    start_idx = max(60, total_bars - days)

    backtest_dates = longest_df.index[start_idx:total_bars]

    all_trades: list[DailyBacktestTrade] = []
    daily_results: list[DailyBacktestDay] = []

    for i, date in enumerate(backtest_dates):
        date_str = str(date.date()) if hasattr(date, "date") else str(date)

        # For each symbol, slice the DataFrame up to this date (exclusive of
        # the current day — we simulate picking at yesterday's close and
        # executing at today's open).
        slice_end = start_idx + i

        analyses: list[MurphyAnalysis] = []
        for sym, (name, df) in data_map.items():
            if len(df) <= slice_end:
                continue
            df_slice = df.iloc[:slice_end]
            if len(df_slice) < 60:
                continue
            try:
                analysis = analyze_data(sym, name, df_slice)
                if analysis is not None and analysis.verdict in ("buy", "strong_buy"):
                    analyses.append(analysis)
            except Exception as e:
                log.debug("Analysis failed for %s on %s: %s", sym, date_str, e)

        # Pick top 5 by composite score.
        analyses.sort(key=lambda a: a.composite_score, reverse=True)
        top_5 = analyses[:5]

        if not top_5:
            daily_results.append(DailyBacktestDay(
                date=date_str,
                picks=[],
                day_pnl_pct=0.0,
            ))
            continue

        # Simulate each trade on the next bar (day D+1).
        day_trades: list[DailyBacktestTrade] = []
        for analysis in top_5:
            sym = analysis.symbol
            if sym not in data_map:
                continue
            name, df = data_map[sym]
            next_idx = slice_end  # the execution day
            if next_idx >= len(df):
                continue
            next_day = df.iloc[next_idx]
            trade = _simulate_trade(analysis, next_day, date_str)
            if trade is not None:
                day_trades.append(trade)
                all_trades.append(trade)

        day_pnl = sum(t.pnl_pct for t in day_trades) / len(day_trades) if day_trades else 0.0

        daily_results.append(DailyBacktestDay(
            date=date_str,
            picks=[asdict(t) for t in day_trades],
            day_pnl_pct=round(day_pnl, 2),
        ))

    # Summary statistics.
    total_trades = len(all_trades)
    wins = sum(1 for t in all_trades if t.pnl_pct > 0)
    losses = sum(1 for t in all_trades if t.pnl_pct <= 0)
    win_rate = (wins / total_trades * 100.0) if total_trades > 0 else 0.0
    avg_return = (sum(t.pnl_pct for t in all_trades) / total_trades) if total_trades > 0 else 0.0

    return DailyBacktestResult(
        days=daily_results,
        summary={
            "total_trades": total_trades,
            "wins": wins,
            "losses": losses,
            "win_rate": round(win_rate, 2),
            "avg_return_pct": round(avg_return, 2),
        },
        all_trades=all_trades,
    )
