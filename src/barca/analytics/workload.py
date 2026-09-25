"""Player Workload Index.

This is **not** a fatigue or injury-risk measure. It summarises how much a
player has been asked to play recently, from the minutes the data records,
on a 0-100 scale with fixed, interpretable reference points:

| Component | Weight | Reaches 1.0 at |
|---|---|---|
| minutes in the last 7 days | 0.30 | 180 (two full matches) |
| minutes in the last 14 days | 0.25 | 360 (four full matches) |
| minutes in the last 30 days | 0.15 | 630 (seven full matches) |
| consecutive starts | 0.15 | 8 in a row |
| short rest since the last appearance | 0.15 | ≤ 2 days (0 at ≥ 7 days) |

Each component is capped at 1, so the index is a weighted sum times 100.
Fixed constants (rather than percentiles fitted to the data) keep the index
free of any information from the future and make every number explainable.

**Coverage caveat.** The data holds La Liga matches (most, not all, of
Barcelona's) and three Champions League finals. Cup and European
fixtures are missing, so the index measures *observed league workload* and
understates true load in congested periods.
"""

from __future__ import annotations

import polars as pl

WEIGHTS = {"m7": 0.30, "m14": 0.25, "m30": 0.15, "streak": 0.15, "rest": 0.15}
BANDS = [(80, "High"), (60, "Elevated"), (35, "Moderate"), (0, "Low")]


def index_expr() -> pl.Expr:
    m7 = (pl.col("minutes_7d") / 180).clip(0, 1)
    m14 = (pl.col("minutes_14d") / 360).clip(0, 1)
    m30 = (pl.col("minutes_30d") / 630).clip(0, 1)
    streak = (pl.col("consecutive_starts") / 8).clip(0, 1)
    rest = ((7 - pl.col("days_since_last_app").fill_null(30)) / 5).clip(0, 1)
    w = WEIGHTS
    return (
        100
        * (w["m7"] * m7 + w["m14"] * m14 + w["m30"] * m30 + w["streak"] * streak + w["rest"] * rest)
    ).round(0)


def band_expr(col: str = "workload_index") -> pl.Expr:
    expr = pl.lit("Low")
    for threshold, name in reversed(BANDS):
        expr = pl.when(pl.col(col) >= threshold).then(pl.lit(name)).otherwise(expr)
    return expr


def components(row: dict) -> dict[str, float]:
    """Contribution of each component to one player's index (for the app's breakdown)."""
    parts = {
        "minutes_7d": min(row["minutes_7d"] / 180, 1) * WEIGHTS["m7"],
        "minutes_14d": min(row["minutes_14d"] / 360, 1) * WEIGHTS["m14"],
        "minutes_30d": min(row["minutes_30d"] / 630, 1) * WEIGHTS["m30"],
        "consecutive_starts": min(row["consecutive_starts"] / 8, 1) * WEIGHTS["streak"],
        "rest": min(max((7 - (row.get("days_since_last_app") or 30)) / 5, 0), 1) * WEIGHTS["rest"],
    }
    return {k: round(100 * v, 1) for k, v in parts.items()}
