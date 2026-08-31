"""Tests for the holdings reviewer (wrong-pick engine) on fixtures."""
from __future__ import annotations

import pandas as pd

from app.holdings.base import Holding
from app.holdings.reviewer import _review_one


def _uptrend(n=120):
    idx = pd.date_range("2024-01-01", periods=n, freq="D")
    closes = [100 + i for i in range(n)]
    return pd.DataFrame({"Open": closes, "High": [c + 1 for c in closes],
                         "Low": [c - 1 for c in closes], "Close": closes,
                         "Volume": [1000] * n}, index=idx)


def _downtrend(n=120):
    idx = pd.date_range("2024-01-01", periods=n, freq="D")
    closes = [300 - i for i in range(n)]
    return pd.DataFrame({"Open": closes, "High": [c + 1 for c in closes],
                         "Low": [c - 1 for c in closes], "Close": closes,
                         "Volume": [1000] * n}, index=idx)


def test_uptrend_holding_verdict_hold():
    h = Holding(symbol="UP", quantity=10, avg_price=110.0, current_price=215.0, product="CNC")
    r = _review_one(h, _uptrend(), today_picks=set())
    assert r.trend == "up"
    assert r.verdict == "hold"


def test_downtrend_holding_flagged_wrong_pick():
    h = Holding(symbol="DOWN", quantity=10, avg_price=290.0, current_price=185.0, product="CNC")
    r = _review_one(h, _downtrend(), today_picks=set())
    assert r.trend == "down"
    # ~38% off peak -> wrong-pick
    assert r.verdict == "wrong-pick"
    assert any("thesis" in a.lower() for a in r.actions)


def test_untracked_intraday_position_flagged():
    h = Holding(symbol="UP", quantity=10, avg_price=110.0, current_price=215.0, product="MIS")
    r = _review_one(h, _uptrend(), today_picks=set())
    # MIS position not in today's picks -> caution/wrong-pick and mentions untracked
    assert r.verdict in ("caution", "wrong-pick")
    assert any("untracked" in a.lower() or "intraday" in a.lower() for a in r.actions)


def test_intraday_position_in_today_picks_not_flagged():
    h = Holding(symbol="UP", quantity=10, avg_price=110.0, current_price=215.0, product="MIS")
    r = _review_one(h, _uptrend(), today_picks={"UP"})
    # Trend up + tracked intraday -> hold
    assert r.verdict == "hold"


def test_empty_history_returns_review():
    h = Holding(symbol="X", quantity=1, avg_price=10.0, current_price=11.0, product="CNC")
    r = _review_one(h, pd.DataFrame(), today_picks=set())
    assert r.verdict == "review"
