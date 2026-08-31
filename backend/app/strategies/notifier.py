"""Telegram & Discord notification sender.

Sends formatted trading alerts to configured notification channels.
- Telegram: uses Bot API (sendMessage)
- Discord: uses incoming webhooks

Channels are configured per-user via the /api/notifications endpoints.
"""
from __future__ import annotations

import logging
from typing import Any

import httpx

log = logging.getLogger("notifier")

TELEGRAM_API = "https://api.telegram.org"


async def send_telegram(bot_token: str, chat_id: str, message: str) -> bool:
    """Send a message via Telegram Bot API."""
    url = f"{TELEGRAM_API}/bot{bot_token}/sendMessage"
    payload = {
        "chat_id": chat_id,
        "text": message,
        "parse_mode": "HTML",
        "disable_web_page_preview": True,
    }
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.post(url, json=payload)
            if resp.status_code == 200:
                log.info("Telegram message sent to chat %s", chat_id)
                return True
            else:
                log.error("Telegram API error: %s — %s", resp.status_code, resp.text)
                return False
    except Exception as e:
        log.error("Telegram send failed: %s", e)
        return False


async def send_discord(webhook_url: str, message: str) -> bool:
    """Send a message via Discord incoming webhook."""
    payload = {"content": message}
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.post(webhook_url, json=payload)
            if resp.status_code in (200, 204):
                log.info("Discord message sent via webhook")
                return True
            else:
                log.error("Discord webhook error: %s — %s", resp.status_code, resp.text)
                return False
    except Exception as e:
        log.error("Discord send failed: %s", e)
        return False


def format_alert_message(alert: dict[str, Any]) -> str:
    """Format an alert dict into a readable message for Telegram/Discord."""
    msg_type = alert.get("type", "alert")
    lines: list[str] = []

    if msg_type == "price_alert":
        lines.append("🔔 <b>Price Alert Triggered</b>")
        lines.append(f"  Symbol: <b>{alert['symbol']}</b>")
        lines.append(f"  Condition: {alert['condition'].replace('_', ' ')} {alert['target_price']}")
        lines.append(f"  Current Price: {alert['triggered_price']}")
    elif msg_type == "signal_alert":
        side_emoji = {"long": "🟢", "short": "🔴", "watch": "🟡"}.get(alert.get("side", ""), "⚪")
        lines.append(f"{side_emoji} <b>Signal Alert</b>")
        lines.append(f"  Symbol: <b>{alert['symbol']}</b>")
        lines.append(f"  Signal: {alert.get('signal_type', 'unknown').replace('_', ' ')}")
        lines.append(f"  Side: {alert.get('side', '')}")
        lines.append(f"  Price: {alert.get('price', 'N/A')}")
        if alert.get("entry"):
            lines.append(f"  Entry: {alert['entry']} | SL: {alert.get('stop_loss', 'N/A')} | Target: {alert.get('target', 'N/A')}")
        lines.append(f"  {alert.get('description', '')}")
    elif msg_type == "digest":
        lines.append("📊 <b>Daily Market Digest</b>")
        lines.append(f"  Date: {alert.get('date', 'today')}")
        if alert.get("picks"):
            lines.append(f"  Picks: {len(alert['picks'])}")
        if alert.get("signals"):
            lines.append(f"  Signals: {len(alert['signals'])}")
        if alert.get("gaps"):
            lines.append(f"  Gaps: {len(alert['gaps'])}")
    else:
        lines.append(f"📢 <b>Notification</b>")
        for k, v in alert.items():
            lines.append(f"  {k}: {v}")

    return "\n".join(lines)


async def notify_user(db, user_id: int, alert: dict[str, Any]) -> dict:
    """Send a notification to all enabled channels for a user.

    Returns a dict with per-channel results.
    """
    from sqlalchemy import select
    from app.db import NotificationChannel

    channels = db.execute(
        select(NotificationChannel)
        .where(NotificationChannel.user_id == user_id)
        .where(NotificationChannel.enabled == True)  # noqa: E712
    ).scalars().all()

    if not channels:
        return {"sent": 0, "results": [], "message": "No notification channels configured"}

    message = format_alert_message(alert)
    results = []

    for ch in channels:
        cfg = ch.config or {}
        success = False

        if ch.channel_type == "telegram":
            bot_token = cfg.get("bot_token", "")
            chat_id = cfg.get("chat_id", "")
            if bot_token and chat_id:
                success = await send_telegram(bot_token, chat_id, message)
        elif ch.channel_type == "discord":
            webhook_url = cfg.get("webhook_url", "")
            if webhook_url:
                success = await send_discord(webhook_url, message)

        results.append({
            "channel_type": ch.channel_type,
            "channel_id": ch.id,
            "success": success,
        })

    return {
        "sent": sum(1 for r in results if r["success"]),
        "total": len(results),
        "results": results,
    }
