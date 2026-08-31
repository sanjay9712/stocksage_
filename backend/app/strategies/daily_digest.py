"""Daily digest generation.

Compiles a comprehensive market summary including:
- Market status and index levels
- Today's picks (if any)
- Signal alerts summary
- Gap scanner results
- Sector rotation snapshot
- Price alerts triggered today

The digest is stored in the DB and optionally emailed via SMTP.
"""
from __future__ import annotations

import asyncio
import logging
import smtplib
from datetime import date, datetime
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import Any

from app.config import settings
from app.db import DailyDigest, SessionLocal
from app.providers.factory import get_provider

log = logging.getLogger("daily_digest")


async def generate_digest(target_date: date | None = None) -> dict[str, Any]:
    """Generate the daily market digest.

    Compiles data from multiple sources into a structured digest.
    Returns a dict with subject, body_text (structured), and body_html.
    """
    target_date = target_date or date.today()
    provider = get_provider()

    # Fetch market status
    try:
        market_status = await provider.get_market_status()
    except Exception:
        market_status = {"market_open": False, "status_text": "Unknown"}

    # Fetch today's picks
    picks_summary = []
    try:
        from sqlalchemy import select
        from app.db import PickRow
        db = SessionLocal()
        picks = db.execute(
            select(PickRow).where(PickRow.date == target_date).limit(5)
        ).scalars().all()
        picks_summary = [
            {
                "symbol": p.symbol,
                "side": p.side,
                "entry": p.entry,
                "stop_loss": p.stop_loss,
                "target1": p.target1,
                "target2": p.target2,
                "confidence": p.confidence,
                "status": p.status,
                "last_price": p.last_price,
            }
            for p in picks
        ]
        db.close()
    except Exception as e:
        log.warning("Failed to fetch picks for digest: %s", e)

    # Fetch signal alerts (NSE)
    signals_summary = []
    try:
        from app.strategies.signal_alerts import NSE_SIGNAL_UNIVERSE, scan_all_signals
        symbols = [(s, s) for s in NSE_SIGNAL_UNIVERSE[:30]]  # top 30 for speed
        signals = await scan_all_signals(provider, symbols, "in", None)
        signals_summary = signals[:10]  # top 10 by confidence
    except Exception as e:
        log.warning("Failed to fetch signals for digest: %s", e)

    # Fetch gap scanner results
    gaps_summary = []
    try:
        from app.strategies.gap_scanner import NSE_GAP_UNIVERSE, scan_all_gaps
        gaps = await scan_all_gaps(provider, [(s, s) for s in NSE_GAP_UNIVERSE[:20]], "in", 0.5)
        gaps_summary = gaps[:5]
    except Exception as e:
        log.warning("Failed to fetch gaps for digest: %s", e)

    # Fetch triggered price alerts
    triggered_alerts = []
    try:
        from sqlalchemy import select
        from app.db import PriceAlert
        db = SessionLocal()
        alerts = db.execute(
            select(PriceAlert)
            .where(PriceAlert.status == "triggered")
            .order_by(PriceAlert.triggered_at.desc())
            .limit(10)
        ).scalars().all()
        triggered_alerts = [
            {
                "symbol": a.symbol,
                "condition": a.condition,
                "target_price": a.target_price,
                "triggered_price": a.triggered_price,
            }
            for a in alerts
        ]
        db.close()
    except Exception as e:
        log.warning("Failed to fetch triggered alerts: %s", e)

    digest_data = {
        "date": target_date.isoformat(),
        "generated_at": datetime.utcnow().isoformat() + "Z",
        "market_status": market_status,
        "picks": picks_summary,
        "signals": signals_summary,
        "gaps": gaps_summary,
        "triggered_alerts": triggered_alerts,
    }

    subject = f"Market Digest — {target_date.strftime('%b %d, %Y')}"

    # Render HTML
    body_html = _render_html(digest_data)

    return {
        "subject": subject,
        "body_text": digest_data,
        "body_html": body_html,
    }


def _render_html(data: dict[str, Any]) -> str:
    """Render the digest as HTML email."""
    html = f"""\
<html><body style="font-family: -apple-system, BlinkMacSystemFont, sans-serif; max-width: 600px; margin: 0 auto; padding: 20px; background: #0f172a; color: #e2e8f0;">

<h1 style="color: #34d399; font-size: 20px; margin-bottom: 5px;">📊 Daily Market Digest</h1>
<p style="color: #64748b; font-size: 13px; margin-bottom: 20px;">{data['date']}</p>

<h2 style="color: #94a3b8; font-size: 14px; border-bottom: 1px solid #1e293b; padding-bottom: 5px;">Market Status</h2>
<p style="font-size: 13px;">{data.get('market_status', {}).get('status_text', 'Unknown')}</p>
"""

    # Picks
    picks = data.get("picks", [])
    if picks:
        html += '<h2 style="color: #94a3b8; font-size: 14px; border-bottom: 1px solid #1e293b; padding-bottom: 5px; margin-top: 20px;">Today\'s Picks</h2><table style="width: 100%; font-size: 12px; border-collapse: collapse;">'
        html += '<tr style="color: #64748b;"><td style="padding: 4px;">Symbol</td><td>Side</td><td>Entry</td><td>SL</td><td>Target</td><td>Conf</td></tr>'
        for p in picks:
            html += f'<tr><td style="padding: 4px; color: #e2e8f0;">{p["symbol"]}</td><td>{p["side"]}</td><td>{p["entry"]}</td><td style="color: #f43f5e;">{p["stop_loss"]}</td><td style="color: #34d399;">{p["target1"]}</td><td>{p["confidence"]:.0%}</td></tr>'
        html += '</table>'

    # Signals
    signals = data.get("signals", [])
    if signals:
        html += '<h2 style="color: #94a3b8; font-size: 14px; border-bottom: 1px solid #1e293b; padding-bottom: 5px; margin-top: 20px;">Signal Alerts</h2>'
        for s in signals[:10]:
            side_color = "#34d399" if s["side"] == "long" else "#f43f5e" if s["side"] == "short" else "#fbbf24"
            html += f'<div style="padding: 6px 0; border-bottom: 1px solid #1e293b;"><span style="font-weight: bold;">{s["symbol"]}</span> <span style="color: {side_color}; font-size: 11px;">{s["side"].upper()}</span> — {s["description"]}</div>'

    # Gaps
    gaps = data.get("gaps", [])
    if gaps:
        html += '<h2 style="color: #94a3b8; font-size: 14px; border-bottom: 1px solid #1e293b; padding-bottom: 5px; margin-top: 20px;">Gap Scanner</h2>'
        for g in gaps[:5]:
            gap_color = "#34d399" if g.get("gap_pct", 0) > 0 else "#f43f5e"
            html += f'<div style="padding: 6px 0; border-bottom: 1px solid #1e293b;"><span style="font-weight: bold;">{g["symbol"]}</span> <span style="color: {gap_color};">gap {g.get("gap_pct", 0):+.1f}%</span></div>'

    # Triggered alerts
    triggered = data.get("triggered_alerts", [])
    if triggered:
        html += '<h2 style="color: #94a3b8; font-size: 14px; border-bottom: 1px solid #1e293b; padding-bottom: 5px; margin-top: 20px;">Price Alerts Triggered</h2>'
        for a in triggered:
            html += f'<div style="padding: 6px 0; border-bottom: 1px solid #1e293b;"><span style="font-weight: bold;">{a["symbol"]}</span> {a["condition"].replace("_", " ")} ${a["target_price"]} → hit at <span style="color: #34d399;">${a["triggered_price"]}</span></div>'

    if not picks and not signals and not gaps and not triggered:
        html += '<p style="color: #64748b; font-size: 13px; margin-top: 20px;">No significant activity today.</p>'

    html += '<p style="color: #475569; font-size: 11px; margin-top: 30px;">— Trading Assistant</p>'
    html += '</body></html>'
    return html


async def send_digest_email(to_email: str, subject: str, html_body: str) -> bool:
    """Send digest email via SMTP. Returns True if sent, False if SMTP not configured."""
    if not settings.smtp_host or not settings.smtp_user:
        log.info("SMTP not configured — digest will be stored but not emailed")
        return False

    try:
        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"] = settings.digest_from_email or settings.smtp_user
        msg["To"] = to_email
        msg.attach(MIMEText(html_body, "html"))

        with smtplib.SMTP(settings.smtp_host, settings.smtp_port) as server:
            server.starttls()
            server.login(settings.smtp_user, settings.smtp_password)
            server.sendmail(msg["From"], [to_email], msg.as_string())

        log.info("Digest email sent to %s", to_email)
        return True
    except Exception as e:
        log.error("Failed to send digest email: %s", e)
        return False


async def generate_and_store_digest(user_email: str | None = None, target_date: date | None = None) -> dict:
    """Generate the digest, store it in DB, and optionally email it."""
    target_date = target_date or date.today()

    digest = await generate_digest(target_date)

    db = SessionLocal()
    try:
        record = DailyDigest(
            date=target_date,
            subject=digest["subject"],
            body_text=digest["body_text"],
            body_html=digest["body_html"],
            emailed=False,
        )
        db.add(record)
        db.commit()
        db.refresh(record)

        # Try to email if configured
        if user_email:
            emailed = await send_digest_email(user_email, digest["subject"], digest["body_html"])
            if emailed:
                record.emailed = True
                db.commit()

        return {
            "id": record.id,
            "date": target_date.isoformat(),
            "subject": digest["subject"],
            "emailed": record.emailed,
            "data": digest["body_text"],
        }
    finally:
        db.close()
