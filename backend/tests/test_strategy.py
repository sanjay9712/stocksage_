"""Strategy + explainer tests on synthetic candle fixtures (no network)."""
from __future__ import annotations

import pandas as pd
from zoneinfo import ZoneInfo

from app.explain import explainer
from app.strategies import intraday_breakout as strat


def _daily(n=30):
    idx = pd.date_range("2024-01-01", periods=n, freq="D")
    closes = [100 + i for i in range(n)]  # gentle uptrend so Close > 20-EMA
    highs = [c + 1 for c in closes]
    lows = [c - 1 for c in closes]
    vols = [1000] * n
    return pd.DataFrame({"Open": closes, "High": highs, "Low": lows, "Close": closes, "Volume": vols}, index=idx)


def _intraday_with_breakout():
    """5-min candles 09:15-10:00 IST. OR = [100, 98]; breakout at 09:35 closing at 101 on 2000 vol."""
    tz = ZoneInfo("Asia/Kolkata")
    times = ["09:15", "09:20", "09:25", "09:30", "09:35", "09:40", "09:45"]
    idx = pd.date_range("2024-02-01 09:15", periods=len(times), freq="5min", tz=tz)
    # OR window bars (09:15,09:20,09:25): high max=100, low min=98
    rows = [
        (99, 100, 98, 99, 100),
        (99, 100, 98, 99, 100),
        (99, 99.5, 98, 99, 100),
        (100, 100.5, 99, 100, 500),     # 09:30 - no breakout (close == OR high, not >)
        (100, 101.5, 100, 101, 2000),  # 09:35 - breakout: close 101 > 100, vol 2000
        (101, 102, 100.5, 101.5, 800),
        (101.5, 102, 101, 101.5, 700),
    ]
    return pd.DataFrame(rows, columns=["Open", "High", "Low", "Close", "Volume"], index=idx)


def test_breakout_long_pick():
    daily = _daily()
    intraday = _intraday_with_breakout()
    ctx = strat.StrategyContext(
        symbol="TEST", daily=daily, intraday=intraday, or_high=100.0, or_low=98.0
    )
    res = strat.evaluate(ctx)
    assert res.side == "long"
    assert res.entry == 100.0
    assert res.stop_loss == 98.0          # OR-Low
    assert res.target1 == 100.0 + res.atr_value
    assert res.target2 == 100.0 + 2 * res.atr_value
    assert res.breakout is not None
    assert res.breakout["volume_ratio"] == 2.0  # 2000 / avg 1000
    assert 0.0 < res.confidence <= 1.0


def test_no_breakout_returns_none_side():
    daily = _daily()
    intraday = _intraday_with_breakout()
    # Force OR high above all closes -> no breakout.
    ctx = strat.StrategyContext(
        symbol="TEST", daily=daily, intraday=intraday, or_high=200.0, or_low=98.0
    )
    res = strat.evaluate(ctx)
    assert res.side is None
    assert res.entry is None


def test_explainer_has_formula_trace_and_verification():
    daily = _daily()
    intraday = _intraday_with_breakout()
    ctx = strat.StrategyContext(
        symbol="TEST", daily=daily, intraday=intraday, or_high=100.0, or_low=98.0
    )
    res = strat.evaluate(ctx)
    exp = explainer.build(res)
    assert exp.summary
    assert len(exp.formula_trace) == 4  # entry, SL, T1, T2
    labels = {f.label for f in exp.formula_trace}
    assert labels == {"Entry", "Stop-Loss", "Target 1", "Target 2"}
    assert len(exp.verification) >= 3
    assert any("delayed" in c.lower() for c in exp.caveats)


def test_explainer_handles_no_pick():
    daily = _daily()
    intraday = _intraday_with_breakout()
    ctx = strat.StrategyContext(
        symbol="TEST", daily=daily, intraday=intraday, or_high=200.0, or_low=98.0
    )
    res = strat.evaluate(ctx)
    exp = explainer.build(res)
    assert exp.formula_trace == []
    assert exp.verification
