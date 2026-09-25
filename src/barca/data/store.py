"""Read access to the processed (cleaned and validated) tables."""

from __future__ import annotations

from pathlib import Path

import polars as pl

from barca import config

VALIDATION_STAMP = config.PROCESSED / "_validation.json"


def _read(name: str, root: Path | None = None) -> pl.DataFrame:
    return pl.read_parquet((root or config.PROCESSED) / f"{name}.parquet")


def matches() -> pl.DataFrame:
    return _read("matches")


def events(root: Path | None = None) -> pl.LazyFrame:
    base = (root or config.PROCESSED) / "events"
    return pl.scan_parquet(base / "**" / "*.parquet", hive_partitioning=True).drop("season_key", strict=False)


def appearances() -> pl.DataFrame:
    return _read("appearances")


def positions() -> pl.DataFrame:
    return _read("positions")


def tactics() -> pl.DataFrame:
    return _read("tactics")


def results() -> pl.DataFrame:
    return _read("results")


def period_bounds() -> pl.DataFrame:
    return _read("period_bounds")


def freeze_frames() -> pl.DataFrame:
    return _read("freeze_frames")


def three_sixty() -> pl.DataFrame | None:
    path = config.PROCESSED / "three_sixty.parquet"
    return pl.read_parquet(path) if path.exists() else None


def features(name: str) -> pl.DataFrame:
    return pl.read_parquet(config.FEATURES / f"{name}.parquet")
