"""Barcelona Intelligence Player Rating (BIPR) and per-match ratings.

BIPR is a transparent, position-specific composite, not an objective truth:

1. Seven **pillars** (passing, creation, progression, carrying, defending,
   shooting, ball security), each the mean percentile of a few per-90
   metrics. Percentiles are taken within the player's position family against
   a fixed **reference population**: every outfield player-season with at
   least 900 minutes in La Liga 2015/16, the only season with every club.
2. An **overall** score: the pillars weighted differently per position family
   (a centre-back is not judged on shooting). It stays on the 0-100 pillar
   scale, so ``overall = 88`` means "on the weighted pillars, this player sits
   around the 88th percentile of the reference population on average".
3. ``overall_pct`` ranks the overall score itself against the reference
   population's scores. It saturates at 100 for the very best players, which
   is why the headline number is the weighted score, not the rank.

Goalkeepers are not rated: judging shot-stopping needs post-shot xG, which the
open data does not include.

Match ratings use the same pillars on a single match (per 90, against a
reference of 2015/16 player-matches of at least 45 minutes). The percentile p
of the match composite is shrunk towards the median for short appearances,
``p' = 0.5 + (p - 0.5) * sqrt(min(minutes, 90) / 90)``, because per-90 rates
from a 20-minute cameo are extreme, and then mapped to
``6.5 + Φ⁻¹(p')``: a median full-match performance scores 6.5, the top 2.5%
of reference performances score above 8.5, and the scale tops out at 9.8.
"""

from __future__ import annotations

import numpy as np
import polars as pl
from scipy.stats import norm

REFERENCE_SEASON = "2015/2016"
MIN_MINUTES_SEASON = 900
MIN_MINUTES_MATCH_REFERENCE = 45
MIN_MINUTES_MATCH_RATING = 20

PILLARS: dict[str, list[tuple[str, int]]] = {
    "passing": [
        ("passes_completed_p90", 1),
        ("pass_completion", 1),
        ("xt_pass_p90", 1),
        ("final_third_entries_p90", 1),
    ],
    "creation": [
        ("xa_p90", 1),
        ("key_passes_p90", 1),
        ("box_entries_p90", 1),
        ("through_balls_p90", 1),
    ],
    "progression": [("progressive_passes_p90", 1), ("progressive_carries_p90", 1), ("xt_p90", 1)],
    "carrying": [
        ("progressive_carries_p90", 1),
        ("dribbles_completed_p90", 1),
        ("xt_carry_p90", 1),
    ],
    "defending": [
        ("padj_tackles_p90", 1),
        ("padj_interceptions_p90", 1),
        ("padj_pressures_p90", 1),
        ("padj_recoveries_p90", 1),
        ("aerials_won_p90", 1),
    ],
    "shooting": [("npxg_p90", 1), ("shots_p90", 1), ("touches_in_box_p90", 1), ("np_goals_p90", 1)],
    "security": [("turnovers_p90", -1), ("pass_completion", 1)],
}

WEIGHTS: dict[str, dict[str, float]] = {
    "CB": {
        "defending": 0.35,
        "passing": 0.25,
        "progression": 0.20,
        "security": 0.10,
        "carrying": 0.05,
        "creation": 0.05,
        "shooting": 0.0,
    },
    "FB": {
        "defending": 0.25,
        "progression": 0.20,
        "creation": 0.20,
        "passing": 0.15,
        "carrying": 0.10,
        "security": 0.10,
        "shooting": 0.0,
    },
    "MF": {
        "passing": 0.25,
        "progression": 0.20,
        "defending": 0.20,
        "creation": 0.15,
        "security": 0.10,
        "carrying": 0.05,
        "shooting": 0.05,
    },
    "AM": {
        "creation": 0.25,
        "carrying": 0.20,
        "shooting": 0.20,
        "progression": 0.15,
        "passing": 0.10,
        "defending": 0.05,
        "security": 0.05,
    },
    "FW": {
        "shooting": 0.40,
        "creation": 0.20,
        "carrying": 0.10,
        "progression": 0.10,
        "passing": 0.10,
        "defending": 0.05,
        "security": 0.05,
    },
}
FAMILIES = tuple(WEIGHTS)
METRICS = sorted({m for items in PILLARS.values() for m, _ in items})


def add_rates(frame: pl.DataFrame) -> pl.DataFrame:
    """Per-90 rates for the rating metrics on any aggregate (season, window or single match)."""
    per90 = [
        "passes_completed",
        "xt_pass",
        "xt_carry",
        "xt",
        "final_third_entries",
        "xa",
        "key_passes",
        "box_entries",
        "through_balls",
        "progressive_passes",
        "progressive_carries",
        "dribbles_completed",
        "padj_tackles",
        "padj_interceptions",
        "padj_pressures",
        "padj_recoveries",
        "aerials_won",
        "npxg",
        "shots",
        "touches_in_box",
        "np_goals",
        "turnovers",
    ]
    return frame.with_columns(
        [(pl.col(m) / pl.col("minutes") * 90).alias(f"{m}_p90") for m in per90]
        + [(pl.col("passes_completed") / pl.col("passes")).alias("pass_completion")]
    )


def build_reference(frame: pl.DataFrame) -> pl.DataFrame:
    """Long table (family, metric, sorted values) used for every percentile lookup."""
    rows = []
    for family in FAMILIES:
        sub = frame.filter(pl.col("position_family") == family)
        for metric in METRICS:
            vals = sub[metric].drop_nulls().drop_nans().sort().to_numpy()
            rows.append({"family": family, "metric": metric, "values": vals.tolist()})
    return pl.DataFrame(
        rows, schema={"family": pl.String, "metric": pl.String, "values": pl.List(pl.Float64)}
    )


def _pct(values: np.ndarray, ref: np.ndarray) -> np.ndarray:
    """Mid-rank empirical percentile of each value against the reference, 0-100."""
    if ref.size == 0:
        return np.full(values.shape, np.nan)
    lo = np.searchsorted(ref, values, side="left")
    hi = np.searchsorted(ref, values, side="right")
    out = 100.0 * (lo + 0.5 * (hi - lo)) / ref.size
    return np.where(np.isnan(values), np.nan, out)


def _composite(pillars: dict[str, np.ndarray], family: str) -> np.ndarray:
    w = WEIGHTS[family]
    num = sum(np.nan_to_num(pillars[p]) * w[p] for p in w)
    den = sum((~np.isnan(pillars[p])) * w[p] for p in w)
    with np.errstate(invalid="ignore", divide="ignore"):
        return np.where(den > 0, num / den, np.nan)


def score(frame: pl.DataFrame, reference_frame: pl.DataFrame) -> pl.DataFrame:
    """Add pillar scores and the overall percentile to ``frame``.

    ``frame`` and ``reference_frame`` must both carry the rate columns
    (``add_rates``) and ``position_family``. ``reference_frame`` is the reference
    population: metric percentiles and composite percentiles are both taken
    against it.
    """
    reference = build_reference(reference_frame)
    lookup = {
        (r["family"], r["metric"]): np.asarray(r["values"], dtype=float)
        for r in reference.iter_rows(named=True)
    }
    parts = []
    for family in FAMILIES:
        sub = frame.filter(pl.col("position_family") == family)
        if sub.height == 0:
            continue
        ref_sub = reference_frame.filter(pl.col("position_family") == family)
        pillars: dict[str, np.ndarray] = {}
        ref_pillars: dict[str, np.ndarray] = {}
        for pillar, items in PILLARS.items():
            cols, ref_cols = [], []
            for metric, sign in items:
                ref = lookup[(family, metric)]
                p = _pct(sub[metric].cast(pl.Float64).fill_nan(None).to_numpy().astype(float), ref)
                rp = _pct(
                    ref_sub[metric].cast(pl.Float64).fill_nan(None).to_numpy().astype(float), ref
                )
                cols.append(p if sign > 0 else 100 - p)
                ref_cols.append(rp if sign > 0 else 100 - rp)
            with np.errstate(invalid="ignore"):
                pillars[pillar] = (
                    np.nanmean(np.vstack(cols), axis=0) if cols else np.full(sub.height, np.nan)
                )
                ref_pillars[pillar] = np.nanmean(np.vstack(ref_cols), axis=0)
        comp = _composite(pillars, family)
        ref_comp = np.sort(
            _composite(ref_pillars, family)[~np.isnan(_composite(ref_pillars, family))]
        )
        overall = _pct(comp, ref_comp)
        parts.append(
            sub.with_columns(
                *[
                    pl.Series(f"pillar_{k}", np.round(v, 1)).fill_nan(None)
                    for k, v in pillars.items()
                ],
                pl.Series("overall", np.round(comp, 1)).fill_nan(None),
                pl.Series("overall_pct", np.round(overall, 1)).fill_nan(None),
            )
        )
    if not parts:
        return frame
    scored = pl.concat(parts, how="diagonal_relaxed")
    rest = frame.filter(
        ~pl.col("position_family").is_in(list(FAMILIES)) | pl.col("position_family").is_null()
    )
    return pl.concat([scored, rest], how="diagonal_relaxed")


RAW_COLUMNS = [
    "passes",
    "passes_completed",
    "xt",
    "xt_pass",
    "xt_carry",
    "final_third_entries",
    "xa",
    "key_passes",
    "box_entries",
    "through_balls",
    "progressive_passes",
    "progressive_carries",
    "dribbles_completed",
    "padj_tackles",
    "padj_interceptions",
    "padj_pressures",
    "padj_recoveries",
    "aerials_won",
    "npxg",
    "shots",
    "touches_in_box",
    "np_goals",
    "turnovers",
]


def aggregate(player_matches: pl.DataFrame, by: list[str]) -> pl.DataFrame:
    """Sum player-match rows over ``by`` (a season, a window...) ready for ``score``.

    The position family is the one the player spent most minutes in.
    """
    fam = (
        player_matches.group_by([*by, "position_family"])
        .agg(pl.col("minutes").sum().alias("_m"))
        .sort("_m", descending=True)
        .group_by(by)
        .agg(pl.col("position_family").first())
    )
    labels = [
        pl.col(c).last()
        for c in ("display_name", "team")
        if c not in by and c in player_matches.columns
    ]
    agg = player_matches.group_by(by).agg(
        *labels,
        pl.len().alias("appearances"),
        pl.col("started").sum().alias("starts"),
        pl.col("minutes").sum(),
        *[pl.col(c).sum() for c in RAW_COLUMNS],
    )
    return add_rates(agg.join(fam, on=by, how="left"))


def match_rating_scale(overall_pct: pl.Expr, minutes: pl.Expr) -> pl.Expr:
    shrink = (minutes.clip(upper_bound=90) / 90).sqrt()
    p = (0.5 + (overall_pct / 100 - 0.5) * shrink).clip(0.0005, 0.9995)
    z = p.map_batches(
        lambda s: pl.Series(norm.ppf(s.to_numpy(allow_copy=True))).fill_nan(None),
        return_dtype=pl.Float64,
    )
    return 6.5 + z
