"""Build the feature store (data/features) from the validated processed tables."""

from __future__ import annotations

import logging

import polars as pl

from barca import config
from barca.analytics import player_match, player_season, ratings, team_match, xt
from barca.data import store, validate
from barca.features import elo, event_form, player_fixture, tables, team_form

log = logging.getLogger(__name__)

MINUTES_COLS = [
    "match_id",
    "team_id",
    "player_id",
    "minutes",
    "started",
    "start_position",
    "positions",
    "on_minute",
    "off_minute",
    "end_reason",
    "match_minutes",
    "position_group",
    "position_family",
]


def _write(frame: pl.DataFrame, name: str) -> None:
    config.FEATURES.mkdir(parents=True, exist_ok=True)
    frame.write_parquet(config.FEATURES / f"{name}.parquet", compression="zstd")


def build() -> dict[str, int]:
    validate.require_stamp(store.VALIDATION_STAMP)
    matches = store.matches()
    events = store.events()
    appearances = store.appearances()
    results = store.results()

    tms = team_match.team_match_stats(events, matches)
    minutes = appearances.filter(pl.col("played")).select(MINUTES_COLS)
    pms = player_match.player_match_stats(events, minutes, matches, appearances)
    pms = player_season.possession_adjust(pms, tms.select("match_id", "team_id", "possession"))

    # expected threat: fitted on the complete 2015/16 season, applied to every match
    grid = xt.fit(events.filter(pl.col("season") == ratings.REFERENCE_SEASON))
    actions = events.select(
        "match_id",
        "event_id",
        "team_id",
        "player_id",
        "type",
        "subtype",
        "outcome",
        "x",
        "y",
        "end_x",
        "end_y",
    ).collect()
    values = xt.action_values(actions, grid)
    pms = pms.join(
        xt.player_match_xt(values), on=["match_id", "team_id", "player_id"], how="left"
    ).with_columns(
        pl.col("xt").fill_null(0.0),
        pl.col("xt_pass").fill_null(0.0),
        pl.col("xt_carry").fill_null(0.0),
    )
    tms = tms.join(xt.team_match_xt(values), on=["match_id", "team_id"], how="left")

    # BIPR (season) and match ratings
    season_rows = ratings.aggregate(pms, ["season", "team", "player_id"])
    season_ref = season_rows.filter(
        pl.col("season") == ratings.REFERENCE_SEASON,
        pl.col("minutes") >= ratings.MIN_MINUTES_SEASON,
        pl.col("position_family").is_in(list(ratings.FAMILIES)),
    )
    player_ratings = ratings.score(season_rows, season_ref).with_columns(
        (pl.col("minutes") >= ratings.MIN_MINUTES_SEASON).alias("rating_reliable")
    )
    match_rows = ratings.add_rates(pms)
    match_ref = match_rows.filter(
        pl.col("season") == ratings.REFERENCE_SEASON,
        pl.col("minutes") >= ratings.MIN_MINUTES_MATCH_REFERENCE,
        pl.col("position_family").is_in(list(ratings.FAMILIES)),
    )
    rated_matches = ratings.score(
        match_rows.filter(pl.col("minutes") >= ratings.MIN_MINUTES_MATCH_RATING), match_ref
    )
    pms = pms.join(
        rated_matches.select(
            "match_id",
            "player_id",
            ratings.match_rating_scale(pl.col("overall_pct"), pl.col("minutes"))
            .round(1)
            .alias("match_rating"),
            *[pl.col(f"pillar_{p}").alias(f"match_{p}") for p in ratings.PILLARS],
        ),
        on=["match_id", "player_id"],
        how="left",
    )

    form = team_form.team_form(results)
    rated = elo.run(results, elo.EloParams())
    ev_form = event_form.event_form(tms, form)
    fixtures = tables.fixture_table(results, form, rated, ev_form)
    barca = tables.barca_table(fixtures)

    candidates = player_fixture.build(barca, matches, appearances, pms, player_ratings)

    for name, frame in {
        "player_fixture": candidates,
        "team_match": tms,
        "player_match": pms,
        "team_form": form,
        "elo": rated,
        "event_form": ev_form,
        "fixtures": fixtures,
        "barca_matches": barca,
        "xt_grid": xt.grid_frame(grid),
        "player_ratings": player_ratings,
        "bipr_reference": season_ref,
        "match_rating_reference": match_ref,
    }.items():
        _write(frame, name)
    counts = {
        "team_match": tms.height,
        "player_match": pms.height,
        "fixtures": fixtures.height,
        "barca_matches": barca.height,
    }
    log.info("features: %s", counts)
    return counts
