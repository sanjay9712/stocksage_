"""Response-edge JSON safety: NaN/Inf must never reach the wire as bare tokens.

json.dumps emits ``NaN``/``Infinity`` by default; those are invalid JSON and
make the frontend's JSON.parse() throw. yfinance can surface NaN cells
(partial bars, missing fundamentals), so responses are sanitized.
"""
import json

from app.main import SafeJSONResponse, _sanitize_json


def test_sanitize_replaces_non_finite():
    out = _sanitize_json({"a": float("nan"), "b": [float("inf"), 1], "c": "x"})
    assert out == {"a": None, "b": [None, 1], "c": "x"}


def test_sanitize_leaves_finite_values_alone():
    out = _sanitize_json({"a": 2.5, "b": [0, -1, 1e308], "c": None})
    assert out == {"a": 2.5, "b": [0, -1, 1e308], "c": None}


def test_render_produces_valid_json():
    resp = SafeJSONResponse({"x": float("nan"), "y": 2.5})
    assert json.loads(resp.body) == {"x": None, "y": 2.5}
