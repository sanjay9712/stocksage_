"""Technical indicators used by the screener.

Pure functions on pandas DataFrames with columns Open/High/Low/Close/Volume.
No I/O, so they are unit-testable with synthetic fixtures.
"""
from __future__ import annotations

import pandas as pd


def atr(df: pd.DataFrame, period: int = 14) -> pd.Series:
    """Average True Range (Wilder's smoothing). Returns a Series aligned to df."""
    high = df["High"]
    low = df["Low"]
    close = df["Close"]
    prev_close = close.shift(1)
    tr = pd.concat(
        [
            (high - low),
            (high - prev_close).abs(),
            (low - prev_close).abs(),
        ],
        axis=1,
    ).max(axis=1)
    # Wilder's smoothing = EMA with alpha = 1/period.
    return tr.ewm(alpha=1 / period, adjust=False, min_periods=period).mean()


def ema(series: pd.Series, period: int) -> pd.Series:
    return series.ewm(span=period, adjust=False, min_periods=period).mean()


def pivots(prev_high: float, prev_low: float, prev_close: float) -> dict[str, float]:
    """Standard (floor) pivot points from the previous day's H/L/C."""
    p = (prev_high + prev_low + prev_close) / 3.0
    r1 = 2 * p - prev_low
    s1 = 2 * p - prev_high
    r2 = p + (prev_high - prev_low)
    s2 = p - (prev_high - prev_low)
    return {"pivot": p, "r1": r1, "r2": r2, "s1": s1, "s2": s2}


def opening_range(intraday: pd.DataFrame, start: str, end: str) -> tuple[float, float] | None:
    """High/low of the opening-range window [start, end) in HH:MM.

    Uses only the most recent trading day's bars. `intraday` must have a
    tz-aware DatetimeIndex. Returns None if the window has no candles yet
    (market hasn't reached it).
    """
    if intraday.empty:
        return None
    local = intraday.index
    if local.tz is None:
        return None
    # Get the most recent trading date.
    if hasattr(local, "tz_convert"):
        kolkata_idx = local.tz_convert("Asia/Kolkata")
    else:
        kolkata_idx = local
    latest_date = kolkata_idx[-1].date()
    today_mask = pd.Series([d.date() == latest_date for d in kolkata_idx], index=intraday.index)
    today_bars = intraday[today_mask]
    if today_bars.empty:
        return None
    # Filter to the OR time window.
    times = kolkata_idx[today_mask].time
    or_window = today_bars[
        (pd.Series(times, index=today_bars.index) >= pd.to_datetime(start, format="%H:%M").time())
        & (pd.Series(times, index=today_bars.index) < pd.to_datetime(end, format="%H:%M").time())
    ]
    if or_window.empty:
        return None
    return float(or_window["High"].max()), float(or_window["Low"].min())


def avg_volume(df: pd.DataFrame, period: int = 20) -> float:
    """Average of the trailing `period` daily volumes (excludes the current bar)."""
    if "Volume" not in df or len(df) < 2:
        return 0.0
    return float(df["Volume"].iloc[-period - 1:-1].mean() if len(df) > period else df["Volume"].iloc[:-1].mean())


def breakout_bar(intraday: pd.DataFrame, or_high: float, or_low: float, avg_vol: float, volume_ratio_min: float) -> dict | None:
    """Find the first 5-min candle after the OR window that closes above OR-High
    on volume >= volume_ratio_min * avg_vol. Uses only the most recent trading
    day's bars. Returns the bar info or None.
    """
    if intraday.empty or avg_vol <= 0:
        return None
    local = intraday.index
    tz = local.tz
    if tz is None:
        return None
    kolkata_idx = local.tz_convert("Asia/Kolkata") if hasattr(local, "tz_convert") else local
    latest_date = kolkata_idx[-1].date()
    today_mask = pd.Series([d.date() == latest_date for d in kolkata_idx], index=intraday.index)
    today_bars = intraday[today_mask]
    if today_bars.empty:
        return None
    times = kolkata_idx[today_mask].time
    # Bars strictly after 09:30 on the current day.
    after_or = today_bars[pd.Series(times, index=today_bars.index) >= pd.to_datetime("09:30", format="%H:%M").time()]
    for ts, row in after_or.iterrows():
        if row["Close"] > or_high and row["Volume"] >= volume_ratio_min * avg_vol:
            return {
                "ts": str(ts),
                "close": float(row["Close"]),
                "high": float(row["High"]),
                "low": float(row["Low"]),
                "volume": float(row["Volume"]),
                "volume_ratio": float(row["Volume"] / avg_vol),
            }
    return None


# ---------------------------------------------------------------------------
# Risk / return metrics for invest-style screeners (ETF, mutual funds).
# All operate on a daily close series; pure functions, unit-testable.
# TRADING_DAYS assumes NSE ~252 sessions per year.
# ---------------------------------------------------------------------------

TRADING_DAYS = 252


def daily_returns(close: pd.Series) -> pd.Series:
    return close.pct_change().dropna()


def annualized_volatility(close: pd.Series, period: int = TRADING_DAYS) -> float:
    """Std-dev of daily returns * sqrt(period)."""
    r = daily_returns(close)
    if len(r) < 2:
        return 0.0
    return float(r.std(ddof=0) * (period ** 0.5))


def cagr(close: pd.Series) -> float:
    """Compound annual growth rate over the span of `close`."""
    if len(close) < 2:
        return 0.0
    start = float(close.iloc[0])
    end = float(close.iloc[-1])
    if start <= 0:
        return 0.0
    years = len(close) / TRADING_DAYS
    if years <= 0:
        return 0.0
    return float((end / start) ** (1.0 / years) - 1.0)


def max_drawdown(close: pd.Series) -> float:
    """Worst peak-to-trough decline as a negative fraction (e.g. -0.32)."""
    if len(close) < 2:
        return 0.0
    running_max = close.cummax()
    dd = (close - running_max) / running_max
    return float(dd.min())


def sharpe_ratio(close: pd.Series, rf_annual: float = 0.06, period: int = TRADING_DAYS) -> float:
    """Annualized Sharpe using daily returns and a flat risk-free rate."""
    r = daily_returns(close)
    if len(r) < 2:
        return 0.0
    rf_daily = rf_annual / period
    excess = r - rf_daily
    sd = r.std(ddof=0)
    if sd == 0:
        return 0.0
    return float(excess.mean() / sd * (period ** 0.5))


def risk_metrics(close: pd.Series, rf_annual: float = 0.06) -> dict[str, float]:
    """Bundle of all invest metrics for a close series."""
    return {
        "volatility": annualized_volatility(close),
        "cagr": cagr(close),
        "max_drawdown": max_drawdown(close),
        "sharpe": sharpe_ratio(close, rf_annual=rf_annual),
    }


# ---------------------------------------------------------------------------
# Intraday indicators used by the advanced scalping strategies.
# VWAP, Bollinger Bands, PPO, RSI — pure functions, unit-testable.
# ---------------------------------------------------------------------------


def vwap(intraday: pd.DataFrame) -> pd.Series:
    """Session Volume-Weighted Average Price.

    Typical price = (High + Low + Close) / 3, weighted by Volume, accumulated
    cumulatively from the start of each session. When the intraday data spans
    multiple days, the cumulative sum resets at each session boundary so VWAP
    is always per-session. `intraday` must have High/Low/Close/Volume columns
    with a tz-aware DatetimeIndex. Returns a Series aligned to `intraday`.
    """
    typical = (intraday["High"] + intraday["Low"] + intraday["Close"]) / 3.0
    vol = intraday["Volume"].astype(float)
    pv = typical * vol

    # Group by trading date to reset VWAP at each session boundary.
    if hasattr(intraday.index, "tz_convert"):
        dates = intraday.index.tz_convert("Asia/Kolkata").date
    else:
        dates = intraday.index.date

    cum_pv = pv.groupby(dates).cumsum()
    cum_vol = vol.groupby(dates).cumsum().replace(0.0, float("nan"))
    return (cum_pv / cum_vol).ffill()


def bollinger_bands(
    close: pd.Series,
    period: int = 20,
    num_std: float = 2.0,
) -> dict[str, pd.Series]:
    """Bollinger Bands.

    Returns a dict with: middle (SMA), upper, lower, bandwidth (range/sma),
    and pct_b (position of close within the bands, 0..1 inside).
    """
    middle = close.rolling(period, min_periods=period).mean()
    sd = close.rolling(period, min_periods=period).std(ddof=0)
    upper = middle + num_std * sd
    lower = middle - num_std * sd
    bandwidth = (upper - lower) / middle.replace(0.0, float("nan"))
    pct_b = (close - lower) / (upper - lower).replace(0.0, float("nan"))
    return {
        "middle": middle,
        "upper": upper,
        "lower": lower,
        "bandwidth": bandwidth,
        "pct_b": pct_b,
    }


def ppo(
    close: pd.Series,
    fast: int = 12,
    slow: int = 26,
    signal: int = 9,
) -> dict[str, pd.Series]:
    """Percentage Price Oscillator.

    PPO = (fast EMA - slow EMA) / slow EMA * 100.
    Signal = EMA of PPO. Histogram = PPO - Signal. Returns dict with all three.
    Percentage-based, so comparable across securities and price levels.
    """
    fast_ema = close.ewm(span=fast, adjust=False, min_periods=slow).mean()
    slow_ema = close.ewm(span=slow, adjust=False, min_periods=slow).mean()
    ppo_line = (fast_ema - slow_ema) / slow_ema.replace(0.0, float("nan")) * 100.0
    signal_line = ppo_line.ewm(span=signal, adjust=False, min_periods=signal).mean()
    histogram = ppo_line - signal_line
    return {"ppo": ppo_line, "signal": signal_line, "histogram": histogram}


def rsi(close: pd.Series, period: int = 14) -> pd.Series:
    """Relative Strength Index (Wilder's smoothing).

    RSI > 70 = overbought, RSI < 30 = oversold. Returns a Series aligned to close.
    """
    delta = close.diff()
    gain = delta.clip(lower=0.0)
    loss = -delta.clip(upper=0.0)
    avg_gain = gain.ewm(alpha=1.0 / period, adjust=False, min_periods=period).mean()
    avg_loss = loss.ewm(alpha=1.0 / period, adjust=False, min_periods=period).mean()
    # When avg_loss is 0 (all gains), RSI = 100. When avg_gain is 0 (all losses),
    # RSI = 0. When both are 0 (flat data), RSI = 50 (neutral).
    rs = avg_gain / avg_loss.replace(0.0, float("nan"))
    rsi = 100.0 - (100.0 / (1.0 + rs))
    # All-gain edge case: avg_loss = 0 and avg_gain > 0 -> RSI = 100.
    rsi = rsi.where(avg_loss > 0, 100.0)
    # Flat edge case: both avg_gain and avg_loss are 0 -> RSI = 50 (neutral).
    rsi = rsi.where(~((avg_gain == 0) & (avg_loss == 0)), 50.0)
    return rsi


# ---------------------------------------------------------------------------
# Relative strength vs benchmark
# ---------------------------------------------------------------------------

def relative_strength(stock_close: pd.Series, benchmark_close: pd.Series, period: int = 252) -> float:
    """Mansfield-style relative strength ratio.

    RS = (stock_close / benchmark_close) normalized as a percentage above/below
    its own moving average. Positive = outperforming the benchmark, negative =
    underperforming.

    Uses a simple ratio approach: RS = (stock_return / benchmark_return) - 1
    over the given period, clipped to [-1, +1] range. Returns 0.0 if
    insufficient data.
    """
    if len(stock_close) < 2 or len(benchmark_close) < 2:
        return 0.0

    # Align to the shorter series
    n = min(len(stock_close), len(benchmark_close), period)
    s = stock_close.iloc[-n:]
    b = benchmark_close.iloc[-n:]

    s_ret = (s.iloc[-1] / s.iloc[0] - 1) * 100
    b_ret = (b.iloc[-1] / b.iloc[0] - 1) * 100

    if b_ret == 0:
        return 0.0

    rs = s_ret - b_ret
    # Clip to [-100, +100] and normalize to [-1, +1]
    return max(-100.0, min(100.0, rs)) / 100.0


def beta(stock_close: pd.Series, benchmark_close: pd.Series, period: int = 252) -> float:
    """Regression beta of stock vs benchmark.

    Beta > 1 = more volatile than market, < 1 = less volatile, < 0 = inversely
    correlated. Returns 1.0 if insufficient data.
    """
    if len(stock_close) < 2 or len(benchmark_close) < 2:
        return 1.0

    n = min(len(stock_close), len(benchmark_close), period)
    s_ret = stock_close.iloc[-n:].pct_change().dropna()
    b_ret = benchmark_close.iloc[-n:].pct_change().dropna()

    # Align indices
    min_len = min(len(s_ret), len(b_ret))
    s_ret = s_ret.iloc[-min_len:]
    b_ret = b_ret.iloc[-min_len:]

    if len(s_ret) < 2 or b_ret.std() == 0:
        return 1.0

    cov = s_ret.cov(b_ret)
    var = b_ret.var()
    if var == 0:
        return 1.0
    return round(cov / var, 2)


# ---------------------------------------------------------------------------
# Volume Profile / POC
# ---------------------------------------------------------------------------

def volume_profile(
    df: pd.DataFrame,
    bins: int = 50,
    value_area_pct: float = 0.70,
) -> dict:
    """Build a volume-by-price histogram (volume profile).

    Divides the price range into `bins` equally spaced rows. For each
    row, sums the volume of bars whose high-low range overlaps that row
    (split proportionally). This reveals the price levels where the most
    volume traded — key support/resistance zones.

    Returns a dict with:
      - ``rows``: list of {price_low, price_high, volume, pct} sorted by price descending.
      - ``poc_price``: Point of Control — the price level with the highest volume.
      - ``vah``: Value Area High — upper boundary of the value area.
      - ``val``: Value Area Low — lower boundary of the value area.
      - ``total_volume``: sum of all volume.
      - ``hvn``: list of High Volume Node price levels (above-average rows).
      - ``lvn``: list of Low Volume Node price levels (below-average rows).
    """
    if df.empty or "Volume" not in df.columns or "High" not in df.columns:
        return {
            "rows": [],
            "poc_price": 0.0,
            "vah": 0.0,
            "val": 0.0,
            "total_volume": 0.0,
            "hvn": [],
            "lvn": [],
        }

    price_min = float(df["Low"].min())
    price_max = float(df["High"].max())
    if price_max <= price_min:
        return {
            "rows": [],
            "poc_price": price_max,
            "vah": price_max,
            "val": price_min,
            "total_volume": float(df["Volume"].sum()),
            "hvn": [],
            "lvn": [],
        }

    bin_size = (price_max - price_min) / bins
    row_volumes = [0.0] * bins

    for _, bar in df.iterrows():
        bar_low = float(bar["Low"])
        bar_high = float(bar["High"])
        bar_vol = float(bar["Volume"])
        if bar_vol <= 0 or bar_high <= bar_low:
            continue

        # Which bins does this bar overlap?
        start_bin = int((bar_low - price_min) / bin_size)
        end_bin = int((bar_high - price_min) / bin_size)
        start_bin = max(0, min(bins - 1, start_bin))
        end_bin = max(0, min(bins - 1, end_bin))

        if start_bin == end_bin:
            row_volumes[start_bin] += bar_vol
        else:
            bar_range = bar_high - bar_low
            for b in range(start_bin, end_bin + 1):
                # Fraction of this bar that falls in bin b
                bin_low = price_min + b * bin_size
                bin_high = price_min + (b + 1) * bin_size
                overlap_low = max(bar_low, bin_low)
                overlap_high = min(bar_high, bin_high)
                overlap = overlap_high - overlap_low
                if overlap > 0 and bar_range > 0:
                    row_volumes[b] += bar_vol * (overlap / bar_range)

    total_vol = sum(row_volumes)
    if total_vol <= 0:
        return {
            "rows": [],
            "poc_price": price_max,
            "vah": price_max,
            "val": price_min,
            "total_volume": 0.0,
            "hvn": [],
            "lvn": [],
        }

    # POC = bin with most volume
    poc_bin = max(range(bins), key=lambda b: row_volumes[b])
    poc_price = price_min + (poc_bin + 0.5) * bin_size

    # Value Area: expand from POC until we capture value_area_pct of total volume
    target_vol = total_vol * value_area_pct
    va_vol = row_volumes[poc_bin]
    va_low_bin = poc_bin
    va_high_bin = poc_bin

    while va_vol < target_vol and (va_low_bin > 0 or va_high_bin < bins - 1):
        # Compare the next bin on each side, pick the one with more volume
        below_vol = row_volumes[va_low_bin - 1] if va_low_bin > 0 else -1
        above_vol = row_volumes[va_high_bin + 1] if va_high_bin < bins - 1 else -1

        if above_vol >= below_vol and va_high_bin < bins - 1:
            va_high_bin += 1
            va_vol += row_volumes[va_high_bin]
        elif va_low_bin > 0:
            va_low_bin -= 1
            va_vol += row_volumes[va_low_bin]
        else:
            break

    vah = price_min + (va_high_bin + 1) * bin_size
    val = price_min + va_low_bin * bin_size

    # Build rows (sorted by price descending for display)
    avg_vol = total_vol / bins
    rows = []
    hvn_prices = []
    lvn_prices = []
    for b in range(bins):
        bin_low = price_min + b * bin_size
        bin_high = price_min + (b + 1) * bin_size
        bin_mid = (bin_low + bin_high) / 2
        vol = row_volumes[b]
        pct = vol / total_vol if total_vol > 0 else 0.0
        rows.append({
            "price_low": round(bin_low, 2),
            "price_high": round(bin_high, 2),
            "price_mid": round(bin_mid, 2),
            "volume": round(vol, 0),
            "pct": round(pct, 4),
            "is_poc": b == poc_bin,
            "in_value_area": va_low_bin <= b <= va_high_bin,
        })
        if vol > avg_vol * 1.5:
            hvn_prices.append(round(bin_mid, 2))
        elif vol < avg_vol * 0.3:
            lvn_prices.append(round(bin_mid, 2))

    rows.reverse()  # high prices at top

    return {
        "rows": rows,
        "poc_price": round(poc_price, 2),
        "vah": round(vah, 2),
        "val": round(val, 2),
        "total_volume": round(total_vol, 0),
        "hvn": hvn_prices,
        "lvn": lvn_prices,
    }


# ---------------------------------------------------------------------------
# Murphy's technical analysis indicators (Chapter 9-11):
# Stochastic, MACD, ADX/DMI, OBV, Supertrend, Williams %R, CCI, MFI, Fibonacci
# ---------------------------------------------------------------------------


def stochastic(
    high: pd.Series,
    low: pd.Series,
    close: pd.Series,
    k_period: int = 14,
    d_period: int = 3,
) -> dict[str, pd.Series]:
    """Stochastic Oscillator (Lane).

    %K = 100 * (close - lowest_low) / (highest_high - lowest_low)
    %D = SMA of %K over ``d_period``.

    Murphy uses 14,3 (slow) and 5,3 (fast).  %K > 80 = overbought,
    %K < 20 = oversold.  %K crossing above %D = bullish, below = bearish.
    """
    lowest_low = low.rolling(k_period, min_periods=k_period).min()
    highest_high = high.rolling(k_period, min_periods=k_period).max()
    raw_k = 100.0 * (close - lowest_low) / (highest_high - lowest_low).replace(0.0, float("nan"))
    # Slow %K = SMA of raw %K (3-period smoothing is standard).
    k = raw_k.rolling(d_period, min_periods=d_period).mean()
    d = k.rolling(d_period, min_periods=d_period).mean()
    return {"k": k, "d": d}


def macd(
    close: pd.Series,
    fast: int = 12,
    slow: int = 26,
    signal: int = 9,
) -> dict[str, pd.Series]:
    """MACD — Moving Average Convergence Divergence (dollar-based, Appel).

    MACD line = EMA(fast) - EMA(slow).
    Signal   = EMA(signal) of MACD.
    Histogram = MACD - Signal.

    Murphy treats MACD as the primary momentum/trend indicator: bullish when
    MACD > Signal (histogram > 0), bearish when MACD < Signal.
    """
    ema_fast = close.ewm(span=fast, adjust=False, min_periods=slow).mean()
    ema_slow = close.ewm(span=slow, adjust=False, min_periods=slow).mean()
    macd_line = ema_fast - ema_slow
    signal_line = macd_line.ewm(span=signal, adjust=False, min_periods=signal).mean()
    histogram = macd_line - signal_line
    return {"macd": macd_line, "signal": signal_line, "histogram": histogram}


def adx(df: pd.DataFrame, period: int = 14) -> dict[str, pd.Series]:
    """ADX / DMI (Wilder's Directional Movement Index).

    Murphy (Chapter 11): ADX measures trend *strength*, not direction.
      - ADX > 25  → strong trend (trade trending strategies)
      - ADX < 20  → weak/no trend (range-bound; avoid trend-following)
    +DI > -DI → bullish, -DI > +DI → bearish.
    """
    high = df["High"]
    low = df["Low"]
    close = df["Close"]

    # True Range
    prev_close = close.shift(1)
    tr = pd.concat(
        [(high - low), (high - prev_close).abs(), (low - prev_close).abs()],
        axis=1,
    ).max(axis=1)

    # Directional Movement
    up_move = high - high.shift(1)
    down_move = low.shift(1) - low
    plus_dm = up_move.where((up_move > down_move) & (up_move > 0), 0.0)
    minus_dm = down_move.where((down_move > up_move) & (down_move > 0), 0.0)

    # Wilder's smoothing
    atr_smooth = tr.ewm(alpha=1.0 / period, adjust=False, min_periods=period).mean()
    plus_di = 100.0 * (plus_dm.ewm(alpha=1.0 / period, adjust=False, min_periods=period).mean() / atr_smooth.replace(0.0, float("nan")))
    minus_di = 100.0 * (minus_dm.ewm(alpha=1.0 / period, adjust=False, min_periods=period).mean() / atr_smooth.replace(0.0, float("nan")))

    # DX = |+DI - -DI| / (+DI + -DI) * 100
    dx = 100.0 * (plus_di - minus_di).abs() / (plus_di + minus_di).replace(0.0, float("nan"))
    adx_line = dx.ewm(alpha=1.0 / period, adjust=False, min_periods=period).mean()

    return {"adx": adx_line, "plus_di": plus_di, "minus_di": minus_di}


def obv(close: pd.Series, volume: pd.Series) -> pd.Series:
    """On-Balance Volume (Granville).

    Cumulative volume: +volume on up-closes, -volume on down-closes, 0 on
    unchanged.  Murphy (Chapter 12): OBV should confirm price direction.
    Rising OBV in an uptrend = healthy accumulation.
    """
    direction = close.diff().apply(lambda x: 1 if x > 0 else (-1 if x < 0 else 0))
    return (direction * volume).cumsum()


def supertrend(df: pd.DataFrame, period: int = 10, multiplier: float = 3.0) -> pd.Series:
    """Supertrend indicator (ATR-based trend follower).

    Returns a Series of price levels. When price is above the level the
    trend is 'up' (green), when below it's 'down' (red). The level flips
    when the opposite band is breached.
    """
    high = df["High"]
    low = df["Low"]
    close = df["Close"]
    atr_val = atr(df, period)

    hl2 = (high + low) / 2.0
    upper_basic = hl2 + multiplier * atr_val
    lower_basic = hl2 - multiplier * atr_val

    final_upper = upper_basic.copy()
    final_lower = lower_basic.copy()

    for i in range(1, len(df)):
        # Carry forward: if close[i-1] <= final_upper[i-1], keep min(upper_basic, final_upper[i-1])
        if close.iloc[i - 1] <= final_upper.iloc[i - 1]:
            final_upper.iloc[i] = min(upper_basic.iloc[i], final_upper.iloc[i - 1])
        else:
            final_upper.iloc[i] = upper_basic.iloc[i]

        if close.iloc[i - 1] >= final_lower.iloc[i - 1]:
            final_lower.iloc[i] = max(lower_basic.iloc[i], final_lower.iloc[i - 1])
        else:
            final_lower.iloc[i] = lower_basic.iloc[i]

    # Build the supertrend line
    st = pd.Series(index=df.index, dtype=float)
    # Initialize: first valid ATR → use upper band (assume downtrend start)
    first_valid = atr_val.first_valid_index()
    if first_valid is not None:
        fi = df.index.get_loc(first_valid)
        st.iloc[fi] = final_upper.iloc[fi]
        for i in range(fi + 1, len(df)):
            prev_st = st.iloc[i - 1]
            if pd.isna(prev_st):
                st.iloc[i] = final_upper.iloc[i]
                continue
            # If close > prev_st (was uptrend), use lower band
            if close.iloc[i - 1] > prev_st:
                st.iloc[i] = final_lower.iloc[i]
            else:
                st.iloc[i] = final_upper.iloc[i]

    return st


def williams_r(
    high: pd.Series,
    low: pd.Series,
    close: pd.Series,
    period: int = 14,
) -> pd.Series:
    """Williams %R (Williams).

    %R = -100 * (highest_high - close) / (highest_high - lowest_low).
    Range: -100 (oversold) to 0 (overbought).
    Murphy: %R < -80 = oversold, %R > -20 = overbought.
    """
    highest_high = high.rolling(period, min_periods=period).max()
    lowest_low = low.rolling(period, min_periods=period).min()
    wr = -100.0 * (highest_high - close) / (highest_high - lowest_low).replace(0.0, float("nan"))
    return wr


def cci(
    high: pd.Series,
    low: pd.Series,
    close: pd.Series,
    period: int = 20,
) -> pd.Series:
    """Commodity Channel Index (Lambert).

    CCI = (TP - SMA(TP)) / (0.015 * mean_deviation(TP))
    where TP = (High + Low + Close) / 3.
    Murphy (Chapter 11): CCI > +100 = overbought, CCI < -100 = oversold.
    """
    tp = (high + low + close) / 3.0
    sma_tp = tp.rolling(period, min_periods=period).mean()
    mean_dev = tp.rolling(period, min_periods=period).apply(
        lambda x: (x - x.mean()).abs().mean(), raw=True
    )
    cci_val = (tp - sma_tp) / (0.015 * mean_dev.replace(0.0, float("nan")))
    return cci_val


def mfi(df: pd.DataFrame, period: int = 14) -> pd.Series:
    """Money Flow Index (Quong & Soudack) — volume-weighted RSI.

    Murphy (Chapter 12): MFI is more reliable than RSI alone because it
    incorporates volume. MFI < 20 = oversold, MFI > 80 = overbought.
    """
    tp = (df["High"] + df["Low"] + df["Close"]) / 3.0
    raw_mf = tp * df["Volume"].astype(float)

    positive_mf = raw_mf.where(tp > tp.shift(1), 0.0)
    negative_mf = raw_mf.where(tp < tp.shift(1), 0.0)

    pos_sum = positive_mf.rolling(period, min_periods=period).sum()
    neg_sum = negative_mf.rolling(period, min_periods=period).sum()

    money_flow_ratio = pos_sum / neg_sum.replace(0.0, float("nan"))
    mfi_val = 100.0 - (100.0 / (1.0 + money_flow_ratio))
    # Edge case: if all negative flow is 0, MFI = 100
    mfi_val = mfi_val.where(neg_sum > 0, 100.0)
    return mfi_val


def fibonacci_levels(prev_high: float, prev_low: float) -> dict[str, float]:
    """Fibonacci retracement levels from the previous swing range.

    Murphy (Chapter 13): key retracement levels are 38.2%, 50%, 61.8%.
    Returns a dict with standard ratios as keys and price levels as values.
    Levels are computed as: prev_low + ratio * (prev_high - prev_low).
    """
    diff = prev_high - prev_low
    ratios = [0.0, 0.236, 0.382, 0.5, 0.618, 0.786, 1.0]
    return {str(r): round(prev_low + r * diff, 2) for r in ratios}
