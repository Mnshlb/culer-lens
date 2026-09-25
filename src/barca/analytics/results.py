"""League results in long format (one row per team per match)."""

from __future__ import annotations

import polars as pl

_PAIRS = {
    "goals": ("home_goals", "away_goals"),
    "goals_ht": ("home_goals_ht", "away_goals_ht"),
    "shots": ("home_shots", "away_shots"),
    "sot": ("home_sot", "away_sot"),
    "corners": ("home_corners", "away_corners"),
    "fouls": ("home_fouls", "away_fouls"),
    "yellow": ("home_yellow", "away_yellow"),
    "red": ("home_red", "away_red"),
}


def long_results(results: pl.DataFrame) -> pl.DataFrame:
    """Turn football-data results (one row per match) into team-match rows.

    Each row carries the team's own figures and the opponent's (``*_against``),
    the venue and the result from the team's point of view.
    """
    base = results.with_row_index("fixture_id")
    sides = []
    for is_home in (True, False):
        team, opp = ("home", "away") if is_home else ("away", "home")
        own = 0 if is_home else 1
        cols = [
            pl.col("fixture_id"),
            pl.col("season"),
            pl.col("season_start"),
            pl.col("date"),
            pl.col(team).alias("team"),
            pl.col(opp).alias("opponent"),
            pl.lit(is_home).alias("is_home"),
        ]
        for name, pair in _PAIRS.items():
            cols.append(pl.col(pair[own]).alias(name))
            cols.append(pl.col(pair[1 - own]).alias(f"{name}_against"))
        sides.append(base.select(cols))
    out = pl.concat(sides).with_columns(
        pl.when(pl.col("goals") > pl.col("goals_against"))
        .then(pl.lit("W"))
        .when(pl.col("goals") == pl.col("goals_against"))
        .then(pl.lit("D"))
        .otherwise(pl.lit("L"))
        .alias("result"),
    )
    return out.with_columns(
        pl.col("result")
        .replace_strict({"W": 3, "D": 1, "L": 0}, return_dtype=pl.Int8)
        .alias("points")
    ).sort("date", "fixture_id", "is_home", descending=[False, False, True])
