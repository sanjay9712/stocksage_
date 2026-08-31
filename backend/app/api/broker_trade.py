"""Broker trading endpoints — order placement, positions, funds.

Extends the existing holdings infrastructure with real broker integration
for placing/canceling orders, viewing positions, and checking funds.
"""
from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from app.api.auth import require_token
from app.db import User
from app.holdings.factory import get_broker

router = APIRouter()
log = logging.getLogger("broker_trade_api")


class PlaceOrderRequest(BaseModel):
    symbol: str
    side: str = Field(..., pattern="^(buy|sell)$")
    quantity: int = Field(..., gt=0)
    order_type: str = Field("MARKET", pattern="^(MARKET|LIMIT|SL|SL-M)$")
    product: str = Field("CNC", pattern="^(CNC|MIS|NRML)$")
    limit_price: float | None = None
    stop_price: float | None = None
    validity: str = "DAY"


@router.get("/broker/status")
async def broker_status(t: User = Depends(require_token)) -> dict:
    """Check if a real broker is connected."""
    from app.config import settings
    connected = bool(
        settings.broker_provider != "mock"
        and settings.fyers_app_id
        and settings.fyers_access_token
    )
    return {
        "broker": settings.broker_provider,
        "connected": connected,
        "message": (
            "Fyers connected — real trading enabled"
            if connected
            else "Using mock broker. Configure Fyers credentials in .env to enable real trading."
        ),
    }


@router.get("/broker/positions")
async def get_positions(t: User = Depends(require_token)) -> dict:
    """Get open positions from the broker."""
    try:
        broker = get_broker()
        positions = await broker.get_positions()
        return {
            "positions": [
                {
                    "symbol": p.symbol,
                    "quantity": p.quantity,
                    "side": p.side,
                    "avg_price": round(p.avg_price, 2),
                    "current_price": round(p.current_price, 2),
                    "product": p.product,
                    "pnl": round(p.pnl, 2),
                }
                for p in positions
            ],
            "total": len(positions),
        }
    except RuntimeError as e:
        return {"positions": [], "total": 0, "error": str(e)}


@router.get("/broker/orders")
async def get_orders(t: User = Depends(require_token)) -> dict:
    """Get today's orders from the broker."""
    try:
        broker = get_broker()
        orders = await broker.get_orders()
        return {"orders": orders, "total": len(orders)}
    except RuntimeError as e:
        return {"orders": [], "total": 0, "error": str(e)}


@router.get("/broker/funds")
async def get_funds(t: User = Depends(require_token)) -> dict:
    """Get account funds/balance from the broker."""
    try:
        broker = get_broker()
        funds = await broker.get_funds()
        if funds:
            return {
                "available_balance": round(funds.available_balance, 2),
                "used_margin": round(funds.used_margin, 2),
                "total_balance": round(funds.total_balance, 2),
            }
        return {"error": "Funds not available from broker"}
    except RuntimeError as e:
        return {"error": str(e)}


@router.post("/broker/place-order")
async def place_order(req: PlaceOrderRequest, t: User = Depends(require_token)) -> dict:
    """Place a real order through the broker.

    ⚠ This places a REAL order with REAL money when Fyers is configured.
    """
    from app.holdings.base import OrderRequest as BrokerOrderRequest
    from app.config import settings

    if settings.broker_provider == "mock":
        return {
            "status": "simulated",
            "message": "Mock broker — order simulated, not placed",
            "symbol": req.symbol,
            "side": req.side,
            "quantity": req.quantity,
        }

    try:
        broker = get_broker()
        order_req = BrokerOrderRequest(
            symbol=req.symbol,
            side=req.side,
            quantity=req.quantity,
            order_type=req.order_type,
            product=req.product,
            limit_price=req.limit_price,
            stop_price=req.stop_price,
            validity=req.validity,
        )
        result = await broker.place_order(order_req)
        return {
            "status": result.status,
            "order_id": result.order_id,
            "message": result.message,
            "symbol": result.symbol,
            "side": result.side,
            "quantity": result.quantity,
        }
    except RuntimeError as e:
        raise HTTPException(status_code=503, detail=str(e))


@router.delete("/broker/cancel-order/{order_id}")
async def cancel_order(order_id: str, t: User = Depends(require_token)) -> dict:
    """Cancel an order through the broker."""
    try:
        broker = get_broker()
        success = await broker.cancel_order(order_id)
        return {"cancelled": success, "order_id": order_id}
    except RuntimeError as e:
        raise HTTPException(status_code=503, detail=str(e))
