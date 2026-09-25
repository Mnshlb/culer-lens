"""Metric definitions on hand-built events (StatsBomb frame: attacking towards x = 120)."""

from __future__ import annotations

import polars as pl
import pytest

from barca.analytics import definitions as D


def ev(**kw: object) -> pl.DataFrame:
    base = {
        "type": "Pass",
        "subtype": None,
        "outcome": None,
        "x": 60.0,
        "y": 40.0,
        "end_x": 75.0,
        "end_y": 40.0,
        "pass_cross": None,
        "pass_through_ball": None,
        "pass_shot_assist": None,
        "pass_goal_assist": None,
        "pass_switch": None,
        "pass_length": 15.0,
        "shot_xg": None,
        "play_pattern": "Regular Play",
        "counterpress": None,
        "recovery_failure": None,
        "aerial_won": None,
    }
    base.update(kw)
    return pl.DataFrame([base])


def check(frame: pl.DataFrame, expr: pl.Expr) -> bool:
    return bool(frame.select(expr).item())


@pytest.mark.parametrize(
    ("kw", "expected"),
    [
        ({}, True),  # 15 yards forward from the middle third
        ({"end_x": 65.0}, False),  # only 5 yards
        ({"outcome": "Incomplete"}, False),  # must be completed
        ({"x": 30.0, "end_x": 50.0}, False),  # starts in the defending 40%
        ({"x": 100.0, "end_x": 105.0, "y": 10.0, "end_y": 40.0}, True),  # short pass into the box
        ({"subtype": "Corner", "x": 119.0, "end_x": 110.0}, False),  # set pieces excluded
    ],
)
def test_progressive_pass(kw: dict, expected: bool) -> None:
    assert check(ev(**kw), D.PROGRESSIVE_PASS) is expected


def test_pass_complete_means_empty_outcome() -> None:
    assert check(ev(), D.PASS_COMPLETE)
    assert not check(ev(outcome="Out"), D.PASS_COMPLETE)


def test_box_geometry() -> None:
    frame = pl.DataFrame({"x": [101.9, 102.0, 110.0, 110.0], "y": [40.0, 40.0, 17.9, 62.0]})
    assert frame.select(D.in_box(pl.col("x"), pl.col("y"))).to_series().to_list() == [
        False,
        True,
        False,
        True,
    ]


@pytest.mark.parametrize(
    ("outcome", "on_target"),
    [
        ("Goal", True),
        ("Saved", True),
        ("Saved to Post", True),
        ("Off T", False),
        ("Blocked", False),
        ("Post", False),
    ],
)
def test_shot_on_target(outcome: str, on_target: bool) -> None:
    assert (
        check(ev(type="Shot", subtype="Open Play", outcome=outcome, shot_xg=0.1), D.SHOT_ON_TARGET)
        is on_target
    )


def test_tackles_are_duels_with_subtype_tackle() -> None:
    assert check(ev(type="Duel", subtype="Tackle", outcome="Won"), D.TACKLE_WON)
    assert not check(ev(type="Duel", subtype="Aerial Lost"), D.TACKLE)


def test_penalties_are_not_open_play_or_big_chances() -> None:
    pen = ev(type="Shot", subtype="Penalty", outcome="Goal", shot_xg=0.78, x=108.0)
    assert not check(pen, D.NON_PENALTY_SHOT)
    assert not check(pen, D.BIG_CHANCE)
