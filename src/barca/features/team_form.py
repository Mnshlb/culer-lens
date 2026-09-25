"""Results-based team form for every club (football-data, complete schedule)."""

from __future__ import annotations

import polars as pl

from barca.analytics import results as res
from barca.features import rolling

FORM_COLS = [
    "points",
    "goals",
    "goals_against",
    "goal_diff",
    "shots",
    "shots_against",
    "sot",
    "sot_against",
    "corners",
    "corners_against",
]
WINDOWS = (3, 5, 10)
ORDER = ["date", "fixture_id"]


def team_form(results: pl.DataFrame) -> pl.DataFrame:
    """One row per team per fixture with pre-match form features.

    Windows run across season boundaries (last-5 in August includes May);
    ``matches_played`` tells a model how far into the season it is.
    """
    long = res.long_results(results).with_columns(
        (pl.col("goals") - pl.col("goals_against")).alias("goal_diff")
    )
    long = rolling.add_rolling_means(long, by="team", order=ORDER, cols=FORM_COLS, windows=WINDOWS)
    long = rolling.add_ewm(long, by="team", order=ORDER, cols=["points", "goal_diff"], half_life=6)
    long = rolling.add_rolling_means(
        long,
        by=["team", "is_home"],
        order=ORDER,
        cols=["points", "goal_diff"],
        windows=[5],
        prefix="venue_",
    )
    long = rolling.add_season_to_date(
        long, by="team", season="season", order=ORDER, cols=["points", "goal_diff"]
    )
    long = rolling.add_days_since(long, by="team", date_col="date", name="days_rest")
    long = rolling.add_rolling_means(
        long,
        by=["team", "opponent"],
        order=ORDER,
        cols=["points", "goal_diff"],
        windows=[4],
        prefix="h2h_",
    )
    return long.sort("date", "fixture_id", "is_home", descending=[False, False, True])
