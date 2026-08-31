# Comprehensive Trading Strategy Guide
## Scalping, Intraday, ETFs & Mutual Funds (US + India Markets)

> Compiled from established trading literature and methodology.
> Sources: Andrew Aziz, Mark Douglas, John Murphy, Richard Ferri, John Bogle,
> Kathy Lien, Steve Nison, Toni Turner, and NSE/SEBI regulatory frameworks.

---

# PART 1: SCALPING STRATEGIES

Scalping = holding positions seconds to minutes, capturing small repeated moves.
Requires: high liquidity, tight spreads, fast execution, and iron discipline.

## 1.1 VWAP + 9 EMA Pullback (Primary Setup)

**Source:** Andrew Aziz — *How to Day Trade for a Living*

### Chart Setup
- Timeframe: 1-min or 2-min for entries; 5-min for trend context
- Indicators: VWAP (session), 9 EMA, 21 EMA, Volume

### Rules (Long — mirror for Short)
1. Trend filter: Price ABOVE both VWAP and 9 EMA (21 EMA sloping up)
2. Trigger: Price pulls back to touch the 9 EMA
3. Confirmation: Candle closes green (hammer/engulfing) with volume > 20-period avg
4. Entry: On close of confirmation candle
5. Stop: 1-2 ticks below the pullback low
6. Target 1: VWAP / high of day (50% off)
7. Target 2: 1.5x risk measured from entry (exit remaining 50%)
8. Invalidation: Skip first 5 min; skip within 5 min of major news

### Win Rate Expectancy
- Historical win rate: 55-62%
- Average R: +0.3R to +0.4R per trade
- Profit factor: 1.5-1.8

---

## 1.2 Moving Average Ribbon Scalp

**Source:** Kathy Lien — *Day Trading the Currency Market*

### Chart Setup
- Timeframe: 1-min chart
- Indicators: 8 EMA, 21 EMA, 50 EMA (ribbon)

### Rules
1. All MAs stacked bullishly (8 > 21 > 50) = uptrend
2. Price pulls to 8 EMA, bounces
3. Entry on bounce with green candle
4. Stop below 21 EMA
5. Target: next extension (prior swing high) or 1R

### Best For: Trending sessions (first 90 min)

---

## 1.3 Bollinger Band Squeeze Scalp

**Source:** John Bollinger — *Bollinger on Bollinger Bands*

### Chart Setup
- Timeframe: 2-min or 3-min
- Indicators: Bollinger Bands (20, 2), Volume

### Rules
1. Bands contract (squeeze) = low volatility, breakout pending
2. Price closes ABOVE upper band with volume spike
3. Entry on next candle if it holds above the band
4. Stop: middle band (20 SMA)
5. Target: 1.5R or measured move of squeeze height

### Best For: Pre-market / midday compression breakouts

---

## 1.4 PPO (Percentage Price Oscillator) Momentum Scalp

**Source:** TradingView indicator methodology

### Chart Setup
- Timeframe: 1-min
- Indicators: PPO (12, 26, 9)

### Rules
1. PPO above zero = bullish momentum
2. PPO crosses above signal line = entry trigger
3. Confirmation: histogram expanding
4. Stop: swing low below entry
5. Target: 1R or exit when PPO crosses back below signal

### Best For: Momentum continuation scalps

---

# PART 2: INTRADAY STRATEGIES (Beyond Scalping)

## 2.1 Opening Range Breakout (ORB)

**Source:** Toni Turner — *A Beginner's Guide to Day Trading Online*

### Timeframes
| Range | Style | Win Rate |
|------|-------|----------|
| 5 min | Aggressive scalp | 45-50% |
| 15 min | Balanced (most popular) | 50-55% |
| 30 min | Swing day trade | 55-60% |

### Rules (15-min ORB)
1. Mark high + low of first 15 min (9:15-9:30 IST / 9:30-9:45 ET)
2. Wait for breakout close above high (long) or below low (short)
3. Volume must be > average of opening range candles
4. Entry: close of breakout candle OR retest of breakout level
5. Stop: midpoint of opening range (aggressive) or opposite end (conservative)
6. Target 1: 1x opening range height (measured move)
7. Target 2: 2x opening range height
8. Time stop: Cancel if no breakout by 11 AM

### False Breakout Filters
- Volume must confirm (low volume = trap)
- Wait for candle close (wicks that close back inside = fakeout)
- Retest entry is safer (wait for pullback to broken level)
- ADR check: if already moved 80%+ of average daily range, skip

---

## 2.2 VWAP Reversion (Mean Reversion)

### Rules
1. Price extends 2+ standard deviations from VWAP
2. RSI < 30 (oversold, long) or > 70 (overbought, short)
3. Entry: first candle that reverses back toward VWAP
4. Stop: beyond the extension extreme
5. Target: VWAP (mean)

### Best For: Range-bound, choppy sessions (not trend days)

---

## 2.3 Momentum Ignition (Gap & Go)

### Rules
1. Stock gaps up/down > 3% pre-market
2. First 5-min candle holds the gap (doesn't fill)
3. Entry: break of first 5-min high (long) or low (short)
4. Stop: opposite end of first 5-min range
5. Target: 2R or ride until momentum stalls

### Best For: Earnings reactions, news catalysts

---

# PART 3: ETF SELECTION FOR INTRADAY

## 3.1 US Market — Best ETFs for Scalping

| ETF | Tracks | Avg Volume | Spread | Best For |
|-----|--------|-----------|--------|----------|
| SPY | S&P 500 | 70M+ | $0.01 | Primary scalping vehicle |
| QQQ | Nasdaq 100 | 40M+ | $0.01 | High-beta momentum |
| IWM | Russell 2000 | 20M+ | $0.02 | Volatility/range |
| XLF | Financials | 30M+ | $0.02 | Sector rotation |
| XLE | Energy | 15M+ | $0.03 | Commodity correlation |
| SMH | Semiconductors | 8M+ | $0.03 | Trend plays |
| ARKK | Innovation | 30M+ | $0.03 | High volatility |

### Selection Criteria
1. **Average daily volume > 5M shares** (liquidity = tight spreads)
2. **Bid-ask spread < $0.05** (cost of entry/exit)
3. **AUM > $1B** (fund stability)
4. **Options chain available** (for hedging or F&O strategies)
5. **Beta > 1.0** (enough movement to profit after costs)

---

## 3.2 Indian Market — Best ETFs for Intraday

| ETF | Tracks | NSE Symbol | Best For |
|-----|--------|-----------|----------|
| NIFTYBEES | Nifty 50 | NIFTYBEES | Primary index scalping |
| BANKBEES | Nifty Bank | BANKBEES | High volatility |
| JUNIORBEES | Nifty Next 50 | JUNIORBEES | Mid-cap momentum |
| ITBEES | IT Sector | ITBEES | Sector-specific |
| GOLDBEES | Gold | GOLDBEES | Safe-haven plays |
| ICICIB22 | BSE Sensex | ICICIB22 | Alternative index |
| SETFNIF50 | Nifty 50 (SBI) | SETFNIF50 | Alternative liquidity |

### Indian ETF Selection Criteria
1. **Volume > 500K shares/day** (NSE)
2. **Tracking error < 0.5%** (how closely it follows index)
3. **Expense ratio < 0.10%** (lower is better)
4. **Market maker presence** (check bid-ask depth in Level 2)

---

## 3.3 Why ETFs Beat Stocks for Scalping
- Tighter spreads on popular ETFs
- No single-stock gap risk (diversified)
- High liquidity = clean fills
- No surprise earnings within ETF
- Lower PDT rule impact (US): still applies, but fills are cleaner

---

# PART 4: MUTUAL FUNDS

## 4.1 CRITICAL: Mutual Funds Are NOT for Intraday

Mutual funds are priced once daily (NAV). You cannot scalp them.
For intraday, use ETFs (which track the same indices).

---

## 4.2 Mutual Fund Selection (Long-Term Investing)

**Source:** John Bogle — *Common Sense on Mutual Funds*

### Selection Criteria (India)
| Criterion | Target |
|-----------|--------|
| Expense ratio (direct) | < 1.0% equity; < 0.5% index |
| Tracking error (index funds) | < 0.5% |
| AUM | > Rs 500 crore (stability) |
| Fund age | > 5 years (track record) |
| Alpha (vs benchmark) | > 0 for active funds |
| Sharpe ratio | > 1.0 |
| Exit load | 0% (after 1 year for equity) |
| Standard deviation | Lower than category avg |

### Types by Strategy
| Type | Best For | Hold Period |
|------|----------|-------------|
| Index funds | Low-cost core | 7+ years |
| Large-cap | Stability | 5+ years |
| Mid/small-cap | Growth | 7-10 years |
| ELSS | Tax saving (80C) | 3 yr lock-in |
| Balanced/Hybrid | Moderate risk | 3-5 years |
| Debt funds | Stability/income | 1-3 years |

---

## 4.3 Top Mutual Fund Categories (India Reference)

### Index Funds (Lowest Cost)
- Mirae Asset Nifty 50 Index Fund
- HDFC Index Fund - Nifty 50 Plan
- SBI Nifty Index Fund
- UTI Nifty 50 Index Fund

### Large-Cap (Active)
- Mirae Asset Large Cap Fund
- Axis Bluechip Fund
- ICICI Prudential Bluechip Fund

### Mid-Cap
- Mirae Asset Emerging Bluechip
- Axis Midcap Fund
- Kotak Emerging Equity Fund

### ELSS (Tax Saver)
- Mirae Asset Tax Saver Fund
- Axis Long Term Equity Fund
- Kotak Tax Saver Fund

> Note: Fund performance changes. Verify current ratings on
> Value Research, Morningstar India, or MoneyControl before investing.

---

# PART 5: INDIAN F&O STRATEGIES

## 5.1 BankNifty/Nifty Options Scalping

### Strike Selection
- ATM (at-the-money): Highest delta, best for directional scalps
- 1 strike OTM: Cheaper, needs bigger move
- Rule: Stick to ATM or 1 OTM for scalping

### Strategy A: Momentum Scalp (Directional)
1. Breakout above 15-min range with volume
2. Buy ATM Call (bullish) or Put (bearish)
3. Hold: 2-10 minutes
4. Stop: 25-30% of premium
5. Target: 30-50% of premium (1:1.5 min)

### Strategy B: Expiry Day Gamma Scalp (Thursday)
1. Identify max pain strike
2. Tendency: index gravitates to max pain in last 2 hours
3. If 100+ points away at 1 PM:
   - Sell credit spreads (reversion to max pain)
   - Or buy ATM if momentum pushing away (squeeze)

### Strategy C: Theta Decay (Range Day)
1. No breakout by 11 AM = range day
2. Sell ATM straddle (CE + PE same strike)
3. Hedge: Buy OTM CE + PE (iron butterfly)
4. Exit by 1-2 PM or if range breaks

### Indian Options Risk Rules
- Position size: Max 1-2% account risk per trade
- Stop: 25-30% premium for buys; wider for sells
- Never hold overnight options (theta + gap risk)
- Check current lot sizes (SEBI revises these):
  - Nifty: 25 units/lot
  - BankNifty: 15 units/lot
  - (Verify on NSE before trading)

---

# PART 6: MARKET-SPECIFIC REFERENCE

## 6.1 Indian Market

### Trading Hours (IST)
- Pre-open: 9:00-9:15 AM
- Regular: 9:15 AM-3:30 PM
- No retail extended hours

### Structure
- NSE: Dominant for derivatives & ETFs
- BSE: Older exchange, some specific stocks
- SEBI: Regulator

### Taxes
- STT: 0.025% sell-side (intraday equity)
- Intraday gains = speculative business income (slab rates)
- F&O gains = business income
- LTCG (equity, >1yr): 10% above Rs 1.25 lakh (FY 2024-25)
- STCG (equity, <1yr): 20%

### Brokers
- Zerodha (Kite)
- Upstox
- Groww
- Angel One

---

## 6.2 US Market

### Trading Hours (Eastern)
- Pre-market: 4:00-9:30 AM
- Regular: 9:30 AM-4:00 PM
- After-hours: 4:00-8:00 PM

### Key Rules
- PDT Rule: Under $25k = max 3 day trades / 5 business days
- Over $25k = unlimited day trades
- Short-term gains (<1 yr): ordinary income
- Trader Tax Status (TTS) + Section 475 MTM can help active traders

### Brokers
- ThinkorSwim (Charles Schwab)
- Interactive Brokers
- TradeStation

---

# PART 7: TRADING PSYCHOLOGY

**Source:** Mark Douglas — *Trading in the Zone*

## 7.1 Core Principles

1. **Process over outcome** — Judge yourself on rule-following, not P&L
2. **Think in probabilities** — You don't know which trade wins, but edge plays out over 100 trades
3. **Pre-define risk** — No stop = no trade, just hope
4. **No revenge trading** — Walk away after 2 consecutive losses

## 7.2 Hard Rules

| Rule | Value |
|------|-------|
| Daily loss limit | 2% of account (stop trading) |
| Max trades/day | 3-5 (prevents overtrading) |
| Max consecutive losses | 2 (then done for day) |
| Rule compliance target | 95%+ |
| Trade size (learning phase) | Smaller than you think |

## 7.3 The Mental Trap of Scalping
Scalping amplifies emotions. Successful scalpers:
- Trade only first 90 min and last 30 min (highest volume)
- Take scheduled breaks
- Use mechanical rules to remove discretion under stress
- Journal emotions, not just trades

---

# PART 8: BOOK ANALYSES

## 8.1 "How to Day Trade for a Living" — Andrew Aziz
**Focus:** Intraday mechanics, scalping setups, risk management

### Key Strategies Covered
- VWAP pullback (detailed above)
- ABCD pattern
- Reversal strategy (top and bottom picking with confirmation)
- Opening Range Breakout

### Core Contributions
- Clear stop-loss placement rules (below signal candle)
- Position sizing formula: Risk = (Entry - Stop) x Shares
- The "1% Rule": never risk more than 1% of account per trade
- Emphasis on pre-market preparation (gappers, catalysts)

### Strengths
- Actionable, not theoretical
- Specific entry/exit rules
- Includes backtesting framework

### Best For: Beginners to intermediate day traders

---

## 8.2 "Trading in the Zone" — Mark Douglas
**Focus:** Trading psychology, probability thinking

### Core Framework
- **Thinking in probabilities:** Accept that any single trade outcome is uncertain; your edge emerges over a sample size
- **The 5 Fundamental Truths:**
  1. Anything can happen
  2. You don't need to know what happens next to make money
  3. For any set of variables, there's a random distribution of wins/losses
  4. An edge is nothing more than an indication of higher probability
  5. Every moment in the market is unique
- **4 Principles of consistency:**
  1. Consistently review your trading results
  2. Identify your mental patterns
  3. Take responsibility for every trade
  4. Create a belief system that supports consistency

### Core Contribution
- Separates the "trader" from the "trade"
- Eliminates the fear of being wrong (biggest account killer)
- Teaches that losses are a cost of doing business, not personal failure

### Strengths
- Addresses the #1 reason traders fail: psychology
- Practical mental models
- Complements any technical strategy

### Best For: All traders, especially those struggling with discipline

---

## 8.3 "Technical Analysis of the Financial Markets" — John Murphy
**Focus:** Chart reading, indicator mechanics

### Core Content
- Dow Theory foundations
- Chart patterns (head & shoulders, triangles, flags)
- Moving averages (simple vs exponential, crossover systems)
- Oscillators (RSI, MACD, Stochastic)
- Volume analysis
- Intermarket analysis (stocks, bonds, commodities, currencies relationships)

### Core Contribution
- The comprehensive reference for technical analysis
- Explains WHY indicators work (not just how to use them)
- Intermarket relationships for context

### Strengths
- Deep, encyclopedic coverage
- Foundational — everything else builds on this
- Clear explanations with examples

### Best For: Building chart-reading foundation; reference manual

---

## 8.4 "Japanese Candlestick Charting Techniques" — Steve Nison
**Focus:** Candlestick patterns

### Core Patterns
- **Hammer / Hanging Man** (reversal)
- **Engulfing patterns** (bullish/bearish)
- **Doji** (indecision)
- **Morning Star / Evening Star** (3-candle reversal)
- **Harami** (inside bar, momentum pause)

### Core Contribution
- Introduced Japanese candlestick analysis to Western traders
- Context matters: patterns at key levels (VWAP, support/resistance) are stronger
- Candlesticks are confirmation tools, not standalone signals

### Strengths
- Pattern recognition for entry timing
- Works on all timeframes (scalping to swing)
- Combines with any other indicator

### Best For: Entry/exit timing refinement

---

## 8.5 "The ETF Book" — Richard Ferri
**Focus:** ETF mechanics and selection

### Core Content
- ETF structure (creation/redemption mechanism)
- Index methodology (cap-weighted, equal-weighted, fundamentally weighted)
- Tracking error analysis
- Tax efficiency vs mutual funds
- Portfolio construction with ETFs

### Core Contribution
- How to evaluate ETFs beyond just expense ratio
- Understanding underlying index methodology matters
- Liquidity = a function of the underlying securities, not just ETF volume

### Strengths
- Comprehensive ETF education
- Practical selection framework
- Portfolio integration guidance

### Best For: ETF selection and portfolio construction

---

## 8.6 "The Little Book of Common Sense Investing" — John Bogle
**Focus:** Index investing philosophy

### Core Thesis
- Active fund managers underperform index funds over time (after fees)
- Costs are the most reliable predictor of long-term returns
- "Don't look for the needle in the haystack. Just buy the haystack."
- Time in market > timing the market

### Core Contribution
- Founded the index fund industry (Vanguard 500)
- Proved that low cost wins over long horizons
- The original case for buy-and-hold indexing

### Strengths
- Simple, proven philosophy
- Backed by decades of data
- Applicable to Indian index funds (Nifty 50, Sensex)

### Best For: Long-term wealth building (not trading)

---

## 8.7 "Day Trading and Swing Trading the Currency Market" — Kathy Lien
**Focus:** Forex scalping techniques (transferable to other markets)

### Core Strategies
- Moving average ribbon scalps
- Range breakout strategies
- News-driven scalping (economic data releases)
- Currency correlation trading

### Core Contribution
- Probability matrices for news events
- Correlation-based strategies (e.g., gold/USD inverse)
- Session overlap timing (London/New York = highest volume)

### Strengths
- Practical, strategy-focused
- Applicable beyond forex
- News event preparation framework

### Best For: Forex traders; scalpers wanting news event strategies

---

## 8.8 Book Priority Reading Order

| Priority | Book | Why First |
|----------|------|-----------|
| 1 | How to Day Trade for a Living (Aziz) | Mechanics + actionable rules |
| 2 | Trading in the Zone (Douglas) | Psychology — prevents account blowup |
| 3 | Technical Analysis (Murphy) | Chart reading foundation |
| 4 | Japanese Candlesticks (Nison) | Entry timing refinement |
| 5 | The ETF Book (Ferri) | ETF selection |
| 6 | Little Book of Common Sense (Bogle) | Long-term investing balance |
| 7 | Day Trading the Currency Market (Lien) | Advanced strategies |

---

# PART 9: BACKTESTING METHODOLOGY

## 9.1 Define the Setup (Phase 0)
Write exact rules before touching data. If you can't describe it in one paragraph, you can't backtest it.

## 9.2 Data Collection (Phase 1)
### Free Sources
- US: TradingView, Yahoo Finance (CSV), ThinkorSwim paperMoney (replay)
- India: NSE bhavcopy downloads, Chartink, Streak (Zerodha), TradingView

## 9.3 Manual Backtest (Phase 2)
- 50-100 trades minimum (30+ for statistical significance)
- Use bar replay to avoid look-ahead bias
- Log EVERY instance of the setup (no cherry-picking)

## 9.4 Metrics (Phase 3)
| Metric | Formula | Target |
|--------|---------|--------|
| Win rate | Wins / Total | 50-60% |
| Avg win R | Avg R of winners | 1.5-2.0 |
| Avg loss R | Avg R of losers | -1.0 |
| Expectancy | (Win% x Avg Win) - (Loss% x Avg Loss) | +0.1R to +0.3R |
| Profit factor | Gross wins / Gross losses | >1.5 tradable |
| Max drawdown | Peak-to-trough | Survivable |

## 9.5 Bias Checklist (Phase 4)
- [ ] Survivorship bias (tested only existing stocks?)
- [ ] Look-ahead bias (no future info used?)
- [ ] Cherry-picking (logged every instance?)
- [ ] Slippage (subtracted realistic costs?)
- [ ] Commissions (brokerage included?)
- [ ] Liquidity (partial fills accounted for?)
- [ ] Market regime (tested trending AND choppy?)
- [ ] Sample size (50+ trades?)

## 9.6 Walk-Forward Validation (Phase 5)
1. In-sample: Jan-June (optimize rules)
2. Out-of-sample: July-Dec (test same rules)
3. If out-of-sample fails = overfit. Simplify and retest.

## 9.7 Forward Test (Phase 6)
- Paper trade 2-4 weeks before real money
- Catches execution + emotional issues

---

# PART 10: ACTION PLAN

## 10.1 Getting Started
1. Pick ONE setup: VWAP Pullback OR ORB (not both)
2. Pick ONE instrument: SPY, QQQ, NIFTYBEES, or BANKBEES
3. Paper trade 4 weeks (journal every trade)
4. Go live with 1 share/lot for 4 weeks
5. Scale only after: discipline + positive expectancy proven
6. Read: Aziz -> Douglas -> Murphy (in that order)

## 10.2 Daily Routine
- Pre-market (30 min before open):
  - Check overnight futures / global markets
  - Identify catalysts (earnings, news, economic data)
  - Mark key levels on chart (prior day high/low, pre-market high/low)
- Market open (first 90 min):
  - Execute planned setups only
  - Max 3-5 trades
- Midday:
  - Review morning trades
  - No new trades (low volume)
- Close (last 30 min):
  - Optional: one high-probability setup
- Post-market:
  - Journal all trades
  - Update weekly metrics

## 10.3 Risk Management Rules (Non-Negotiable)
1. Max 1% account risk per trade
2. Max 2% daily loss limit (stop trading)
3. Max 2 consecutive losses = done for the day
4. Max 3-5 trades/day
5. Always use a stop loss (no exceptions)
6. Never average down on a losing trade
7. Never trade without a plan

---

# APPENDIX A: JOURNAL TEMPLATE

## Trade Log Columns
```
Date | Time | Instrument | Setup | Direction | Entry | Stop |
Target1 | Target2 | Exit | Shares | Risk | Result | R-Mult |
Violation? | Emotion | Notes
```

## Dashboard Formulas
```
Win Rate:        =COUNTIF(R:R,">0")/COUNT(R:R)
Avg R:           =AVERAGE(R:R)
Total P&L:        =SUM(Result column)
Expectancy:      =(WinRate * AvgWinR) - (LossRate * AvgLossR)
Max Drawdown:    =MIN(cumulative P&L column)
```

## Weekly Review Columns
```
Week Of | Trades | Wins | Losses | Win% | Avg Win R |
Avg Loss R | Expectancy | Total P&L | Largest Win |
Largest Loss | Violations | Time Pattern | Emotional Notes |
What to Fix Next Week
```

---

*Disclaimer: This guide is for educational purposes. Trading involves
substantial risk of loss. Past performance does not guarantee future results.
Always paper trade and validate strategies before risking real capital.*
