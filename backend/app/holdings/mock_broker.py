"""MockBroker — returns sample holdings so the holdings-review flow works
end-to-end without any broker credentials. Swap in a real BrokerProvider
(Kite/Upstox) when you have API keys; the reviewer is unchanged.
"""
from __future__ import annotations

from app.holdings.base import BrokerProvider, Holding


_SAMPLE_HOLDINGS = [
    Holding(symbol="RELIANCE", quantity=20, avg_price=2450.0, current_price=2480.0, product="CNC"),
    Holding(symbol="TATAMOTORS", quantity=50, avg_price=720.0, current_price=695.0, product="CNC"),
    Holding(symbol="HDFCBANK", quantity=15, avg_price=1500.0, current_price=1520.0, product="CNC"),
    Holding(symbol="INFY", quantity=30, avg_price=1400.0, current_price=1380.0, product="CNC"),
]


class MockBroker(BrokerProvider):
    name = "mock"

    async def get_holdings(self) -> list[Holding]:
        return [Holding(**h.__dict__) for h in _SAMPLE_HOLDINGS]
