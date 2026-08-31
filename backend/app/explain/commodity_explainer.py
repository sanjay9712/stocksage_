"""Explainer for commodity breakout picks (mirrors the stock explainer style)."""
from __future__ import annotations

from app.models import Explanation, FormulaStep
from app.strategies.commodity_breakout import CommodityResult


def build(res: CommodityResult) -> Explanation:
    inputs = {
        "PreviousDayHigh": _r(res.pdh),
        "PreviousDayLow": _r(res.pdl),
        "ATR": _r(res.atr_value),
        "AvgVolume_20": _r(res.avg_volume_20),
    }
    formula_trace: list[FormulaStep] = []
    if res.side is not None:
        formula_trace.append(FormulaStep(
            label="Entry", formula="Entry = Previous-Day High (break level)",
            substituted=f"Entry = {_r(res.pdh)}", result=float(res.pdh),
        ))
        formula_trace.append(FormulaStep(
            label="Stop-Loss", formula="Stop-Loss = Previous-Day Low",
            substituted=f"Stop-Loss = {_r(res.pdl)}", result=float(res.pdl),
        ))
        formula_trace.append(FormulaStep(
            label="Target 1", formula="Target1 = Entry + 1 x ATR",
            substituted=f"Target1 = {_r(res.entry)} + 1 x {_r(res.atr_value)} = {_r(res.target1)}",
            result=float(res.target1),
        ))
        formula_trace.append(FormulaStep(
            label="Target 2", formula="Target2 = Entry + 2 x ATR",
            substituted=f"Target2 = {_r(res.entry)} + 2 x {_r(res.atr_value)} = {_r(res.target2)}",
            result=float(res.target2),
        ))

    summary = (
        f"{res.name}: long above previous-day high ₹{_r(res.pdh)} with stop at "
        f"previous-day low ₹{_r(res.pdl)}; targets ₹{_r(res.target1)} and ₹{_r(res.target2)}."
        if res.side else f"{res.name}: no breakout above previous-day high today."
    )
    verification = [
        f"Open {res.symbol} (yfinance ticker) daily chart.",
        f"Mark previous session high ({_r(res.pdh)}) and low ({_r(res.pdl)}).",
        "Confirm today's intraday high exceeded the previous-day high on above-average volume.",
        f"Entry should equal PDH (₹{_r(res.entry)}); Stop-Loss should equal PDL (₹{_r(res.stop_loss)}).",
    ] if res.side else ["No breakout to verify today."]
    return Explanation(
        summary=summary, inputs=inputs, formula_trace=formula_trace,
        verification=verification, caveats=res.notes,
    )


def _r(x) -> str:
    if isinstance(x, str):
        return x
    if x is None:
        return "n/a"
    return f"{float(x):.2f}"
