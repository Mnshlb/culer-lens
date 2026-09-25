"""Leak-free rolling features.

Every feature for match t is computed from matches 1..t-1 of the same team:

    Feature_t = f(M_1, ..., M_{t-1})

The current match is always excluded by shifting one row *before* the window
is applied. ``tests/unit/test_leakage.py`` checks this property directly by
perturbing match t and asserting that its own features do not move.
"""

from __future__ import annotations

from collections.abc import Sequence

import polars as pl


def add_rolling_means(
    frame: pl.DataFrame,
    *,
    by: str | Sequence[str],
    order: Sequence[str],
    cols: Sequence[str],
    windows: Sequence[int],
    prefix: str = "",
    min_samples: int = 1,
) -> pl.DataFrame:
    """Mean of the previous ``w`` rows of each group, excluding the current row.

    Missing values inside the window are ignored (mean over available rows), so
    a window that crosses a match without event data averages the matches that
    do have it. ``{prefix}n_{col}_{w}`` counts how many values were available.
    """
    keys = [by] if isinstance(by, str) else list(by)
    out = frame.sort([*keys, *order])
    exprs: list[pl.Expr] = []
    for col in cols:
        present = pl.col(col).is_not_null().cast(pl.Float64)
        value = pl.col(col).fill_null(0).cast(pl.Float64)
        for w in windows:
            total = value.shift(1).rolling_sum(window_size=w, min_samples=1).over(keys)
            n = present.shift(1).rolling_sum(window_size=w, min_samples=1).over(keys)
            exprs.append(pl.when(n >= min_samples).then(total / n).alias(f"{prefix}{col}_{w}"))
    return out.with_columns(exprs)


def add_ewm(
    frame: pl.DataFrame,
    *,
    by: str | Sequence[str],
    order: Sequence[str],
    cols: Sequence[str],
    half_life: float,
    prefix: str = "",
) -> pl.DataFrame:
    """Exponentially weighted mean of previous rows (current row excluded)."""
    keys = [by] if isinstance(by, str) else list(by)
    out = frame.sort([*keys, *order])
    return out.with_columns(
        [
            pl.col(c)
            .shift(1)
            .ewm_mean(half_life=half_life, ignore_nulls=True)
            .over(keys)
            .alias(f"{prefix}{c}_ewm")
            for c in cols
        ]
    )


def add_season_to_date(
    frame: pl.DataFrame,
    *,
    by: str,
    season: str,
    order: Sequence[str],
    cols: Sequence[str],
    prefix: str = "",
) -> pl.DataFrame:
    """Per-match average of each column over earlier matches in the same season."""
    keys = [by, season]
    out = frame.sort([*keys, *order])
    exprs: list[pl.Expr] = [
        (pl.int_range(pl.len()).over(keys)).alias(f"{prefix}matches_played"),
    ]
    for c in cols:
        value = pl.col(c).fill_null(0).cast(pl.Float64)
        present = pl.col(c).is_not_null().cast(pl.Float64)
        prior_sum = value.cum_sum().over(keys) - value
        prior_n = present.cum_sum().over(keys) - present
        exprs.append(pl.when(prior_n > 0).then(prior_sum / prior_n).alias(f"{prefix}{c}_std"))
    return out.with_columns(exprs)


def add_days_since(
    frame: pl.DataFrame, *, by: str, date_col: str, name: str = "days_rest"
) -> pl.DataFrame:
    out = frame.sort([by, date_col])
    return out.with_columns(
        (pl.col(date_col) - pl.col(date_col).shift(1).over(by)).dt.total_days().alias(name)
    )
