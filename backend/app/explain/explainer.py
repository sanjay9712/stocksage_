"""Build a structured Explanation from a StrategyResult.

The explanation has four parts:
  1. Plain-English summary
  2. Numeric inputs
  3. Formula trace (entry / SL / target1 / target2)
  4. Verification checklist (user-reproducible on a 5-min chart)
"""
from __future__ import annotations

from app.models import Explanation, FormulaStep
from app.strategies.intraday_breakout import StrategyResult


def build(res: StrategyResult) -> Explanation:
    piv = res.pivot
    inputs = {
        "PreviousDayHigh": _r(res.pdh),
        "PreviousDayLow": _r(res.pdl),
        "ATR_14": _r(res.atr_value),
        "AvgVolume_20": _r(res.avg_volume_20),
        "OR_High": _r(res.or_high) if res.or_high is not None else "n/a",
        "OR_Low": _r(res.or_low) if res.or_low is not None else "n/a",
        "Pivot_P": _r(piv["pivot"]),
        "R1": _r(piv["r1"]),
        "R2": _r(piv["r2"]),
        "S1": _r(piv["s1"]),
        "S2": _r(piv["s2"]),
        "TrendUp": res.trend_up,
    }
    if res.breakout:
        inputs["BreakoutClose"] = _r(res.breakout["close"])
        inputs["BreakoutVolumeRatio"] = _r(res.breakout["volume_ratio"])

    formula_trace: list[FormulaStep] = []
    if res.side is not None:
        formula_trace.append(FormulaStep(
            label="Entry",
            formula="Entry = OR_High (price closing above the opening-range high triggers the long)",
            substituted=f"Entry = {_r(res.or_high)}",
            result=float(res.or_high),
        ))
        formula_trace.append(FormulaStep(
            label="Stop-Loss",
            formula="Stop-Loss = OR_Low (a close back below the opening-range low invalidates the breakout)",
            substituted=f"Stop-Loss = {_r(res.or_low)}",
            result=float(res.or_low),
        ))
        formula_trace.append(FormulaStep(
            label="Target 1",
            formula="Target1 = Entry + 1 x ATR(14)",
            substituted=f"Target1 = {_r(res.or_high)} + 1 x {_r(res.atr_value)} = {_r(res.target1)}",
            result=float(res.target1),
        ))
        formula_trace.append(FormulaStep(
            label="Target 2",
            formula="Target2 = Entry + 2 x ATR(14)",
            substituted=f"Target2 = {_r(res.or_high)} + 2 x {_r(res.atr_value)} = {_r(res.target2)}",
            result=float(res.target2),
        ))

    summary = _summary(res)
    verification = _verification(res)
    caveats = list(res.notes)
    caveats.append("Data is delayed ~15 minutes via Yahoo Finance - levels only, not for tick scalping.")
    caveats.append("Systematic screen, not investment advice.")

    return Explanation(
        summary=summary,
        inputs={k: v for k, v in inputs.items()},
        formula_trace=formula_trace,
        verification=verification,
        caveats=caveats,
    )


def _summary(res: StrategyResult) -> str:
    if res.side is None:
        return f"{res.symbol}: no valid breakout yet today. " + (" ".join(res.notes) if res.notes else "")
    return (
        f"{res.symbol} closed above its 09:15-09:30 opening range high "
        f"(₹{_r(res.or_high)}) on {_r(res.breakout['volume_ratio'])}x average volume. "
        f"Long above ₹{_r(res.entry)} with stop-loss at OR-Low ₹{_r(res.stop_loss)}; "
        f"targets ₹{_r(res.target1)} and ₹{_r(res.target2)} (1x/2x ATR). "
        f"Confidence {_r(res.confidence)}."
    )


def _verification(res: StrategyResult) -> list[str]:
    if res.side is None:
        return [
            f"Open {res.symbol} 5-min chart.",
            "Mark the 09:15-09:30 high/low - no close above OR-High has occurred on required volume yet.",
        ]
    return [
        f"Open {res.symbol} on a 5-minute chart.",
        f"Mark the opening range: 09:15 to 09:30. OR-High = ₹{_r(res.or_high)}, OR-Low = ₹{_r(res.or_low)}.",
        f"Find the first 5-min candle after 09:30 that closed above OR-High (₹{_r(res.or_high)}).",
        f"Confirm that candle's volume >= {settings().volume_ratio_min}x the 20-day average volume ({_r(res.avg_volume_20)}).",
        f"Entry should equal OR-High (₹{_r(res.entry)}); Stop-Loss should equal OR-Low (₹{_r(res.stop_loss)}).",
        f"Targets: ₹{_r(res.target1)} (Entry + 1x ATR) and ₹{_r(res.target2)} (Entry + 2x ATR).",
    ]


def _r(x) -> str:
    """Format a number to 2 decimals; pass through strings unchanged."""
    if isinstance(x, str):
        return x
    if x is None:
        return "n/a"
    return f"{float(x):.2f}"


def settings():
    # Late import to keep the module importable in tests without config side effects.
    from app.config import settings as _s
    return _s
