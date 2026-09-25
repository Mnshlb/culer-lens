"""Stage orchestration: raw -> interim -> processed -> validated -> features.

Each stage reads only from the stage before it and writes Parquet. Raw data is
never modified; rerunning a stage overwrites that stage's outputs only.
"""

from __future__ import annotations

import logging
import shutil
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

import polars as pl

from barca import config
from barca.data import clean, load, normalize, parse, sources, store, validate

log = logging.getLogger(__name__)


def _parse_match(match_id: int) -> dict[str, pl.DataFrame]:
    out = parse.parse_events(match_id, load.load_events(match_id))
    out.update(parse.parse_lineups(match_id, load.load_lineups(match_id)))
    path_360 = load.statsbomb_path("three-sixty", match_id)
    if path_360.exists():
        out["three_sixty"] = parse.three_sixty_frame(match_id, load.read_json(path_360))
    return out


def _write(frame: pl.DataFrame, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    frame.write_parquet(path, compression="zstd", statistics=True)


def build_interim(workers: int | None = None) -> dict[str, int]:
    """Flatten every downloaded match into interim Parquet tables."""
    matches = [
        m for m in load.in_scope_matches() if load.statsbomb_path("events", m["match_id"]).exists()
    ]
    catalogue = [
        m
        for season in load.catalogue_seasons()
        for m in load.load_matches(season["competition_id"], season["season_id"])
    ]
    _write(parse.matches_frame(catalogue), config.INTERIM / "catalogue.parquet")
    _write(parse.matches_frame(matches), config.INTERIM / "matches.parquet")

    season_of = {m["match_id"]: m["season"]["season_name"] for m in matches}
    ids = [m["match_id"] for m in matches]

    buckets: dict[str, list[pl.DataFrame]] = {}
    events_by_season: dict[str, list[pl.DataFrame]] = {}
    with ProcessPoolExecutor(max_workers=workers) as pool:
        for match_id, tables in zip(ids, pool.map(_parse_match, ids, chunksize=8), strict=True):
            for name, frame in tables.items():
                if name == "events":
                    events_by_season.setdefault(season_of[match_id], []).append(frame)
                else:
                    buckets.setdefault(name, []).append(frame)

    events_dir = config.INTERIM / "events"
    if events_dir.exists():
        shutil.rmtree(events_dir)
    n_events = 0
    for season, frames in events_by_season.items():
        frame = pl.concat(frames, how="vertical")
        n_events += frame.height
        _write(frame, events_dir / f"season={season.replace('/', '-')}" / "part-0.parquet")

    counts = {"matches": len(matches), "events": n_events}
    for name, frames in buckets.items():
        frame = pl.concat(frames, how="vertical")
        _write(frame, config.INTERIM / f"{name}.parquet")
        counts[name] = frame.height

    results = []
    for season in sources.football_data_seasons():
        path = load.football_data_path(season)
        if path.exists():
            results.append(parse.football_data_frame(path.read_bytes(), season.label))
    if results:
        frame = pl.concat(results, how="diagonal_relaxed")
        _write(frame, config.INTERIM / "football_data.parquet")
        counts["football_data"] = frame.height

    log.info("interim: %s", counts)
    return counts


def scan_events(stage: Path | None = None) -> pl.LazyFrame:
    root = (stage or config.INTERIM) / "events"
    return pl.scan_parquet(root / "**" / "*.parquet", hive_partitioning=True)


# Processed (cleaned) --------------------------------------------------------------


def build_processed() -> dict[str, int]:
    """Interim -> processed: normalise names/types/units and apply the cleaning rules."""
    raw_matches = pl.read_parquet(config.INTERIM / "matches.parquet")
    matches = normalize.matches(raw_matches)
    raw_events = scan_events(config.INTERIM)
    bounds = normalize.period_bounds(raw_events)
    clipped = clean.clipped_locations(raw_events)
    events = clean.clean_events(raw_events, matches, bounds).collect()

    out_dir = config.PROCESSED / "events"
    if out_dir.exists():
        shutil.rmtree(out_dir)
    for (season,), frame in events.group_by(["season"]):
        _write(frame.sort("match_id", "index"), out_dir / f"season_key={str(season).replace('/', '-')}" / "part-0.parquet")

    positions = pl.read_parquet(config.INTERIM / "positions.parquet")
    lineups = pl.read_parquet(config.INTERIM / "lineups.parquet")
    tactics = pl.read_parquet(config.INTERIM / "tactics.parquet")
    minutes = normalize.player_minutes(positions, bounds)
    appearances = clean.appearances(lineups, minutes, tactics, matches)
    results = normalize.football_data_results(pl.read_parquet(config.INTERIM / "football_data.parquet"))

    _write(matches, config.PROCESSED / "matches.parquet")
    _write(bounds, config.PROCESSED / "period_bounds.parquet")
    _write(appearances, config.PROCESSED / "appearances.parquet")
    _write(positions, config.PROCESSED / "positions.parquet")
    _write(tactics, config.PROCESSED / "tactics.parquet")
    _write(results, config.PROCESSED / "results.parquet")
    _write(pl.read_parquet(config.INTERIM / "freeze_frames.parquet"), config.PROCESSED / "freeze_frames.parquet")
    three_sixty = config.INTERIM / "three_sixty.parquet"
    if three_sixty.exists():
        shutil.copyfile(three_sixty, config.PROCESSED / "three_sixty.parquet")

    counts = {
        "matches": matches.height,
        "events": events.height,
        "locations_clipped": clipped,
        "appearances": appearances.height,
        "results": results.height,
    }
    log.info("processed: %s", counts)
    return counts


def processed_tables() -> dict[str, pl.DataFrame | pl.LazyFrame]:
    return {
        "events": store.events(),
        "matches": store.matches(),
        "appearances": store.appearances(),
        "tactics": store.tactics(),
        "results": store.results(),
    }


def validate_processed() -> list[validate.Result]:
    """Run every data-quality rule on the processed tables and stamp the result."""
    results = validate.run(processed_tables())
    validate.write_report(results, config.REPORTS / "data_quality.md")
    validate.write_stamp(results, store.VALIDATION_STAMP)
    failed = [r.code for r in results if not r.passed]
    log.info("validation: %d rules, gate %s, not passed: %s", len(results),
             "passed" if validate.gate_passed(results) else "FAILED", failed or "none")
    return results
