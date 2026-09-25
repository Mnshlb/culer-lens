"""Model datasets: feature matrices, ordered targets and row metadata."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd
import polars as pl

from barca.features import tables

LEAGUE_CLASSES = ("H", "D", "A")
BARCA_CLASSES = ("W", "D", "L")
TRAIN_START = 2005  # first season with every results-based feature (D-018)
TEST_SEASONS = tuple(range(2008, 2021))  # 2008/09 .. 2020/21


@dataclass
class Dataset:
    X: pd.DataFrame
    y: np.ndarray
    meta: pl.DataFrame  # identifiers, season, targets, market probabilities
    classes: tuple[str, str, str]
    features: list[str]

    def rows(self, mask: np.ndarray) -> Dataset:
        return Dataset(
            self.X[mask].reset_index(drop=True),
            self.y[mask],
            self.meta.filter(pl.Series(mask)),
            self.classes,
            self.features,
        )

    @property
    def season(self) -> np.ndarray:
        return self.meta["season_start"].to_numpy()

    def goals(self) -> tuple[np.ndarray, np.ndarray]:
        """Goals for and against the reference side (home team, or Barcelona)."""
        if self.classes == LEAGUE_CLASSES:
            return self.meta["home_goals"].to_numpy(), self.meta["away_goals"].to_numpy()
        return self.meta["barca_goals"].to_numpy(), self.meta["opp_goals"].to_numpy()


def _matrix(frame: pl.DataFrame, features: list[str]) -> pd.DataFrame:
    return frame.select([pl.col(f).cast(pl.Float64) for f in features]).to_pandas()


def league_dataset(fixtures: pl.DataFrame, start: int = TRAIN_START) -> Dataset:
    features = tables.league_feature_list()
    frame = fixtures.filter(pl.col("season_start") >= start).sort("date", "fixture_id")
    y = (
        frame["result"]
        .replace_strict({c: i for i, c in enumerate(LEAGUE_CLASSES)}, return_dtype=pl.Int64)
        .to_numpy()
    )
    meta = frame.select(
        "fixture_id",
        "date",
        "season",
        "season_start",
        "home",
        "away",
        "home_goals",
        "away_goals",
        "result",
        pl.col("^mkt_.*$"),
    )
    return Dataset(_matrix(frame, features), y, meta, LEAGUE_CLASSES, features)


def barca_dataset(
    barca: pl.DataFrame, start: int = TRAIN_START, include_events: bool = True
) -> Dataset:
    features = tables.barca_feature_list(include_events=include_events)
    frame = barca.filter(pl.col("season_start") >= start).sort("date")
    y = (
        frame["result"]
        .replace_strict({c: i for i, c in enumerate(BARCA_CLASSES)}, return_dtype=pl.Int64)
        .to_numpy()
    )
    meta = frame.select(
        "fixture_id",
        "sb_match_id",
        "date",
        "season",
        "season_start",
        "opponent",
        "is_home",
        "barca_goals",
        "opp_goals",
        "result",
        pl.col("^mkt_.*$"),
    )
    return Dataset(_matrix(frame, features), y, meta, BARCA_CLASSES, features)


def market_probs(meta: pl.DataFrame, book: str, classes: tuple[str, str, str]) -> np.ndarray:
    """Bookmaker probabilities in class order (margin removed); NaN rows where odds are missing."""
    suffix = ("h", "d", "a") if classes == LEAGUE_CLASSES else ("w", "d", "l")
    return meta.select([pl.col(f"mkt_{book}_{s}") for s in suffix]).to_numpy()
