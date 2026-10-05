"""Unit tests for the pure OI-analysis math in the options-oi endpoint."""
from app.api.options_oi import _compute_max_pain


def _call(strike, oi):
    return {"strike": strike, "openInterest": oi}


def _put(strike, oi):
    return {"strike": strike, "openInterest": oi}


def test_max_pain_single_minimum():
    # Writer pain by settlement:
    #   90  -> put@120 pays (120-90)*50   = 1500
    #   100 -> put@120 pays (120-100)*50  = 1000
    #   110 -> everything OTM/ATM         = 0   <- unique minimum
    #   120 -> call@110 pays (120-110)*100 = 1000
    calls = [_call(110, 100)]
    puts = [_put(90, 100), _put(120, 50)]
    strikes = [90, 100, 110, 120]
    assert _compute_max_pain(calls, puts, strikes) == 110


def test_max_pain_plateau_picks_first_strike():
    # Call wall at 110, put wall at 90: any settlement in [90, 110] has zero
    # writer pain. The plateau's first strike is returned.
    calls = [_call(110, 100)]
    puts = [_put(90, 100)]
    assert _compute_max_pain(calls, puts, [90, 100, 110]) == 90


def test_max_pain_empty_strikes():
    assert _compute_max_pain([], [], []) == 0.0


def test_max_pain_single_strike():
    assert _compute_max_pain([_call(100, 10)], [_put(90, 10)], [100]) == 100
