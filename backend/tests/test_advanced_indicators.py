"""Unit tests for the advanced intraday indicators (VWAP, Bollinger, PPO, RSI)."""
from __future__ import annotations

import math

import pandas as pd

from app import indicators as ind


def _intraday(closes, start="2024-02-01 09:15", freq="5min", tz="Asia/Kolkata"):
    """Build an intraday frame with synthetic H/L/V around the closes."""
    idx = pd.date_range(start, periods=len(closes), freq=freq, tz=tz)
    highs = [c + 0.5 for c in closes]
    lows = [c - 0.5 for c in closes]
    vols = [1000.0] * len(closes)
    return pd.DataFrame(
        {"Open": closes, "High": highs, "Low": lows, "Close": closes, "Volume": vols},
        index=idx,
    )


# ---------------------------------------------------------------------------
# VWAP
# ---------------------------------------------------------------------------

def test_vwap_flat_data_equals_price():
    # If H=L=C and uniform volume, VWAP should equal the close at every bar.
    df = _intraday([100, 100, 100, 100, 100])
    v = ind.vwap(df)
    assert all(abs(x - 100.0) < 1e-9 for x in v.tolist())


def test_vwap_weighted_by_volume():
    # Two bars: bar1 typical=100 vol=1000, bar2 typical=110 vol=3000.
    # VWAP = (100*1000 + 110*3000) / (1000+3000) = (100000+330000)/4000 = 107.5
    idx = pd.date_range("2024-02-01 09:15", periods=2, freq="5min", tz="Asia/Kolkata")
    df = pd.DataFrame(
        {
            "Open": [100, 110], "High": [100, 110], "Low": [100, 110],
            "Close": [100, 110], "Volume": [1000.0, 3000.0],
        },
        index=idx,
    )
    v = ind.vwap(df)
    assert abs(v.iloc[-1] - 107.5) < 1e-9


def test_vwap_length_matches_input():
    df = _intraday([100 + i for i in range(30)])
    v = ind.vwap(df)
    assert len(v) == len(df)


# ---------------------------------------------------------------------------
# Bollinger Bands
# ---------------------------------------------------------------------------

def test_bollinger_middle_is_sma():
    closes = [100 + i for i in range(25)]  # 100..124
    s = pd.Series(closes)
    bb = ind.bollinger_bands(s, period=20, num_std=2.0)
    # Middle at the last bar = mean of last 20 closes = mean(105..124)
    expected_middle = sum(range(105, 125)) / 20
    assert abs(bb["middle"].iloc[-1] - expected_middle) < 1e-9


def test_bollinger_upper_lower_symmetric():
    closes = [100 + i for i in range(25)]
    s = pd.Series(closes)
    bb = ind.bollinger_bands(s, period=20, num_std=2.0)
    mid = bb["middle"].iloc[-1]
    upper = bb["upper"].iloc[-1]
    lower = bb["lower"].iloc[-1]
    assert abs((upper - mid) - (mid - lower)) < 1e-9


def test_bollinger_bandwidth_positive():
    closes = [100 + i for i in range(25)]
    s = pd.Series(closes)
    bb = ind.bollinger_bands(s, period=20, num_std=2.0)
    assert bb["bandwidth"].iloc[-1] > 0


def test_bollinger_pct_b_inside_bands_is_0_to_1():
    closes = [100 + i for i in range(25)]
    s = pd.Series(closes)
    bb = ind.bollinger_bands(s, period=20, num_std=2.0)
    pct_b = bb["pct_b"].iloc[-1]
    assert 0.0 <= pct_b <= 1.0


def test_bollinger_nan_before_period():
    s = pd.Series([100, 101, 102])
    bb = ind.bollinger_bands(s, period=20, num_std=2.0)
    assert math.isnan(bb["middle"].iloc[-1])


# ---------------------------------------------------------------------------
# PPO
# ---------------------------------------------------------------------------

def test_ppo_flat_data_is_zero():
    # If close is constant, fast EMA = slow EMA = close, so PPO = 0.
    s = pd.Series([100.0] * 40)
    p = ind.ppo(s, fast=12, slow=26, signal=9)
    assert abs(p["ppo"].iloc[-1]) < 1e-9
    assert abs(p["signal"].iloc[-1]) < 1e-9
    assert abs(p["histogram"].iloc[-1]) < 1e-9


def test_ppo_uptrend_positive():
    # Steady uptrend should produce a positive PPO.
    s = pd.Series([100 + i * 0.5 for i in range(50)])
    p = ind.ppo(s, fast=12, slow=26, signal=9)
    assert p["ppo"].iloc[-1] > 0


def test_ppo_downtrend_negative():
    s = pd.Series([100 - i * 0.5 for i in range(50)])
    p = ind.ppo(s, fast=12, slow=26, signal=9)
    assert p["ppo"].iloc[-1] < 0


def test_ppo_histogram_equals_ppo_minus_signal():
    s = pd.Series([100 + i * 0.3 for i in range(50)])
    p = ind.ppo(s, fast=12, slow=26, signal=9)
    hist = p["histogram"].iloc[-1]
    expected = p["ppo"].iloc[-1] - p["signal"].iloc[-1]
    assert abs(hist - expected) < 1e-9


def test_ppo_percentage_based():
    # PPO is percentage-based: scaling the input should not change PPO.
    s1 = pd.Series([100 + i for i in range(50)])
    s2 = pd.Series([200 + 2 * i for i in range(50)])  # 2x scale
    p1 = ind.ppo(s1)
    p2 = ind.ppo(s2)
    assert abs(p1["ppo"].iloc[-1] - p2["ppo"].iloc[-1]) < 1e-6


# ---------------------------------------------------------------------------
# RSI
# ---------------------------------------------------------------------------

def test_rsi_all_gains_is_100():
    # If every bar gains, RSI should be 100.
    s = pd.Series([100 + i for i in range(30)])
    r = ind.rsi(s, period=14)
    assert abs(r.iloc[-1] - 100.0) < 1e-6


def test_rsi_all_losses_is_0():
    s = pd.Series([100 - i for i in range(30)])
    r = ind.rsi(s, period=14)
    assert abs(r.iloc[-1]) < 1e-6


def test_rsi_flat_data_is_nan_or_neutral():
    # Flat data: no gains or losses after first bar. avg_gain=0, avg_loss=0.
    # rs = 0/0 = nan, RSI = 100 - 100/(1+nan) = nan. That's acceptable.
    s = pd.Series([100.0] * 30)
    r = ind.rsi(s, period=14)
    assert math.isnan(r.iloc[-1]) or abs(r.iloc[-1] - 50.0) < 1e-6


def test_rsi_bounded_0_to_100():
    import numpy as np
    np.random.seed(42)
    s = pd.Series(100 + np.cumsum(np.random.randn(50)))
    r = ind.rsi(s, period=14)
    val = r.iloc[-1]
    assert 0.0 <= val <= 100.0
