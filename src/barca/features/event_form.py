"""Event-based (StatsBomb) team form, laid over the complete league schedule.

Windows are defined over the team's *scheduled* league matches, not over the
matches that happen to have event data. A window that contains uncovered
matches averages the covered ones, and ``ev_n_{w}`` records how many there
were, so a model can distinguish a thin window from a full one.

Event form exists for Barcelona in every season and for all clubs in
2015/16; other clubs only appear against Barcelona, which is too sparse to
form a window, so they are left out.
"""

from __future__ import annotations

import polars as pl

from barca.features import rolling

EVENT_COLS = [
    "xg",
    "xga",
    "npxg",
    "npxga",
    "xg_diff",
    "shots",
    "opp_shots",
    "big_chances",
    "opp_big_chances",
    "xg_open_play",
    "xg_set_piece",
    "possession",
    "field_tilt",
    "ppda",
    "progressive_passes",
    "progressive_carries",
    "pressures",
    "pressures_final_third",
    "counterpresses",
    "high_recoveries",
    "box_entries",
    "opp_box_entries",
    "defensive_action_height",
    "pass_completion",
    "touches_in_box",
]
WINDOWS = (3, 5, 10)


def event_form(team_match_stats: pl.DataFrame, team_form: pl.DataFrame) -> pl.DataFrame:
    league = team_match_stats.filter(pl.col("competition") == "La Liga").select(
        "date", "team", "match_id", *EVENT_COLS
    )
    schedule = team_form.select(
        "fixture_id", "date", "season", "team", "opponent", "is_home"
    ).filter((pl.col("team") == "Barcelona") | (pl.col("season") == "2015/2016"))
    joined = schedule.join(league, on=["date", "team"], how="left").with_columns(
        pl.col("match_id").is_not_null().cast(pl.Int8).alias("has_events")
    )
    out = rolling.add_rolling_means(
        joined,
        by="team",
        order=["date", "fixture_id"],
        cols=EVENT_COLS,
        windows=WINDOWS,
        prefix="ev_",
    )
    out = out.with_columns(
        [
            pl.col("has_events")
            .shift(1)
            .rolling_sum(window_size=w, min_samples=1)
            .over("team")
            .fill_null(0)
            .cast(pl.Int8)
            .alias(f"ev_n_{w}")
            for w in WINDOWS
        ]
    )
    keep = ["fixture_id", "date", "season", "team", "opponent", "is_home", "match_id", "has_events"]
    return out.select(keep + [c for c in out.columns if c.startswith("ev_")])
