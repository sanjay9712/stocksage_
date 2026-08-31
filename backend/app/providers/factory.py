"""Provider factory: build the active DataProvider from settings."""
from __future__ import annotations

from app.config import settings
from app.providers.base import DataProvider

_provider: DataProvider | None = None


def get_provider() -> DataProvider:
    global _provider
    if _provider is not None:
        return _provider
    name = settings.data_provider.lower()
    # If Fyers credentials are set, prefer Fyers for real-time data regardless
    # of the configured provider name (Fyers gives live NSE quotes + intraday).
    if settings.fyers_app_id and settings.fyers_access_token:
        try:
            from app.providers.fyers_provider import FyersProvider
            _provider = FyersProvider()
            return _provider
        except Exception:
            pass  # fall through to the configured provider
    if name == "yfinance":
        from app.providers.yfinance_provider import YFinanceProvider
        _provider = YFinanceProvider()
        return _provider
    if name == "nse":
        from app.providers.nse_equity_provider import NSEEquityProvider
        _provider = NSEEquityProvider()
        return _provider
    if name == "fyers":
        from app.providers.fyers_provider import FyersProvider
        _provider = FyersProvider()
        return _provider
    raise ValueError(f"Unknown data_provider: {settings.data_provider}")


def get_expiry_provider() -> DataProvider | None:
    """NSE provider for expiry/lot-size metadata (None if unavailable)."""
    try:
        from app.providers.nse_provider import NSEProvider
        return NSEProvider()
    except Exception:
        return None
