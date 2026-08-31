"""BrokerProvider abstraction for holdings review + wrong-pick alerts.

A pluggable interface so a real broker (Kite/Upstox/Fyers) drops in later
without touching the reviewer logic. Today only MockBroker ships.

Wiring a real broker (example: Zerodha Kite Connect):
  1. `pip install kiteconnect`
  2. Implement `KiteBroker(DataProvider)` using the user's api_key/access_token
     for holdings/positions and kite.quote() for live prices.
  3. Set APP_BROKER_PROVIDER=kite in .env.
The reviewer is broker-agnostic; it only needs a list of Holding objects.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass
class Holding:
    symbol: str
    quantity: int
    avg_price: float          # buy average
    current_price: float      # latest available
    product: str = "CNC"     # CNC (delivery) / MIS (intraday) / NRML
    pnl: float = 0.0


@dataclass
class Position:
    symbol: str
    quantity: int
    side: str  # long, short
    avg_price: float
    current_price: float
    product: str = "MIS"
    pnl: float = 0.0


@dataclass
class OrderRequest:
    symbol: str
    side: str  # buy, sell
    quantity: int
    order_type: str = "MARKET"  # MARKET, LIMIT, SL, SL-M
    product: str = "CNC"  # CNC, MIS, NRML
    limit_price: float | None = None
    stop_price: float | None = None
    validity: str = "DAY"


@dataclass
class OrderResult:
    order_id: str | None
    status: str  # success, failed, rejected
    message: str = ""
    symbol: str = ""
    side: str = ""
    quantity: int = 0
    price: float | None = None


@dataclass
class Funds:
    available_balance: float
    used_margin: float
    total_balance: float


class BrokerProvider(ABC):
    name: str = "base"

    @abstractmethod
    async def get_holdings(self) -> list[Holding]: ...

    async def get_quote(self, symbol: str) -> float:
        """Latest price for a held symbol. Default: assume current_price cached."""
        raise NotImplementedError

    async def get_positions(self) -> list[Position]:
        """Open positions. Default: no positions."""
        return []

    async def place_order(self, req: OrderRequest) -> OrderResult:
        """Place an order. Default: not supported."""
        return OrderResult(order_id=None, status="failed", message="Order placement not supported by this broker")

    async def cancel_order(self, order_id: str) -> bool:
        """Cancel an order. Default: not supported."""
        return False

    async def get_orders(self) -> list[dict]:
        """Get today's orders. Default: empty."""
        return []

    async def get_funds(self) -> Funds | None:
        """Get account funds/balance. Default: not available."""
        return None
