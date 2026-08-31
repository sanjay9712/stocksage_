"""Price alert endpoints.

Users can create, list, delete, and check price alerts. Each alert
specifies a symbol, condition (above/below/cross_up/cross_down), and
target price. The check endpoint fetches current quotes and marks
triggered alerts.
"""
from __future__ import annotations

import asyncio
import logging
from datetime import datetime
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select

from app.api.auth import require_token
from app.db import PriceAlert, SessionLocal, User
from app.providers.factory import get_provider

log = logging.getLogger("price_alerts")
router = APIRouter()


class CreateAlertRequest(BaseModel):
    symbol: str
    condition: str = Field(..., pattern="^(above|below|cross_up|cross_down)$")
    target_price: float = Field(..., gt=0)
    note: str | None = None


class AlertResponse(BaseModel):
    id: int
    symbol: str
    condition: str
    target_price: float
    note: str | None
    status: str
    created_at: str
    triggered_at: str | None
    triggered_price: float | None


def _to_dict(a: PriceAlert) -> dict:
    return {
        "id": a.id,
        "symbol": a.symbol,
        "condition": a.condition,
        "target_price": a.target_price,
        "note": a.note,
        "status": a.status,
        "created_at": a.created_at.isoformat() if a.created_at else None,
        "triggered_at": a.triggered_at.isoformat() if a.triggered_at else None,
        "triggered_price": a.triggered_price,
    }


@router.get("/price-alerts")
async def list_alerts(t: User = Depends(require_token)) -> dict:
    """List all alerts for the current user."""
    db = SessionLocal()
    try:
        rows = db.execute(
            select(PriceAlert)
            .where(PriceAlert.user_id == t.id)
            .where(PriceAlert.status != "deleted")
            .order_by(PriceAlert.created_at.desc())
        ).scalars().all()
        return {"alerts": [_to_dict(a) for a in rows]}
    finally:
        db.close()


@router.post("/price-alerts")
async def create_alert(req: CreateAlertRequest, t: User = Depends(require_token)) -> dict:
    """Create a new price alert."""
    symbol = req.symbol.strip().upper().replace(".NS", "").replace("NSE:", "")
    db = SessionLocal()
    try:
        alert = PriceAlert(
            user_id=t.id,
            symbol=symbol,
            condition=req.condition,
            target_price=req.target_price,
            note=req.note,
            status="active",
        )
        db.add(alert)
        db.commit()
        db.refresh(alert)
        return _to_dict(alert)
    finally:
        db.close()


@router.delete("/price-alerts/{alert_id}")
async def delete_alert(alert_id: int, t: User = Depends(require_token)) -> dict:
    """Delete a price alert (soft delete)."""
    db = SessionLocal()
    try:
        alert = db.execute(
            select(PriceAlert)
            .where(PriceAlert.id == alert_id)
            .where(PriceAlert.user_id == t.id)
        ).scalar_one_or_none()
        if not alert:
            raise HTTPException(status_code=404, detail="Alert not found")
        alert.status = "deleted"
        db.commit()
        return {"deleted": True, "id": alert_id}
    finally:
        db.close()


@router.post("/price-alerts/check")
async def check_alerts(t: User = Depends(require_token)) -> dict:
    """Check all active alerts against current market prices.

    Fetches current quotes for all symbols with active alerts,
    triggers any that have met their condition.
    """
    db = SessionLocal()
    try:
        active = db.execute(
            select(PriceAlert)
            .where(PriceAlert.user_id == t.id)
            .where(PriceAlert.status == "active")
        ).scalars().all()

        if not active:
            return {"checked": 0, "triggered": [], "prices": {}}

        # Get unique symbols
        symbols = list({a.symbol for a in active})

        # Fetch current prices
        provider = get_provider()
        prices: dict[str, float] = {}

        async def _get_price(sym: str):
            try:
                quote = await provider.get_quote(sym)
                if quote and quote.price:
                    prices[sym] = float(quote.price)
            except Exception as e:
                log.warning("Failed to get quote for %s: %s", sym, e)

        await asyncio.gather(*[_get_price(s) for s in symbols])

        triggered: list[dict] = []
        for alert in active:
            price = prices.get(alert.symbol)
            if price is None:
                continue

            should_trigger = False
            if alert.condition == "above" and price >= alert.target_price:
                should_trigger = True
            elif alert.condition == "below" and price <= alert.target_price:
                should_trigger = True
            elif alert.condition == "cross_up" and price >= alert.target_price:
                should_trigger = True
            elif alert.condition == "cross_down" and price <= alert.target_price:
                should_trigger = True

            if should_trigger:
                alert.status = "triggered"
                alert.triggered_at = datetime.utcnow()
                alert.triggered_price = price
                triggered.append(_to_dict(alert))

        if triggered:
            db.commit()

        return {
            "checked": len(active),
            "triggered": triggered,
            "prices": {k: round(v, 2) for k, v in prices.items()},
        }
    finally:
        db.close()
