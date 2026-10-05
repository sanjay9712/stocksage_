"""Regression: repeated intraday scans must not corrupt pick storage.

Original bug: _persist_picks used a bulk ``query().delete()``, which bypasses
the ORM ``cascade="all, delete-orphan"`` — and with SQLite's foreign_keys
pragma OFF (the default) the child PickExplanation rows were orphaned.
SQLite reuses deleted rowids, so the second scan of the day crashed with
"UNIQUE constraint failed: pick_explanations.pick_id".
"""
from datetime import date

from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

import app.screener.runner as runner
from app.db import Base
from app.models import Explanation, Pick


def _pick(day: date, symbol: str) -> Pick:
    return Pick(
        date=day,
        symbol=symbol,
        side="long",
        entry=100.0,
        stop_loss=98.0,
        target1=103.0,
        target2=106.0,
        confidence=0.6,
        last_price=101.0,
        explanation=Explanation(
            summary="test pick", inputs={}, formula_trace=[], verification=[]
        ),
    )


def test_repeated_scan_same_symbol_no_unique_collision(tmp_path, monkeypatch):
    engine = create_engine(
        f"sqlite:///{tmp_path / 'picks-test.db'}",
        connect_args={"check_same_thread": False},
    )
    Base.metadata.create_all(engine)
    monkeypatch.setattr(
        runner,
        "SessionLocal",
        sessionmaker(bind=engine, autoflush=False, autocommit=False),
    )

    day = date(2026, 10, 5)
    # Three intraday scans on the same day — each previously crashed on
    # the second run.
    runner._persist_picks([_pick(day, "RELIANCE"), _pick(day, "TCS")])
    runner._persist_picks([_pick(day, "RELIANCE"), _pick(day, "INFY")])
    runner._persist_picks([_pick(day, "RELIANCE")])

    with engine.connect() as c:
        counts = dict(
            c.execute(text("SELECT symbol, COUNT(*) FROM picks GROUP BY symbol")).fetchall()
        )
        orphans = c.execute(
            text(
                "SELECT COUNT(*) FROM pick_explanations "
                "WHERE pick_id NOT IN (SELECT id FROM picks)"
            )
        ).scalar()

    # One row per symbol — rescans replace, never duplicate.
    assert counts == {"RELIANCE": 1, "TCS": 1, "INFY": 1}
    # No orphaned explanation rows (the root of the UNIQUE collision).
    assert orphans == 0
