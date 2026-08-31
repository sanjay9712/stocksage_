"""Broker provider factory."""
from __future__ import annotations

from app.config import settings
from app.holdings.base import BrokerProvider


def get_broker() -> BrokerProvider:
    name = getattr(settings, "broker_provider", "mock").lower()
    if name == "mock":
        from app.holdings.mock_broker import MockBroker
        return MockBroker()
    if name == "fyers":
        from app.holdings.fyers_broker import FyersBroker
        return FyersBroker()
    if name == "kite":
        try:
            from app.holdings.kite_broker import KiteBroker  # optional, user-implemented
            return KiteBroker()
        except Exception as e:  # pragma: no cover
            raise RuntimeError(
                "Kite broker not configured. Implement app/holdings/kite_broker.py "
                "and set APP_KITE_API_KEY / APP_KITE_ACCESS_TOKEN. Falling back to mock."
            ) from e
    raise ValueError(f"Unknown broker_provider: {name}")
