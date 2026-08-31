"""Mutual fund screener using AMFI NAV data.

Primary history source: mfapi.in (free, keyless, wraps AMFI).
Fallback for current NAV: AMFI's own NAVAll.txt dump
(https://www.amfiindia.com/spages/NAVAll.txt) — semicolon-delimited, reachable
even when mfapi.in is not.

When mfapi.in is unreachable we still show the real current NAV (not 0.0) and
mark risk metrics as pending; the daily AMFI snapshot job accumulates history
over time so metrics populate without any third-party dependency.
"""
from __future__ import annotations

import logging
import time
from dataclasses import dataclass, asdict

import httpx
import pandas as pd

from app import indicators as ind

log = logging.getLogger("mf_screener")

MFAPI_URL = "https://api.mfapi.in/mf/{code}"
AMFI_NAVALL_URL = "https://www.amfiindia.com/spages/NAVAll.txt"

# In-process cache of {scheme_code: nav} from the AMFI dump; refreshed at most
# every 15 min so a single screener run (10 funds) doesn't re-download the file.
_amfi_cache: dict[str, float] = {}
_amfi_cache_ts: float = 0.0
_AMFI_TTL = 900  # 15 minutes


@dataclass
class MfScreen:
    code: str
    name: str
    category: str
    horizon_hint: str
    last_nav: float
    volatility: float
    cagr: float
    max_drawdown: float
    sharpe: float
    suggested_horizon: str
    risk_level: str
    risks: list[str]
    verdict: str
    # New fields
    fund_house: str = ""
    scheme_type: str = ""
    expense_ratio_est: float = 0.0
    expense_ratio_note: str = ""
    exit_load: str = ""
    entry_strategy: str = ""
    exit_strategy: str = ""


# SEBI-capped expense ratio estimates by category (direct plan / growth).
_MF_EXPENSE_ESTIMATES = {
    "large-cap": {"est": 0.75, "note": "Large-cap direct: ~0.50-1.00% (SEBI cap 2.25%)"},
    "mid-cap": {"est": 1.10, "note": "Mid-cap direct: ~0.80-1.50% (SEBI cap 2.25%)"},
    "small-cap": {"est": 1.25, "note": "Small-cap direct: ~0.90-1.75% (SEBI cap 2.25%)"},
    "flexi-cap": {"est": 0.90, "note": "Flexi-cap direct: ~0.60-1.25% (SEBI cap 2.25%)"},
    "hybrid": {"est": 0.80, "note": "Hybrid direct: ~0.50-1.20% (SEBI cap 2.25%)"},
    "factor": {"est": 0.80, "note": "Factor/smart-beta direct: ~0.50-1.20% (SEBI cap 2.25%)"},
    "liquid": {"est": 0.20, "note": "Liquid direct: ~0.10-0.30% (very low)"},
}


def _estimate_mf_expense(category: str) -> tuple[float, str]:
    est = _MF_EXPENSE_ESTIMATES.get(category, {"est": 0.80, "note": "Estimated — verify on AMC fact sheet"})
    return est["est"], est["note"]


def _exit_load_for_category(category: str) -> str:
    """Standard exit load by category (SEBI norms, direct plans)."""
    if category == "liquid":
        return "Nil (no exit load for liquid funds)"
    if category in ("large-cap", "mid-cap", "small-cap", "flexi-cap", "factor"):
        return "1% if redeemed within 1 year; nil after 1 year"
    if category == "hybrid":
        return "1% if redeemed within 1-2 years; nil after (varies by scheme)"
    return "Check scheme information document — typically 1% if redeemed <1 year"


# Cache for mfapi.in metadata: {code: (ts, meta_dict)}
_meta_cache: dict[str, tuple[float, dict]] = {}
_META_TTL = 86400  # 24 hours — fund metadata rarely changes


async def _fetch_mf_meta(code: str) -> dict:
    """Fetch fund metadata (fund_house, scheme_type, scheme_category) from mfapi.in."""
    cached = _meta_cache.get(code)
    if cached and (time.time() - cached[0]) < _META_TTL:
        return cached[1]
    headers = {"User-Agent": "Mozilla/5.0 (trading-app-mf-screener)"}
    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            r = await client.get(MFAPI_URL.format(code=code), headers=headers)
            r.raise_for_status()
            payload = r.json()
        meta = payload.get("meta", {})
        result = {
            "fund_house": meta.get("fund_house", ""),
            "scheme_type": meta.get("scheme_type", ""),
            "scheme_category": meta.get("scheme_category", ""),
        }
        _meta_cache[code] = (time.time(), result)
        return result
    except Exception:
        return {}


async def _fetch_nav_history(code: str) -> pd.Series:
    """Fetch NAV history from mfapi.in with a retry (free API, often slow)."""
    headers = {"User-Agent": "Mozilla/5.0 (trading-app-mf-screener)"}
    payload = None
    last_err: Exception | None = None
    for _ in range(2):
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                r = await client.get(MFAPI_URL.format(code=code), headers=headers)
                r.raise_for_status()
                payload = r.json()
            break
        except Exception as e:
            last_err = e
    if payload is None:
        raise last_err or RuntimeError("mfapi.in fetch failed")
    rows = payload.get("data", [])
    if not rows:
        return pd.Series(dtype=float)
    df = pd.DataFrame(rows)
    df["date"] = pd.to_datetime(df["date"], format="%d-%m-%Y")
    df["nav"] = pd.to_numeric(df["nav"], errors="coerce")
    df = df.dropna(subset=["nav"]).sort_values("date").set_index("date")
    # Keep the last ~2 years.
    return df["nav"].last("730D")


async def _fetch_amfi_current_navs() -> dict[str, float]:
    """Fetch the AMFI NAVAll.txt dump and return {scheme_code: nav}.

    Reachable even when mfapi.in is blocked. Cached 15 min in-process.
    """
    global _amfi_cache, _amfi_cache_ts
    now = time.time()
    if _amfi_cache and (now - _amfi_cache_ts) < _AMFI_TTL:
        return _amfi_cache
    headers = {"User-Agent": "Mozilla/5.0 (trading-app-mf-screener)"}
    try:
        async with httpx.AsyncClient(timeout=20.0, follow_redirects=True) as client:
            r = await client.get(AMFI_NAVALL_URL, headers=headers)
            r.raise_for_status()
            text = r.text
    except Exception:
        return _amfi_cache  # may be stale/empty; caller handles

    navs: dict[str, float] = {}
    for line in text.splitlines():
        parts = line.split(";")
        # Data rows have >= 8 fields; field[0] is scheme code, field[6] is NAV.
        if len(parts) >= 8:
            code = parts[0].strip()
            try:
                nav = float(parts[6].strip().replace(",", ""))
            except (ValueError, IndexError):
                continue
            if code.isdigit() and nav > 0:
                navs[code] = nav
    if navs:
        _amfi_cache = navs
        _amfi_cache_ts = now
    return navs


def _load_local_nav_history(code: str) -> pd.Series | None:
    """Load locally accumulated AMFI NAV history from SQLite.

    Returns None if no history exists (e.g. before the daily snapshot job
    has run enough times). Once ~60+ days accumulate, the screener uses this
    for real risk metrics without needing mfapi.in.
    """
    try:
        from app.db import MfNavRow, SessionLocal
        db = SessionLocal()
        try:
            rows = db.query(MfNavRow).filter_by(scheme_code=code).order_by(MfNavRow.date).all()
        finally:
            db.close()
        if len(rows) < 2:
            return None
        idx = pd.DatetimeIndex([r.date for r in rows])
        return pd.Series([r.nav for r in rows], index=idx).astype(float)
    except Exception:
        return None


async def screen_mf(code: str, name: str, category: str, horizon_hint: str) -> MfScreen:
    nav: pd.Series | None = None
    try:
        nav = await _fetch_nav_history(code)
    except Exception as e:
        # mfapi.in unreachable — try locally accumulated AMFI history.
        nav = _load_local_nav_history(code)

    if nav is None or len(nav) < 60:
        # Not enough history — fall back to AMFI direct for current NAV.
        amfi_navs = await _fetch_amfi_current_navs()
        cur = amfi_navs.get(code)
        if cur and cur > 0:
            return _pending(code, name, category, horizon_hint, cur, [
                "Historical metrics unavailable (mfapi.in unreachable). "
                f"Showing current NAV ₹{cur:.4f} from AMFI. Risk metrics will "
                "populate as the daily AMFI snapshot accumulates."
            ])
        return _empty(code, name, category, horizon_hint, ["Failed to fetch NAV data."])

    if len(nav) < 60:
        return _empty(code, name, category, horizon_hint, ["Insufficient NAV history (<60 points)."])

    m = ind.risk_metrics(nav)
    last_nav = float(nav.iloc[-1])
    vol = m["volatility"]
    mdd = m["max_drawdown"]
    sharpe = m["sharpe"]
    cagr_val = m["cagr"]

    if vol < 0.12 and mdd > -0.15:
        risk_level = "low"
    elif vol < 0.20 and mdd > -0.28:
        risk_level = "moderate"
    else:
        risk_level = "high"

    if risk_level == "low":
        suggested_horizon = "short (6m+)"
    elif risk_level == "moderate":
        suggested_horizon = "medium (1-3y)"
    else:
        suggested_horizon = "long (3y+)"

    risks: list[str] = []
    if category in ("small-cap", "mid-cap"):
        risks.append(f"{category} funds are volatile; expect deep drawdowns in corrections.")
    if category == "hybrid":
        risks.append("Hybrid funds carry both equity and debt risk; not as safe as pure debt.")
    if category == "liquid":
        risks.append("Liquid funds are low-risk but also low-return; not for wealth creation.")
    if category == "flexi-cap":
        risks.append("Flexi-cap allocation shifts at manager discretion; performance varies by call quality.")
    if mdd < -0.30:
        risks.append(f"Historical max drawdown was {mdd*100:.1f}%.")
    if sharpe < 0.5:
        risks.append(f"Low risk-adjusted return (Sharpe {sharpe:.2f}).")
    risks.append("Past performance is not indicative of future returns; expense ratio and exit load also apply.")

    verdict = (
        f"{name}: {risk_level} risk, {cagr_val*100:.1f}% CAGR, "
        f"Sharpe {sharpe:.2f}, max DD {mdd*100:.1f}%. "
        f"Suggested horizon: {suggested_horizon}."
    )

    # New: fetch metadata, estimate expense ratio, set exit/entry strategy
    meta = await _fetch_mf_meta(code)
    exp_est, exp_note = _estimate_mf_expense(category)
    exit_load = _exit_load_for_category(category)

    # Entry/exit strategy for MFs (long-term, not technical levels)
    entry_strategy = (
        f"Start SIP at current NAV (₹{last_nav:.4f}). MFs are always investable — "
        f"stagger lumpsum over 3-4 months if market is near highs. "
        f"Best entered via SIP for rupee-cost averaging."
    )
    exit_strategy = (
        f"Review exit if: (1) drawdown exceeds 15% from your entry, "
        f"(2) fund underperforms category average for 3+ consecutive quarters, "
        f"(3) fund manager changes, or (4) your investment goal is met. "
        f"Avoid panic exits during market-wide corrections — hold through cycles."
        if category != "liquid" else
        "Liquid funds: exit anytime (no exit load). Use for parking cash, not wealth creation."
    )

    return MfScreen(
        code=code, name=name, category=category, horizon_hint=horizon_hint,
        last_nav=round(last_nav, 4), volatility=round(vol, 4),
        cagr=round(cagr_val, 4), max_drawdown=round(mdd, 4),
        sharpe=round(sharpe, 2), suggested_horizon=suggested_horizon,
        risk_level=risk_level, risks=risks, verdict=verdict,
        fund_house=meta.get("fund_house", ""),
        scheme_type=meta.get("scheme_type", ""),
        expense_ratio_est=exp_est,
        expense_ratio_note=exp_note,
        exit_load=exit_load,
        entry_strategy=entry_strategy,
        exit_strategy=exit_strategy,
    )


def _empty(code, name, category, horizon_hint, risks) -> MfScreen:
    exp_est, exp_note = _estimate_mf_expense(category)
    return MfScreen(
        code=code, name=name, category=category, horizon_hint=horizon_hint,
        last_nav=0.0, volatility=0.0, cagr=0.0, max_drawdown=0.0, sharpe=0.0,
        suggested_horizon="n/a", risk_level="unknown", risks=risks,
        verdict="Not enough data to screen.",
        expense_ratio_est=exp_est,
        expense_ratio_note=exp_note,
        exit_load=_exit_load_for_category(category),
    )


def _pending(code, name, category, horizon_hint, last_nav, risks) -> MfScreen:
    """Current NAV known from AMFI; historical metrics pending accumulation."""
    exp_est, exp_note = _estimate_mf_expense(category)
    return MfScreen(
        code=code, name=name, category=category, horizon_hint=horizon_hint,
        last_nav=round(last_nav, 4), volatility=0.0, cagr=0.0,
        max_drawdown=0.0, sharpe=0.0,
        suggested_horizon=horizon_hint or "n/a",
        risk_level="pending", risks=risks,
        verdict=(
            f"{name}: current NAV ₹{last_nav:.4f}. Historical risk metrics "
            f"pending — accumulating daily AMFI snapshots."
        ),
        expense_ratio_est=exp_est,
        expense_ratio_note=exp_note,
        exit_load=_exit_load_for_category(category),
        entry_strategy=(
            f"Start SIP at current NAV (₹{last_nav:.4f}). Risk metrics pending."
        ),
        exit_strategy="Review exit if drawdown exceeds 15% or fund underperforms category for 3+ quarters.",
    )


def to_dict(s: MfScreen) -> dict:
    return asdict(s)


async def snapshot_amfi_navs() -> int:
    """Pull AMFI NAVAll.txt and persist today's NAV for each tracked fund.

    Called by the daily scheduler (18:00 IST). Over time this builds the
    history needed for real risk metrics without depending on mfapi.in.
    Returns the number of NAVs persisted.
    """
    from app.db import MfNavRow, SessionLocal
    from app.market_hours import today_ist
    from app.universe import get_mutual_funds

    navs = await _fetch_amfi_current_navs()
    if not navs:
        log.warning("AMFI snapshot: no NAVs fetched, skipping")
        return 0

    funds = get_mutual_funds()
    today = today_ist()
    persisted = 0
    db = SessionLocal()
    try:
        for fund in funds:
            nav = navs.get(fund["code"])
            if not nav or nav <= 0:
                continue
            existing = db.query(MfNavRow).filter_by(
                scheme_code=fund["code"], date=today
            ).first()
            if existing:
                existing.nav = nav
            else:
                db.add(MfNavRow(scheme_code=fund["code"], date=today, nav=nav))
            persisted += 1
        db.commit()
        log.info("AMFI snapshot: persisted %d NAVs for %s", persisted, today)
    except Exception:
        db.rollback()
        log.exception("AMFI snapshot DB error")
    finally:
        db.close()
    return persisted
