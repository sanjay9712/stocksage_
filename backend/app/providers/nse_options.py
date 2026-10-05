"""NSE option chain data — /api/option-chain-v3 + contract-info endpoints.

yfinance exposes no NSE option chains (get_option_chain returns no expiries
for indices or NSE stocks), so this fetches directly from nseindia.com using
the same cookie handshake as NSEEquityProvider.

Verified working (2026-10-05):
  - /api/option-chain-contract-info?symbol=NIFTY
      -> {"expiryDates": ["06-Oct-2026", "13-Oct-2026", ...], "strikePrice": [...]}
  - /api/option-chain-v3?type=indices&symbol=NIFTY&expiry=06-OCT-2026
      -> records.data: one row per strike with nested CE/PE objects
         (strikePrice, openInterest, lastPrice, impliedVolatility, ...)
  - /api/option-chain-v3?type=stocks&symbol=RELIANCE&expiry=... (stock options)

The old /api/option-chain-indices endpoint is gone (404).
"""
from __future__ import annotations

import logging
from datetime import datetime
from typing import Any

from app.providers.nse_equity_provider import BROWSER_HEADERS, NSEEquityProvider

log = logging.getLogger("nse_options")


def _to_nse_expiry(expiry: str) -> str:
    """Normalize an expiry to NSE format DD-MON-YYYY (e.g. 06-OCT-2026).

    Accepts ISO (YYYY-MM-DD, as the API documents) or NSE-style input.
    """
    e = expiry.strip()
    try:
        d = datetime.strptime(e, "%Y-%m-%d")
    except ValueError:
        d = datetime.strptime(e, "%d-%b-%Y")
    return f"{d.day:02d}-{d.strftime('%b').upper()}-{d.year}"


def _row_to_option(side: dict[str, Any] | None) -> dict[str, Any] | None:
    """Convert one NSE v3 CE/PE object to the flat row shape the
    options_oi endpoint expects (strike, openInterest, ...)."""
    if not side:
        return None
    return {
        "strike": float(side.get("strikePrice", 0) or 0),
        "openInterest": int(side.get("openInterest", 0) or 0),
        "lastPrice": float(side.get("lastPrice", 0) or 0),
        "impliedVolatility": float(side.get("impliedVolatility", 0) or 0),
        "totalTradedVolume": int(side.get("totalTradedVolume", 0) or 0),
        "changeinOpenInterest": int(side.get("changeinOpenInterest", 0) or 0),
    }


async def fetch_nse_option_chain(
    symbol: str,
    is_index: bool,
    expiry: str | None = None,
) -> dict[str, Any]:
    """Fetch a NSE option chain.

    Args:
        symbol: NSE symbol (e.g. "NIFTY", "BANKNIFTY", "RELIANCE").
        is_index: True for index options (type=indices), False for stocks.
        expiry: "YYYY-MM-DD" or "DD-MON-YYYY"; None → nearest expiry.

    Returns the same shape YFinanceProvider.get_option_chain yields:
        {"calls": [...], "puts": [...], "expiries": [...], "expiry": str|None,
         "underlying": float|None}
    Empty calls/puts on any failure so callers can fall back.
    """
    empty = {"calls": [], "puts": [], "expiries": [], "expiry": None, "underlying": None}
    try:
        provider = NSEEquityProvider()
        client = await provider._get_client()
        base = "https://www.nseindia.com"

        # Expiry list (also validates the symbol has derivatives).
        r = await client.get(
            f"{base}/api/option-chain-contract-info?symbol={symbol}", headers=BROWSER_HEADERS
        )
        if r.status_code != 200:
            log.warning("NSE option contract-info %s -> %d", symbol, r.status_code)
            return empty
        info = r.json()
        expiry_dates: list[str] = info.get("expiryDates") or []
        if not expiry_dates:
            return empty

        target = expiry if expiry else expiry_dates[0]
        target_nse = _to_nse_expiry(target)

        chain_type = "indices" if is_index else "stocks"
        r = await client.get(
            f"{base}/api/option-chain-v3?type={chain_type}&symbol={symbol}&expiry={target_nse}",
            headers=BROWSER_HEADERS,
        )
        if r.status_code != 200:
            log.warning("NSE option chain %s/%s -> %d", symbol, target_nse, r.status_code)
            return empty
        records = r.json().get("records", {})
        rows = records.get("data") or []

        calls: list[dict[str, Any]] = []
        puts: list[dict[str, Any]] = []
        for row in rows:
            c = _row_to_option(row.get("CE"))
            p = _row_to_option(row.get("PE"))
            if c:
                calls.append(c)
            if p:
                puts.append(p)

        return {
            "calls": calls,
            "puts": puts,
            "expiries": expiry_dates,
            "expiry": target_nse,
            "underlying": records.get("underlyingValue"),
        }
    except Exception as e:
        log.warning("Failed to fetch NSE option chain for %s: %s", symbol, e)
        return empty
