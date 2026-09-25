from __future__ import annotations

from datetime import date, timedelta

import numpy as np
import polars as pl
import pytest


def _double_round_robin(
    teams: list[str], rng: np.random.Generator
) -> list[tuple[str | None, str | None]]:
    """Circle-method schedule: every team plays once per round; (None, None) marks a new round."""
    order = list(teams)
    rng.shuffle(order)
    n = len(order)
    rounds = []
    for r in range(n - 1):
        pairs = [(order[i], order[n - 1 - i]) for i in range(n // 2)]
        rounds.append([(a, b) if r % 2 == 0 else (b, a) for a, b in pairs])
        order = [order[0], order[-1], *order[1:-1]]
    schedule: list[tuple[str | None, str | None]] = []
    for rnd in rounds + [[(b, a) for a, b in rnd] for rnd in rounds]:
        schedule.append((None, None))
        schedule.extend(rnd)
    return schedule


def make_results(n_teams: int = 6, seasons: int = 3, seed: int = 0) -> pl.DataFrame:
    """A synthetic league in the shape of the normalised football-data table.

    Double round robin each season, one round per week, team strength drawn
    once so that results have structure for the rating code to find.
    """
    rng = np.random.default_rng(seed)
    teams = [f"Team {chr(65 + i)}" for i in range(n_teams)]
    strength = dict(zip(teams, rng.normal(0, 0.5, n_teams), strict=True))
    rows = []
    for s in range(seasons):
        start = 2000 + s
        day = date(start, 8, 20)
        for h, a in _double_round_robin(teams, rng):
            if h is None:  # new round
                day += timedelta(days=7)
                continue
            hg = int(rng.poisson(np.exp(0.3 + strength[h] - strength[a])))
            ag = int(rng.poisson(np.exp(0.0 + strength[a] - strength[h])))
            hs, as_ = int(rng.integers(5, 20)), int(rng.integers(3, 16))
            rows.append(
                {
                    "season": f"{start}/{start + 1}",
                    "season_start": start,
                    "date": day,
                    "home": h,
                    "away": a,
                    "home_goals": hg,
                    "away_goals": ag,
                    "home_goals_ht": min(hg, int(rng.integers(0, 3))),
                    "away_goals_ht": min(ag, int(rng.integers(0, 2))),
                    "home_shots": hs,
                    "away_shots": as_,
                    "home_sot": int(rng.integers(0, hs + 1)),
                    "away_sot": int(rng.integers(0, as_ + 1)),
                    "home_corners": int(rng.integers(0, 10)),
                    "away_corners": int(rng.integers(0, 8)),
                    "home_fouls": 12,
                    "away_fouls": 13,
                    "home_yellow": 2,
                    "away_yellow": 2,
                    "home_red": 0,
                    "away_red": 0,
                    "odds_b365_h": 2.1,
                    "odds_b365_d": 3.3,
                    "odds_b365_a": 3.6,
                    "odds_psc_h": 2.2,
                    "odds_psc_d": 3.4,
                    "odds_psc_a": 3.7,
                    "odds_avg_h": 2.15,
                    "odds_avg_d": 3.35,
                    "odds_avg_a": 3.65,
                }
            )
    return (
        pl.DataFrame(rows)
        .with_columns(
            pl.col("season_start").cast(pl.Int16),
            *[
                pl.col(c).cast(pl.Int16)
                for c in (
                    "home_goals",
                    "away_goals",
                    "home_goals_ht",
                    "away_goals_ht",
                    "home_shots",
                    "away_shots",
                    "home_sot",
                    "away_sot",
                    "home_corners",
                    "away_corners",
                )
            ],
        )
        .sort("date", "home")
    )


def scramble_from(results: pl.DataFrame, cutoff: date, seed: int = 1) -> pl.DataFrame:
    """Replace every outcome on or after ``cutoff`` with random values."""
    rng = np.random.default_rng(seed)
    n = results.height
    future = pl.col("date") >= cutoff
    return results.with_columns(
        pl.when(future)
        .then(pl.Series(rng.integers(0, 7, n)).cast(pl.Int16))
        .otherwise(pl.col("home_goals"))
        .alias("home_goals"),
        pl.when(future)
        .then(pl.Series(rng.integers(0, 7, n)).cast(pl.Int16))
        .otherwise(pl.col("away_goals"))
        .alias("away_goals"),
        pl.when(future)
        .then(pl.Series(rng.integers(0, 30, n)).cast(pl.Int16))
        .otherwise(pl.col("home_shots"))
        .alias("home_shots"),
        pl.when(future)
        .then(pl.Series(rng.integers(0, 5, n)).cast(pl.Int16))
        .otherwise(pl.col("home_sot"))
        .alias("home_sot"),
    )


@pytest.fixture
def results() -> pl.DataFrame:
    return make_results()
