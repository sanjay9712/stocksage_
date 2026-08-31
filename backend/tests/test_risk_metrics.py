"""Tests for invest risk metrics (volatility, CAGR, max drawdown, Sharpe)."""
from __future__ import annotations

import math

import pandas as pd

from app import indicators as ind


def test_cagr_steady_growth():
    # 252 daily bars rising 10% total over one year -> CAGR ~10%.
    idx = pd.date_range("2024-01-01", periods=252, freq="D")
    closes = [100 * (1.10 ** (i / 252)) for i in range(252)]
    s = pd.Series(closes, index=idx)
    c = ind.cagr(s)
    assert abs(c - 0.10) < 0.01


def test_max_drawdown_known_value():
    # 100 -> 120 -> 90 -> 95. Peak 120, trough 90 -> DD = -25%.
    s = pd.Series([100, 120, 90, 95])
    assert math.isclose(ind.max_drawdown(s), -0.25, abs_tol=1e-9)


def test_volatility_zero_for_flat_series():
    s = pd.Series([100, 100, 100, 100, 100])
    assert ind.annualized_volatility(s) == 0.0


def test_sharpe_positive_for_gaining_low_vol_series():
    idx = pd.date_range("2024-01-01", periods=252, freq="D")
    # small steady positive daily return
    closes = [100 * (1 + 0.0004) ** i for i in range(252)]
    s = pd.Series(closes, index=idx)
    assert ind.sharpe_ratio(s) > 0


def test_risk_metrics_bundle_keys():
    s = pd.Series([100, 101, 99, 102, 100, 105, 103, 107, 106, 110] * 30)
    m = ind.risk_metrics(s)
    assert set(m.keys()) == {"volatility", "cagr", "max_drawdown", "sharpe"}
