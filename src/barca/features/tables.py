"""Model-ready tables: one row per fixture (league-wide) and one per Barcelona match.

Feature groups (see docs/feature-engineering.md for the catalogue):

* ``form``    rolling results-based form per side (football-data, every club)
* ``elo``     pre-match Elo ratings
* ``relative`` sign-consistent differences between the two sides (D-014)
* ``event``   StatsBomb rolling form (Barcelona every season; all clubs 2015/16)

Market probabilities from bookmaker odds are attached as ``mkt_*`` columns for
benchmarking only. They are never listed as features.
"""

from __future__ import annotations

import polars as pl

from barca.features.event_form import EVENT_COLS
from barca.features.event_form import WINDOWS as EVENT_WINDOWS
from barca.features.team_form import FORM_COLS, WINDOWS

FORM_FEATURES = [f"{c}_{w}" for c in FORM_COLS for w in WINDOWS] + [
    "points_ewm", "goal_diff_ewm", "venue_points_5", "venue_goal_diff_5", "matches_played",
    "points_std", "goal_diff_std", "days_rest",
]
H2H_FEATURES = ["h2h_points_4", "h2h_goal_diff_4"]
EVENT_FEATURES = [f"ev_{c}_{w}" for c in EVENT_COLS for w in EVENT_WINDOWS] + [f"ev_n_{w}" for w in EVENT_WINDOWS]
RELATIVE_FEATURES = [
    "elo_diff", "form_diff_5", "form_diff_10", "strength_diff_10", "sot_strength_diff_10", "attack_matchup_10",
    "defence_matchup_10", "ppg_std_diff", "rest_diff",
]
TARGETS = ["result", "home_goals", "away_goals"]


def _implied(prefix: str, h: str, d: str, a: str) -> list[pl.Expr]:
    """Bookmaker odds -> probabilities, with the margin removed proportionally."""
    inv = 1 / pl.col(h) + 1 / pl.col(d) + 1 / pl.col(a)
    return [
        ((1 / pl.col(h)) / inv).alias(f"{prefix}_h"),
        ((1 / pl.col(d)) / inv).alias(f"{prefix}_d"),
        ((1 / pl.col(a)) / inv).alias(f"{prefix}_a"),
    ]


def _relative(side_a: str, side_b: str) -> list[pl.Expr]:
    a, b = side_a, side_b
    return [
        (pl.col(f"{a}elo") - pl.col(f"{b}elo")).alias("elo_diff"),
        (pl.col(f"{a}points_5") - pl.col(f"{b}points_5")).alias("form_diff_5"),
        (pl.col(f"{a}points_10") - pl.col(f"{b}points_10")).alias("form_diff_10"),
        (pl.col(f"{a}goal_diff_10") - pl.col(f"{b}goal_diff_10")).alias("strength_diff_10"),
        ((pl.col(f"{a}sot_10") - pl.col(f"{a}sot_against_10")) - (pl.col(f"{b}sot_10") - pl.col(f"{b}sot_against_10")))
        .alias("sot_strength_diff_10"),
        (pl.col(f"{a}goals_10") + pl.col(f"{b}goals_against_10")).alias("attack_matchup_10"),
        (pl.col(f"{a}goals_against_10") + pl.col(f"{b}goals_10")).alias("defence_matchup_10"),
        (pl.col(f"{a}points_std") - pl.col(f"{b}points_std")).alias("ppg_std_diff"),
        (pl.col(f"{a}days_rest") - pl.col(f"{b}days_rest")).alias("rest_diff"),
    ]


def fixture_table(
    results: pl.DataFrame, form: pl.DataFrame, rated: pl.DataFrame, events: pl.DataFrame
) -> pl.DataFrame:
    """Home-perspective table of every league fixture with features, targets and market odds."""
    base = results.with_row_index("fixture_id").with_columns(
        pl.when(pl.col("home_goals") > pl.col("away_goals")).then(pl.lit("H"))
        .when(pl.col("home_goals") == pl.col("away_goals")).then(pl.lit("D"))
        .otherwise(pl.lit("A")).alias("result"),
        *_implied("mkt_b365", "odds_b365_h", "odds_b365_d", "odds_b365_a"),
        *_implied("mkt_psc", "odds_psc_h", "odds_psc_d", "odds_psc_a"),
        *_implied("mkt_avg", "odds_avg_h", "odds_avg_d", "odds_avg_a"),
    ).select(
        "fixture_id", "season", "season_start", "date", "home", "away", *TARGETS,
        pl.col("^mkt_.*$"),
    )
    side_cols = FORM_FEATURES + H2H_FEATURES
    home = form.filter(pl.col("is_home")).select("fixture_id", *[pl.col(c).alias(f"h_{c}") for c in side_cols])
    away = form.filter(~pl.col("is_home")).select("fixture_id", *[pl.col(c).alias(f"a_{c}") for c in side_cols])
    elo = rated.select(
        "date", "home", "away", pl.col("home_elo").alias("h_elo"), pl.col("away_elo").alias("a_elo"),
        pl.col("home_expected").alias("elo_expected"),
    )
    ev_cols = [c for c in events.columns if c.startswith("ev_")]
    ev_home = events.filter(pl.col("is_home")).select("fixture_id", pl.col("match_id").alias("sb_match_id"),
                                                      *[pl.col(c).alias(f"h_{c}") for c in ev_cols])
    ev_away = events.filter(~pl.col("is_home")).select("fixture_id", pl.col("match_id").alias("sb_match_id_away"),
                                                       *[pl.col(c).alias(f"a_{c}") for c in ev_cols])
    out = (
        base.join(home, on="fixture_id", how="left")
        .join(away, on="fixture_id", how="left")
        .join(elo, on=["date", "home", "away"], how="left")
        .join(ev_home, on="fixture_id", how="left")
        .join(ev_away, on="fixture_id", how="left")
        .with_columns(pl.coalesce("sb_match_id", "sb_match_id_away").alias("sb_match_id"))
        .drop("sb_match_id_away")
    )
    return out.with_columns(_relative("h_", "a_")).sort("date", "fixture_id")


def barca_table(fixtures: pl.DataFrame, team: str = "Barcelona") -> pl.DataFrame:
    """Barcelona-perspective rows (``barca_*`` vs ``opp_*``), targets as W/D/L."""
    rows = fixtures.filter((pl.col("home") == team) | (pl.col("away") == team))
    home = pl.col("home") == team
    side_features = sorted({c[2:] for c in fixtures.columns if c.startswith(("h_", "a_"))})
    exprs: list[pl.Expr] = [
        pl.col("fixture_id"), pl.col("sb_match_id"), pl.col("season"), pl.col("season_start"), pl.col("date"),
        home.alias("is_home"),
        pl.when(home).then(pl.col("away")).otherwise(pl.col("home")).alias("opponent"),
        pl.when(home).then(pl.col("home_goals")).otherwise(pl.col("away_goals")).alias("barca_goals"),
        pl.when(home).then(pl.col("away_goals")).otherwise(pl.col("home_goals")).alias("opp_goals"),
        pl.col("elo_expected"),
    ]
    for f in side_features:
        exprs.append(pl.when(home).then(pl.col(f"h_{f}")).otherwise(pl.col(f"a_{f}")).alias(f"barca_{f}"))
        exprs.append(pl.when(home).then(pl.col(f"a_{f}")).otherwise(pl.col(f"h_{f}")).alias(f"opp_{f}"))
    for book in ("b365", "psc", "avg"):
        exprs += [
            pl.when(home).then(pl.col(f"mkt_{book}_h")).otherwise(pl.col(f"mkt_{book}_a")).alias(f"mkt_{book}_w"),
            pl.col(f"mkt_{book}_d").alias(f"mkt_{book}_d"),
            pl.when(home).then(pl.col(f"mkt_{book}_a")).otherwise(pl.col(f"mkt_{book}_h")).alias(f"mkt_{book}_l"),
        ]
    out = rows.select(exprs).with_columns(
        pl.when(pl.col("barca_goals") > pl.col("opp_goals")).then(pl.lit("W"))
        .when(pl.col("barca_goals") == pl.col("opp_goals")).then(pl.lit("D"))
        .otherwise(pl.lit("L")).alias("result"),
        # the home-perspective Elo expectation, re-expressed for Barcelona
        pl.when(pl.col("is_home")).then(pl.col("elo_expected")).otherwise(1 - pl.col("elo_expected"))
        .alias("elo_expected"),
    )
    # h2h is already from each side's own perspective in the form table
    return out.with_columns(_relative("barca_", "opp_")).sort("date")


def league_feature_list() -> list[str]:
    """Features for the league-wide outcome model (available for every club, every season)."""
    side = [f"h_{c}" for c in FORM_FEATURES] + [f"a_{c}" for c in FORM_FEATURES] + ["h_h2h_points_4", "h_h2h_goal_diff_4"]
    return side + ["h_elo", "a_elo", "elo_expected", *RELATIVE_FEATURES]


def barca_feature_list(include_events: bool = True) -> list[str]:
    side = [f"barca_{c}" for c in FORM_FEATURES] + [f"opp_{c}" for c in FORM_FEATURES]
    base = side + ["barca_h2h_points_4", "barca_h2h_goal_diff_4", "barca_elo", "opp_elo", "elo_expected", "is_home",
                   *RELATIVE_FEATURES]
    if include_events:
        base += [f"barca_{c}" for c in EVENT_FEATURES]
    return base
