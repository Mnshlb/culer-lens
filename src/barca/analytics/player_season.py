"""Season (or any window) aggregates of player-match statistics."""

from __future__ import annotations

import polars as pl

from barca.analytics.player_match import COUNT_METRICS, VALUE_METRICS

MIN_MINUTES_SEASON = 900  # ten full matches
MIN_MINUTES_CAREER = 1800

PER90_METRICS = [
    "goals",
    "np_goals",
    "assists",
    "xg",
    "npxg",
    "xa",
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
]
DEFENSIVE_METRICS = [
    "pressures",
    "tackles",
    "tackles_won",
    "interceptions",
    "recoveries",
    "clearances",
    "blocks",
]


def possession_adjust(pm: pl.DataFrame, team_possession: pl.DataFrame) -> pl.DataFrame:
    """Add possession-adjusted defensive counts per match.

    A team with 65% of the ball has only 35% of the match to defend. Scaling by
    0.5 / (opponent possession) puts players of dominant and passive teams on
    the same footing (the usual PAdj convention).
    """
    factor = team_possession.select(
        "match_id", "team_id", (0.5 / (1 - pl.col("possession")).clip(0.2, 0.8)).alias("_padj")
    )
    return (
        pm.join(factor, on=["match_id", "team_id"], how="left")
        .with_columns(
            [
                (pl.col(m) * pl.col("_padj").fill_null(1.0)).alias(f"padj_{m}")
                for m in DEFENSIVE_METRICS
            ]
        )
        .drop("_padj")
    )


def aggregate(pm: pl.DataFrame, by: list[str]) -> pl.DataFrame:
    """Sum player-match rows over ``by`` and add per-90 rates.

    The player's position is the position group in which they played the most
    minutes over the window.
    """
    padj_cols = [c for c in pm.columns if c.startswith("padj_")]
    pos = (
        pm.group_by([*by, "position_group"])
        .agg(pl.col("minutes").sum().alias("_m"))
        .sort("_m", descending=True)
        .group_by(by)
        .agg(pl.col("position_group").first().alias("position_group"))
    )
    labels = [pl.col(c).last() for c in ("display_name", "team") if c not in by]
    agg = pm.group_by(by).agg(
        *labels,
        pl.len().alias("appearances"),
        pl.col("started").sum().alias("starts"),
        pl.col("minutes").sum(),
        *[pl.col(c).sum() for c in COUNT_METRICS + VALUE_METRICS + padj_cols],
    )
    out = agg.join(pos, on=by, how="left").with_columns(
        [(pl.col(m) / pl.col("minutes") * 90).alias(f"{m}_p90") for m in PER90_METRICS]
        + [(pl.col(c) / pl.col("minutes") * 90).alias(f"{c}_p90") for c in padj_cols]
    )
    return out.with_columns(
        (pl.col("passes_completed") / pl.col("passes")).alias("pass_completion"),
        (pl.col("dribbles_completed") / pl.col("dribbles")).alias("dribble_success"),
        (pl.col("tackles_won") / pl.col("tackles")).alias("tackle_success"),
        (pl.col("aerials_won") / (pl.col("aerials_won") + pl.col("aerials_lost"))).alias(
            "aerial_win_rate"
        ),
        ((pl.col("npxg") + pl.col("xa")) / pl.col("minutes") * 90).alias("npxg_xa_p90"),
        (pl.col("np_goals") - pl.col("npxg")).alias("np_goals_minus_npxg"),
    )
