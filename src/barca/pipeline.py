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
from barca.data import load, parse, sources

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
