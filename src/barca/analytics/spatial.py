"""Spatial analytics: zones, channels, heatmap grids and player spatial profiles.

StatsBomb coordinates put every event in the acting team's frame (attacking
towards x = 120). y = 0 is the team's *left* touchline (left-backs average
y ≈ 12, right-backs y ≈ 68).

Zones follow the positional-play grid: three thirds along the pitch and five
vertical channels across it (wide left, left half-space, centre, right
half-space, wide right). The half-spaces run between the edge of the penalty
area (y = 18 / 62) and the edge of the six-yard box (y = 30 / 50).

These are *action* heatmaps: they show where a player did recorded things
with or around the ball, not where the player physically was.
"""

from __future__ import annotations

from datetime import date

import numpy as np
import polars as pl

from barca.analytics import definitions as D

THIRD_EDGES = [0.0, 40.0, 80.0, 120.0]
THIRDS = ["defensive", "middle", "attacking"]
CHANNEL_EDGES = [0.0, 18.0, 30.0, 50.0, 62.0, 80.0]
CHANNELS = ["left_wing", "left_half_space", "centre", "right_half_space", "right_wing"]


def with_zones[F: (pl.LazyFrame, pl.DataFrame)](events: F) -> F:
    x = pl.col("x").clip(0, 119.999)
    y = pl.col("y").clip(0, 79.999)
    third = (
        pl.when(x < 40)
        .then(pl.lit("defensive"))
        .when(x < 80)
        .then(pl.lit("middle"))
        .otherwise(pl.lit("attacking"))
    )
    channel = (
        pl.when(y < 18)
        .then(pl.lit("left_wing"))
        .when(y < 30)
        .then(pl.lit("left_half_space"))
        .when(y < 50)
        .then(pl.lit("centre"))
        .when(y < 62)
        .then(pl.lit("right_half_space"))
        .otherwise(pl.lit("right_wing"))
    )
    return events.with_columns(third.alias("third"), channel.alias("channel"))


def filter_actions[F: (pl.LazyFrame, pl.DataFrame)](events: F, family: str) -> F:
    if family not in D.ACTION_FAMILIES:
        raise ValueError(
            f"unknown action family {family!r}; choose from {sorted(D.ACTION_FAMILIES)}"
        )
    return events.filter(D.ACTION_FAMILIES[family], pl.col("x").is_not_null())


def heatmap_grid(x: np.ndarray, y: np.ndarray, bins: tuple[int, int] = (12, 8)) -> np.ndarray:
    """Counts on a regular grid; shape (bins_x, bins_y) with [0, 0] at the own-goal, left corner."""
    grid, _, _ = np.histogram2d(
        np.clip(x, 0, 119.999), np.clip(y, 0, 79.999), bins=bins, range=[[0, 120], [0, 80]]
    )
    return grid


def zone_counts(events: pl.DataFrame) -> pl.DataFrame:
    """Counts per (third, channel) cell, all 15 cells present."""
    full = pl.DataFrame(
        {"third": [t for t in THIRDS for _ in CHANNELS], "channel": CHANNELS * len(THIRDS)}
    )
    counts = with_zones(events).group_by("third", "channel").agg(pl.len().alias("n"))
    return full.join(counts, on=["third", "channel"], how="left").with_columns(
        pl.col("n").fill_null(0)
    )


def spatial_profile(events: pl.DataFrame) -> dict[str, float | None]:
    """Summary of where a set of actions happened.

    * average position (x, y)
    * share of actions per third and per channel (left = wing + half-space)
    * box involvement: share of actions inside the opponent's penalty area
    * positional spread: standard deviation along and across the pitch, and
      the area (square yards) of the 1-sigma ellipse, a compact measure of how
      much ground the recorded actions cover.
    """
    ev = with_zones(events.filter(pl.col("x").is_not_null()))
    n = ev.height
    if n == 0:
        return {"n": 0}
    xs, ys = ev["x"].to_numpy().astype(float), ev["y"].to_numpy().astype(float)
    cov = np.cov(np.vstack([xs, ys])) if n > 2 else np.zeros((2, 2))
    ellipse = float(np.pi * np.sqrt(max(np.linalg.det(cov), 0.0))) if n > 2 else None
    thirds = ev["third"].value_counts(normalize=True)
    channels = ev["channel"].value_counts(normalize=True)
    share = lambda frame, col, key: float(frame.filter(pl.col(col) == key)["proportion"].sum())  # noqa: E731
    left = share(channels, "channel", "left_wing") + share(channels, "channel", "left_half_space")
    right = share(channels, "channel", "right_wing") + share(
        channels, "channel", "right_half_space"
    )
    return {
        "n": n,
        "avg_x": float(xs.mean()),
        "avg_y": float(ys.mean()),
        "defensive_third": share(thirds, "third", "defensive"),
        "middle_third": share(thirds, "third", "middle"),
        "attacking_third": share(thirds, "third", "attacking"),
        "left": left,
        "centre": share(channels, "channel", "centre"),
        "right": right,
        "box_share": float(ev.filter(D.in_box(pl.col("x"), pl.col("y"))).height / n),
        "spread_x": float(xs.std()),
        "spread_y": float(ys.std()),
        "ellipse_area": ellipse,
    }


def window_matches(
    player_matches: pl.DataFrame,
    *,
    as_of: date | None = None,
    window: str = "season",
    season: str | None = None,
) -> list[int]:
    """Match ids for a player's time window.

    ``window`` is one of ``match`` (the latest match), ``last5``, ``last10`` or
    ``season``. Only matches strictly before ``as_of`` are considered when it is
    given, which is how the app shows what was known before a fixture.
    """
    pm = player_matches.sort("kickoff")
    if as_of is not None:
        pm = pm.filter(pl.col("date") < as_of)
    if pm.height == 0:
        return []
    if window == "season":
        target = season or pm["season"][-1]
        return pm.filter(pl.col("season") == target)["match_id"].to_list()
    size = {"match": 1, "last5": 5, "last10": 10}.get(window)
    if size is None:
        raise ValueError(f"unknown window {window!r}")
    return pm.tail(size)["match_id"].to_list()


def flip_to_left_to_right(frame: pl.DataFrame, flip: pl.Expr) -> pl.DataFrame:
    """Mirror rows where ``flip`` is true, e.g. to draw both teams on one pitch."""
    cols = [c for c in ("x", "end_x") if c in frame.columns]
    rows = [c for c in ("y", "end_y") if c in frame.columns]
    return frame.with_columns(
        [pl.when(flip).then(120 - pl.col(c)).otherwise(pl.col(c)).alias(c) for c in cols]
        + [pl.when(flip).then(80 - pl.col(c)).otherwise(pl.col(c)).alias(c) for c in rows]
    )
