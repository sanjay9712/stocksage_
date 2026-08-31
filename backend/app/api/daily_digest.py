"""Daily digest endpoints.

Generate and view daily market digests. Optionally email them via SMTP.
"""
from __future__ import annotations

import logging
from datetime import date

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select

from app.api.auth import require_token
from app.db import DailyDigest, SessionLocal, User
from app.strategies.daily_digest import generate_and_store_digest

router = APIRouter()
log = logging.getLogger("daily_digest_api")


@router.post("/daily-digest/generate")
async def generate_digest(
    target_date: str | None = Query(None, description="YYYY-MM-DD, defaults to today"),
    t: User = Depends(require_token),
) -> dict:
    """Generate a daily market digest.

    Compiles picks, signals, gaps, and triggered alerts into a structured digest.
    Stores it in the DB and optionally emails it if SMTP is configured.
    """
    d = date.fromisoformat(target_date) if target_date else date.today()
    result = await generate_and_store_digest(user_email=t.email, target_date=d)
    return result


@router.get("/daily-digest")
async def list_digests(
    limit: int = Query(7, ge=1, le=30),
    _t: User = Depends(require_token),
) -> dict:
    """List recent daily digests."""
    db = SessionLocal()
    try:
        rows = db.execute(
            select(DailyDigest)
            .order_by(DailyDigest.date.desc())
            .limit(limit)
        ).scalars().all()
        return {
            "digests": [
                {
                    "id": r.id,
                    "date": r.date.isoformat(),
                    "subject": r.subject,
                    "emailed": r.emailed,
                    "created_at": r.created_at.isoformat() if r.created_at else None,
                }
                for r in rows
            ]
        }
    finally:
        db.close()


@router.get("/daily-digest/{digest_id}")
async def get_digest(digest_id: int, _t: User = Depends(require_token)) -> dict:
    """Get full digest by ID."""
    db = SessionLocal()
    try:
        row = db.execute(
            select(DailyDigest).where(DailyDigest.id == digest_id)
        ).scalar_one_or_none()
        if not row:
            return {"error": "Digest not found"}
        return {
            "id": row.id,
            "date": row.date.isoformat(),
            "subject": row.subject,
            "emailed": row.emailed,
            "created_at": row.created_at.isoformat() if row.created_at else None,
            "data": row.body_text,
            "html": row.body_html,
        }
    finally:
        db.close()
