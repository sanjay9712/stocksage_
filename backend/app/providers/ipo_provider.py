"""IPO data provider — scrapes ipowatch.in for current, upcoming, and recent IPOs.

ipowatch.in provides:
  - Homepage (https://www.ipowatch.in/): 2 tables — Main Board + SME current IPOs
    with company name, IPO date, issue size, and links to detail pages.
  - /upcoming-ipo/: upcoming IPOs in the same table format.
  - Detail pages (e.g. /deepa-jewellers-ipo-gmp-grey-market-premium/):
    GMP history, price band, face value, lot size, open/close dates,
    allotment/listing dates, financials, peer comparison.

Data is fetched in parallel (detail pages via asyncio.gather with a semaphore)
so a full refresh takes ~3-5s for ~20 IPOs.
"""
from __future__ import annotations

import asyncio
import logging
import re
import time
from datetime import datetime, timezone

import httpx

log = logging.getLogger("ipo_provider")

BASE_URL = "https://www.ipowatch.in"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
}

# Cache for the GMP/summary data (10 min TTL — GMP doesn't change fast).
_cache: dict = {"data": None, "ts": 0, "ttl": 600}


# ---------------------------------------------------------------------------
# HTML parsing helpers
# ---------------------------------------------------------------------------

def _clean(text: str) -> str:
    """Strip HTML tags and normalize whitespace."""
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", "", text)).strip()


def _extract_tables(html: str) -> list[list[list[list[str]]]]:
    """Extract all tables from HTML as list of tables, each a list of rows, each a list of cells (clean text)."""
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
    {text, link} for the first cell and plain text for the rest.
    """
    tables = re.findall(r"<table[^>]*>(.*?)</table>", html, re.DOTALL | re.IGNORECASE)
    result = []
    for table in tables:
        rows = re.findall(r"<tr[^>]*>(.*?)</tr>", table, re.DOTALL | re.IGNORECASE)
        table_rows = []
        for row in rows:
            cells = re.findall(r"<td[^>]*>(.*?)</td>", row, re.DOTALL | re.IGNORECASE)
            if not cells:
                continue
            # First cell: extract text + link.
            link = _extract_links_from_cell(cells[0])
            text = _clean(cells[0])
            row_data = {"company": text, "link": link}
            # Remaining cells: just text.
            for i, c in enumerate(cells[1:], 1):
                row_data[f"col_{i}"] = _clean(c)
            if text:
                table_rows.append(row_data)
        if table_rows:
            result.append(table_rows)
    return result


def _parse_ipo_date(s: str) -> str | None:
    """Parse IPO date strings like '1-3 September' → month + day range.
    Returns a human-readable date string (we can't always get full ISO).
    """
    if not s:
        return None
    return s.strip()


def _parse_issue_size(s: str) -> float | None:
    """Parse '₹459.72 Cr.' → 459.72."""
    if not s:
        return None
    m = re.search(r"[\d,]+\.?\d*", s.replace("₹", ""))
    if m:
        try:
            return float(m.group().replace(",", ""))
        except ValueError:
            pass
    return None


# ---------------------------------------------------------------------------
# Detail page parsing
# ---------------------------------------------------------------------------

def _parse_detail_page(html: str, company_name: str, link: str | None) -> dict:
    """Parse an IPO detail page for GMP, price band, dates, etc."""
    tables = _extract_tables(html)
    data: dict = {
        "gmp": None,
        "price_band": None,
        "price_low": None,
        "price_high": None,
        "face_value": None,
        "issue_size_crs": None,
        "lot_size": None,
        "open_date": None,
        "close_date": None,
        "allotment_date": None,
        "listing_date": None,
        "issue_type": None,
        "fresh_issue": None,
        "listing_at": None,
        "registrar": None,
        "market_maker": None,
        "lead_manager": None,
    }

    # Search through key-value tables (2-column tables with label/value).
    for table in tables:
        if len(table) < 2:
            continue
        for row in table:
            if len(row) < 2:
                continue
            key = row[0].lower().rstrip(":").strip()
            val = row[1].strip()
            if "price band" in key:
                data["price_band"] = val
                # Parse ₹168 to ₹177 → (168, 177)
                prices = re.findall(r"[\d,]+\.?\d*", val)
                if len(prices) >= 2:
                    data["price_low"] = float(prices[0].replace(",", ""))
                    data["price_high"] = float(prices[1].replace(",", ""))
                elif len(prices) == 1:
                    data["price_low"] = float(prices[0].replace(",", ""))
                    data["price_high"] = float(prices[0].replace(",", ""))
            elif "face value" in key:
                m = re.search(r"[\d,]+\.?\d*", val)
                if m:
                    data["face_value"] = float(m.group().replace(",", ""))
            elif "issue size" in key and "fresh" not in key:
                data["issue_size_crs"] = _parse_issue_size(val)
            elif "fresh issue" in key:
                data["fresh_issue"] = _parse_issue_size(val)
            elif "issue type" in key:
                data["issue_type"] = val
            elif "lot size" in key or "market lot" in key:
                m = re.search(r"[\d,]+", val)
                if m:
                    data["lot_size"] = int(m.group().replace(",", ""))
            elif "open date" in key or "bid open" in key:
                data["open_date"] = _parse_date_text(val)
            elif "close date" in key or "bid close" in key:
                data["close_date"] = _parse_date_text(val)
            elif "allotment" in key or "basis of allotment" in key:
                data["allotment_date"] = _parse_date_text(val)
            elif "listing date" in key or "listing at" in key:
                if "listing date" in key:
                    data["listing_date"] = _parse_date_text(val)
                else:
                    data["listing_at"] = val
            elif "registrar" in key:
                data["registrar"] = val
            elif "market maker" in key:
                data["market_maker"] = val
            elif "lead manager" in key or "lead managers" in key:
                data["lead_manager"] = val

    # Find GMP from the GMP history table.
    # The GMP table has columns: Date, IPO GMP, GMP Trend, Gain, Last Updated.
    for table in tables:
        if not table:
            continue
        header = " ".join(table[0]).lower() if table else ""
        if "gmp" in header and len(table) > 1:
            # First data row has the latest GMP.
            first_row = table[1]
            for cell in first_row:
                m = re.search(r"[₹]?\s*(\d+)", cell)
                if m and cell.strip() not in ("🟢", "🟡", "🔴"):
                    try:
                        premium = int(m.group(1))
                        if premium > 0 or cell.startswith("₹") or cell.startswith("-"):
                            # Compute premium_pct if we have price_high.
                            pct = None
                            if data["price_high"] and data["price_high"] > 0:
                                pct = round((premium / data["price_high"]) * 100, 2)
                            # Look for gain % in the same row.
                            for c2 in first_row:
                                pm = re.search(r"([+-]?\d+\.?\d*)\s*%", c2)
                                if pm:
                                    pct = float(pm.group(1))
                                    break
                            data["gmp"] = {
                                "premium": premium,
                                "premium_pct": pct,
                                "last_updated": datetime.now(timezone.utc).isoformat(),
                            }
                            break
                    except ValueError:
                        continue
            if data["gmp"]:
                break

    return data


def _parse_date_text(s: str) -> str | None:
    """Parse date strings like 'September 1, 2026' → '2026-09-01'."""
    if not s:
        return None
    s = s.strip()
    for fmt in ("%B %d, %Y", "%b %d, %Y", "%d %B %Y", "%d %b %Y", "%Y-%m-%d", "%d-%m-%Y"):
        try:
            return datetime.strptime(s, fmt).strftime("%Y-%m-%d")
        except ValueError:
            continue
    return s  # return as-is if unparseable


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


async def _fetch_detail(client: httpx.AsyncClient, company: str, link: str | None, board: str, status: str, ipo_date: str, issue_size: float | None) -> dict:
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
        "lot_size": None,
        "open_date": None,
        "close_date": None,
        "allotment_date": None,
        "listing_date": None,
        "listing_at": None,
        "registrar": None,
        "market_maker": None,
        "lead_manager": None,
        "subscription": None,
        "gmp": None,
        "selection_score": None,
        "score_factors": None,
    }

    if not link:
        return base

    # Try the GMP page first (has GMP data), fall back to the regular page.
    gmp_link = link.rstrip("/") + "-gmp-grey-market-premium/"
    # If link already ends with -ipo/, try converting to -ipo-gmp-grey-market-premium/
    if link.endswith("-ipo/"):
        slug = link.rstrip("/").rsplit("/", 1)[-1]
        gmp_link = f"{BASE_URL}/{slug}-gmp-grey-market-premium/"

    html = await _fetch_page(client, gmp_link)
    if not html:
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
            link = row.get("link")
            ipo_date = row.get("col_1", "")
            issue_size = _parse_issue_size(row.get("col_2", ""))
            ipos.append({
                "company": company,
                "link": link,
                "ipo_date": _parse_ipo_date(ipo_date),
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


async def fetch_all_ipos() -> dict:
    """Fetch current + upcoming IPOs from ipowatch.in with GMP and full details."""
    now = time.time()
    if _cache["data"] and now - _cache["ts"] < _cache["ttl"]:
        return _cache["data"]

    async with httpx.AsyncClient(timeout=20, follow_redirects=True, http2=False) as client:
        # Fetch current + upcoming in parallel.
        current, upcoming = await asyncio.gather(
            _scrape_ipo_list(client, f"{BASE_URL}/", "current"),
            _scrape_ipo_list(client, f"{BASE_URL}/upcoming-ipo/", "upcoming"),
            return_exceptions=True,
        )

    if isinstance(current, Exception):
        log.error("Current IPO scrape failed: %s", current)
        current = {"mainboard": [], "sme": []}
    if isinstance(upcoming, Exception):
        log.error("Upcoming IPO scrape failed: %s", upcoming)
        upcoming = {"mainboard": [], "sme": []}

    data = {
        "mainboard": {
            "current": current.get("mainboard", []),
            "recent": [],  # ipowatch doesn't have a clean recent/listed page
            "upcoming": upcoming.get("mainboard", []),
        },
        "sme": {
            "current": current.get("sme", []),
            "recent": [],
            "upcoming": upcoming.get("sme", []),
        },
        "refreshed_at": datetime.now(timezone.utc).isoformat(),
    }

    _cache["data"] = data
    _cache["ts"] = now
    return data


async def fetch_current_recent_ipos() -> dict:
    """Fetch current IPOs from ipowatch.in."""
    now = time.time()
    # Reuse full cache if available.
    if _cache["data"] and now - _cache["ts"] < _cache["ttl"]:
        d = _cache["data"]
        return {
            "mainboard": {"current": d["mainboard"]["current"], "recent": []},
            "sme": {"current": d["sme"]["current"], "recent": []},
            "refreshed_at": d.get("refreshed_at"),
        }

    async with httpx.AsyncClient(timeout=20, follow_redirects=True, http2=False) as client:
        current = await _scrape_ipo_list(client, f"{BASE_URL}/", "current")

    return {
        "mainboard": {"current": current.get("mainboard", []), "recent": []},
        "sme": {"current": current.get("sme", []), "recent": []},
        "refreshed_at": datetime.now(timezone.utc).isoformat(),
    }


async def fetch_upcoming_ipos() -> dict:
    """Fetch upcoming IPOs from ipowatch.in."""
    now = time.time()
    if _cache["data"] and now - _cache["ts"] < _cache["ttl"]:
        d = _cache["data"]
        return {
            "mainboard": {"current": [], "recent": [], "upcoming": d["mainboard"]["upcoming"]},
            "sme": {"current": [], "recent": [], "upcoming": d["sme"]["upcoming"]},
            "refreshed_at": d.get("refreshed_at"),
        }

    async with httpx.AsyncClient(timeout=20, follow_redirects=True, http2=False) as client:
        upcoming = await _scrape_ipo_list(client, f"{BASE_URL}/upcoming-ipo/", "upcoming")

    return {
        "mainboard": {"current": [], "recent": [], "upcoming": upcoming.get("mainboard", [])},
        "sme": {"current": [], "recent": [], "upcoming": upcoming.get("sme", [])},
        "refreshed_at": datetime.now(timezone.utc).isoformat(),
    }
