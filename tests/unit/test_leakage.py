"""No feature for match t may depend on match t or anything after it.

    Features_t = f(M_1, ..., M_{t-1})

Each test scrambles every outcome from a cutoff date onwards and checks that
features of matches *on or before* the cutoff are unchanged. Matches on the
cutoff date itself are the sharp edge: their own result is scrambled, so any
feature that looked at the current match would move.
"""

from __future__ import annotations

from datetime import date

import polars as pl
import pytest
from polars.testing import assert_frame_equal

from barca.features import elo, rolling, tables, team_form
from tests.conftest import scramble_from


def _cutoffs(results: pl.DataFrame) -> list[date]:
    dates = results["date"].unique().sort()
    return [dates[len(dates) // 4], dates[len(dates) // 2], dates[-3]]


def test_rolling_mean_ignores_current_and_future_rows() -> None:
    frame = pl.DataFrame({"team": ["A"] * 6, "t": range(6), "x": [1.0, 2.0, 3.0, 4.0, 5.0, 6.0]})
    base = rolling.add_rolling_means(frame, by="team", order=["t"], cols=["x"], windows=[3])
    perturbed = rolling.add_rolling_means(
        frame.with_columns(pl.when(pl.col("t") >= 3).then(999.0).otherwise(pl.col("x")).alias("x")),
        by="team", order=["t"], cols=["x"], windows=[3],
    )
    # rows 0..3 only see rows before them, which are unchanged
    assert base["x_3"][:4].to_list() == perturbed["x_3"][:4].to_list()
    assert base["x_3"].to_list()[:4] == [None, 1.0, 1.5, 2.0]
    # row 4 sees the perturbed row 3
    assert perturbed["x_3"][4] != base["x_3"][4]


def test_season_to_date_excludes_current_match() -> None:
    frame = pl.DataFrame({"team": ["A"] * 4, "season": ["s"] * 4, "t": range(4), "p": [3, 0, 1, 3]})
    out = rolling.add_season_to_date(frame, by="team", season="season", order=["t"], cols=["p"])
    assert out["p_std"].to_list() == [None, 3.0, 1.5, 4 / 3]
    assert out["matches_played"].to_list() == [0, 1, 2, 3]


@pytest.mark.parametrize("which", [0, 1, 2])
def test_team_form_is_future_invariant(results: pl.DataFrame, which: int) -> None:
    cutoff = _cutoffs(results)[which]
    base = team_form.team_form(results)
    other = team_form.team_form(scramble_from(results, cutoff))
    cols = ["fixture_id", "team"] + [c for c in tables.FORM_FEATURES + tables.H2H_FEATURES if c in base.columns]
    past = pl.col("date") <= cutoff
    assert_frame_equal(base.filter(past).select(cols).sort("fixture_id", "team"),
                       other.filter(past).select(cols).sort("fixture_id", "team"))


@pytest.mark.parametrize("which", [0, 1, 2])
def test_elo_pre_match_ratings_are_future_invariant(results: pl.DataFrame, which: int) -> None:
    cutoff = _cutoffs(results)[which]
    base = elo.run(results)
    other = elo.run(scramble_from(results, cutoff))
    cols = ["date", "home", "away", "home_elo", "away_elo", "home_expected"]
    past = pl.col("date") <= cutoff
    assert_frame_equal(base.filter(past).select(cols), other.filter(past).select(cols))


def test_elo_updates_after_the_match(results: pl.DataFrame) -> None:
    rated = elo.run(results)
    first = rated.row(0, named=True)
    # the first fixture's post-match rating differs from its pre-match rating unless it was a perfect expectation
    assert first["home_elo_post"] != first["home_elo"]
    later = rated.filter(pl.col("home") == first["home"]).row(1, named=True)
    assert later["home_elo"] != first["home_elo"]


def test_feature_lists_contain_no_targets_or_market_columns() -> None:
    banned = {"result", "home_goals", "away_goals", "barca_goals", "opp_goals"}
    for features in (tables.league_feature_list(), tables.barca_feature_list()):
        assert not banned & set(features)
        assert not [f for f in features if f.startswith("mkt_") or "_post" in f]
