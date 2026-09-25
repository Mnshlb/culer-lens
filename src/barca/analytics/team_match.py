"""Team-level statistics for every match: one row per (match, team)."""

from __future__ import annotations

import polars as pl

from barca.analytics import definitions as D

_CARD_YELLOW = pl.col("card") == "Yellow Card"
_CARD_RED = pl.col("card").is_in(["Red Card", "Second Yellow"])


def _aggregations() -> list[pl.Expr]:
    xg = pl.col("shot_xg")
    return [
        D.SHOT.sum().alias("shots"),
        D.NON_PENALTY_SHOT.sum().alias("np_shots"),
        D.SHOT_ON_TARGET.sum().alias("shots_on_target"),
        D.SHOT_IN_BOX.sum().alias("shots_in_box"),
        D.BIG_CHANCE.sum().alias("big_chances"),
        D.PENALTY.sum().alias("penalties"),
        xg.filter(D.SHOT).sum().alias("xg"),
        xg.filter(D.NON_PENALTY_SHOT).sum().alias("npxg"),
        xg.filter(D.OPEN_PLAY_SHOT).sum().alias("xg_open_play"),
        xg.filter(D.SET_PIECE_SHOT).sum().alias("xg_set_piece"),
        D.NON_PENALTY_GOAL.sum().alias("np_goals"),
        D.PASS.sum().alias("passes"),
        D.PASS_COMPLETE.sum().alias("passes_completed"),
        D.PROGRESSIVE_PASS.sum().alias("progressive_passes"),
        D.PROGRESSIVE_CARRY.sum().alias("progressive_carries"),
        (D.FINAL_THIRD_PASS | D.FINAL_THIRD_CARRY).sum().alias("final_third_entries"),
        (D.BOX_PASS | D.BOX_CARRY).sum().alias("box_entries"),
        D.PASS_IN_FINAL_THIRD.sum().alias("final_third_passes"),
        D.CROSS.sum().alias("crosses"),
        D.KEY_PASS.sum().alias("key_passes"),
        D.THROUGH_BALL.sum().alias("through_balls"),
        D.LONG_PASS.sum().alias("long_passes"),
        pl.col("pass_length").filter(D.PASS_COMPLETE).mean().alias("avg_pass_length"),
        (D.PASS & (pl.col("subtype") == "Corner")).sum().alias("corners"),
        D.DRIBBLE.sum().alias("dribbles"),
        D.DRIBBLE_COMPLETE.sum().alias("dribbles_completed"),
        D.TOUCH_IN_BOX.sum().alias("touches_in_box"),
        D.TURNOVER.sum().alias("turnovers"),
        D.PRESSURE.sum().alias("pressures"),
        D.COUNTERPRESS.sum().alias("counterpresses"),
        (D.PRESSURE & (D.X >= D.FINAL_THIRD_X)).sum().alias("pressures_final_third"),
        D.TACKLE.sum().alias("tackles"),
        D.TACKLE_WON.sum().alias("tackles_won"),
        D.INTERCEPTION.sum().alias("interceptions"),
        D.RECOVERY.sum().alias("recoveries"),
        D.HIGH_RECOVERY.sum().alias("high_recoveries"),
        D.CLEARANCE.sum().alias("clearances"),
        D.BLOCK.sum().alias("blocks"),
        D.FOUL.sum().alias("fouls"),
        (D.PPDA_ACTION & (D.X >= D.PROGRESSION_MIN_X)).sum().alias("ppda_actions"),
        # Passes a team makes in its own 60% are the numerator of the *opponent's* PPDA.
        (D.PASS & (D.X <= 72)).sum().alias("passes_own_60"),
        pl.col("x").filter(D.DEFENSIVE_ACTION).mean().alias("defensive_action_height"),
        (_CARD_YELLOW.fill_null(False)).sum().alias("yellow_cards"),
        (_CARD_RED.fill_null(False)).sum().alias("red_cards"),
    ]


def team_match_stats(events: pl.LazyFrame, matches: pl.DataFrame) -> pl.DataFrame:
    """Per (match, team) statistics, each row carrying its opponent's figures too.

    ``matches`` must be the normalised match table (``normalize.matches``).
    Goals come from the official score so own goals are included; shot-based
    goals are available as ``np_goals`` for finishing analysis.
    """
    stats = (
        events.filter(pl.col("period") <= 4, pl.col("team_id").is_not_null())
        .group_by("match_id", "team_id")
        .agg(_aggregations())
        .collect()
    )

    sides = pl.concat(
        [
            matches.select(
                "match_id",
                pl.col("home_team_id").alias("team_id"),
                pl.col("home").alias("team"),
                pl.col("away_team_id").alias("opponent_id"),
                pl.col("away").alias("opponent"),
                pl.lit(True).alias("is_home"),
                pl.col("home_score").alias("goals"),
                pl.col("away_score").alias("goals_against"),
            ),
            matches.select(
                "match_id",
                pl.col("away_team_id").alias("team_id"),
                pl.col("away").alias("team"),
                pl.col("home_team_id").alias("opponent_id"),
                pl.col("home").alias("opponent"),
                pl.lit(False).alias("is_home"),
                pl.col("away_score").alias("goals"),
                pl.col("home_score").alias("goals_against"),
            ),
        ]
    )
    info = matches.select(
        "match_id",
        "date",
        "kickoff",
        "season",
        "season_start",
        "competition",
        "competition_id",
        "match_week",
    )

    metric_cols = [c for c in stats.columns if c not in ("match_id", "team_id")]
    opp = stats.rename({c: f"opp_{c}" for c in metric_cols} | {"team_id": "opponent_id"})

    out = (
        sides.join(info, on="match_id")
        .join(stats, on=["match_id", "team_id"], how="left")
        .join(opp, on=["match_id", "opponent_id"], how="left")
    )
    out = out.with_columns(
        pl.when(pl.col("goals") > pl.col("goals_against"))
        .then(pl.lit("W"))
        .when(pl.col("goals") == pl.col("goals_against"))
        .then(pl.lit("D"))
        .otherwise(pl.lit("L"))
        .alias("result"),
        (pl.col("xg") - pl.col("opp_xg")).alias("xg_diff"),
        pl.col("opp_xg").alias("xga"),
        pl.col("opp_npxg").alias("npxga"),
        (pl.col("passes") / (pl.col("passes") + pl.col("opp_passes"))).alias("possession"),
        (
            pl.col("final_third_passes")
            / (pl.col("final_third_passes") + pl.col("opp_final_third_passes"))
        ).alias("field_tilt"),
        (pl.col("opp_passes_own_60") / pl.col("ppda_actions").clip(lower_bound=1)).alias("ppda"),
        (pl.col("passes_completed") / pl.col("passes")).alias("pass_completion"),
    ).with_columns(
        pl.col("result")
        .replace_strict({"W": 3, "D": 1, "L": 0}, return_dtype=pl.Int8)
        .alias("points"),
    )
    return out.sort("kickoff", "match_id", "is_home", descending=[False, False, True])
