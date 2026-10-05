"""MockBroker — returns sample holdings so the holdings-review flow works
end-to-end without any broker credentials. Swap in a real BrokerProvider
(Kite/Upstox) when you have API keys; the reviewer is unchanged.
"""
from __future__ import annotations

from app.holdings.base import BrokerProvider, Holding


_SAMPLE_HOLDINGS = [
    # avg_price levels are realistic vs. live prices (~Oct 2026) so the demo
    # shows a mix of winners and losers. current_price is only a fallback —
    # the review/tax-harvest endpoints override it with live quotes.
    Holding(symbol="RELIANCE", quantity=20, avg_price=1250.0, current_price=1186.0, product="CNC"),
    Holding(symbol="TMCV", quantity=50, avg_price=405.0, current_price=427.0, product="CNC"),
    Holding(symbol="HDFCBANK", quantity=15, avg_price=655.0, current_price=705.0, product="CNC"),
    Holding(symbol="INFY", quantity=30, avg_price=1080.0, current_price=1021.0, product="CNC"),
]


class MockBroker(BrokerProvider):
    name = "mock"

    async def get_holdings(self) -> list[Holding]:
        return [Holding(**h.__dict__) for h in _SAMPLE_HOLDINGS]
