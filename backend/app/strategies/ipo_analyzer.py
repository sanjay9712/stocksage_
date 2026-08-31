"""IPO selection scoring — pure functions, no network calls.

Computes a 0-100 selection score for each IPO based on 9 factors:
subscription momentum, GMP signal, issue pricing, issue size, timeline
freshness, registrar quality, board type, market maker presence, and
data completeness.
"""
from __future__ import annotations

from datetime import date, datetime, timezone

TOP_REGISTRARS = {
    "linkintime", "kfintech", "bigshare", "mashitran", "skyline",
    "link intime", "k fin technologies", "kfintech", "big share",
}


def _score_subscription(sub: dict | None) -> float:
    """0-25 based on total subscription times."""
    if not sub:
        return 12.5  # neutral — no data (typically upcoming IPOs)
    total = sub.get("total")
    if total is None:
        return 12.5
    # Map [0x, 50x] → [0, 25], cap at 50x.
    clamped = min(max(total, 0), 50)
    return round((clamped / 50) * 25, 2)


def _score_gmp(gmp: dict | None) -> float:
    """0-20 based on GMP percentage."""
    if not gmp:
        return 10.0  # neutral
    pct = gmp.get("premium_pct")
    if pct is None:
        # Try to derive pct from premium and a price estimate.
        premium = gmp.get("premium")
        if premium is None:
            return 10.0
        # Can't compute pct without price — use premium as a rough proxy.
        # ₹0-10 premium = low, ₹50+ = strong.
        if premium <= 0:
            return 0.0
        clamped = min(premium, 100)
        return round((clamped / 100) * 20, 2)
    # Map [-5%, +30%] → [0, 20], clamp.
    if pct <= -5:
        return 0.0
    if pct >= 30:
        return 20.0
    return round(((pct + 5) / 35) * 20, 2)


def _score_pricing(price_high: float | None, face_value: float | None) -> float:
    """0-15 — penalizes excessively priced issues (price/face_value)."""
    if not price_high or not face_value or face_value <= 0:
        return 7.5  # neutral
    ratio = price_high / face_value
    if ratio <= 50:
        return 15.0
    if ratio <= 200:
        # Scale from 15 down to 5.
        return round(15 - ((ratio - 50) / 150) * 10, 2)
    return 3.0  # minimal — very high premium


def _score_issue_size(issue_size_crs: float | None, board: str) -> float:
    """0-10 based on issue size (larger = more stable)."""
    if not issue_size_crs:
        return 5.0  # neutral
    # Map [0, 5000 Cr] → [0, 10], cap at 5000.
    clamped = min(max(issue_size_crs, 0), 5000)
    return round((clamped / 5000) * 10, 2)


def _score_freshness(status: str, listing_date: str | None) -> float:
    """0-10 based on timeline position."""
    if status == "current":
        return 10.0
    if status == "upcoming":
        return 8.0
    if status == "recent":
        if listing_date:
            try:
                ld = datetime.strptime(listing_date, "%Y-%m-%d").date()
                days_ago = (date.today() - ld).days
                if days_ago <= 30:
                    return 5.0
                if days_ago <= 90:
                    return 3.0
            except ValueError:
                pass
        return 2.0
    return 0.0


def _score_registrar(registrar: str | None) -> float:
    """0-5 — known top registrars get full marks."""
    if not registrar:
        return 2.0
    r_lower = registrar.lower()
    if any(name in r_lower for name in TOP_REGISTRARS):
        return 5.0
    return 2.0


def _score_board(board: str) -> float:
    """0-5 — mainboard gets full marks, SME is riskier."""
    return 5.0 if board == "mainboard" else 1.0


def _score_market_maker(market_maker: str | None) -> float:
    """0-5 — presence of a market maker (especially for SME)."""
    return 5.0 if market_maker else 0.0


def _score_completeness(ipo: dict) -> float:
    """0-5 — penalize missing fields."""
    fields = [
        "price_band", "issue_size_crs", "lot_size",
        "open_date", "close_date", "subscription", "gmp",
        "registrar", "face_value",
    ]
    missing = sum(1 for f in fields if not ipo.get(f))
    return round(max(0, 5 - missing * 0.5), 2)


def score_ipo(ipo: dict) -> tuple[float, dict]:
    """Compute the 0-100 selection score.

    Returns (total_score, factors_dict).
    """
    sub = ipo.get("subscription")
    factors = {
        "subscription": _score_subscription(sub),
        "gmp": _score_gmp(ipo.get("gmp")),
        "pricing": _score_pricing(ipo.get("price_high"), ipo.get("face_value")),
        "issue_size": _score_issue_size(ipo.get("issue_size_crs"), ipo.get("board")),
        "freshness": _score_freshness(ipo.get("status"), ipo.get("listing_date")),
        "registrar": _score_registrar(ipo.get("registrar")),
        "board": _score_board(ipo.get("board", "")),
        "market_maker": _score_market_maker(ipo.get("market_maker")),
        "completeness": _score_completeness(ipo),
    }
    total = round(sum(factors.values()), 2)
    return total, factors


def annotate_ipos(data: dict) -> dict:
    """Walk the {mainboard: {...}, sme: {...}} structure and fill scores.

    Mutates each IPO dict in-place adding selection_score + score_factors.
    Returns the same data dict.
    """
    for board_key in ("mainboard", "sme"):
        board = data.get(board_key, {})
        if not isinstance(board, dict):
            continue
        for section in ("current", "recent", "upcoming"):
            items = board.get(section, [])
            if not isinstance(items, list):
                continue
            for ipo in items:
                if isinstance(ipo, dict):
                    score, factors = score_ipo(ipo)
                    ipo["selection_score"] = score
                    ipo["score_factors"] = factors
    return data
