"""Holdings review endpoints (broker abstraction + wrong-pick alerts)."""
from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.auth import require_token
from app.api.cache import cached
from app.config import settings
from app.db import PickRow, get_db
from app.holdings.factory import get_broker
from app.holdings import reviewer
from app.market_hours import today_ist

router = APIRouter()


@router.get("/holdings/status")
async def holdings_status(_t: str = Depends(require_token)):
    """Tell the frontend whether a real broker is connected or showing mock data."""
    broker = settings.broker_provider.lower()
    connected = broker in ("fyers", "kite") and bool(
        (broker == "fyers" and settings.fyers_app_id and settings.fyers_access_token)
    )
    return {
        "broker": broker,
        "connected": connected,
        "message": (
            "Mock broker — showing sample holdings. Connect Fyers to see your real portfolio."
            if not connected else f"{broker.capitalize()} connected — showing real holdings."
        ),
    }


@router.get("/holdings")
async def list_holdings(_t: str = Depends(require_token)):
    async def _fetch():
        broker = get_broker()
        holdings = await broker.get_holdings()
        out = []
        for h in holdings:
            pnl = (h.current_price - h.avg_price) * h.quantity
            out.append({
                "symbol": h.symbol, "quantity": h.quantity, "avg_price": h.avg_price,
                "current_price": h.current_price, "product": h.product,
                "pnl": round(pnl, 2),
            })
        return out
    return await cached("holdings", 60, _fetch)


@router.get("/holdings/review")
async def review(db: Session = Depends(get_db), _t: str = Depends(require_token)):
    async def _fetch():
        broker = get_broker()
        rows = db.execute(select(PickRow).where(PickRow.date == today_ist())).scalars().all()
        today_picks = {r.symbol for r in rows}
        reviews = await reviewer.review_holdings(broker, today_picks)
        return [reviewer.to_dict(r) for r in reviews]
    return await cached("holdings_review", 120, _fetch)
