"""Cleaning rules, each one traced back to a finding in the EDA/profiling notebooks.

| Rule | Finding | Fix |
|---|---|---|
| C1 | 325 locations fractionally beyond the touchline/by-line (max 120.9 x 80.9) | clip to the 120 x 80 pitch |
| C2 | StatsBomb flags (under_pressure, cross, ...) are null when false | fill with False |
| C3 | a pass's empty outcome means "complete" | explicit ``pass_complete`` column |
| C4 | lineup spells label 3 team-matches' starters as "Tactical Shift" | ``started`` comes from the Starting XI event |
| C5 | football-data spells Villarreal "Villareal" in early seasons | canonical names (normalize) |
| C6 | football-data dates switch from dd/mm/yy to dd/mm/yyyy | length-aware parsing (normalize) |
| C7 | hive partition values use "2015-2016", match metadata "2015/2016" | one canonical ``season`` column |
| C8 | penalty shoot-outs are not playing time | events with period 5 dropped |

Nothing is imputed. Where a value is genuinely unknown it stays null.
"""

from __future__ import annotations

import polars as pl

from barca.data import normalize

BOOLEAN_FLAGS = [
    "under_pressure",
    "counterpress",
    "off_camera",
    "out",
    "pass_cross",
    "pass_switch",
    "pass_through_ball",
    "pass_cut_back",
    "pass_shot_assist",
    "pass_goal_assist",
    "pass_deflected",
    "shot_first_time",
    "shot_one_on_one",
    "shot_open_goal",
    "dribble_nutmeg",
    "recovery_failure",
    "foul_penalty",
    "aerial_won",
]


def clean_events(events: pl.LazyFrame, matches: pl.DataFrame, bounds: pl.DataFrame) -> pl.LazyFrame:
    info = matches.select("match_id", "season", "season_start", "date", "competition").lazy()
    b = bounds.select("match_id", "period", "start_s", "elapsed_before_s").lazy()
    ev = events
    if "season" in ev.collect_schema().names():
        ev = ev.drop("season")  # C7: partition value, replaced by the match's canonical season
    ev = (
        ev.filter(pl.col("period") <= 4)  # C8
        .with_columns(
            *[pl.col(c).clip(0.0, 120.0) for c in ("x", "end_x")],  # C1
            *[pl.col(c).clip(0.0, 80.0) for c in ("y", "end_y")],
            *[pl.col(c).fill_null(False) for c in BOOLEAN_FLAGS],  # C2
        )
        .with_columns(
            ((pl.col("type") == "Pass") & pl.col("outcome").is_null()).alias("pass_complete")
        )  # C3
        .join(info, on="match_id", how="left")
        .join(b, on=["match_id", "period"], how="left")
        .with_columns(
            (
                pl.col("elapsed_before_s")
                + (pl.col("minute").cast(pl.Float64) * 60 + pl.col("second") - pl.col("start_s"))
            )
            .clip(lower_bound=pl.col("elapsed_before_s"))
            .alias("elapsed_s")
        )
        .drop("start_s", "elapsed_before_s")
    )
    return normalize.events(ev)


def clipped_locations(events: pl.LazyFrame) -> int:
    cond = pl.lit(False)
    for c, hi in (("x", 120), ("end_x", 120), ("y", 80), ("end_y", 80)):
        cond = cond | (pl.col(c) < 0) | (pl.col(c) > hi)
    return int(events.filter(cond).select(pl.len()).collect().item())


def appearances(
    lineups: pl.DataFrame, minutes: pl.DataFrame, tactics: pl.DataFrame, matches: pl.DataFrame
) -> pl.DataFrame:
    """Every player listed for a match (starters, used and unused substitutes).

    ``started`` comes from the Starting XI event (C4); ``minutes`` from the
    lineup spells (``normalize.player_minutes``). Unused substitutes get 0
    minutes and ``played = False``.
    """
    xi = tactics.filter(pl.col("event_type") == "Starting XI").select(
        "match_id",
        "team_id",
        "player_id",
        pl.col("position").alias("xi_position"),
        pl.lit(True).alias("started"),
    )
    match_len = minutes.group_by("match_id").agg(pl.col("match_minutes").max())
    out = (
        lineups.join(
            minutes.drop("started", "match_minutes"),
            on=["match_id", "team_id", "player_id"],
            how="left",
        )
        .join(xi, on=["match_id", "team_id", "player_id"], how="left")
        .join(match_len, on="match_id", how="left")
        .join(
            matches.select("match_id", "date", "kickoff", "season", "competition"),
            on="match_id",
            how="left",
        )
        .with_columns(
            pl.col("started").fill_null(False),
            pl.col("minutes").fill_null(0.0),
            (pl.col("minutes").fill_null(0.0) > 0).alias("played"),
            pl.coalesce("nickname", "player").alias("display_name"),
            normalize.statsbomb_team_name(pl.col("team")).alias("team_name"),
        )
        .with_columns(
            # starters take the Starting XI position; substitutes their first spell
            pl.coalesce(
                pl.when(pl.col("started")).then(pl.col("xi_position")), pl.col("start_position")
            ).alias("start_position"),
        )
        .with_columns(
            pl.col("start_position")
            .replace_strict(normalize.POSITION_GROUP, default=None)
            .alias("position_group"),
        )
        .with_columns(
            pl.col("position_group")
            .replace_strict(normalize.POSITION_FAMILY, default=None)
            .alias("position_family"),
        )
        .drop("xi_position")
    )
    return out.sort(
        "kickoff",
        "match_id",
        "team_id",
        "started",
        "minutes",
        descending=[False, False, False, True, True],
    )
