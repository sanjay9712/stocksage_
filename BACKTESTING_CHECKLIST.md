# Backtesting Checklist

## Phase 0: Define the Setup
- [ ] Setup name written down
- [ ] Instrument specified
- [ ] Timeframe specified
- [ ] Trend filter rule written
- [ ] Entry trigger rule written
- [ ] Entry price rule written
- [ ] Stop loss rule written
- [ ] Target 1 rule written
- [ ] Target 2 rule written
- [ ] Invalidation/skip conditions written

## Phase 1: Data Collection
- [ ] 6+ months of historical data sourced
- [ ] Data source verified (TradingView / Yahoo / NSE bhavcopy / Streak)
- [ ] Timeframe matches trading plan
- [ ] Data includes volume

## Phase 2: Manual Backtest
- [ ] Bar replay / chart hidden on right side (no look-ahead)
- [ ] Every instance of setup logged (no cherry-picking)
- [ ] Minimum 50 trades recorded
- [ ] Winning AND losing trades both logged
- [ ] Entry, stop, target, exit captured per trade

## Phase 3: Metrics Calculated
- [ ] Win rate computed
- [ ] Average win (in R) computed
- [ ] Average loss (in R) computed
- [ ] Expectancy computed: (Win% x Avg Win) - (Loss% x Avg Loss)
- [ ] Profit factor computed: Gross wins / Gross losses
- [ ] Max drawdown computed
- [ ] Expectancy >= +0.1R (or setup needs fixing)

## Phase 4: Bias Checklist
- [ ] Survivorship bias checked (delisted stocks included?)
- [ ] Look-ahead bias checked (no future info used?)
- [ ] Cherry-picking checked (every instance logged?)
- [ ] Slippage subtracted (1-2 ticks for ETFs, more for options)
- [ ] Commissions/brokerage included
- [ ] Liquidity / partial fills accounted for
- [ ] Market regimes covered (trending AND choppy days)
- [ ] Sample size >= 50 trades

## Phase 5: Walk-Forward Validation
- [ ] In-sample data tested (e.g., Jan-June)
- [ ] Rules optimized on in-sample only
- [ ] Out-of-sample data tested (e.g., July-Dec)
- [ ] Out-of-sample results hold (expectancy stays positive)
- [ ] If failed: simplified rules and retested

## Phase 6: Forward Test (Paper Trading)
- [ ] Simulator/paper account set up
- [ ] Same setup traded live for 2-4 weeks
- [ ] Every trade journaled
- [ ] Rule compliance >= 95%
- [ ] Execution issues noted
- [ ] Emotional discipline maintained

## Phase 7: Go Live (Minimum Viable)
- [ ] 50+ backtested trades
- [ ] Expectancy >= +0.1R
- [ ] Profit factor > 1.3
- [ ] Max drawdown survivable on account size
- [ ] All 8 bias checks passed
- [ ] 2+ weeks paper trading, rule-compliant
- [ ] Trading plan written and signed
- [ ] Daily loss limit set (2% of account)
- [ ] Max trades/day set (3-5)
- [ ] Starting with minimum position size (1 share / 1 lot)

## Graduation Criteria (Before Scaling)
- [ ] 4 consecutive weeks rule-compliant
- [ ] Positive expectancy confirmed live
- [ ] Journal reviewed weekly
- [ ] Monthly review completed
- [ ] Only then: increase size 1 -> 2 -> 4 -> 8 (doubling, never 10x)
