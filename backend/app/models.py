"""Pydantic schemas (API contract). DB models live in db.py."""
from __future__ import annotations

from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Auth schemas
# ---------------------------------------------------------------------------

class UserOut(BaseModel):
    """Public user info returned by auth endpoints."""
    id: int
    name: str
    email: str
    capital: float
    is_guest: bool = False
    created_at: datetime | None = None


class RegisterRequest(BaseModel):
    name: str
    email: str
    password: str
    capital: float = 500000.0  # ₹5L default, ₹10L option


class LoginRequest(BaseModel):
    email: str
    password: str


class TokenResponse(BaseModel):
    token: str
    user: UserOut


class Quote(BaseModel):
    symbol: str
    price: float
    prev_close: float | None = None
    day_high: float | None = None
    day_low: float | None = None
    volume: int | None = None


class Level(BaseModel):
    name: str
    value: float
    source: str  # how it was derived, e.g. "OR-High", "PDH", "ATR"


class FormulaStep(BaseModel):
    label: str          # e.g. "Stop-Loss"
    formula: str        # human-readable formula
    substituted: str    # formula with numbers plugged in
    result: float


class Explanation(BaseModel):
    summary: str                       # plain-English summary
    inputs: dict[str, float | str]     # raw numeric inputs
    formula_trace: list[FormulaStep]   # how entry/SL/targets were computed
    verification: list[str]            # user-reproducible checklist
    caveats: list[str] = Field(default_factory=list)


class Pick(BaseModel):
    date: date
    symbol: str
    side: Literal["long", "short"]
    entry: float
    stop_loss: float
    target1: float
    target2: float
    confidence: float                  # 0..1
    last_price: float = 0.0            # latest traded price at scan time
    name: str = ""                     # company name from NSE list
    expiry_day: bool = False
    status: Literal["active", "hit-target1", "stopped-out", "expired"] = "active"
    explanation: Explanation


class DayStatus(BaseModel):
    date: date
    market_open: bool
    no_trade: bool
    reason: str | None = None
    expiry_day: bool = False
    picks_count: int = 0


class PaperTrade(BaseModel):
    """A paper-trade signal with hypothetical outcome tracking."""
    id: int
    date: date
    symbol: str
    market: str = "nse"
    strategy: str
    side: str
    entry: float
    stop_loss: float
    target: float
    confidence: float = 0.0
    status: str = "open"          # open, hit_target, stopped_out, expired
    entry_time: datetime | None = None
    exit_time: datetime | None = None
    exit_price: float | None = None
    pnl_pct: float | None = None
    explanation: dict | None = None
    created_at: datetime | None = None


class PaperTradeStats(BaseModel):
    """Aggregate stats for paper-trade performance."""
    total_signals: int
    open: int
    resolved: int
    wins: int
    losses: int
    win_rate: float
    avg_pnl_pct: float
    total_pnl_pct: float
    best_trade_pct: float | None
    worst_trade_pct: float | None
    by_strategy: dict[str, dict]  # {strategy: {count, wins, win_rate, avg_pnl}}
    capital: float = 0.0
    position_size: float = 0.0       # 10% of capital per trade
    total_pnl_rupees: float = 0.0    # sum of pnl_pct/100 * position_size
    portfolio_value: float = 0.0     # capital + total_pnl_rupees
