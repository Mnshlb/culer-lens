"""Error analysis: the matches the model got most confidently wrong."""

from __future__ import annotations

import polars as pl


def high_confidence_errors(barca_pred: pl.DataFrame, threshold: float = 0.7) -> pl.DataFrame:
    """Barcelona fixtures where the model gave ≥ ``threshold`` to an outcome that did not happen."""
    probs = pl.concat_list("p_win", "p_draw", "p_loss")
    pred = (
        barca_pred.with_columns(
            probs.list.arg_max().alias("_argmax"),
            probs.list.max().alias("confidence"),
        )
        .with_columns(
            pl.col("_argmax")
            .replace_strict({0: "W", 1: "D", 2: "L"}, return_dtype=pl.String)
            .alias("predicted"),
        )
        .drop("_argmax")
    )
    wrong = pred.filter(
        pl.col("confidence") >= threshold, pl.col("predicted") != pl.col("barca_result")
    )
    return wrong.with_columns(
        (
            -pl.when(pl.col("barca_result") == "W")
            .then(pl.col("p_win"))
            .when(pl.col("barca_result") == "D")
            .then(pl.col("p_draw"))
            .otherwise(pl.col("p_loss"))
            .log()
        ).alias("surprise")
    ).sort("surprise", descending=True)


def match_context(
    errors: pl.DataFrame, barca: pl.DataFrame, team_match: pl.DataFrame, appearances: pl.DataFrame
) -> pl.DataFrame:
    """What happened in each error match: xG, shots, red cards and which usual starters were missing."""
    sb = barca.select("fixture_id", "sb_match_id")
    tm = team_match.filter(pl.col("team") == "Barcelona").select(
        pl.col("match_id").alias("sb_match_id"),
        pl.col("xg").alias("barca_xg"),
        pl.col("opp_xg").alias("opp_xg"),
        pl.col("shots").alias("barca_shots"),
        pl.col("opp_shots"),
        pl.col("possession"),
        pl.col("red_cards").alias("barca_reds"),
        pl.col("opp_red_cards").alias("opp_reds"),
    )
    starters = (
        appearances.filter(pl.col("team") == "Barcelona", pl.col("started"))
        .group_by("match_id")
        .agg(pl.col("display_name").sort().alias("starters"))
        .rename({"match_id": "sb_match_id"})
    )
    return (
        errors.join(sb, on="fixture_id", how="left")
        .join(tm, on="sb_match_id", how="left")
        .join(starters, on="sb_match_id", how="left")
    )
