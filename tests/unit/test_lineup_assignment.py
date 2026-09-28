from datetime import date

import polars as pl

from barca.models.lineup import assign, side_of, side_preference


def _history() -> pl.DataFrame:
    rows = []
    for k in range(10):
        d = date(2015, 9, 1 + k)
        rows += [
            {"date": d, "player_id": 1, "position": "Left Back", "family": "FB"},
            {"date": d, "player_id": 2, "position": "Right Back", "family": "FB"},
        ]
    return pl.DataFrame(rows)


def test_side_of_reads_the_position_name():
    assert side_of("Left Wing") == "left"
    assert side_of("Right Center Back") == "right"
    assert side_of("Center Defensive Midfield") == "centre"
    assert side_of(None) == "centre"


def test_full_backs_keep_their_usual_flank():
    history = _history()
    before = date(2015, 10, 1)
    candidates = pl.DataFrame({"player_id": [1, 2], "p_start": [0.9, 0.9]})
    elig = {1: {"FB": 1.0}, 2: {"FB": 1.0}}
    sides = {pid: side_preference(history, pid, before) for pid in (1, 2)}
    # slots listed right first, so an order-driven assignment would swap them
    chosen = dict(assign(candidates, ["Right Back", "Left Back"], elig, sides))
    assert chosen == {1: "Left Back", 2: "Right Back"}


def test_side_preference_does_not_override_selection():
    history = _history()
    candidates = pl.DataFrame({"player_id": [1, 2], "p_start": [0.9, 0.2]})
    elig = {1: {"FB": 1.0}, 2: {"FB": 1.0}}
    sides = {pid: side_preference(history, pid, date(2015, 10, 1)) for pid in (1, 2)}
    # one right-back slot: the far likelier starter gets it despite playing on the left
    assert dict(assign(candidates, ["Right Back"], elig, sides)) == {1: "Right Back"}
