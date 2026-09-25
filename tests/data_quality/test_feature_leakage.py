"""Full-pipeline leakage check on the real data.

Scramble every result from a cutoff date onwards, rebuild the fixture table,
and require that every feature of every fixture on or before the cutoff is
identical. This covers form, venue form, head-to-head, season-to-date, rest
days, Elo and the relative features together.
"""

from __future__ import annotations

from datetime import date

import polars as pl
import pytest
from polars.testing import assert_frame_equal

from barca.data import store
from barca.features import elo, event_form, tables, team_form
from tests.conftest import scramble_from


def _fixtures(results: pl.DataFrame) -> pl.DataFrame:
    form = team_form.team_form(results)
    rated = elo.run(results)
    empty_events = pl.DataFrame(
        schema={
            "fixture_id": pl.UInt32,
            "is_home": pl.Boolean,
            "match_id": pl.Int64,
            "ev_xg_5": pl.Float64,
        }
    )
    return tables.fixture_table(results, form, rated, empty_events)


@pytest.mark.parametrize("cutoff", [date(2008, 1, 13), date(2015, 11, 21), date(2020, 7, 1)])
def test_fixture_features_do_not_see_the_future(cutoff: date) -> None:
    results = store.results()
    base = _fixtures(results)
    other = _fixtures(scramble_from(results, cutoff))
    features = tables.league_feature_list()
    past = pl.col("date") <= cutoff
    assert base.filter(pl.col("date") == cutoff).height > 0 or cutoff == date(2020, 7, 1)
    assert_frame_equal(
        base.filter(past).select("fixture_id", *features),
        other.filter(past).select("fixture_id", *features),
    )


def test_event_form_uses_only_earlier_matches() -> None:
    tms = store.features("team_match")
    form = store.features("team_form")
    base = event_form.event_form(tms, form)
    cutoff = date(2016, 2, 1)
    scrambled = tms.with_columns(
        pl.when(pl.col("date") >= cutoff)
        .then(pl.col("xg") * 10)
        .otherwise(pl.col("xg"))
        .alias("xg")
    )
    other = event_form.event_form(scrambled, form)
    cols = ["fixture_id", "team", "ev_xg_3", "ev_xg_5", "ev_xg_10"]
    past = pl.col("date") <= cutoff
    assert_frame_equal(
        base.filter(past).select(cols).sort("fixture_id", "team"),
        other.filter(past).select(cols).sort("fixture_id", "team"),
    )
