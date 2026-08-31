"""DataProvider abstraction.

A pluggable interface so the free yfinance provider works today and a paid
broker feed can be dropped in later without touching the strategy layer.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import date

import pandas as pd

from app.models import Quote


class DataProvider(ABC):
    """Market-data source for both daily and intraday bars plus metadata."""

    name: str = "base"

    @abstractmethod
    async def get_daily_history(self, symbol: str, days: int = 60) -> pd.DataFrame:
        """Return daily OHLCV indexed by date (tz-naive, descending not assumed)."""

    @abstractmethod
    async def get_intraday(
        self, symbol: str, interval: str = "5m", days: int = 1
    ) -> pd.DataFrame:
        """Return intraday OHLCV indexed by tz-aware timestamp."""

    @abstractmethod
    async def get_quote(self, symbol: str) -> Quote: ...

    async def get_expiry_calendar(self, symbol: str | None = None) -> list[date]:
        """NSE F&O expiry dates. Default provider returns [] (unknown)."""
        return []

    async def get_option_chain(self, symbol: str, expiry: str | None = None) -> dict:
        """Option chain data. Default provider returns empty (unsupported)."""
        return {"calls": [], "puts": [], "expiries": [], "expiry": None}
