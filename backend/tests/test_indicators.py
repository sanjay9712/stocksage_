"""Unit tests for indicator math against hand-computed values."""
from __future__ import annotations

import pandas as pd

from app import indicators as ind


def _daily(closes):
    """Build a tiny daily frame where High=Low=Close and zero volume."""
    idx = pd.date_range("2024-01-01", periods=len(closes), freq="D")
    return pd.DataFrame({"Open": closes, "High": closes, "Low": closes, "Close": closes, "Volume": [0]*len(closes)}, index=idx)


def test_pivots_floor_formula():
    # prev high=110, low=90, close=100 -> pivot = (110+90+100)/3 = 100
    p = ind.pivots(110.0, 90.0, 100.0)
    assert p["pivot"] == 100.0
    # R1 = 2*P - L = 200 - 90 = 110
    assert p["r1"] == 110.0
    # S1 = 2*P - H = 200 - 110 = 90
    assert p["s1"] == 90.0
    # R2 = P + (H-L) = 100 + 20 = 120
    assert p["r2"] == 120.0
    # S2 = P - (H-L) = 100 - 20 = 80
    assert p["s2"] == 80.0


def test_atr_constant_range_is_zero():
    # If every bar has High==Low==Close, true range = 0, so ATR = 0.
    df = _daily([100, 100, 100, 100, 100, 100, 100, 100, 100, 100, 100, 100, 100, 100, 100])
    assert ind.atr(df, 14).iloc[-1] == 0.0


def test_atr_known_value():
    # Every bar H=110, L=90, C=100 with prev close 100 -> TR=20 for all bars.
    # With adjust=False, Wilder EMA seeds on the first TR value (20) and stays 20.
    idx = pd.date_range("2024-01-01", periods=20, freq="D")
    highs = [110] * 20
    lows = [90] * 20
    closes = [100] * 20
    df = pd.DataFrame({"Open": closes, "High": highs, "Low": lows, "Close": closes, "Volume": [0]*20}, index=idx)
    a = ind.atr(df, 14).iloc[-1]
    assert a == 20.0


def test_avg_volume_excludes_current_bar():
    # 22 bars; only the FINAL bar is 999 (the "current" bar that must be excluded).
    idx = pd.date_range("2024-01-01", periods=22, freq="D")
    vols = [100]*21 + [999]
    df = pd.DataFrame({"Open": 0, "High": 0, "Low": 0, "Close": 0, "Volume": vols}, index=idx)
    avg = ind.avg_volume(df, 20)
    # Trailing 20 of the final bar = bars 1..20 = all 100 -> avg 100.
    assert avg == 100.0
