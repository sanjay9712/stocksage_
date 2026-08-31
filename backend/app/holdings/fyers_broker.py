"""Fyers broker integration (Fyers API v3).

Gives REAL holdings, positions, and live quotes from your Fyers account.

SETUP:
  1. Create a Fyers API app at https://myapi.fyers.in/ (free with Fyers account)
  2. Get your app_id and secret_id
  3. Run the OAuth flow to get an access_token (valid 1 day; refresh daily)
  4. Set in backend/.env:
       APP_BROKER_PROVIDER=fyers
       APP_FYERS_APP_ID=your_app_id
       APP_FYERS_SECRET=your_secret_id
       APP_FYERS_ACCESS_TOKEN=your_access_token

The access_token expires daily. For production, implement the refresh flow
(documented at https://myapi.fyers.in/docs). For now, paste a fresh token
each day.

FYERS symbol format: NSE:RELIANCE-EQ
"""
from __future__ import annotations

import httpx

from app.config import settings
from app.holdings.base import BrokerProvider, Holding, OrderRequest, OrderResult, Position, Funds

FYERS_API_BASE = "https://api-t1.fyers.in/api/v3"


class FyersBroker(BrokerProvider):
    name = "fyers"

    def __init__(self):
        self.app_id = settings.fyers_app_id
        self.token = settings.fyers_access_token
        if not self.app_id or not self.token:
            raise RuntimeError(
                "Fyers broker not configured. Set APP_FYERS_APP_ID and "
                "APP_FYERS_ACCESS_TOKEN in backend/.env. Get them from "
                "https://myapi.fyers.in/"
            )

    def _headers(self):
        return {
            "Authorization": f"{self.app_id}:{self.token}",
            "Accept": "application/json",
        }

    def _fyers_symbol(self, nse_symbol: str) -> str:
        """Convert NSE symbol to Fyers format: NSE:RELIANCE-EQ"""
        return f"NSE:{nse_symbol}-EQ"

    async def get_holdings(self) -> list[Holding]:
        """Fetch real holdings from Fyers."""
        async with httpx.AsyncClient(timeout=15) as c:
            r = await c.get(f"{FYERS_API_BASE}/holdings", headers=self._headers())
            r.raise_for_status()
            data = r.json()

        holdings = []
        for item in data.get("holdings", []):
            symbol = item.get("symbol", "").replace("NSE:", "").replace("-EQ", "")
            holdings.append(Holding(
                symbol=symbol,
                quantity=int(item.get("quantity", 0)),
                avg_price=float(item.get("costPrice", 0)),
                current_price=float(item.get("ltp", 0)),
                product="CNC",
                pnl=float(item.get("pl", 0)),
            ))
        return holdings

    async def get_quote(self, symbol: str) -> float:
        """Live quote for a symbol via Fyers."""
        fy_sym = self._fyers_symbol(symbol)
        async with httpx.AsyncClient(timeout=10) as c:
            r = await c.get(
                f"{FYERS_API_BASE}/quotes",
                params={"symbols": fy_sym},
                headers=self._headers(),
            )
            r.raise_for_status()
            data = r.json()
            quotes = data.get("d", [])
            if quotes:
                return float(quotes[0].get("v", {}).get("lp", 0))
        return 0.0

    async def get_positions(self) -> list[Position]:
        """Fetch open positions from Fyers."""
        async with httpx.AsyncClient(timeout=15) as c:
            r = await c.get(f"{FYERS_API_BASE}/positions", headers=self._headers())
            r.raise_for_status()
            data = r.json()

        positions = []
        for item in data.get("netPositions", []):
            symbol = item.get("symbol", "").replace("NSE:", "").replace("-EQ", "")
            qty = int(item.get("netQty", 0))
            if qty == 0:
                continue
            side = "long" if qty > 0 else "short"
            positions.append(Position(
                symbol=symbol,
                quantity=abs(qty),
                side=side,
                avg_price=float(item.get("avgPrice", 0)),
                current_price=float(item.get("ltp", 0)),
                product=item.get("product", "MIS"),
                pnl=float(item.get("pl", 0)),
            ))
        return positions

    async def place_order(self, req: OrderRequest) -> OrderResult:
        """Place a real order via Fyers API."""
        fy_sym = self._fyers_symbol(req.symbol)

        # Map our order types to Fyers values
        # Fyers: 1=Limit, 2=Market, 3=Stop, 4=StopMarket
        type_map = {"MARKET": 2, "LIMIT": 1, "SL": 3, "SL-M": 4}
        fyers_type = type_map.get(req.order_type.upper(), 2)

        # Fyers: 1=Buy, -1=Sell
        side_val = 1 if req.side.lower() == "buy" else -1

        payload = {
            "symbol": fy_sym,
            "qty": req.quantity,
            "type": fyers_type,
            "side": side_val,
            "productType": req.product,
            "validity": req.validity,
            "offlineOrder": False,
        }
        if req.limit_price:
            payload["limitPrice"] = req.limit_price
        if req.stop_price:
            payload["stopPrice"] = req.stop_price

        try:
            async with httpx.AsyncClient(timeout=15) as c:
                r = await c.post(
                    f"{FYERS_API_BASE}/orders/sync",
                    json=payload,
                    headers={**self._headers(), "Content-Type": "application/json"},
                )
                r.raise_for_status()
                data = r.json()

            if data.get("s") == "ok":
                order_id = data.get("id", "")
                return OrderResult(
                    order_id=order_id,
                    status="success",
                    message=f"Order placed: {order_id}",
                    symbol=req.symbol,
                    side=req.side,
                    quantity=req.quantity,
                )
            else:
                msg = data.get("message", "Unknown error")
                return OrderResult(
                    order_id=None,
                    status="failed",
                    message=msg,
                    symbol=req.symbol,
                    side=req.side,
                    quantity=req.quantity,
                )
        except Exception as e:
            return OrderResult(
                order_id=None,
                status="failed",
                message=str(e),
                symbol=req.symbol,
                side=req.side,
                quantity=req.quantity,
            )

    async def cancel_order(self, order_id: str) -> bool:
        """Cancel an order via Fyers API."""
        try:
            async with httpx.AsyncClient(timeout=10) as c:
                r = await c.delete(
                    f"{FYERS_API_BASE}/orders/sync",
                    params={"id": order_id},
                    headers=self._headers(),
                )
                r.raise_for_status()
                data = r.json()
                return data.get("s") == "ok"
        except Exception:
            return False

    async def get_orders(self) -> list[dict]:
        """Fetch today's orders from Fyers."""
        try:
            async with httpx.AsyncClient(timeout=15) as c:
                r = await c.get(f"{FYERS_API_BASE}/orders", headers=self._headers())
                r.raise_for_status()
                data = r.json()
            return data.get("orderBook", [])
        except Exception:
            return []

    async def get_funds(self) -> Funds | None:
        """Fetch account funds/balance from Fyers."""
        try:
            async with httpx.AsyncClient(timeout=10) as c:
                r = await c.get(f"{FYERS_API_BASE}/funds", headers=self._headers())
                r.raise_for_status()
                data = r.json()
            funds = data.get("fund_limit", [])
            if funds:
                return Funds(
                    available_balance=float(funds[0].get("availableBalance", 0)),
                    used_margin=float(funds[0].get(" utilizedDebits", 0)),
                    total_balance=float(funds[0].get("totalBalance", 0)),
                )
        except Exception:
            pass
        return None
