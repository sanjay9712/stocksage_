"""Stock universe (static seed; refreshable later via NSE constituent lists)."""

NIFTY_50 = [
    "RELIANCE", "TCS", "HDFCBANK", "INFY", "ICICIBANK", "HINDUNILVR", "ITC",
    "SBIN", "BHARTIARTL", "KOTAKBANK", "LT", "AXISBANK", "ASIANPAINT",
    "MARUTI", "SUNPHARMA", "TITAN", "ULTRACEMCO", "NESTLEIND", "BAJFINANCE",
    "BAJAJFINSV", "WIPRO", "HCLTECH", "POWERGRID", "NTPC", "ADANIENT",
    "JSWSTEEL", "TATAMOTORS", "TATASTEEL", "COALINDIA", "GRASIM", "TECHM",
    "ONGC", "DIVISLAB", "DRREDDY", "CIPLA", "EICHERMOT", "BRITANNIA",
    "HEROMOTOCO", "BAJAJ-AUTO", "INDUSINDBK", "M&M", "SHRIRAMFIN",
    "BPCL", "HINDALCO", "SBILIFE", "ICICIGI", "TATACONSUM",
    "UPL", "ADANIPORTS",
]

# Nifty Next 50 — the 51st–100th largest by market cap. Broadens the intraday
# scan so more breakouts are surfaced on a trading day.
NIFTY_NEXT_50 = [
    "DMART", "BAJAJHLDNG", "PIDILITIND", "SBICARD", "TVSMOTOR", "GODREJCP",
    "COLPAL", "DABUR", "VEDL", "MARICO", "AMBUJACEM", "PGHH", "SIEMENS",
    "PERSISTENT", "TATAPOWER", "BHARTIHEXA", "BERGEPAINT", "PIIND",
    "TORNTPHARM", "MUTHOOTFIN", "NAUKRI", "BOSCHLTD", "ICICIPRULI",
    "DLF", "HDFCLIFE", "HAVELLS", "IOC", "BANDHANBNK", "COFORGE",
    "GAIL", "LICI", "METROPOLIS", "ABB", "POLYCAB", "MPHASIS",
    "CHOLAFIN", "JINDALSTEL", "ZYDUSLIFE", "INDUSTOWER", "SRF",
    "RECLTD", "PFC", "MCDOWELL-N", "UNITDSPR", "LODHA", "FEDERALBNK",
    "TATASTEEL", "BPCL", "ESCORTS", "AUBANK", "DIXON",
]

UNIVERSES = {"nifty50": NIFTY_50, "nifty100": NIFTY_50 + NIFTY_NEXT_50}


def get_universe(name: str) -> list[str]:
    return list(UNIVERSES.get(name.lower(), NIFTY_50))


# ---------------------------------------------------------------------------
# Commodities universe.
# yfinance exposes global futures (USD-denominated) which track the same
# underlying as MCX contracts. They are a FREE PROXY, not INR MCX tick data.
# Real MCX live data requires a paid feed (GDFL/Truedata) or a broker that
# offers MCX (e.g. Angel One, Fyers).
# `name` = MCX-equivalent display name; `symbol` = yfinance ticker.
# ---------------------------------------------------------------------------
COMMODITIES = [
    {"name": "Gold (MCX proxy)", "symbol": "GC=F", "category": "metals"},
    {"name": "Silver (MCX proxy)", "symbol": "SI=F", "category": "metals"},
    {"name": "Crude Oil (MCX proxy)", "symbol": "CL=F", "category": "energy"},
    {"name": "Natural Gas (MCX proxy)", "symbol": "NG=F", "category": "energy"},
    {"name": "Copper (MCX proxy)", "symbol": "HG=F", "category": "metals"},
    {"name": "Aluminium (LME proxy)", "symbol": "ALI=F", "category": "metals"},
    {"name": "Zinc (LME proxy)", "symbol": "ZIN=F", "category": "metals"},
]


def get_commodities() -> list[dict]:
    return [dict(c) for c in COMMODITIES]


# ---------------------------------------------------------------------------
# ETF universe (NSE-listed ETFs, yfinance .NS suffix works).
# Categorised by theme so the invest screener can suggest horizon + risks.
# ---------------------------------------------------------------------------
ETF_UNIVERSE = [
    {"symbol": "NIFTYBEES", "name": "Nippon Nifty 50 ETF", "category": "broad-index", "horizon": "long"},
    {"symbol": "SETFNIF50", "name": "SBI Nifty 50 ETF", "category": "broad-index", "horizon": "long"},
    {"symbol": "GOLDBEES", "name": "Nippon Gold ETF", "category": "gold", "horizon": "long"},
    {"symbol": "HDFCGOLD", "name": "HDFC Gold ETF", "category": "gold", "horizon": "long"},
    {"symbol": "BANKBEES", "name": "Nippon Bank ETF", "category": "sector-bank", "horizon": "medium"},
    {"symbol": "ITBEES", "name": "Nippon IT ETF", "category": "sector-it", "horizon": "medium"},
    {"symbol": "LIQUIDBEES", "name": "Nippon Liquid ETF", "category": "liquid", "horizon": "short"},
    {"symbol": "CPSEETF", "name": "CPSE ETF", "category": "sector-psu", "horizon": "medium"},
    {"symbol": "MID150BEES", "name": "Nippon Midcap 150 ETF", "category": "midcap", "horizon": "long"},
    {"symbol": "SILVERBEES", "name": "Nippon Silver ETF", "category": "silver", "horizon": "long"},
]


def get_etf_universe() -> list[dict]:
    return [dict(e) for e in ETF_UNIVERSE]


# ---------------------------------------------------------------------------
# Mutual funds. Each entry's `code` is the AMFI scheme code — the same code
# used by mfapi.in (https://api.mfapi.in/mf/<code>) AND by AMFI's own
# NAVAll.txt dump (https://www.amfiindia.com/spages/NAVAll.txt). When mfapi.in
# is unreachable, the screener falls back to NAVAll.txt using these codes.
# Names match AMFI's current scheme names (some funds were renamed).
# ---------------------------------------------------------------------------
MUTUAL_FUNDS = [
    {"code": "119598", "name": "SBI Large Cap Fund - Direct", "category": "large-cap", "horizon": "long"},
    {"code": "118989", "name": "HDFC Mid Cap Fund - Direct", "category": "mid-cap", "horizon": "long"},
    {"code": "118825", "name": "Mirae Asset Large Cap Fund - Direct", "category": "large-cap", "horizon": "long"},
    {"code": "125497", "name": "SBI Small Cap Fund - Direct", "category": "small-cap", "horizon": "long"},
    {"code": "120505", "name": "Axis Midcap Fund - Direct", "category": "mid-cap", "horizon": "long"},
    {"code": "122639", "name": "Parag Parikh Flexi Cap Fund - Direct", "category": "flexi-cap", "horizon": "long"},
    {"code": "118968", "name": "HDFC Balanced Advantage Fund - Direct", "category": "hybrid", "horizon": "medium"},
    {"code": "120251", "name": "ICICI Prudential Aggressive Hybrid Fund - Direct", "category": "hybrid", "horizon": "medium"},
    {"code": "146643", "name": "SBI Equity Minimum Variance Fund - Direct", "category": "factor", "horizon": "long"},
    {"code": "119800", "name": "SBI Liquid Fund - Direct", "category": "liquid", "horizon": "short"},
]


def get_mutual_funds() -> list[dict]:
    return [dict(m) for m in MUTUAL_FUNDS]


# ---------------------------------------------------------------------------
# US stock universe — popular large-cap US stocks (no yfinance suffix needed).
# yfinance fetches US tickers as bare symbols (AAPL, MSFT, etc.).
# ---------------------------------------------------------------------------
US_STOCKS = [
    "AAPL", "MSFT", "GOOGL", "AMZN", "NVDA", "META", "TSLA", "AVGO",
    "BRK-B", "LLY", "JPM", "V", "UNH", "XOM", "WMT", "MA", "PG", "JNJ",
    "HD", "ORCL", "COST", "NFLX", "ABBV", "BAC", "CRM", "KO", "AMD",
    "PEP", "ADBE", "INTC", "CSCO", "DIS", "PFE", "TMO", "VZ", "WFC",
    "QCOM", "ABT", "NKE", "DHR", "TXN", "NEE", "PM", "IBM", "GE",
]

# Company names for US stocks (for search autocomplete display).
US_STOCK_NAMES: dict[str, str] = {
    "AAPL": "Apple Inc.", "MSFT": "Microsoft Corp.", "GOOGL": "Alphabet Inc.",
    "AMZN": "Amazon.com Inc.", "NVDA": "NVIDIA Corp.", "META": "Meta Platforms",
    "TSLA": "Tesla Inc.", "AVGO": "Broadcom Inc.", "BRK-B": "Berkshire Hathaway",
    "LLY": "Eli Lilly & Co.", "JPM": "JPMorgan Chase", "V": "Visa Inc.",
    "UNH": "UnitedHealth Group", "XOM": "Exxon Mobil", "WMT": "Walmart Inc.",
    "MA": "Mastercard Inc.", "PG": "Procter & Gamble", "JNJ": "Johnson & Johnson",
    "HD": "Home Depot", "ORCL": "Oracle Corp.", "COST": "Costco Wholesale",
    "NFLX": "Netflix Inc.", "ABBV": "AbbVie Inc.", "BAC": "Bank of America",
    "CRM": "Salesforce Inc.", "KO": "Coca-Cola Co.", "AMD": "Advanced Micro Devices",
    "PEP": "PepsiCo Inc.", "ADBE": "Adobe Inc.", "INTC": "Intel Corp.",
    "CSCO": "Cisco Systems", "DIS": "Walt Disney Co.", "PFE": "Pfizer Inc.",
    "TMO": "Thermo Fisher", "VZ": "Verizon Comm.", "WFC": "Wells Fargo",
    "QCOM": "Qualcomm Inc.", "ABT": "Abbott Laboratories", "NKE": "Nike Inc.",
    "DHR": "Danaher Corp.", "TXN": "Texas Instruments", "NEE": "NextEra Energy",
    "PM": "Philip Morris", "IBM": "IBM Corp.", "GE": "General Electric",
}


# US ETF universe — popular US-listed ETFs across categories.
US_ETF_UNIVERSE = [
    {"symbol": "SPY", "name": "SPDR S&P 500 ETF", "category": "broad-index", "horizon": "long"},
    {"symbol": "QQQ", "name": "Invesco QQQ (Nasdaq 100)", "category": "broad-index", "horizon": "long"},
    {"symbol": "VTI", "name": "Vanguard Total Stock Market ETF", "category": "broad-index", "horizon": "long"},
    {"symbol": "VOO", "name": "Vanguard S&P 500 ETF", "category": "broad-index", "horizon": "long"},
    {"symbol": "DIA", "name": "SPDR Dow Jones ETF", "category": "broad-index", "horizon": "long"},
    {"symbol": "IWM", "name": "iShares Russell 2000 ETF", "category": "midcap", "horizon": "long"},
    {"symbol": "XLK", "name": "Technology Select Sector SPDR", "category": "sector-tech", "horizon": "medium"},
    {"symbol": "XLF", "name": "Financial Select Sector SPDR", "category": "sector-finance", "horizon": "medium"},
    {"symbol": "XLE", "name": "Energy Select Sector SPDR", "category": "sector-energy", "horizon": "medium"},
    {"symbol": "XLV", "name": "Health Care Select Sector SPDR", "category": "sector-health", "horizon": "medium"},
    {"symbol": "XLU", "name": "Utilities Select Sector SPDR", "category": "sector-utility", "horizon": "medium"},
    {"symbol": "ARKK", "name": "ARK Innovation ETF", "category": "sector-tech", "horizon": "long"},
    {"symbol": "GLD", "name": "SPDR Gold Shares", "category": "gold", "horizon": "long"},
    {"symbol": "TLT", "name": "iShares 20+ Year Treasury Bond", "category": "bond", "horizon": "medium"},
    {"symbol": "EEM", "name": "iShares MSCI Emerging Markets", "category": "broad-index", "horizon": "long"},
]


# Combined set for O(1) lookup — used by _suffix() to avoid appending .NS.
_US_SYMBOL_SET = set(s.upper() for s in US_STOCKS) | set(e["symbol"].upper() for e in US_ETF_UNIVERSE)


def is_us_symbol(symbol: str) -> bool:
    """Check if a symbol is a known US stock/ETF (no .NS suffix needed)."""
    return symbol.strip().upper() in _US_SYMBOL_SET


def get_us_stocks() -> list[str]:
    return list(US_STOCKS)


def get_us_etf_universe() -> list[dict]:
    return [dict(e) for e in US_ETF_UNIVERSE]
