from __future__ import annotations

import polars as pl
import pytest

from barca.features import elo


@pytest.mark.parametrize(("gd", "expected"), [(0, 1.0), (1, 1.0), (-2, 1.5), (3, 14 / 8), (5, 2.0)])
def test_goal_multiplier(gd: int, expected: float) -> None:
    assert elo.goal_multiplier(gd) == pytest.approx(expected)


def test_expected_score_is_symmetric_without_home_advantage() -> None:
    assert elo.expected_home(1600, 1500, 0) == pytest.approx(1 - elo.expected_home(1500, 1600, 0))
    assert elo.expected_home(1500, 1500, 0) == pytest.approx(0.5)


def test_rating_points_are_conserved_within_a_season(results: pl.DataFrame) -> None:
    rated = elo.run(results)
    first = rated.filter(pl.col("season_start") == rated["season_start"].min())
    delta = (first["home_elo_post"] - first["home_elo"]) + (
        first["away_elo_post"] - first["away_elo"]
    )
    assert delta.abs().max() < 1e-9


def test_stronger_teams_end_with_higher_ratings(results: pl.DataFrame) -> None:
    long = elo.long_ratings(elo.run(results))
    final = long.group_by("team").agg(pl.col("elo_post").last())
    points = results.with_columns(
        pl.when(pl.col("home_goals") > pl.col("away_goals"))
        .then(3)
        .when(pl.col("home_goals") == pl.col("away_goals"))
        .then(1)
        .otherwise(0)
        .alias("hp"),
        pl.when(pl.col("away_goals") > pl.col("home_goals"))
        .then(3)
        .when(pl.col("home_goals") == pl.col("away_goals"))
        .then(1)
        .otherwise(0)
        .alias("ap"),
    )
    table = (
        pl.concat(
            [
                points.select(pl.col("home").alias("team"), pl.col("hp").alias("pts")),
                points.select(pl.col("away").alias("team"), pl.col("ap").alias("pts")),
            ]
        )
        .group_by("team")
        .agg(pl.col("pts").sum())
    )
    joined = final.join(table, on="team")
    assert joined.select(pl.corr("elo_post", "pts")).item() > 0.7
