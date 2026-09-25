"""The data-quality rules must catch the defects they are written for."""

from __future__ import annotations

import polars as pl

from barca.data import validate


def events(**overrides: list) -> pl.DataFrame:
    base = {
        "match_id": [1, 1, 1],
        "event_id": ["a", "b", "c"],
        "index": [1, 2, 3],
        "period": [1, 1, 1],
        "timestamp": ["00:00:01.000", "00:00:02.000", "00:00:03.000"],
        "minute": [0, 0, 0],
        "second": [1, 2, 3],
        "type": ["Pass", "Shot", "Carry"],
        "team_id": [1, 1, 1],
        "player_id": [10, 10, 10],
        "x": [60.0, 105.0, 50.0],
        "y": [40.0, 40.0, 40.0],
        "end_x": [70.0, 120.0, 55.0],
        "end_y": [40.0, 40.0, 40.0],
        "outcome": [None, "Goal", None],
        "recipient_id": [11, None, None],
        "shot_xg": [None, 0.3, None],
        "shot_key_pass_id": [None, "a", None],
        "replacement_id": [None, None, None],
        "related_events": [[], [], []],
    }
    base.update(overrides)
    return pl.DataFrame(base)


def run(rule_code: str, ev: pl.DataFrame) -> int:
    rule = next(r for r in validate.RULES if r.code == rule_code)
    return validate.run({"events": ev}, [rule])[0].violations


def test_clean_events_pass() -> None:
    ev = events()
    for code in ("E01", "E02", "E07", "E08", "E09", "E10", "E11", "E18"):
        assert run(code, ev) == 0, code


def test_duplicate_ids_are_caught() -> None:
    assert run("E01", events(event_id=["a", "a", "c"])) == 1


def test_off_pitch_locations_are_caught() -> None:
    assert run("E07", events(x=[125.0, 105.0, 50.0])) == 1


def test_shot_without_xg_is_caught() -> None:
    assert run("E08", events(shot_xg=[None, None, None])) == 1


def test_dangling_key_pass_is_caught() -> None:
    assert run("E18", events(shot_key_pass_id=[None, "zzz", None])) == 1


def test_gate_only_fails_on_errors() -> None:
    warning = validate.Result("X", "t", "d", "warning", 5, 0, False)
    error_ok = validate.Result("Y", "t", "d", "error", 0, 0, True)
    assert validate.gate_passed([warning, error_ok])
    assert not validate.gate_passed([validate.Result("Z", "t", "d", "error", 1, 0, False)])
