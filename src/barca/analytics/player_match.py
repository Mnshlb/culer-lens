"""Player-level statistics for every match: one row per (match, player)."""

from __future__ import annotations

import polars as pl

from barca.analytics import definitions as D

COUNT_METRICS = [
    "goals",
    "np_goals",
    "assists",
    "shots",
    "shots_on_target",
    "key_passes",
    "touches",
    "touches_in_box",
    "passes",
    "passes_completed",
    "progressive_passes",
    "progressive_carries",
    "carries",
    "final_third_entries",
    "box_entries",
    "crosses",
    "through_balls",
    "dribbles",
    "dribbles_completed",
    "pressures",
    "counterpresses",
    "tackles",
    "tackles_won",
    "interceptions",
    "recoveries",
    "high_recoveries",
    "clearances",
    "blocks",
    "aerials_won",
    "aerials_lost",
    "fouls",
    "fouls_won",
    "turnovers",
    "yellow_cards",
    "red_cards",
]
VALUE_METRICS = ["xg", "npxg", "xa"]


def _aggregations() -> list[pl.Expr]:
    xg = pl.col("shot_xg")
    return [
        D.GOAL.sum().alias("goals"),
        D.NON_PENALTY_GOAL.sum().alias("np_goals"),
        D.ASSIST.sum().alias("assists"),
        D.SHOT.sum().alias("shots"),
        D.SHOT_ON_TARGET.sum().alias("shots_on_target"),
        xg.filter(D.SHOT).sum().alias("xg"),
        xg.filter(D.NON_PENALTY_SHOT).sum().alias("npxg"),
        D.KEY_PASS.sum().alias("key_passes"),
        D.TOUCH.sum().alias("touches"),
        D.TOUCH_IN_BOX.sum().alias("touches_in_box"),
        D.PASS.sum().alias("passes"),
        D.PASS_COMPLETE.sum().alias("passes_completed"),
        D.PROGRESSIVE_PASS.sum().alias("progressive_passes"),
        D.PROGRESSIVE_CARRY.sum().alias("progressive_carries"),
        D.CARRY.sum().alias("carries"),
        (D.FINAL_THIRD_PASS | D.FINAL_THIRD_CARRY).sum().alias("final_third_entries"),
        (D.BOX_PASS | D.BOX_CARRY).sum().alias("box_entries"),
        D.CROSS.sum().alias("crosses"),
        D.THROUGH_BALL.sum().alias("through_balls"),
        D.DRIBBLE.sum().alias("dribbles"),
        D.DRIBBLE_COMPLETE.sum().alias("dribbles_completed"),
        D.PRESSURE.sum().alias("pressures"),
        D.COUNTERPRESS.sum().alias("counterpresses"),
        D.TACKLE.sum().alias("tackles"),
        D.TACKLE_WON.sum().alias("tackles_won"),
        D.INTERCEPTION.sum().alias("interceptions"),
        D.RECOVERY.sum().alias("recoveries"),
        D.HIGH_RECOVERY.sum().alias("high_recoveries"),
        D.CLEARANCE.sum().alias("clearances"),
        D.BLOCK.sum().alias("blocks"),
        D.AERIAL_WON.sum().alias("aerials_won"),
        D.AERIAL_LOST.sum().alias("aerials_lost"),
        D.FOUL.sum().alias("fouls"),
        (pl.col("type") == "Foul Won").sum().alias("fouls_won"),
        D.TURNOVER.sum().alias("turnovers"),
        (pl.col("card") == "Yellow Card").fill_null(False).sum().alias("yellow_cards"),
        pl.col("card")
        .is_in(["Red Card", "Second Yellow"])
        .fill_null(False)
        .sum()
        .alias("red_cards"),
        pl.col("x").filter(D.TOUCH).mean().alias("avg_touch_x"),
        pl.col("y").filter(D.TOUCH).mean().alias("avg_touch_y"),
    ]


def expected_assists(events: pl.LazyFrame) -> pl.DataFrame:
    """xA: the xG of every shot credited to the player who played the key pass."""
    shots = events.filter(D.SHOT, pl.col("shot_key_pass_id").is_not_null()).select(
        "match_id", pl.col("shot_key_pass_id").alias("event_id"), pl.col("shot_xg").alias("xa")
    )
    passes = events.filter(D.PASS).select("match_id", "event_id", "player_id", "team_id")
    return (
        shots.join(passes, on=["match_id", "event_id"], how="inner")
        .group_by("match_id", "team_id", "player_id")
        .agg(pl.col("xa").sum())
        .collect()
    )


def player_match_stats(
    events: pl.LazyFrame,
    minutes: pl.DataFrame,
    matches: pl.DataFrame,
    lineups: pl.DataFrame,
) -> pl.DataFrame:
    """Per (match, player) statistics for everyone who played.

    ``minutes`` comes from ``normalize.player_minutes`` and defines the rows:
    a player who never entered the pitch has no row here (unused substitutes
    are kept separately in the lineups table).
    """
    ev = events.filter(pl.col("period") <= 4, pl.col("player_id").is_not_null())
    stats = ev.group_by("match_id", "team_id", "player_id").agg(_aggregations()).collect()
    xa = expected_assists(ev)

    people = lineups.select(
        "match_id", "team_id", "player_id", "player", "nickname", "jersey_number", "country"
    )
    teams = pl.concat(
        [
            matches.select(
                "match_id",
                pl.col("home_team_id").alias("team_id"),
                pl.col("home").alias("team"),
                pl.col("away").alias("opponent"),
                pl.lit(True).alias("is_home"),
            ),
            matches.select(
                "match_id",
                pl.col("away_team_id").alias("team_id"),
                pl.col("away").alias("team"),
                pl.col("home").alias("opponent"),
                pl.lit(False).alias("is_home"),
            ),
        ]
    )
    info = matches.select("match_id", "date", "kickoff", "season", "season_start", "competition")

    out = (
        minutes.join(people, on=["match_id", "team_id", "player_id"], how="left")
        .join(teams, on=["match_id", "team_id"], how="left")
        .join(info, on="match_id", how="left")
        .join(stats, on=["match_id", "team_id", "player_id"], how="left")
        .join(xa, on=["match_id", "team_id", "player_id"], how="left")
    )
    fill = [pl.col(c).fill_null(0) for c in COUNT_METRICS] + [
        pl.col(c).fill_null(0.0) for c in VALUE_METRICS
    ]
    out = out.with_columns(fill).with_columns(
        pl.coalesce(pl.col("nickname"), pl.col("player")).alias("display_name"),
    )
    return out.sort(
        "kickoff",
        "match_id",
        "team_id",
        "started",
        "minutes",
        descending=[False, False, False, True, True],
    )


def per90(frame: pl.DataFrame, metrics: list[str], minutes_col: str = "minutes") -> pl.DataFrame:
    """Metric_90 = Metric / Minutes * 90 (minutes include stoppage time, see D-010)."""
    return frame.with_columns(
        [(pl.col(m) / pl.col(minutes_col) * 90).alias(f"{m}_p90") for m in metrics]
    )
