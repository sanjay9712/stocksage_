"""Institutional flow data — FII/DII for NSE, institutional holders for US.

NSE FII/DII: Fetches from nseindia.com/api/fiidiiTradeReact (today's net
buy/sell by foreign and domestic institutions). Uses the same cookie
handshake as NSEEquityProvider.

US Institutional: Uses yfinance's ticker.institutional_holders and
ticker.major_holders for top-10 holders and ownership breakdown.

All calls are wrapped in asyncio.to_thread() since both httpx sync and
yfinance use blocking I/O.
"""
from __future__ import annotations

import asyncio
import logging
import time
from typing import Any

import httpx

log = logging.getLogger("institutional_flow")

NSE_BASE = "https://www.nseindia.com"
BROWSER_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "application/json, text/javascript, */*; q=0.01",
    "Accept-Language": "en-US,en;q=0.9",
    "Referer": "https://www.nseindia.com/",
    "X-Requested-With": "XMLHttpRequest",
}

_cookie_cache: dict = {"client": None, "ts": 0, "ttl": 300}


async def _get_nse_client() -> httpx.AsyncClient:
    now = time.time()
    if _cookie_cache["client"] and now - _cookie_cache["ts"] < _cookie_cache["ttl"]:
        return _cookie_cache["client"]
    client = httpx.AsyncClient(timeout=15, follow_redirects=True, http2=False)
    try:
        await client.get(NSE_BASE, headers={
            "User-Agent": BROWSER_HEADERS["User-Agent"],
            "Accept": "text/html",
        })
    except Exception:
        pass
    _cookie_cache["client"] = client
    _cookie_cache["ts"] = now
    return client


async def fetch_fii_dii_cashflow() -> list[dict[str, Any]]:
    """Fetch today's FII/DII cash flow from NSE.

    Returns a list of dicts, each with: category, buy_value, sell_value,
    net_value (in crores).
    """
    try:
        client = await _get_nse_client()
        r = await client.get(
            f"{NSE_BASE}/api/fiidiiTradeReact",
            headers=BROWSER_HEADERS,
        )
        if r.status_code != 200:
            log.warning("FII/DII endpoint returned %d", r.status_code)
            return []
        data = r.json()
        rows = data.get("data", [])
        out = []
        for row in rows:
            out.append({
                "category": row.get("category", ""),
                "buy_value": float(row.get("buyValue", 0) or 0),
                "sell_value": float(row.get("sellValue", 0) or 0),
                "net_value": float(row.get("netValue", 0) or 0),
            })
        return out
    except Exception as e:
        log.warning("Failed to fetch FII/DII data: %s", e)
        return []


def _fetch_us_institutional_sync(symbol: str) -> dict[str, Any]:
    """Synchronous yfinance call for US institutional holders."""
    import yfinance as yf

    ticker = yf.Ticker(symbol)
    result: dict[str, Any] = {
        "symbol": symbol,
        "institutional_pct": None,
        "insider_pct": None,
        "top_holders": [],
    }

    try:
        info = ticker.info
        result["institutional_pct"] = round(info.get("heldPercentInstitutions", 0) * 100, 2) if info.get("heldPercentInstitutions") else None
        result["insider_pct"] = round(info.get("heldPercentInsiders", 0) * 100, 2) if info.get("heldPercentInsiders") else None
    except Exception:
        pass

    try:
        df = ticker.institutional_holders
        if df is not None and not df.empty:
            holders = []
            for _, row in df.head(10).iterrows():
                holders.append({
                    "holder": str(row.get("Holder", "")),
                    "shares": int(row.get("Shares", 0)) if row.get("Shares") else None,
                    "value": float(row.get("Value", 0)) if row.get("Value") else None,
                    "pct_out": round(float(row.get("pctHeld", 0)), 2) if row.get("pctHeld") else None,
                    "date_reported": str(row.get("Date Reported", "")),
                })
            result["top_holders"] = holders
    except Exception:
        pass

    return result


async def fetch_us_institutional(symbol: str) -> dict[str, Any]:
    """Fetch US institutional holders data via yfinance."""
    return await asyncio.to_thread(_fetch_us_institutional_sync, symbol)
