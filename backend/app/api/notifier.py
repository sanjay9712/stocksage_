"""Notification channel endpoints.

Configure and test Telegram/Discord notification channels.
"""
from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select

from app.api.auth import require_token
from app.db import NotificationChannel, SessionLocal, User
from app.strategies.notifier import notify_user, send_telegram, send_discord

router = APIRouter()
log = logging.getLogger("notifier_api")


class CreateChannelRequest(BaseModel):
    channel_type: str  # telegram, discord
    config: dict  # {bot_token, chat_id} or {webhook_url}


class TestNotificationRequest(BaseModel):
    message: str = "🧪 Test notification from Trading Assistant"


@router.get("/notifications/channels")
async def list_channels(t: User = Depends(require_token)) -> dict:
    """List all notification channels for the current user."""
    db = SessionLocal()
    try:
        rows = db.execute(
            select(NotificationChannel)
            .where(NotificationChannel.user_id == t.id)
            .order_by(NotificationChannel.created_at.desc())
        ).scalars().all()
        return {
            "channels": [
                {
                    "id": ch.id,
                    "channel_type": ch.channel_type,
                    "config": _mask_config(ch.channel_type, ch.config),
                    "enabled": ch.enabled,
                    "created_at": ch.created_at.isoformat() if ch.created_at else None,
                }
                for ch in rows
            ]
        }
    finally:
        db.close()


@router.post("/notifications/channels")
async def create_channel(req: CreateChannelRequest, t: User = Depends(require_token)) -> dict:
    """Create a new notification channel."""
    if req.channel_type not in ("telegram", "discord"):
        raise HTTPException(status_code=400, detail="channel_type must be 'telegram' or 'discord'")

    if req.channel_type == "telegram":
        if not req.config.get("bot_token") or not req.config.get("chat_id"):
            raise HTTPException(status_code=400, detail="Telegram requires bot_token and chat_id")
    elif req.channel_type == "discord":
        if not req.config.get("webhook_url"):
            raise HTTPException(status_code=400, detail="Discord requires webhook_url")

    db = SessionLocal()
    try:
        channel = NotificationChannel(
            user_id=t.id,
            channel_type=req.channel_type,
            config=req.config,
            enabled=True,
        )
        db.add(channel)
        db.commit()
        db.refresh(channel)
        return {
            "id": channel.id,
            "channel_type": channel.channel_type,
            "enabled": channel.enabled,
            "created_at": channel.created_at.isoformat() if channel.created_at else None,
        }
    finally:
        db.close()


@router.delete("/notifications/channels/{channel_id}")
async def delete_channel(channel_id: int, t: User = Depends(require_token)) -> dict:
    """Delete a notification channel."""
    db = SessionLocal()
    try:
        channel = db.execute(
            select(NotificationChannel)
            .where(NotificationChannel.id == channel_id)
            .where(NotificationChannel.user_id == t.id)
        ).scalar_one_or_none()
        if not channel:
            raise HTTPException(status_code=404, detail="Channel not found")
        db.delete(channel)
        db.commit()
        return {"deleted": True, "id": channel_id}
    finally:
        db.close()


@router.post("/notifications/test")
async def test_notification(req: TestNotificationRequest, t: User = Depends(require_token)) -> dict:
    """Send a test notification to all enabled channels."""
    db = SessionLocal()
    try:
        result = await notify_user(db, t.id, {
            "type": "test",
            "message": req.message,
        })
        return result
    finally:
        db.close()


def _mask_config(channel_type: str, config: dict) -> dict:
    """Mask sensitive fields in config for display."""
    if channel_type == "telegram":
        token = config.get("bot_token", "")
        masked = token[:8] + "..." + token[-4:] if len(token) > 12 else "***"
        return {"bot_token": masked, "chat_id": config.get("chat_id", "")}
    elif channel_type == "discord":
        url = config.get("webhook_url", "")
        masked = url[:30] + "..." if len(url) > 30 else "***"
        return {"webhook_url": masked}
    return config
