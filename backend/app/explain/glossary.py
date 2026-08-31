"""Beginner-mode glossary for trading terms.

Every term a beginner might encounter in a strategy explanation is defined here
in plain English. The glossary is served as a standalone API endpoint and can
also be attached to individual signal responses so a complete beginner can
understand every part of a pick without prior stock-market knowledge.
"""
from __future__ import annotations

GLOSSARY: dict[str, str] = {
    # ---- Core trading terms ----
    "long": "Betting the price will go UP. You buy first, sell later at a higher price.",
    "short": "Betting the price will go DOWN. You sell first (borrowed shares), buy back later at a lower price.",
    "entry": "The price at which you open the trade.",
    "stop_loss": "The price at which you exit the trade to limit your loss if the market moves against you. This is your safety net.",
    "stop-loss": "The price at which you exit the trade to limit your loss if the market moves against you. This is your safety net.",
    "target": "The price at which you exit the trade to take profit.",
    "target1": "Your first profit-taking level. You sell part of your position here.",
    "target2": "Your second profit-taking level. You sell the remaining position here.",
    "risk_reward": "How much you stand to gain versus how much you risk. 1:1.5 means for every ₹1 you risk, you aim to gain ₹1.50.",
    "r:r": "Risk-to-reward ratio. 1:1.5 means for every ₹1 you risk, you aim to gain ₹1.50.",
    "confidence": "A score from 0 to 1 showing how strong the signal is. Higher = more conviction. Not a guarantee.",

    # ---- Indicators ----
    "vwap": "Volume-Weighted Average Price. The average price weighted by volume for the session. Institutional traders use it as a 'fair value' benchmark.",
    "ema": "Exponential Moving Average. A line that follows price but smooths out noise. Gives more weight to recent prices.",
    "ema9": "9-period Exponential Moving Average. A fast trend line that closely follows recent price action.",
    "ema21": "21-period Exponential Moving Average. A slightly slower trend line used to confirm the broader short-term trend.",
    "sma": "Simple Moving Average. The average of closing prices over a set number of periods.",
    "atr": "Average True Range. Measures how volatile a stock is. A higher ATR means bigger price swings. Used to set stop-losses and targets.",
    "rsi": "Relative Strength Index. A 0-100 scale. Above 70 = potentially overbought (too high). Below 30 = potentially oversold (too low).",
    "ppo": "Percentage Price Oscillator. A momentum indicator showing the difference between two moving averages as a percentage. Above zero = bullish momentum. Below zero = bearish momentum.",
    "signal_line": "A moving average of the PPO. When PPO crosses above it, momentum is accelerating upward.",
    "histogram": "The difference between the PPO and its signal line. Growing bars = momentum strengthening.",
    "bollinger_bands": "Three lines: a middle average and upper/lower bands that widen/narrow with volatility. Price touching the upper band = potentially overbought. Touching the lower band = potentially oversold.",
    "upper_band": "The top Bollinger Band. Price closing above it suggests strong upward momentum.",
    "lower_band": "The bottom Bollinger Band. Price closing below it suggests strong downward momentum.",
    "middle_band": "The middle Bollinger Band, which is a 20-period simple moving average. Acts as a reference for 'average' price.",
    "bandwidth": "The width of the Bollinger Bands relative to the middle band. Narrow = low volatility (squeeze). Wide = high volatility.",
    "squeeze": "When Bollinger Bands are unusually narrow, indicating low volatility. A breakout (big move) often follows.",
    "pct_b": "Where the price sits within the Bollinger Bands. 0 = at the lower band. 1 = at the upper band. 0.5 = at the middle.",

    # ---- Strategy concepts ----
    "pullback": "A temporary move against the trend. In an uptrend, price drops briefly then continues up. Pullbacks are entry opportunities.",
    "breakout": "When price moves beyond a key level (like an opening range high) with increased volume. Suggests a new trend is starting.",
    "opening_range": "The high and low of the first 15 minutes of trading. Used to identify the day's initial direction.",
    "orb": "Opening Range Breakout. A strategy that enters when price breaks above or below the first 15-minute range.",
    "trend": "The general direction of price. Uptrend = making higher highs and lows. Downtrend = making lower highs and lows. Sideways = no clear direction.",
    "uptrend": "Price is generally rising over time, making higher highs and higher lows.",
    "downtrend": "Price is generally falling over time, making lower highs and lower lows.",
    "sideways": "Price is moving roughly flat with no clear up or down direction. Avoid trading trend strategies here.",
    "volume_ratio": "Current bar's volume compared to the average. Above 1.5x means above-average interest, which adds conviction to a move.",
    "volume": "The number of shares traded. High volume = more participants and more conviction behind a move.",

    # ---- Market mechanics ----
    "candle": "A bar on a chart showing Open, High, Low, and Close for a time period. Green/white = price went up. Red/black = price went down.",
    "bullish": "Optimistic. Expecting prices to rise.",
    "bearish": "Pessimistic. Expecting prices to fall.",
    "hammer": "A candlestick pattern with a small body and long lower shadow. Suggests buyers pushed price back up after selling. Bullish reversal signal.",
    "engulfing": "A candlestick pattern where the current candle's body completely covers the previous one. Signals a strong shift in momentum.",
    "gamma": "How fast an option's delta changes. High gamma (like on expiry day) means option prices can swing wildly. Be extra cautious.",
    "theta": "Time decay of options. Options lose value as expiry approaches. Option sellers profit from theta.",
    "expiry": "The day when options contracts expire. In India, Nifty options expire on Thursday, BankNifty on Thursday. High volatility expected.",

    # ---- Risk terms ----
    "scalp": "A very short-term trade held for seconds to minutes, aiming for small quick profits.",
    "intraday": "A trade opened and closed within the same trading day. No overnight risk.",
    "position_size": "How many shares/units you trade. Should be calculated from your stop-loss distance and risk budget, not guesswork.",
    "risk_pct": "The percentage of your account you could lose if your stop-loss is hit. Keep this under 1% per trade.",
}


def get_term(term: str) -> str | None:
    """Look up a term in the glossary (case-insensitive)."""
    return GLOSSARY.get(term.lower().replace(" ", "_"))


def get_relevant_terms(terms: list[str]) -> dict[str, str]:
    """Return definitions for a list of terms, skipping unknown ones."""
    result = {}
    for t in terms:
        definition = get_term(t)
        if definition:
            result[t] = definition
    return result
