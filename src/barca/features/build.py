"""Build the feature store (data/features) from the validated processed tables."""

from __future__ import annotations

import logging

import polars as pl

from barca import config
from barca.analytics import player_match, player_season, team_match
from barca.data import store, validate
from barca.features import elo, event_form, tables, team_form

log = logging.getLogger(__name__)

MINUTES_COLS = [
    "match_id", "team_id", "player_id", "minutes", "started", "start_position", "positions", "on_minute",
    "off_minute", "end_reason", "match_minutes", "position_group", "position_family",
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

    form = team_form.team_form(results)
    rated = elo.run(results, elo.EloParams())
    ev_form = event_form.event_form(tms, form)
    fixtures = tables.fixture_table(results, form, rated, ev_form)
    barca = tables.barca_table(fixtures)

    for name, frame in {
        "team_match": tms, "player_match": pms, "team_form": form, "elo": rated,
        "event_form": ev_form, "fixtures": fixtures, "barca_matches": barca,
    }.items():
        _write(frame, name)
    counts = {"team_match": tms.height, "player_match": pms.height, "fixtures": fixtures.height,
              "barca_matches": barca.height}
    log.info("features: %s", counts)
    return counts
