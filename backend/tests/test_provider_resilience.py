"""yfinance fetch resilience: retries on transient empties, safe quote fallback.

Without these, one flaky Yahoo response silently drops a symbol from every
universe scan, and a missing last_price raised TypeError out of get_quote.
"""
from types import SimpleNamespace

import pandas as pd

import app.providers.yfinance_provider as yfp


def _good_daily_df() -> pd.DataFrame:
    idx = pd.date_range("2026-09-01", periods=5, freq="D")
    return pd.DataFrame(
        {
            "Open": [100, 101, 102, 103, 104],
            "High": [105, 106, 107, 108, 109],
            "Low": [99, 100, 101, 102, 103],
            "Close": [101, 102, 103, 104, 105],
            "Volume": [1000] * 5,
        },
        index=idx,
    )


def test_daily_fetch_retries_on_transient_empty(monkeypatch):
    monkeypatch.setattr(yfp.time, "sleep", lambda s: None)  # don't actually wait
    state = {"calls": 0}

    def fake_ticker(symbol):
        def history(**kw):
            state["calls"] += 1
            return pd.DataFrame() if state["calls"] == 1 else _good_daily_df()
        return SimpleNamespace(history=history)

    monkeypatch.setattr(yfp.yf, "Ticker", fake_ticker)
    df = yfp._fetch_daily_sync("RELIANCE", 60)
    assert not df.empty
    assert state["calls"] == 2  # retried once, then succeeded


def test_intraday_fetch_retries_on_transient_empty(monkeypatch):
    monkeypatch.setattr(yfp.time, "sleep", lambda s: None)
    state = {"calls": 0}

    def fake_ticker(symbol):
        def history(**kw):
            state["calls"] += 1
            return pd.DataFrame() if state["calls"] == 1 else _good_daily_df()
        return SimpleNamespace(history=history)

    monkeypatch.setattr(yfp.yf, "Ticker", fake_ticker)
    df = yfp._fetch_intraday_sync("RELIANCE", "5m", 1)
    assert not df.empty
    assert state["calls"] == 2


def test_intraday_fetch_drops_nan_close_rows(monkeypatch):
    monkeypatch.setattr(yfp.time, "sleep", lambda s: None)

    def fake_ticker(symbol):
        df = _good_daily_df()
        bad = df.iloc[[-1]].copy()
        bad["Close"] = float("nan")  # partial current bar, real volume
        return SimpleNamespace(history=lambda **kw: pd.concat([df, bad]))

    monkeypatch.setattr(yfp.yf, "Ticker", fake_ticker)
    df = yfp._fetch_intraday_sync("RELIANCE", "5m", 1)
    assert not df["Close"].isna().any()
    assert len(df) == 5


class _ExplodingInfo:
    def __getattr__(self, name):
        raise RuntimeError("no data from yahoo")


def test_quote_fallback_zero_when_fast_info_raises(monkeypatch):
    monkeypatch.setattr(yfp.time, "sleep", lambda s: None)
    monkeypatch.setattr(
        yfp.yf, "Ticker", lambda symbol: SimpleNamespace(fast_info=_ExplodingInfo())
    )
    q = yfp._fetch_quote_sync("RELIANCE")
    assert q.price == 0.0  # not an exception — callers guard on price > 0


def test_quote_fallback_zero_when_last_price_none(monkeypatch):
    monkeypatch.setattr(yfp.time, "sleep", lambda s: None)
    info = SimpleNamespace(
        last_price=None, previous_close=None, day_high=None, day_low=None
    )
    monkeypatch.setattr(yfp.yf, "Ticker", lambda symbol: SimpleNamespace(fast_info=info))
    q = yfp._fetch_quote_sync("RELIANCE")
    assert q.price == 0.0
