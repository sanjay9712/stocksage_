"""IPO selection scoring — pure functions, no network calls.

Computes a 0-100 selection score for each IPO based on 10 factors:
subscription momentum, GMP signal, issue pricing, issue size, timeline
freshness, registrar quality, board type, market maker presence,
financial health, and data completeness.
"""
from __future__ import annotations

import re
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


def _score_financials(ipo: dict) -> float:
    """0-5 — based on financial health (revenue growth, margin trend, profitability).

    Uses financials table (Revenue, Net Income, Margin) and return ratios
    (RONW, ROCE, Debt/Equity) from the detail page.
    """
    fin = ipo.get("financials")
    ratios = ipo.get("return_ratios")
    if not fin and not ratios:
        return 2.5  # neutral — no data

    score = 0.0
    components = 0

    # Revenue growth: compare latest vs earliest year.
    if fin and "Revenue" in fin:
        rev = fin["Revenue"]
        rev_values = [v for v in rev.values() if isinstance(v, (int, float))]
        if len(rev_values) >= 2:
            earliest, latest = rev_values[0], rev_values[-1]
            if earliest > 0:
                growth = (latest - earliest) / earliest
                # Growth > 20% = 1.5, growth > 0 = 1.0, negative = 0.0
                if growth > 0.2:
                    score += 1.5
                elif growth > 0:
                    score += 1.0
                else:
                    score += 0.0
                components += 1

    # Profitability: Net Income positive in latest year.
    if fin and "Net Income" in fin:
        ni = fin["Net Income"]
        ni_values = [v for v in ni.values() if isinstance(v, (int, float))]
        if ni_values:
            latest_ni = ni_values[-1]
            if latest_ni > 0:
                score += 1.0
            components += 1

    # Margin trend: improving margins.
    if fin and "Margin (%)" in fin:
        mar = fin["Margin (%)"]
        mar_values = [v for v in mar.values() if isinstance(v, (int, float))]
        if len(mar_values) >= 2:
            if mar_values[-1] > mar_values[0]:
                score += 0.5  # improving
            elif mar_values[-1] > 0:
                score += 0.25  # at least positive
            components += 1

    # Debt/Equity: lower is better.
    if ratios and "Debt/Equity" in ratios:
        de = ratios["Debt/Equity"]
        de_values = [v for v in de.values() if isinstance(v, (int, float))]
        if de_values:
            latest_de = de_values[-1]
            if latest_de < 0.5:
                score += 1.0
            elif latest_de < 1.0:
                score += 0.5
            components += 1

    # RONW: higher is better.
    if ratios and "RONW (%)" in ratios:
        ronw = ratios["RONW (%)"]
        ronw_values = [v for v in ronw.values() if isinstance(v, (int, float))]
        if ronw_values:
            latest_ronw = ronw_values[-1]
            if latest_ronw > 20:
                score += 1.0
            elif latest_ronw > 10:
                score += 0.5
            components += 1

    if components == 0:
        return 2.5

    # Normalize to 0-5 scale.
    max_possible = components * 1.0  # each component can contribute up to ~1.5
    normalized = min((score / max_possible) * 5.0, 5.0) if max_possible > 0 else 2.5
    return round(normalized, 2)


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
        "financials": _score_financials(ipo),
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
                    ipo["recommendation"] = recommend_ipo(ipo, score)
    return data


# ---------------------------------------------------------------------------
# IPO recommendation — verdict + pros/cons with domain knowledge
# ---------------------------------------------------------------------------

def _latest_value(fin: dict | None, metric: str) -> float | None:
    """Return the latest numeric value for a metric in a {year: value} dict."""
    if not fin or metric not in fin:
        return None
    vals = [v for v in fin[metric].values() if isinstance(v, (int, float))]
    return vals[-1] if vals else None


def _growth(fin: dict | None, metric: str) -> float | None:
    """Return CAGR-like growth from earliest to latest year."""
    if not fin or metric not in fin:
        return None
    vals = [v for v in fin[metric].values() if isinstance(v, (int, float))]
    if len(vals) < 2 or vals[0] == 0:
        return None
    return (vals[-1] - vals[0]) / abs(vals[0])


def _issue_structure(ipo: dict) -> dict:
    """Analyse Fresh Issue vs OFS split.

    Fresh Issue: money goes to the company (growth, debt reduction) — positive.
    OFS: existing shareholders/promoters sell their shares — money leaves the
    company. A high OFS % signals promoter exit and is a red flag.
    """
    fresh = ipo.get("fresh_issue_crs")
    ofs = ipo.get("ofs_amount_crs")
    total = ipo.get("issue_size_crs")
    if total and total > 0:
        if fresh is None and ofs:
            fresh = max(total - ofs, 0)
        if ofs is None and fresh:
            ofs = max(total - fresh, 0)
    fresh_pct = (fresh / total * 100) if (fresh is not None and total and total > 0) else None
    ofs_pct = (ofs / total * 100) if (ofs is not None and total and total > 0) else None
    return {
        "fresh_issue_crs": fresh,
        "ofs_amount_crs": ofs,
        "fresh_pct": round(fresh_pct, 1) if fresh_pct is not None else None,
        "ofs_pct": round(ofs_pct, 1) if ofs_pct is not None else None,
        "promoter_exit_heavy": ofs_pct is not None and ofs_pct > 50,
    }


def _valuation_vs_peers(ipo: dict) -> dict:
    """Compare the IPO's PE ratio to the peer average.

    A PE below the peer median suggests reasonable pricing; above suggests
    overvaluation (unless justified by superior growth/returns).
    """
    peers = ipo.get("peer_comparison") or []
    metrics = ipo.get("per_share_metrics") or {}

    # Extract the IPO's own post-issue PE ratio (string like "15.41 - 16.24").
    ipo_pe = None
    if metrics and "PE Ratio" in metrics:
        pe_vals = list(metrics["PE Ratio"].values())
        if pe_vals:
            pe_str = str(pe_vals[-1])
            nums = re.findall(r"[\d.]+", pe_str)
            if nums:
                ipo_pe = float(nums[-1])  # take upper end for conservatism

    # Extract peer PE ratios.
    peer_pes = []
    for p in peers[1:]:  # skip first row (the IPO itself)
        for k, v in p.items():
            if k.strip().lower() in ("pe ratio", "pe", "p/e") and isinstance(v, (int, float)):
                peer_pes.append(v)
                break

    peer_avg = round(sum(peer_pes) / len(peer_pes), 2) if peer_pes else None
    discount = None
    if ipo_pe and peer_avg and peer_avg > 0:
        discount = round(((ipo_pe - peer_avg) / peer_avg) * 100, 1)

    return {
        "ipo_pe": ipo_pe,
        "peer_pe_avg": peer_avg,
        "discount_to_peers_pct": discount,  # negative = cheaper, positive = premium
    }


def recommend_ipo(ipo: dict, score: float | None = None) -> dict:
    """Generate an invest/avoid recommendation with pros, cons, and a summary.

    Encodes IPO evaluation domain knowledge:
      - Issue structure: Fresh Issue (company gets funds) vs OFS (promoter exit)
      - Subscription demand: QIB > 5x = strong institutional interest
      - GMP: grey market premium signals secondary demand
      - Anchor investors: their participation locks in institutional confidence
      - Financials: revenue growth, profitability, debt/equity, RONW
      - Valuation: PE vs peer average
      - Board type: mainboard (stricter SEBI compliance) vs SME (riskier)
      - Registrar/market maker: operational quality signals

    Returns:
      verdict: "Apply" | "Consider" | "Avoid" | "Insufficient Data"
      pros: list of positive signals (string)
      cons: list of negative signals (string)
      summary: one-paragraph summary
      issue_structure: dict from _issue_structure
      valuation: dict from _valuation_vs_peers
    """
    if score is None:
        score = ipo.get("selection_score") or 0

    pros: list[str] = []
    cons: list[str] = []
    critical_flags: list[str] = []

    # --- Issue structure ---
    struct = _issue_structure(ipo)
    if struct["fresh_pct"] is not None:
        if struct["fresh_pct"] >= 75:
            pros.append(f"Fresh issue is {struct['fresh_pct']}% of the total — most funds go to the company for growth/debt reduction.")
        elif struct["ofs_pct"] is not None and struct["ofs_pct"] >= 75:
            cons.append(f"OFS is {struct['ofs_pct']}% of the issue — promoters/existing shareholders are exiting, not funding the company.")
    if struct["promoter_exit_heavy"]:
        critical_flags.append("Promoter-exit heavy (OFS > 50% of issue size)")

    # --- Subscription demand ---
    sub = ipo.get("subscription") or {}
    if sub.get("total") is not None:
        total_sub = sub["total"]
        if total_sub >= 10:
            pros.append(f"Strong overall subscription: {total_sub:.1f}x.")
        elif total_sub >= 3:
            pros.append(f"Healthy subscription: {total_sub:.1f}x.")
        elif total_sub < 1 and total_sub > 0:
            cons.append(f"Weak subscription: only {total_sub:.2f}x — below 1x means undersubscribed.")
    if sub.get("qib") is not None:
        qib = sub["qib"]
        if qib >= 5:
            pros.append(f"Strong QIB demand: {qib:.1f}x — institutional investors are bullish.")
        elif qib < 1 and qib >= 0:
            cons.append(f"QIB subscription is {qib:.2f}x — below 1x signals weak institutional interest.")

    # --- GMP (Grey Market Premium) ---
    gmp = ipo.get("gmp") or {}
    if gmp.get("premium_pct") is not None:
        pct = gmp["premium_pct"]
        if pct >= 15:
            pros.append(f"GMP is +{pct:.1f}% — strong grey-market demand for listing gains.")
        elif pct >= 5:
            pros.append(f"GMP is +{pct:.1f}% — moderate positive grey-market sentiment.")
        elif pct < 0:
            cons.append(f"GMP is {pct:.1f}% — negative grey-market premium indicates weak listing expectations.")
    elif gmp.get("premium") is not None and gmp["premium"] > 0:
        pros.append(f"GMP is ₹{gmp['premium']} (positive).")

    # --- Anchor investors ---
    anchor = ipo.get("anchor_investors") or {}
    if anchor.get("amount_crs"):
        pros.append(f"Anchor investors committed ₹{anchor['amount_crs']:.0f} Cr — institutional confidence with lock-in.")
        # Compute anchor % of issue if possible
        total = ipo.get("issue_size_crs")
        if total and total > 0:
            anchor_pct = anchor["amount_crs"] / total * 100
            if anchor_pct >= 30:
                pros.append(f"Anchor portion is {anchor_pct:.0f}% of the issue — high institutional backing.")
    else:
        if ipo.get("status") == "current":
            cons.append("No anchor investor data — institutional demand unclear.")

    # --- Financials ---
    fin = ipo.get("financials")
    ratios = ipo.get("return_ratios")

    rev_growth = _growth(fin, "Revenue") if fin else None
    if rev_growth is not None:
        if rev_growth > 0.3:
            pros.append(f"Revenue grew {rev_growth*100:.0f}% over the reported period — strong top-line growth.")
        elif rev_growth < 0:
            cons.append(f"Revenue declined {abs(rev_growth)*100:.0f}% over the reported period.")

    latest_ni = _latest_value(fin, "Net Income") if fin else None
    if latest_ni is not None:
        if latest_ni > 0:
            pros.append("Company is profitable (positive net income in the latest year).")
        else:
            critical_flags.append("Company is loss-making in the latest reported year.")

    # Margin trend
    if fin and "Margin (%)" in fin:
        mar_vals = [v for v in fin["Margin (%)"].values() if isinstance(v, (int, float))]
        if len(mar_vals) >= 2:
            if mar_vals[-1] > mar_vals[0] and mar_vals[-1] > 0:
                pros.append(f"Margins are improving ({mar_vals[0]:.1f}% → {mar_vals[-1]:.1f}%).")
            elif mar_vals[-1] < mar_vals[0]:
                cons.append(f"Margins are declining ({mar_vals[0]:.1f}% → {mar_vals[-1]:.1f}%).")

    # Debt/Equity
    latest_de = _latest_value(ratios, "Debt/Equity") if ratios else None
    if latest_de is not None:
        if latest_de < 0.5:
            pros.append(f"Low debt-to-equity ratio ({latest_de:.2f}) — healthy balance sheet.")
        elif latest_de > 1.0:
            cons.append(f"High debt-to-equity ratio ({latest_de:.2f}) — leveraged balance sheet.")

    # RONW
    latest_ronw = _latest_value(ratios, "RONW (%)") if ratios else None
    if latest_ronw is not None:
        if latest_ronw > 20:
            pros.append(f"Strong return on net worth ({latest_ronw:.1f}%) — efficient equity deployment.")
        elif latest_ronw < 10:
            cons.append(f"Low return on net worth ({latest_ronw:.1f}%) — below-average capital efficiency.")

    # --- Valuation vs peers ---
    val = _valuation_vs_peers(ipo)
    if val["discount_to_peers_pct"] is not None:
        d = val["discount_to_peers_pct"]
        if d < -10:
            pros.append(f"Priced at a {abs(d):.0f}% discount to peer average PE — reasonably valued.")
        elif d > 20:
            cons.append(f"Priced at a {d:.0f}% premium to peer average PE — potentially overvalued.")

    # --- Board type ---
    board = ipo.get("board", "")
    if board == "mainboard":
        pros.append("Mainboard IPO — stricter SEBI disclosure and compliance requirements.")
    else:
        cons.append("SME board IPO — lower disclosure thresholds, less liquidity, higher risk.")
        if not ipo.get("market_maker"):
            critical_flags.append("SME IPO without a market maker — liquidity risk post-listing.")
        else:
            pros.append("Market maker appointed — provides post-listing liquidity support.")

    # --- Registrar quality ---
    registrar = ipo.get("registrar") or ""
    if registrar and any(r in registrar.lower() for r in TOP_REGISTRARS):
        pros.append(f"Top-tier registrar ({registrar}) — smoother allotment process.")

    # --- Verdict ---
    has_critical = len(critical_flags) > 0
    if score < 35 or (has_critical and score < 50):
        verdict = "Avoid"
    elif score >= 65 and not has_critical:
        verdict = "Apply"
    else:
        verdict = "Consider"

    if not pros and not cons:
        verdict = "Insufficient Data"

    # --- Criteria checklist — explains exactly why this verdict was reached ---
    criteria = []
    # Score threshold
    criteria.append({
        "factor": "Selection Score",
        "value": f"{score:.0f}/100",
        "threshold": "≥65 for Apply, <35 for Avoid",
        "met": score >= 65 if verdict == "Apply" else (score >= 35 if verdict == "Consider" else True),
        "detail": f"Score of {score:.0f} {'meets' if score >= 65 else 'falls below'} the Apply threshold (65)." if verdict != "Avoid" else f"Score of {score:.0f} is below the Avoid threshold (35).",
    })
    # Critical flags
    criteria.append({
        "factor": "Red Flags",
        "value": f"{len(critical_flags)} found",
        "threshold": "0 for Apply",
        "met": len(critical_flags) == 0,
        "detail": "; ".join(critical_flags) if critical_flags else "No critical red flags detected.",
    })
    # Subscription
    if sub.get("total") is not None:
        total_sub = sub["total"]
        criteria.append({
            "factor": "Subscription Demand",
            "value": f"{total_sub:.1f}x",
            "threshold": "≥3x healthy, ≥10x strong",
            "met": total_sub >= 3,
            "detail": f"Overall subscription is {total_sub:.1f}x." + (" Strong demand." if total_sub >= 10 else (" Healthy." if total_sub >= 3 else " Weak — below 3x.")),
        })
    # GMP
    if gmp.get("premium_pct") is not None:
        pct = gmp["premium_pct"]
        criteria.append({
            "factor": "Grey Market Premium (GMP)",
            "value": f"{pct:+.1f}%",
            "threshold": "≥+5% positive, ≥+15% strong",
            "met": pct >= 5,
            "detail": f"GMP is {pct:+.1f}%." + (" Strong grey-market demand." if pct >= 15 else (" Positive." if pct >= 5 else (" Negative." if pct < 0 else " Neutral."))),
        })
    # Anchor investors
    if anchor.get("amount_crs"):
        anchor_pct = (anchor["amount_crs"] / ipo.get("issue_size_crs", 1)) * 100 if ipo.get("issue_size_crs") else 0
        criteria.append({
            "factor": "Anchor Investors",
            "value": f"₹{anchor['amount_crs']:.0f} Cr ({anchor_pct:.0f}% of issue)",
            "threshold": "≥30% high backing",
            "met": anchor_pct >= 30,
            "detail": f"Anchor investors committed ₹{anchor['amount_crs']:.0f} Cr ({anchor_pct:.0f}% of issue)." + (" High institutional backing." if anchor_pct >= 30 else " Moderate backing."),
        })
    # Valuation vs peers
    if val["discount_to_peers_pct"] is not None:
        d = val["discount_to_peers_pct"]
        criteria.append({
            "factor": "Valuation vs Peers",
            "value": f"{val['ipo_pe']:.1f} PE vs {val['peer_pe_avg']:.1f} peer avg",
            "threshold": "≤0% (discount) is good",
            "met": d <= 0,
            "detail": f"Priced at a {abs(d):.0f}% {'discount' if d < 0 else 'premium'} to peer average PE.",
        })
    # Financials — profitability
    if latest_ni is not None:
        criteria.append({
            "factor": "Profitability",
            "value": "Profitable" if latest_ni > 0 else "Loss-making",
            "threshold": "Profitable for Apply",
            "met": latest_ni > 0,
            "detail": "Company is profitable (positive net income)." if latest_ni > 0 else "Company is loss-making in the latest reported year.",
        })
    # Issue structure
    if struct["fresh_pct"] is not None:
        criteria.append({
            "factor": "Issue Structure",
            "value": f"{struct['fresh_pct']:.0f}% fresh, {struct['ofs_pct']:.0f}% OFS" if struct['ofs_pct'] is not None else f"{struct['fresh_pct']:.0f}% fresh",
            "threshold": "High fresh % is good",
            "met": struct["fresh_pct"] >= 50,
            "detail": f"Fresh issue is {struct['fresh_pct']:.0f}% of the total." + (" Most funds go to the company." if struct["fresh_pct"] >= 75 else (" Promoter-exit heavy." if struct.get("ofs_pct", 0) and struct["ofs_pct"] > 50 else " Balanced structure.")),
        })
    # Board type
    criteria.append({
        "factor": "Board Type",
        "value": board or "Unknown",
        "threshold": "Mainboard preferred",
        "met": board == "mainboard",
        "detail": "Mainboard IPO — stricter SEBI compliance." if board == "mainboard" else "SME board — higher risk, lower liquidity.",
    })

    # --- Summary paragraph ---
    parts = []
    if struct["fresh_pct"] is not None:
        parts.append(f"Fresh issue is {struct['fresh_pct']:.0f}% of the ₹{ipo.get('issue_size_crs', 0):.0f} Cr issue")
    if sub.get("total") is not None:
        parts.append(f"subscription is {sub['total']:.1f}x")
    if gmp.get("premium_pct") is not None:
        parts.append(f"GMP is {gmp['premium_pct']:+.1f}%")
    if val["ipo_pe"] is not None and val["peer_pe_avg"] is not None:
        parts.append(f"PE of {val['ipo_pe']:.1f} vs peer avg {val['peer_pe_avg']:.1f}")
    summary = (", ".join(parts) + ".") if parts else "Limited data available for analysis."
    if critical_flags:
        summary += " Key concern: " + "; ".join(critical_flags) + "."

    return {
        "verdict": verdict,
        "pros": pros,
        "cons": cons,
        "critical_flags": critical_flags,
        "summary": summary,
        "issue_structure": struct,
        "valuation": val,
        "criteria": criteria,
    }
