# Intraday Screener (NSE) — Vertical Slice 1

A mobile + desktop web app that surfaces daily **intraday stock picks** with
**entry / stop-loss / target** levels and a **fully explained, verifiable**
reasoning for how each level was calculated.

## Honest caveats
- **Data is free but delayed ~15 min** (Yahoo Finance via `yfinance`). This is
  fine for screening levels (opening-range breakout uses 5-min candles and EOD
  math). It is **not** suitable for tick-by-tick scalping. A paid/broker feed
  can be dropped in later via the `DataProvider` abstraction without touching
  the strategy layer.
- Picks are a **systematic screen, not investment advice**.
- Sharing beyond close personal use may require SEBI RIA registration.

## Architecture
- **Backend** (Python, FastAPI): `backend/app/`
  - `providers/` — pluggable data source (`yfinance` default; `nse` for expiry metadata)
  - `indicators.py` — ATR, pivots, opening range, volume ratio (pure functions, unit-tested)
  - `strategies/intraday_breakout.py` — Opening-Range Breakout (09:15–09:30 IST)
  - `explain/explainer.py` — builds structured explanation + verification checklist
  - `screener/runner.py` — universe → data → strategy → picks → SQLite
  - `scheduler.py` — APScheduler on IST market hours
  - `api/picks.py` — `/api/picks/today`, `/api/picks/{symbol}`, `/api/day/status`, `/api/picks/scan`
- **Frontend** (Next.js + Tailwind): `frontend/`
  - Dashboard: responsive picks table with entry/SL/target/confidence
  - Detail page: level diagram (risk:reward) + explanation panel + verification checklist

## Strategy
- Universe: Nifty 50.
- Pre-market: previous-day H/L/C → pivots, ATR(14), 20-day avg volume.
- Opening range: 09:15–09:30 IST 5-min candles → OR-High / OR-Low.
- Breakout: first 5-min candle after 09:30 closing **above** OR-High, with
  volume ≥ 1.5× the 20-day average.
- **Entry** = OR-High · **Stop-Loss** = OR-Low · **Target 1** = Entry + 1×ATR ·
  **Target 2** = Entry + 2×ATR.
- No-trade flag: Nifty overnight gap > 1%.
- Expiry day tagged with a gamma warning.

## Run

### Backend
```bash
cd backend
pip install -e ".[dev]"          # may need --user --break-system-packages
python -m pytest -q              # 8 tests, no network
uvicorn app.main:app --reload --port 8000
```
Quick API check:
```bash
curl -H "Authorization: Bearer dev-secret-change-me" http://localhost:8000/api/day/status
```
Trigger a scan out of market hours (uses yfinance, delayed):
```bash
curl -X POST -H "Authorization: Bearer dev-secret-change-me" http://localhost:8000/api/picks/scan
```

### Frontend
```bash
cd frontend
npm install
npm run dev          # http://localhost:3000
```

Open the dashboard on your phone by visiting `http://<your-computer-LAN-IP>:3000`
(from the same network). For true remote access, put the backend behind a
tunnel (e.g. Cloudflare Tunnel / Tailscale) — not included here.

## Modules (all built)

| Page | Endpoint | What it does |
|------|----------|--------------|
| Intraday | `GET /api/picks/today`, `POST /api/picks/scan` | Nifty 50 opening-range breakout picks with entry/SL/target + verifiable explanation |
| Commodities | `GET /api/commodities/today` | Gold/Silver/Crude/etc. previous-day-high breakout (global futures proxy for MCX) |
| ETFs | `GET /api/etf/screener` | ~2y risk/return (volatility, CAGR, max-DD, Sharpe), risk level + suggested horizon + risks |
| Mutual funds | `GET /api/mf/screener` | AMFI NAV history (mfapi.in, keyless) → same metrics + horizon |
| Holdings | `GET /api/holdings`, `GET /api/holdings/review` | Broker holdings + wrong-pick alerts (trend vs 20/50-EMA, untracked intraday) |
| Day status | `GET /api/day/status`, `GET /api/day/events` | No-trade flag (gap/ATR/breadth) + scheduled events |

### Broker integration (holdings review)

Ships with a **MockBroker** (sample holdings) so the flow runs with zero setup.
To use your real broker, implement a `BrokerProvider` and set
`APP_BROKER_PROVIDER` in `backend/.env`. Example for Zerodha Kite:

1. `pip install kiteconnect`
2. Create `backend/app/holdings/kite_broker.py` implementing
   `BrokerProvider.get_holdings()` using `kite.holdings()` and live prices from
   `kite.quote()`.
3. Set `APP_BROKER_PROVIDER=kite` plus `APP_KITE_API_KEY` / `APP_KITE_ACCESS_TOKEN`.
   (Kite Connect is free with a funded Zerodha account; live historical data
   needs a paid subscription, but holdings/positions/quotes work free.)

### Data sources — honest breakdown

| Data | Source | Real? | Notes |
|------|--------|-------|-------|
| Market status, NIFTY/Bank Nifty/sectoral indices, India VIX | **nseindia.com** directly | ✅ Real, live | `api/marketStatus` + `api/allIndices` work |
| Stock daily/intraday bars, quotes | yfinance (Yahoo) | ⚠️ Delayed ~15 min | NSE blocks `/api/quote-equity` with Akamai bot protection from server-side |
| Commodities | yfinance global futures | ⚠️ USD proxy for MCX | True MCX data needs paid feed |
| Mutual funds | mfapi.in (AMFI) | ✅ Real NAV data | Occasionally unreachable from some networks |
| Holdings | Fyers API (if configured) or Mock | ✅ Real if Fyers configured | Without Fyers, shows mock data |

**NSE direct access limitations:** NSE's public API is partially blocked by Akamai bot protection. Market status, index values, and index chart data work. Individual stock quotes (`/api/quote-equity`) and historical data return 403 from server-side requests. To get real-time stock data, you need either:
  - A **broker API** (Fyers/Kite) — gives live quotes + holdings
  - A **paid data feed** (GDFL/Truedata) — gives true tick data

### Broker integration (Fyers — for real holdings)

Ships with a **MockBroker** (sample holdings) by default. To use your real Fyers account:

1. Create a Fyers API app at https://myapi.fyers.in/ (free with Fyers account)
2. Get your `app_id` and `secret_id`
3. Run the OAuth flow to get an `access_token` (valid 1 day; refresh daily)
4. Set in `backend/.env`:
   ```
   APP_BROKER_PROVIDER=fyers
   APP_FYERS_APP_ID=your_app_id
   APP_FYERS_SECRET=your_secret_id
   APP_FYERS_ACCESS_TOKEN=your_access_token
   ```
5. Restart the backend — `/api/holdings` and `/api/holdings/review` will now show YOUR real holdings with live prices and wrong-pick alerts.

**Note on Groww:** Groww does not offer a public trading API. Fyers or Zerodha Kite are the recommended options for API access.

## Roadmap (remaining)
- Paid/broker live-data provider for true scalping-grade data
- Full event calendar with actual RBI/FOMC dates (currently a seed list)
- Order placement via broker (currently read-only holdings review)

