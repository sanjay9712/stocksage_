"""IPO data provider — scrapes ipocentral.in for current, upcoming, and recent IPOs.

ipocentral.in is a WordPress site with server-rendered HTML tables:
  - Homepage: 2 tables — Upcoming Main Board + SME IPOs (includes currently open)
  - /ipo-2026/: Listed mainboard IPOs in 2026 (recent)
  - /sme-ipo-2026/: Listed SME IPOs in 2026 (recent)
  - Detail pages (e.g. /deepa-jewellers-ipo-gmp-price-allotment/):
    10 tables with IPO details, financials, GMP history, subscription,
    anchor investors, peer comparison, and IPO timeline.

Data is fetched in parallel (detail pages via asyncio.gather with a semaphore)
so a full refresh takes ~3-5s for ~24 IPOs.
"""
from __future__ import annotations

import asyncio
import logging
import re
import time
from datetime import datetime, timezone

import httpx

log = logging.getLogger("ipo_provider")

BASE_URL = "https://ipocentral.in"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
}

# Cache for the full IPO dataset (10 min TTL — GMP/subscription change during market hours).
_cache: dict = {"data": None, "ts": 0, "ttl": 600}

_MONTHS = {
    "jan": 1, "feb": 2, "mar": 3, "apr": 4, "may": 5, "jun": 6,
    "jul": 7, "aug": 8, "sep": 9, "oct": 10, "nov": 11, "dec": 12,
    "january": 1, "february": 2, "march": 3, "april": 4, "june": 6,
    "july": 7, "august": 8, "september": 9, "october": 10, "november": 11, "december": 12,
}


# ---------------------------------------------------------------------------
# HTML parsing helpers
# ---------------------------------------------------------------------------

def _clean(text: str) -> str:
    """Strip HTML tags, decode entities, and normalize whitespace."""
    text = text.replace("&#8211;", "-").replace("&#8212;", "-")
    text = text.replace("&nbsp;", " ").replace("&amp;", "&")
    text = text.replace("&#8377;", "₹").replace("&₹;", "₹")
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", "", text)).strip()


def _extract_tables(html: str) -> list[list[list[str]]]:
    """Extract all tables from HTML as list of tables, each a list of rows, each a list of clean text cells."""
    tables = re.findall(r"<table[^>]*>(.*?)</table>", html, re.DOTALL | re.IGNORECASE)
    result = []
    for table in tables:
        rows = re.findall(r"<tr[^>]*>(.*?)</tr>", table, re.DOTALL | re.IGNORECASE)
        table_rows = []
        for row in rows:
            cells = re.findall(r"<t[hd][^>]*>(.*?)</t[hd]>", row, re.DOTALL | re.IGNORECASE)
            clean_cells = [_clean(c) for c in cells]
            if any(clean_cells):
                table_rows.append(clean_cells)
        if table_rows:
            result.append(table_rows)
    return result


def _extract_links_from_cell(cell_html: str) -> str | None:
    """Extract the first href from a table cell's raw HTML."""
    m = re.search(r'href=["\']([^"\']+)["\']', cell_html)
    return m.group(1) if m else None


def _extract_link_tables(html: str) -> list[list[dict]]:
    """Extract tables preserving links in the first column.

    Returns list of tables; each table is a list of row dicts with
    {company, link, col_1, col_2, ...} keys.
    """
    tables = re.findall(r"<table[^>]*>(.*?)</table>", html, re.DOTALL | re.IGNORECASE)
    result = []
    for table in tables:
        rows = re.findall(r"<tr[^>]*>(.*?)</tr>", table, re.DOTALL | re.IGNORECASE)
        table_rows = []
        for row in rows:
            cells = re.findall(r"<t[dh][^>]*>(.*?)</t[dh]>", row, re.DOTALL | re.IGNORECASE)
            if not cells:
                continue
            link = _extract_links_from_cell(cells[0])
            text = _clean(cells[0])
            row_data: dict = {"company": text, "link": link}
            for i, c in enumerate(cells[1:], 1):
                row_data[f"col_{i}"] = _clean(c)
            if text:
                table_rows.append(row_data)
        if table_rows:
            result.append(table_rows)
    return result


def _parse_number(s: str) -> float | None:
    """Parse '1,024.57' or '₹459.72' → float. Returns None if not a number."""
    if not s:
        return None
    s = re.sub(r"[₹,]", "", s).strip()
    # Handle ranges like "168 - 177" — take the first number.
    s = s.split("-")[0].strip()
    try:
        return float(s)
    except ValueError:
        return None


def _parse_date_range(s: str) -> tuple[str | None, str | None]:
    """Parse date strings like '1 - 3 Sep', '31 Aug - 2 Sep', '10 - 15 September'.

    Returns (open_date_iso, close_date_iso). Both may be None if unparseable.
    Assumes the current year (or next year if month is before current month).
    """
    if not s:
        return None, None
    s = s.strip()
    now = datetime.now(timezone.utc)

    # Pattern: "DD - DD Mon" (same month)
    m = re.match(r"(\d+)\s*[-–]\s*(\d+)\s+(\w+)", s)
    if m:
        d1, d2, mon = int(m.group(1)), int(m.group(2)), m.group(3).lower()
        month = _MONTHS.get(mon)
        if month:
            year = now.year
            if month < now.month:
                year += 1
            try:
                d1 = min(d1, 31)
                d2 = min(d2, 31)
                open_d = f"{year}-{month:02d}-{d1:02d}"
                close_d = f"{year}-{month:02d}-{d2:02d}"
                return open_d, close_d
            except Exception:
                pass

    # Pattern: "DD Mon - DD Mon" (cross-month)
    m = re.match(r"(\d+)\s+(\w+)\s*[-–]\s*(\d+)\s+(\w+)", s)
    if m:
        d1, mon1, d2, mon2 = int(m.group(1)), m.group(2).lower(), int(m.group(3)), m.group(4).lower()
        m1, m2 = _MONTHS.get(mon1), _MONTHS.get(mon2)
        if m1 and m2:
            year = now.year
            if m1 < now.month or (m1 == now.month and d1 < now.day):
                year += 1
            try:
                open_d = f"{year}-{m1:02d}-{min(d1,31):02d}"
                close_d = f"{year}-{m2:02d}-{min(d2,31):02d}"
                return open_d, close_d
            except Exception:
                pass

    # Pattern: "DD Month YYYY"
    for fmt in ("%d %B %Y", "%d %b %Y"):
        try:
            dt = datetime.strptime(s, fmt)
            iso = dt.strftime("%Y-%m-%d")
            return iso, iso
        except ValueError:
            continue

    return None, None


def _parse_date_text(s: str) -> str | None:
    """Parse date strings like '1 September 2026' → '2026-09-01'."""
    if not s:
        return None
    s = _clean(s)
    for fmt in ("%d %B %Y", "%d %b %Y", "%B %d, %Y", "%b %d, %Y", "%Y-%m-%d", "%d-%m-%Y"):
        try:
            return datetime.strptime(s, fmt).strftime("%Y-%m-%d")
        except ValueError:
            continue
    return s  # return as-is if unparseable


# ---------------------------------------------------------------------------
# Detail page parsing
# ---------------------------------------------------------------------------

def _parse_detail_page(html: str, company_name: str, link: str | None) -> dict:
    """Parse an IPO detail page for all available data.

    ipocentral.in detail pages have 9-10 tables (the live subscription
    table is only present for IPOs that are currently open):
      0: IPO basics (dates, price, fresh issue, OFS, total size, lot, face value)
      1: Investor category quotas (QIB/NII/Retail percentages)
      2: Financials — Revenue, Expenses, Net Income, Margin (3 years)
      3: Per-share metrics — EPS, PE ratio, Price/Sales, Current Ratio
      4: Return ratios — RONW, NAV, ROCE, EBITDA, Debt/Equity
      5: Anchor investor data
      6: GMP history (date, premium, subject to sauda)
      7+: Subscription (if open) / Peer comparison / IPO timeline

    Tables 7+ are detected by header content rather than fixed index
    because the subscription table is absent for upcoming IPOs.
    """
    tables = _extract_tables(html)
    data: dict = {
        "price_band": None,
        "price_low": None,
        "price_high": None,
        "face_value": None,
        "issue_size_crs": None,
        "fresh_issue_crs": None,
        "offer_for_sale": None,
        "ofs_amount_crs": None,
        "lot_size": None,
        "lot_value": None,
        "open_date": None,
        "close_date": None,
        "allotment_date": None,
        "listing_date": None,
        "listing_at": None,
        "registrar": None,
        "market_maker": None,
        "lead_manager": None,
        "issue_type": None,
        "quota_percent": None,
        "financials": None,
        "per_share_metrics": None,
        "return_ratios": None,
        "anchor_investors": None,
        "gmp": None,
        "gmp_history": None,
        "subscription": None,
        "peer_comparison": None,
        "ipo_timeline": None,
    }

    # Table 0: IPO basics
    if len(tables) > 0:
        for row in tables[0]:
            if len(row) < 2:
                continue
            key = row[0].lower().rstrip(":").strip()
            val = row[1].strip()
            if "issue price" in key or "price band" in key:
                data["price_band"] = val
                prices = re.findall(r"[\d,]+\.?\d*", val)
                if len(prices) >= 2:
                    data["price_low"] = float(prices[0].replace(",", ""))
                    data["price_high"] = float(prices[1].replace(",", ""))
                elif len(prices) == 1:
                    data["price_low"] = float(prices[0].replace(",", ""))
                    data["price_high"] = float(prices[0].replace(",", ""))
            elif "fresh issue" in key:
                data["fresh_issue_crs"] = _parse_issue_size(val)
            elif "offer for sale" in key or "ofs" in key:
                data["offer_for_sale"] = val
                data["ofs_amount_crs"] = _parse_ofs_amount(val)
            elif "total" in key and "size" in key:
                data["issue_size_crs"] = _parse_issue_size(val)
            elif "lot size" in key or "minimum bid" in key:
                m = re.search(r"(\d[\d,]*)", val)
                if m:
                    data["lot_size"] = int(m.group(1).replace(",", ""))
                # Also try to get lot value
                m2 = re.search(r"₹?\s*([\d,]+(?:\.\d+)?)", val)
                if m2:
                    # Look for the amount in parentheses
                    m3 = re.search(r"\(₹?\s*([\d,]+(?:\.\d+)?)\)", val)
                    if m3:
                        data["lot_value"] = float(m3.group(1).replace(",", ""))
            elif "face value" in key:
                m = re.search(r"[\d,]+", val)
                if m:
                    data["face_value"] = float(m.group().replace(",", ""))
            elif "listing on" in key:
                data["listing_at"] = val
            elif "pre-issue" in key or "pre issue" in key:
                # Pre-issue shares — not critical, skip
                pass

    # Table 1: Investor category quotas
    if len(tables) > 1:
        quota: dict = {}
        for row in tables[1][1:]:  # skip header
            if len(row) >= 2:
                cat = row[0].strip().upper()
                pct = _parse_number(row[1])
                if cat and pct is not None:
                    quota[cat] = pct
        if quota:
            data["quota_percent"] = quota

    # Table 2: Financials (Revenue, Expenses, Net Income, Margin)
    if len(tables) > 2:
        fin = _parse_financial_table(tables[2])
        if fin:
            data["financials"] = fin

    # Table 3: Per-share metrics (EPS, PE ratio, Price/Sales, Current Ratio)
    if len(tables) > 3:
        metrics = _parse_financial_table(tables[3])
        if metrics:
            data["per_share_metrics"] = metrics

    # Table 4: Return ratios (RONW, NAV, ROCE, EBITDA, Debt/Equity)
    if len(tables) > 4:
        ratios = _parse_financial_table(tables[4])
        if ratios:
            data["return_ratios"] = ratios

    # Table 5: Anchor investor data
    if len(tables) > 5:
        anchor: dict = {}
        for row in tables[5]:
            if len(row) >= 2:
                key = row[0].strip()
                val = row[1].strip()
                if "bid date" in key.lower():
                    anchor["bid_date"] = _parse_date_text(val)
                elif "shares offered" in key.lower():
                    anchor["shares_offered"] = val
                elif "portion" in key.lower() or "amount" in key.lower():
                    anchor["amount_crs"] = _parse_issue_size(val)
                elif "lock-in" in key.lower() or "lock in" in key.lower():
                    if "50%" in key or "50%" in val or "30 days" in key.lower() or "30 days" in key.lower():
                        anchor["lock_in_50pct_date"] = _parse_date_text(val)
                    elif "90 days" in key.lower() or "remaining" in key.lower():
                        anchor["lock_in_90pct_date"] = _parse_date_text(val)
        if anchor:
            data["anchor_investors"] = anchor

    # Table 6: GMP history
    if len(tables) > 6:
        gmp_history: list[dict] = []
        latest_gmp: dict | None = None
        for row in tables[6][1:]:  # skip header
            if len(row) >= 2:
                date_str = row[0].strip()
                gmp_val = _parse_number(row[1])
                sauda = _parse_number(row[2]) if len(row) >= 3 else None
                entry = {"date": date_str, "gmp": gmp_val, "subject_to_sauda": sauda}
                gmp_history.append(entry)
                if latest_gmp is None and gmp_val is not None:
                    latest_gmp = entry
        if gmp_history:
            data["gmp_history"] = gmp_history
            # Set current GMP from the latest entry.
            if latest_gmp and latest_gmp["gmp"] is not None:
                premium = latest_gmp["gmp"]
                pct = None
                if data["price_high"] and data["price_high"] > 0:
                    pct = round((premium / data["price_high"]) * 100, 2)
                data["gmp"] = {
                    "premium": premium,
                    "premium_pct": pct,
                    "last_updated": datetime.now(timezone.utc).isoformat(),
                }

    # Tables 7+: Subscription, Peer comparison, Timeline.
    # These are detected by header content rather than fixed index because
    # the subscription table is only present for currently-open IPOs.
    for ti in range(7, len(tables)):
        table = tables[ti]
        if not table or not table[0]:
            continue
        header_text = " ".join(c.lower() for c in table[0])

        # Subscription table: header contains "Subscription" or
        # ("Category" + "Applied") and has a "Total" row.
        is_subscription = (
            "subscription" in header_text
            or ("category" in header_text and "applied" in header_text)
        )
        if is_subscription and not data["subscription"]:
            sub: dict = {}
            for row in table[1:]:  # skip header
                if len(row) < 2:
                    continue
                cat = row[0].strip().upper()
                sub_val = _parse_number(row[-1]) if row[-1] else None
                if cat == "QIB":
                    sub["qib"] = sub_val
                elif "HNI" in cat and "B " not in cat and "S " not in cat:
                    sub["nii"] = sub_val
                elif cat in ("RETAIL", "RII"):
                    sub["rii"] = sub_val
                elif cat == "TOTAL":
                    sub["total"] = sub_val
            if sub:
                data["subscription"] = sub
            continue

        # Peer comparison: header contains "Company" + ("PE" or "EPS" or "Revenue").
        is_peer = "company" in header_text and any(
            k in header_text for k in ("pe ratio", "pe ", "eps", "revenue", "ronw")
        )
        if is_peer and not data["peer_comparison"]:
            peers: list[dict] = []
            header = table[0]
            for row in table[1:]:
                if len(row) >= 2:
                    peer: dict = {"company": row[0].strip()}
                    for i, col_name in enumerate(header[1:], 1):
                        if i < len(row):
                            val = row[i].strip()
                            num = _parse_number(val)
                            peer[col_name.lower()] = num if num is not None else val
                    peers.append(peer)
            if peers:
                data["peer_comparison"] = peers
            continue

        # Timeline: first cell contains "opening date" or "closing date".
        first_cell = table[0][0].lower() if table[0] and table[0][0] else ""
        is_timeline = "opening date" in first_cell or "ipo opening" in first_cell
        if is_timeline and not data["ipo_timeline"]:
            timeline: dict = {}
            for row in table:
                if len(row) < 2:
                    continue
                key = row[0].strip()
                val = row[1].strip()
                key_lower = key.lower()
                if "opening" in key_lower:
                    timeline["open_date"] = _parse_date_text(val)
                    if not data["open_date"]:
                        data["open_date"] = timeline["open_date"]
                elif "closing" in key_lower:
                    timeline["close_date"] = _parse_date_text(val)
                    if not data["close_date"]:
                        data["close_date"] = timeline["close_date"]
                elif "allotment" in key_lower or "basis" in key_lower:
                    timeline["allotment_date"] = _parse_date_text(val)
                    if not data["allotment_date"]:
                        data["allotment_date"] = timeline["allotment_date"]
                elif "refund" in key_lower:
                    timeline["refund_date"] = _parse_date_text(val)
                elif "demat" in key_lower or "transfer" in key_lower or "credit" in key_lower:
                    timeline["demat_credit_date"] = _parse_date_text(val)
                elif "listing" in key_lower:
                    timeline["listing_date"] = _parse_date_text(val)
                    if not data["listing_date"]:
                        data["listing_date"] = timeline["listing_date"]
            if timeline:
                data["ipo_timeline"] = timeline
            continue

    return data


def _parse_financial_table(table: list[list[str]]) -> dict | None:
    """Parse a financial table with years as column headers.

    Returns {metric_name: {year: value}}.
    """
    if not table or len(table) < 2:
        return None
    header = table[0]
    # Year columns start from index 1.
    years = [h.strip() for h in header[1:]]
    result: dict = {}
    for row in table[1:]:
        if len(row) < 2:
            continue
        metric = row[0].strip()
        values: dict = {}
        for i, year in enumerate(years):
            if i + 1 < len(row):
                val_str = row[i + 1].strip()
                num = _parse_number(val_str)
                values[year] = num if num is not None else val_str
        if metric:
            result[metric] = values
    return result if result else None


def _parse_issue_size(s: str) -> float | None:
    """Parse '₹459.72 Cr.' or 'INR 250 crore' → 459.72."""
    if not s:
        return None
    m = re.search(r"[\d,]+\.?\d*", s.replace("₹", ""))
    if m:
        try:
            return float(m.group().replace(",", ""))
        except ValueError:
            pass
    return None


def _parse_ofs_amount(s: str | None) -> float | None:
    """Extract the OFS amount in ₹ Cr from strings like
    '1,18,48,340 shares (INR 199.05 - 209.72 crore)'.

    Looks for a crore amount first; falls back to the plain issue-size parser.
    """
    if not s:
        return None
    # Look for "INR N crore" or "₹ N crore" (may be a range — take the lower end).
    m = re.search(r"(?:INR|₹|Rs\.?)\s*([\d,]+\.?\d*)\s*(?:-|to|–)\s*[\d,]+\.?\d*\s*cr", s, re.IGNORECASE)
    if m:
        try:
            return float(m.group(1).replace(",", ""))
        except ValueError:
            pass
    # Single amount: "INR 199.05 crore"
    m = re.search(r"(?:INR|₹|Rs\.?)\s*([\d,]+\.?\d*)\s*cr", s, re.IGNORECASE)
    if m:
        try:
            return float(m.group(1).replace(",", ""))
        except ValueError:
            pass
    return _parse_issue_size(s)


# ---------------------------------------------------------------------------
# Fetching
# ---------------------------------------------------------------------------

async def _fetch_page(client: httpx.AsyncClient, url: str) -> str:
    """Fetch a page, returning HTML text. Empty string on failure."""
    try:
        r = await client.get(url, headers=HEADERS)
        if r.status_code == 200:
            return r.text
        log.info("Fetch %s returned %s", url, r.status_code)
    except Exception as e:
        log.warning("Fetch %s failed: %s", url, e)
    return ""


async def _fetch_wp_page(client: httpx.AsyncClient, slug: str) -> str:
    """Fetch a page's rendered content via WordPress REST API."""
    try:
        r = await client.get(
            f"{BASE_URL}/wp-json/wp/v2/pages",
            params={"slug": slug},
            headers={**HEADERS, "Accept": "application/json"},
        )
        if r.status_code == 200:
            data = r.json()
            if data and isinstance(data, list) and len(data) > 0:
                return data[0].get("content", {}).get("rendered", "")
    except Exception as e:
        log.warning("WP API fetch %s failed: %s", slug, e)
    return ""


async def _fetch_detail(
    client: httpx.AsyncClient,
    company: str,
    link: str | None,
    board: str,
    status: str,
    ipo_date: str,
    issue_size: float | None,
) -> dict:
    """Fetch and parse a single IPO detail page."""
    base = {
        "company_name": company,
        "symbol": company,
        "board": board,
        "status": status,
        "price_band": None,
        "price_low": None,
        "price_high": None,
        "face_value": None,
        "issue_size_crs": issue_size,
        "fresh_issue_crs": None,
        "offer_for_sale": None,
        "ofs_amount_crs": None,
        "lot_size": None,
        "lot_value": None,
        "open_date": None,
        "close_date": None,
        "allotment_date": None,
        "listing_date": None,
        "listing_at": None,
        "registrar": None,
        "market_maker": None,
        "lead_manager": None,
        "issue_type": None,
        "quota_percent": None,
        "financials": None,
        "per_share_metrics": None,
        "return_ratios": None,
        "anchor_investors": None,
        "gmp": None,
        "gmp_history": None,
        "subscription": None,
        "peer_comparison": None,
        "ipo_timeline": None,
        "selection_score": None,
        "score_factors": None,
    }

    if not link:
        return base

    html = await _fetch_page(client, link)
    if not html:
        return base

    details = _parse_detail_page(html, company, link)
    base.update(details)
    # Override issue_size if we got it from the summary table.
    if issue_size and not base["issue_size_crs"]:
        base["issue_size_crs"] = issue_size

    return base


async def _scrape_ipo_list(client: httpx.AsyncClient, url: str, status: str) -> dict:
    """Scrape a page with Main Board + SME IPO tables.

    Returns {mainboard: [...], sme: [...]} with basic data.
    Fetches detail pages in parallel for full data.
    """
    html = await _fetch_page(client, url)
    if not html:
        return {"mainboard": [], "sme": []}

    link_tables = _extract_link_tables(html)
    if len(link_tables) < 2:
        return {"mainboard": [], "sme": []}

    # Table 0 = Main Board, Table 1 = SME.
    boards = ["mainboard", "sme"]
    result = {"mainboard": [], "sme": []}

    for bi, board in enumerate(boards):
        if bi >= len(link_tables):
            result[board] = []
            continue
        rows = link_tables[bi]
        ipos = []
        for row in rows:
            company = row.get("company", "").strip()
            if not company:
                continue
            # Skip header rows (e.g. "Upcoming IPO 2026", "Company Name").
            company_lower = company.lower()
            if any(skip in company_lower for skip in ("upcoming ipo", "company name", "ipo name", "sme ipo")):
                continue
            link = row.get("link")
            ipo_date = row.get("col_1", "")
            issue_size = _parse_issue_size(row.get("col_2", ""))
            ipos.append({
                "company": company,
                "link": link,
                "ipo_date": ipo_date,
                "issue_size": issue_size,
            })
        result[board] = ipos

    # Fetch detail pages in parallel for GMP + full data.
    sem = asyncio.Semaphore(8)

    async def _fetch_one(board: str, ipo: dict) -> dict:
        async with sem:
            return await _fetch_detail(
                client, ipo["company"], ipo["link"],
                board, status, ipo["ipo_date"], ipo["issue_size"],
            )

    tasks = []
    for board in boards:
        for ipo in result[board]:
            tasks.append((board, _fetch_one(board, ipo)))

    completed = await asyncio.gather(*[t[1] for t in tasks], return_exceptions=True)

    result = {"mainboard": [], "sme": []}
    for (board, _), item in zip(tasks, completed):
        if isinstance(item, Exception):
            log.warning("Detail fetch failed: %s", item)
            continue
        if isinstance(item, dict):
            result[board].append(item)

    return result


async def _scrape_recent_ipos(client: httpx.AsyncClient, slug: str, board: str) -> list[dict]:
    """Scrape listed/recent IPOs from a WordPress page (ipo-2026 or sme-ipo-2026).

    Returns a list of IPO dicts with company_name, listing_date, listing_return_pct.
    """
    html = await _fetch_wp_page(client, slug)
    if not html:
        return []

    tables = _extract_tables(html)
    if not tables:
        return []

    # First table has: IPO Name, Listing Date, Allotment/Listed Price, Listing Return (%)
    ipos: list[dict] = []
    table = tables[0]
    for row in table[1:]:  # skip header
        if len(row) < 2:
            continue
        company = row[0].strip()
        if not company:
            continue
        listing_date = None
        if len(row) >= 2:
            listing_date = _parse_listing_date(row[1])
        allotment_price = _parse_number(row[2]) if len(row) >= 3 else None
        listing_return = _parse_number(row[3]) if len(row) >= 4 else None

        ipos.append({
            "company_name": company,
            "symbol": company,
            "board": board,
            "status": "recent",
            "listing_date": listing_date,
            "allotment_price": allotment_price,
            "listing_return_pct": listing_return,
            "price_band": None,
            "price_low": None,
            "price_high": allotment_price,
            "face_value": None,
            "issue_size_crs": None,
            "fresh_issue_crs": None,
            "offer_for_sale": None,
            "ofs_amount_crs": None,
            "lot_size": None,
            "open_date": None,
            "close_date": None,
            "allotment_date": None,
            "listing_at": None,
            "registrar": None,
            "market_maker": None,
            "lead_manager": None,
            "issue_type": None,
            "quota_percent": None,
            "financials": None,
            "per_share_metrics": None,
            "return_ratios": None,
            "anchor_investors": None,
            "gmp": None,
            "gmp_history": None,
            "subscription": None,
            "peer_comparison": None,
            "ipo_timeline": None,
            "selection_score": None,
            "score_factors": None,
        })

    return ipos


def _parse_listing_date(s: str) -> str | None:
    """Parse '9/1/2026' → '2026-09-01'."""
    if not s:
        return None
    s = s.strip()
    for fmt in ("%m/%d/%Y", "%d/%m/%Y", "%Y-%m-%d", "%d-%m-%Y"):
        try:
            return datetime.strptime(s, fmt).strftime("%Y-%m-%d")
        except ValueError:
            continue
    return s


def _classify_status(ipo: dict) -> str:
    """Determine if an IPO is 'current', 'upcoming', or 'recent' based on dates.

    IPOs from the homepage are initially tagged 'upcoming' — this refines
    the status by checking if the IPO is currently open.
    """
    open_d = ipo.get("open_date")
    close_d = ipo.get("close_date")
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    if open_d and close_d:
        if open_d <= today <= close_d:
            return "current"
        if today < open_d:
            return "upcoming"
        if today > close_d:
            return "recent"
    elif open_d:
        if today < open_d:
            return "upcoming"
        else:
            return "current"
    return ipo.get("status", "upcoming")


async def fetch_all_ipos() -> dict:
    """Fetch current + upcoming + recent IPOs from ipocentral.in with full details."""
    now = time.time()
    if _cache["data"] and now - _cache["ts"] < _cache["ttl"]:
        return _cache["data"]

    async with httpx.AsyncClient(timeout=20, follow_redirects=True, http2=False) as client:
        # Fetch current+upcoming (homepage) and recent (WP API) in parallel.
        current_upcoming, recent_main, recent_sme = await asyncio.gather(
            _scrape_ipo_list(client, f"{BASE_URL}/", "upcoming"),
            _scrape_recent_ipos(client, "ipo-2026", "mainboard"),
            _scrape_recent_ipos(client, "sme-ipo-2026", "sme"),
            return_exceptions=True,
        )

    if isinstance(current_upcoming, Exception):
        log.error("Current/upcoming IPO scrape failed: %s", current_upcoming)
        current_upcoming = {"mainboard": [], "sme": []}
    if isinstance(recent_main, Exception):
        log.error("Recent mainboard IPO scrape failed: %s", recent_main)
        recent_main = []
    if isinstance(recent_sme, Exception):
        log.error("Recent SME IPO scrape failed: %s", recent_sme)
        recent_sme = []

    # Classify current vs upcoming using parsed dates.
    for board in ("mainboard", "sme"):
        for ipo in current_upcoming.get(board, []):
            ipo["status"] = _classify_status(ipo)

    data = {
        "mainboard": {
            "current": [i for i in current_upcoming.get("mainboard", []) if i.get("status") == "current"],
            "recent": recent_main if isinstance(recent_main, list) else [],
            "upcoming": [i for i in current_upcoming.get("mainboard", []) if i.get("status") == "upcoming"],
        },
        "sme": {
            "current": [i for i in current_upcoming.get("sme", []) if i.get("status") == "current"],
            "recent": recent_sme if isinstance(recent_sme, list) else [],
            "upcoming": [i for i in current_upcoming.get("sme", []) if i.get("status") == "upcoming"],
        },
        "refreshed_at": datetime.now(timezone.utc).isoformat(),
    }

    _cache["data"] = data
    _cache["ts"] = now
    return data


async def fetch_current_recent_ipos() -> dict:
    """Fetch current IPOs from ipocentral.in."""
    now = time.time()
    if _cache["data"] and now - _cache["ts"] < _cache["ttl"]:
        d = _cache["data"]
        return {
            "mainboard": {"current": d["mainboard"]["current"], "recent": d["mainboard"]["recent"]},
            "sme": {"current": d["sme"]["current"], "recent": d["sme"]["recent"]},
            "refreshed_at": d.get("refreshed_at"),
        }

    async with httpx.AsyncClient(timeout=20, follow_redirects=True, http2=False) as client:
        current_upcoming, recent_main, recent_sme = await asyncio.gather(
            _scrape_ipo_list(client, f"{BASE_URL}/", "upcoming"),
            _scrape_recent_ipos(client, "ipo-2026", "mainboard"),
            _scrape_recent_ipos(client, "sme-ipo-2026", "sme"),
            return_exceptions=True,
        )

    if isinstance(current_upcoming, Exception):
        current_upcoming = {"mainboard": [], "sme": []}
    if isinstance(recent_main, Exception):
        recent_main = []
    if isinstance(recent_sme, Exception):
        recent_sme = []

    for board in ("mainboard", "sme"):
        for ipo in current_upcoming.get(board, []):
            ipo["status"] = _classify_status(ipo)

    return {
        "mainboard": {
            "current": [i for i in current_upcoming.get("mainboard", []) if i.get("status") == "current"],
            "recent": recent_main if isinstance(recent_main, list) else [],
        },
        "sme": {
            "current": [i for i in current_upcoming.get("sme", []) if i.get("status") == "current"],
            "recent": recent_sme if isinstance(recent_sme, list) else [],
        },
        "refreshed_at": datetime.now(timezone.utc).isoformat(),
    }


async def fetch_upcoming_ipos() -> dict:
    """Fetch upcoming IPOs from ipocentral.in."""
    now = time.time()
    if _cache["data"] and now - _cache["ts"] < _cache["ttl"]:
        d = _cache["data"]
        return {
            "mainboard": {"current": [], "recent": [], "upcoming": d["mainboard"]["upcoming"]},
            "sme": {"current": [], "recent": [], "upcoming": d["sme"]["upcoming"]},
            "refreshed_at": d.get("refreshed_at"),
        }

    async with httpx.AsyncClient(timeout=20, follow_redirects=True, http2=False) as client:
        current_upcoming = await _scrape_ipo_list(client, f"{BASE_URL}/", "upcoming")

    for board in ("mainboard", "sme"):
        for ipo in current_upcoming.get(board, []):
            ipo["status"] = _classify_status(ipo)

    return {
        "mainboard": {"current": [], "recent": [], "upcoming": [i for i in current_upcoming.get("mainboard", []) if i.get("status") == "upcoming"]},
        "sme": {"current": [], "recent": [], "upcoming": [i for i in current_upcoming.get("sme", []) if i.get("status") == "upcoming"]},
        "refreshed_at": datetime.now(timezone.utc).isoformat(),
    }
