"""Application settings loaded from environment / .env."""
from __future__ import annotations

from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_prefix="APP_", extra="ignore")

    # Shared bearer token for the small private group (auth on /api/*).
    auth_token: str = "dev-secret-change-me"

    # JWT settings for per-user authentication.
    jwt_secret: str = "dev-jwt-secret-change-me"
    jwt_expire_days: int = 7

    # Which DataProvider implementation to use.
    data_provider: str = "yfinance"

    # Timezone for market scheduling.
    tz: str = "Asia/Kolkata"

    # SQLite database path (resolved relative to backend/ root).
    db_path: str = "data/trading.db"

    # Universe of stocks to scan.
    universe: str = "nifty50"

    # Opening-range window (IST session time, 24h).
    or_start: str = "09:15"
    or_end: str = "09:30"
    intraday_interval: str = "5m"

    # Strategy thresholds.
    volume_ratio_min: float = 1.2
    no_trade_gap_pct: float = 1.0
    no_trade_breadth_pct: float = 40.0

    # CORS: frontend origin(s) allowed to call the API.
    cors_origins: str = "http://localhost:3000"

    # Broker provider for holdings review: 'mock' (default), 'fyers', or 'kite'.
    broker_provider: str = "mock"

    # Fyers API credentials (optional, for real holdings).
    fyers_app_id: str = ""
    fyers_secret: str = ""
    fyers_access_token: str = ""

    # SMTP settings for daily digest email (optional — if not set, digests are stored but not emailed).
    smtp_host: str = ""
    smtp_port: int = 587
    smtp_user: str = ""
    smtp_password: str = ""
    digest_from_email: str = ""
    digest_send_hour: int = 16  # 4 PM IST — after market close

    @property
    def db_url(self) -> str:
        path = Path(self.db_path)
        if not path.is_absolute():
            path = Path(__file__).resolve().parent.parent / path
        path.parent.mkdir(parents=True, exist_ok=True)
        return f"sqlite:///{path}"


settings = Settings()
