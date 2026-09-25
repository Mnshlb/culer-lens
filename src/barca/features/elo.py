"""Elo team-strength ratings for every La Liga club, 1995/96 onwards.

Each club carries a rating that moves after every league match:

    E_home = 1 / (1 + 10 ** ((R_away - R_home - HFA) / 400))
    R_home' = R_home + K * G * (S_home - E_home)       (R_away moves by the opposite amount)

with S = 1 / 0.5 / 0 for a win / draw / loss and G a goal-difference
multiplier (1, 1.5, (11 + |gd|) / 8), as in the World Football Elo ratings.
Between seasons every rating is pulled part of the way back to the league
mean, and promoted clubs start at the average rating of the clubs they
replaced.

Ratings stored for a fixture are always the *pre-match* values, so they can
be used as features without leakage. Parameters are tuned on seasons that
end before the model backtest window begins (see ``tune``).
"""

from __future__ import annotations

import itertools
from dataclasses import asdict, dataclass

import numpy as np
import polars as pl

TUNING_SEASONS = (1996, 2007)  # season start years used to choose K / HFA / regression


@dataclass(frozen=True)
class EloParams:
    # tuned on 1996/97-2007/08 (see ``tune`` and notebook 09)
    k: float = 8.0
    home_advantage: float = 80.0
    regress: float = 0.1
    initial: float = 1500.0


def goal_multiplier(goal_diff: int) -> float:
    gd = abs(goal_diff)
    if gd <= 1:
        return 1.0
    if gd == 2:
        return 1.5
    return (11 + gd) / 8


def expected_home(r_home: float, r_away: float, home_advantage: float) -> float:
    return 1.0 / (1.0 + 10 ** ((r_away - r_home - home_advantage) / 400))


def run(results: pl.DataFrame, params: EloParams | None = None) -> pl.DataFrame:
    """Walk through every fixture in date order and record pre/post ratings.

    ``results`` is the normalised football-data table (one row per fixture).
    """
    p = params or EloParams()
    fixtures = results.select("season", "season_start", "date", "home", "away", "home_goals", "away_goals").sort(
        "season_start", "date", "home"
    )
    ratings: dict[str, float] = {}
    prev_teams: set[str] = set()
    out: dict[str, list] = {k: [] for k in ("home_elo", "away_elo", "home_expected", "home_elo_post", "away_elo_post")}

    for (_,), season in fixtures.group_by(["season_start"], maintain_order=True):
        teams = set(season["home"]) | set(season["away"])
        if prev_teams:
            mean = float(np.mean([ratings[t] for t in prev_teams]))
            for t in list(ratings):
                ratings[t] = mean + (ratings[t] - mean) * (1 - p.regress)
            relegated = prev_teams - teams
            base = float(np.mean([ratings[t] for t in relegated])) if relegated else mean
            for t in teams - prev_teams:
                ratings[t] = base
        else:
            for t in teams:
                ratings[t] = p.initial
        for h, a, hg, ag in season.select("home", "away", "home_goals", "away_goals").iter_rows():
            rh, ra = ratings[h], ratings[a]
            e = expected_home(rh, ra, p.home_advantage)
            s = 1.0 if hg > ag else 0.5 if hg == ag else 0.0
            delta = p.k * goal_multiplier(hg - ag) * (s - e)
            ratings[h], ratings[a] = rh + delta, ra - delta
            out["home_elo"].append(rh)
            out["away_elo"].append(ra)
            out["home_expected"].append(e)
            out["home_elo_post"].append(rh + delta)
            out["away_elo_post"].append(ra - delta)
        prev_teams = teams

    return fixtures.with_columns(
        *[pl.Series(k, v, dtype=pl.Float64) for k, v in out.items()]
    ).with_columns((pl.col("home_elo") - pl.col("away_elo")).alias("elo_diff"))


def expected_score_brier(rated: pl.DataFrame, seasons: tuple[int, int]) -> float:
    """Squared error between Elo's expected score and the actual score (1/0.5/0)."""
    frame = rated.filter(pl.col("season_start").is_between(*seasons)).with_columns(
        pl.when(pl.col("home_goals") > pl.col("away_goals")).then(1.0)
        .when(pl.col("home_goals") == pl.col("away_goals")).then(0.5).otherwise(0.0).alias("s")
    )
    return float(((frame["s"] - frame["home_expected"]) ** 2).mean())


def tune(
    results: pl.DataFrame,
    seasons: tuple[int, int] = TUNING_SEASONS,
    ks: tuple[float, ...] = (4, 6, 8, 10, 12, 15, 20, 30),
    hfas: tuple[float, ...] = (50, 60, 70, 80, 90, 100),
    regress: tuple[float, ...] = (0.0, 0.1, 0.2, 0.3, 0.5),
) -> tuple[EloParams, pl.DataFrame]:
    """Grid search on seasons before the backtest window; returns the best params and the grid."""
    rows = []
    for k, h, r in itertools.product(ks, hfas, regress):
        params = EloParams(k=k, home_advantage=h, regress=r)
        rows.append({**asdict(params), "brier": expected_score_brier(run(results, params), seasons)})
    grid = pl.DataFrame(rows).sort("brier")
    best = grid.row(0, named=True)
    return EloParams(k=best["k"], home_advantage=best["home_advantage"], regress=best["regress"]), grid


def long_ratings(rated: pl.DataFrame) -> pl.DataFrame:
    """One row per team per fixture with the team's pre-match rating and the opponent's."""
    home = rated.select(
        "season", "season_start", "date", pl.col("home").alias("team"), pl.col("away").alias("opponent"),
        pl.lit(True).alias("is_home"), pl.col("home_elo").alias("elo"), pl.col("away_elo").alias("opp_elo"),
        pl.col("home_elo_post").alias("elo_post"),
    )
    away = rated.select(
        "season", "season_start", "date", pl.col("away").alias("team"), pl.col("home").alias("opponent"),
        pl.lit(False).alias("is_home"), pl.col("away_elo").alias("elo"), pl.col("home_elo").alias("opp_elo"),
        pl.col("away_elo_post").alias("elo_post"),
    )
    return pl.concat([home, away]).sort("date", "team")
