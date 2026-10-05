"""Regression: _fetch_nav_history must not crash on the pandas 2.x API.

Historically this used Series.last("730D") — a method removed in pandas 2.x
(row-position selection, not a date cutoff). The per-fund try/except in
screen_mf swallowed the AttributeError and every fund silently degraded to
zero risk metrics, masquerading as an "mfapi.in unreachable" outage.
"""
import httpx
import pandas as pd

import app.strategies.mf_screener as scr


def _make_rows(days: int = 900) -> list[dict]:
    """~2.5 years of daily NAV rows in mfapi.in's format (dd-mm-yyyy, str nav)."""
    end = pd.Timestamp("2026-10-01")
    out = []
    nav = 50.0
    for i in range(days, 0, -1):
        d = end - pd.Timedelta(days=i)
        nav *= 1.0005  # steady growth so values differ per row
        out.append({"date": d.strftime("%d-%m-%Y"), "nav": f"{nav:.5f}"})
    return out


def test_nav_history_truncates_to_two_years(monkeypatch):
    rows = _make_rows()

    async def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200, json={"meta": {}, "data": rows, "status": "SUCCESS"}
        )

    original_client = httpx.AsyncClient  # capture before patching

    def fake_client(**kw):
        return original_client(transport=httpx.MockTransport(handler))

    monkeypatch.setattr(scr.httpx, "AsyncClient", fake_client)

    import asyncio

    series = asyncio.run(scr._fetch_nav_history("119598"))
    assert len(series) > 0
    span = (series.index.max() - series.index.min()).days
    assert span <= 731, f"expected ~2y window, got {span} days"
    assert not series.isna().any()
