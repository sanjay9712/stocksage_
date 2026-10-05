"""Growth projection for recently-listed IPOs.

Resolves each recent IPO to its live NSE ticker, pulls the current price and
fundamentals (PE, EPS, growth, ROE, debt), and models a fair-value target price
under two lenses:

  * Value target  — current (trailing) EPS × a growth-adjusted target P/E.
  * Growth target — EPS projected N years out at the company's own growth rate
                    × that same target P/E.

The two targets are compared to the live price to estimate *upside* (or
downside) — i.e. "how much it could go up" from today. Recent IPOs that have
already run up a lot (high price vs. earnings) will show little or negative
upside, which is the correct signal; the picker surfaces the cheaper, still-
growing names instead.

This is a rules-based estimate for research. It is **not** a price forecast and
**not** financial advice — see ``disclaimer`` in the response.
"""
from __future__ import annotations

import asyncio
import difflib
import logging
import re
from datetime import datetime, timezone

log = logging.getLogger("strategies.ipo_growth")

# ---- model constants ----
HORIZON_YEARS = 3        # how far out the growth target projects EPS
GROWTH_CAP = 0.35        # assume at most 35%/yr (avoids blow-ups on noisy data)
PEG_RATIO = 1.0          # target P/E ≈ 1.0 × expected growth (classic PEG=1, no premium)
PE_FLOOR = 10.0
PE_CEIL = 30.0
MIN_MCAP_CRS = 300.0     # ignore micro-caps below this market cap (₹ Cr)

_DISCLAIMER = (
    "Model-based fair-value estimate for research only — not a price forecast "
    "and not financial advice. Targets use reported earnings, a growth-adjusted "
    "P/E, and the company's own growth rate; real prices can and do diverge."
)

_MODEL_NOTES = {
    "horizon_years": HORIZON_YEARS,
    "growth_cap": GROWTH_CAP,
    "peg_ratio": PEG_RATIO,
    "value_target": "trailing EPS × target P/E",
    "growth_target": f"EPS projected {HORIZON_YEARS}y at company growth × target P/E",
    "target_pe": (
        f"growth-adjusted (PEG≈{PEG_RATIO}) blended with peer P/E when available, "
        f"clamped to {PE_FLOOR:.0f}–{PE_CEIL:.0f}"
    ),
    "ranking": "scored on modeled upside, growth rate, and quality (profitability, PEG, debt, ROE)",
}


# ---------------------------------------------------------------------------
# Ticker resolution (IPO company name → live NSE symbol)
# ---------------------------------------------------------------------------

_SUF = re.compile(
    r"\b(LIMITED|LTD|PRIVATE|PVT|COMPANY|CORPORATION|GROUP|LLP|CO|AND)\b\.?"
)


def _norm_name(s: str) -> str:
    s = (s or "").upper()
    s = _SUF.sub(" ", s)
    s = re.sub(r"[^A-Z0-9 ]", " ", s)
    return re.sub(r"\s+", " ", s).strip()


def build_name_index(nse_stocks: list[dict]) -> list[tuple[str, str]]:
    """Return [(normalized_name, symbol)] for fuzzy matching. Build once per run."""
    return [(_norm_name(s.get("name", "")), s.get("symbol", "").upper()) for s in nse_stocks]


def resolve_ticker(company_name: str, index: list[tuple[str, str]] | None = None,
                   nse_stocks: list[dict] | None = None) -> tuple[str | None, float]:
    """Resolve an IPO company name to an NSE symbol.

    Returns (symbol, confidence 0-1). symbol is None when no confident match.
    Pass ``index`` (from build_name_index) to avoid re-normalizing, else pass
    ``nse_stocks`` and it builds one (and caches it on the argument).
    """
    if index is None:
        if nse_stocks is None:
            return None, 0.0
        index = build_name_index(nse_stocks)

    q = _norm_name(company_name)
    if not q:
        return None, 0.0
    q_first = q.split()[0]

    best, best_ratio = None, 0.0
    for name, sym in index:
        if not sym:
            continue
        # Exact normalized-name match wins outright.
        if name == q:
            return sym, 1.0
        ratio = difflib.SequenceMatcher(None, q, name).ratio()
        # Strong bonus when the symbol itself appears in the company name
        # (e.g. "ESDS SOFTWARE..." → ESDS) — these are near-certain.
        if q_first and sym == q_first:
            ratio = max(ratio, 0.92)
        elif sym and (sym in q):
            ratio = max(ratio, 0.86)
        if ratio > best_ratio:
            best_ratio, best = ratio, sym

    if best and best_ratio >= 0.82:
        return best, round(best_ratio, 3)
    return None, round(best_ratio, 3)


# ---------------------------------------------------------------------------
# Growth / fair-value projection
# ---------------------------------------------------------------------------

def _peer_pe_from_ipo(ipo: dict) -> float | None:
    """Average peer P/E from the IPO's peer_comparison table (row 0 is the IPO)."""
    peers = ipo.get("peer_comparison") or []
    pes: list[float] = []
    for p in peers[1:]:
        if not isinstance(p, dict):
            continue
        for k, v in p.items():
            if k.strip().lower() in ("pe ratio", "pe", "p/e") and isinstance(v, (int, float)):
                pes.append(v)
                break
    return round(sum(pes) / len(pes), 2) if pes else None


def project_growth(fund: dict, last_price: float, peer_pe: float | None = None,
                   horizon: int = HORIZON_YEARS) -> dict:
    """Compute the fair-value targets and upside for one stock.

    ``fund`` is the dict from ``get_stock_fundamentals``; ``last_price`` is the
    current market price. Returns a flat dict of computed fields.
    """
    price = float(last_price) if last_price else 0.0
    eps = fund.get("earnings_per_share")
    trailing_pe = fund.get("trailing_pe")
    forward_pe = fund.get("forward_pe")
    revenue_growth = fund.get("revenue_growth")
    earnings_growth = fund.get("earnings_growth")
    roe = fund.get("return_on_equity")
    # yfinance reports debtToEquity as a PERCENT (17.73 = 0.177 ratio) — normalise.
    dte = fund.get("debt_to_equity")
    debt_to_equity = round(dte / 100.0, 2) if dte is not None else None
    market_cap = fund.get("market_cap")
    market_cap_crs = round(market_cap / 1e7, 1) if market_cap else None
    high52 = fund.get("52w_high")

    # Expected sustainable growth: prefer earnings growth, fall back to revenue.
    # ``g_raw`` is the reported figure (used for ranking/display); ``g`` is capped
    # for the target math so noisy small-cap data can't blow up the projection.
    g_raw: float | None = None
    if earnings_growth is not None and earnings_growth > 0:
        g_raw = float(earnings_growth)
    elif revenue_growth is not None and revenue_growth > 0:
        g_raw = float(revenue_growth)
    g = min(g_raw, GROWTH_CAP) if g_raw is not None else None

    # Target P/E: growth-adjusted (PEG) blended with peer P/E when available.
    growth_pe = (g * 100 * PEG_RATIO) if g is not None else 15.0
    growth_pe = max(PE_FLOOR, min(PE_CEIL, growth_pe))
    if peer_pe and 8.0 < peer_pe < 60.0:
        target_pe = 0.5 * growth_pe + 0.5 * min(peer_pe, PE_CEIL)
    else:
        target_pe = growth_pe
    target_pe = max(PE_FLOOR, min(PE_CEIL, target_pe))

    # Two upside lenses, so the user sees what's "earnings growth" vs "re-rating":
    #   value_target / upside_value  — today's earnings at the fair multiple.
    #   growth_target / upside_growth — earnings projected N yrs at the fair multiple
    #       (includes the move to the fair P/E, i.e. a re-rating for cheap stocks).
    #   earnings_upside — pure growth only: constant multiple, = (1+g)^N - 1.
    value_target = round(eps * target_pe, 2) if (eps and eps > 0) else None
    projected_eps = round(eps * ((1 + g) ** horizon), 2) if (eps and g is not None) else None
    growth_target = round(projected_eps * target_pe, 2) if projected_eps else None
    earnings_upside = round(((1 + g) ** horizon - 1) * 100, 1) if g is not None else None

    def _upside(target: float | None) -> float | None:
        if target and price > 0:
            return round((target - price) / price * 100, 1)
        return None

    upside_value = _upside(value_target)
    upside_growth = _upside(growth_target)
    headroom_high = round((high52 - price) / price * 100, 1) if (high52 and price > 0) else None

    # PEG on trailing earnings (lower = cheaper for the growth).
    peg = None
    if trailing_pe and g is not None and g > 0:
        peg = round(trailing_pe / (g * 100), 2)

    proj = {
        "current_price": round(price, 2),
        "eps": round(eps, 2) if eps is not None else None,
        "trailing_pe": round(trailing_pe, 1) if trailing_pe is not None else None,
        "forward_pe": round(forward_pe, 1) if forward_pe is not None else None,
        "revenue_growth": round(revenue_growth * 100, 1) if revenue_growth is not None else None,
        "earnings_growth": round(earnings_growth * 100, 1) if earnings_growth is not None else None,
        "growth_raw_pct": round(g_raw * 100, 1) if g_raw is not None else None,
        "assumed_growth": round(g * 100, 1) if g is not None else None,
        "roe": round(roe * 100, 1) if roe is not None else None,
        "debt_to_equity": debt_to_equity,
        "market_cap_crs": market_cap_crs,
        "target_pe": round(target_pe, 1),
        "value_target": value_target,
        "projected_eps": projected_eps,
        "growth_target": growth_target,
        "upside_value_pct": upside_value,
        "upside_growth_pct": upside_growth,
        "earnings_upside_pct": earnings_upside,
        "headroom_to_52w_high_pct": headroom_high,
        "peg": peg,
    }
    proj["verdict"] = _verdict(proj)
    proj["flags"] = _flags(proj)
    proj["rationale"] = _rationale(proj)
    return proj


def _verdict(p: dict) -> str:
    ug = p.get("upside_growth_pct")
    if p.get("current_price") in (None, 0):
        return "Insufficient Data"
    eps = p.get("eps")
    if eps is None:
        return "Insufficient Data"  # missing EPS ≠ a genuine loss
    if eps <= 0:
        return "Not Profitable"
    if ug is None:
        return "Flat Growth"
    near_high = (
        p.get("headroom_to_52w_high_pct") is not None
        and p["headroom_to_52w_high_pct"] <= 15
    )
    if ug >= 30:
        return "High Upside"
    if ug >= 10:
        return "Moderate Upside"
    if ug >= -5:
        return "Extended" if near_high else "Limited Upside"
    return "Overvalued"


def _flags(p: dict) -> list[str]:
    flags: list[str] = []
    if (p.get("eps") or 0) <= 0:
        flags.append("Loss-making (EPS ≤ 0)")
    if (p.get("trailing_pe") or 0) > 80:
        flags.append(f"Rich trailing P/E ({p['trailing_pe']:.0f})")
    if (p.get("peg") or 0) > 2.5:
        flags.append(f"High PEG ({p['peg']:.1f}) — expensive for its growth")
    if (p.get("debt_to_equity") or 0) > 1.0:
        flags.append(f"High debt/equity ({p['debt_to_equity']:.1f})")
    if p.get("headroom_to_52w_high_pct") is not None and p["headroom_to_52w_high_pct"] <= 15:
        flags.append("Trading near 52-week high (already run up)")
    return flags


def _rationale(p: dict) -> list[str]:
    r: list[str] = []
    if p.get("assumed_growth") is not None:
        r.append(f"Assumes ~{p['assumed_growth']:.0f}%/yr growth for {HORIZON_YEARS} years.")
    if p.get("earnings_upside_pct") is not None:
        r.append(
            f"Pure earnings growth (constant multiple) is worth {p['earnings_upside_pct']:+.0f}% "
            f"over {HORIZON_YEARS} years."
        )
    if p.get("growth_target") and p.get("current_price"):
        d = p["upside_growth_pct"]
        extra = ""
        if p.get("earnings_upside_pct") is not None and d - p["earnings_upside_pct"] > 20:
            extra = f" (includes ~{d - p['earnings_upside_pct']:.0f}% re-rating to a fair multiple)"
        r.append(
            f"Fair-value target ₹{p['growth_target']:.0f} = {d:+.0f}% vs the current ₹{p['current_price']:.0f}{extra}."
        )
    if p.get("value_target") and p.get("current_price"):
        d = p["upside_value_pct"]
        r.append(f"Value target (today's earnings) ₹{p['value_target']:.0f} = {d:+.0f}%.")
    if p.get("flags"):
        r.append("Watch: " + "; ".join(p["flags"]) + ".")
    return r


def _growth_score(p: dict) -> float:
    """0-100 rank: genuine growth (50) + fair-value upside (30) + quality (20).

    Growth uses the *reported* (uncapped) rate so faster growers rank higher,
    while the upside component uses the model's fair-value estimate.
    """
    score = 0.0
    gr = p.get("growth_raw_pct")
    if gr:
        score += max(0.0, min(50.0, (gr / 40.0) * 50))  # 0-40% growth → 0-50
    ug = p.get("upside_growth_pct")
    if ug is not None:
        score += max(0.0, min(30.0, ((ug + 20) / 120) * 30))  # -20..+100% → 0-30
    q = 0.0
    if (p.get("eps") or 0) > 0:
        q += 6
    if (p.get("assumed_growth") or 0) > 0:
        q += 4
    if p.get("peg") is not None and 0 < p["peg"] <= 2:
        q += 4
    if (p.get("debt_to_equity") or 0) < 0.8:
        q += 3
    if (p.get("roe") or 0) > 12:
        q += 3
    score += min(20.0, q)
    return round(score, 1)


# ---------------------------------------------------------------------------
# Orchestration
# ---------------------------------------------------------------------------

async def analyze_symbol(symbol: str) -> dict:
    """Analyze a single ticker (used by the manual search box)."""
    from app.providers.fundamentals import get_stock_fundamentals
    from app.providers.factory import get_provider

    sym = symbol.strip().upper()
    fund = await get_stock_fundamentals(sym)
    provider = get_provider()
    try:
        q = await provider.get_quote(sym)
        price = q.price if (q and q.price) else None
    except Exception:
        price = None
    if not price:
        eps, pe = fund.get("earnings_per_share"), fund.get("trailing_pe")
        price = round(eps * pe, 2) if (eps and pe) else None
    if not price:
        return {"symbol": sym, "company_name": fund.get("company_name"), "error": "No price data available."}
    proj = project_growth(fund, price, None)
    proj.update({
        "symbol": sym,
        "company_name": fund.get("company_name"),
        "sector": fund.get("sector"),
        "industry": fund.get("industry"),
        "growth_score": _growth_score(proj),
    })
    return proj


async def pick_growth_stocks(limit: int = 40, board: str = "mainboard",
                             min_mcap_crs: float = MIN_MCAP_CRS) -> dict:
    """Screen recent IPOs, resolve to live tickers, and rank by upside.

    ``board`` is "mainboard" (default — investable, cleaner data), "sme", or
    "all". Names below ``min_mcap_crs`` (₹ Cr) are dropped from the ranked
    list to keep out illiquid micro-caps.
    """
    from app.providers.ipo_provider import fetch_all_ipos
    from app.providers.nse_list import get_nse_stocks
    from app.providers.fundamentals import get_stock_fundamentals
    from app.providers.factory import get_provider

    data = await fetch_all_ipos()
    boards = ("mainboard", "sme") if board == "all" else (board,)
    recent: list[dict] = []
    for b in boards:
        recent.extend((data.get(b, {}) or {}).get("recent", []) or [])

    # De-dupe by company name.
    seen: set[str] = set()
    uniq: list[dict] = []
    for ipo in recent:
        key = (ipo.get("company_name") or "").upper()
        if key and key not in seen:
            seen.add(key)
            uniq.append(ipo)

    nse = await get_nse_stocks()
    index = build_name_index(nse)
    provider = get_provider()
    sem = asyncio.Semaphore(8)

    async def _one(ipo: dict):
        company = ipo.get("company_name") or ""
        sym, conf = resolve_ticker(company, index)
        if not sym:
            return None
        async with sem:
            try:
                fund = await get_stock_fundamentals(sym)
            except Exception:
                return None
            try:
                q = await provider.get_quote(sym)
                price = q.price if (q and q.price) else None
            except Exception:
                price = None
            if not price:
                eps, pe = fund.get("earnings_per_share"), fund.get("trailing_pe")
                price = round(eps * pe, 2) if (eps and pe) else None
            if not price:
                return None
        peer_pe = _peer_pe_from_ipo(ipo)
        proj = project_growth(fund, price, peer_pe)
        proj.update({
            "symbol": sym,
            "company_name": company,
            "resolved_confidence": conf,
            "board": ipo.get("board"),
            "listing_date": ipo.get("listing_date"),
            "allotment_price": ipo.get("allotment_price"),
            "listing_return_pct": ipo.get("listing_return_pct"),
            "sector": fund.get("sector"),
            "industry": fund.get("industry"),
            "growth_score": _growth_score(proj),
        })
        return proj

    results = await asyncio.gather(*(_one(i) for i in uniq), return_exceptions=True)
    analyzed = [r for r in results if isinstance(r, dict)]
    # Drop illiquid micro-caps from the ranked list (keep count for transparency).
    picks = [p for p in analyzed
             if p.get("market_cap_crs") is None or p["market_cap_crs"] >= min_mcap_crs]
    picks.sort(key=lambda x: x.get("growth_score", 0), reverse=True)

    return {
        "picks": picks[:limit],
        "total_analyzed": len(analyzed),
        "total_recent": len(uniq),
        "board": board,
        "min_mcap_crs": min_mcap_crs,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "horizon_years": HORIZON_YEARS,
        "model": _MODEL_NOTES,
        "disclaimer": _DISCLAIMER,
    }
