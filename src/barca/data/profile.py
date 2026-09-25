"""Column profiling: the formal description of every important table."""

from __future__ import annotations

import polars as pl

NUMERIC = (
    pl.Int8,
    pl.Int16,
    pl.Int32,
    pl.Int64,
    pl.UInt8,
    pl.UInt16,
    pl.UInt32,
    pl.UInt64,
    pl.Float32,
    pl.Float64,
)


def _is_numeric(dtype: pl.DataType) -> bool:
    return isinstance(dtype, NUMERIC)


def profile_column(s: pl.Series) -> dict[str, object]:
    n = s.len()
    nulls = s.null_count()
    row: dict[str, object] = {
        "column": s.name,
        "dtype": str(s.dtype),
        "count": n - nulls,
        "unique": s.n_unique() if not isinstance(s.dtype, pl.List) else None,
        "missing": nulls,
        "missing_pct": round(100 * nulls / n, 2) if n else None,
    }
    if _is_numeric(s.dtype) and n - nulls > 0:
        v = s.drop_nulls().cast(pl.Float64)
        q1, q3 = v.quantile(0.25), v.quantile(0.75)
        iqr = (q3 or 0) - (q1 or 0)
        lo, hi = (q1 or 0) - 1.5 * iqr, (q3 or 0) + 1.5 * iqr
        row.update(
            min=v.min(),
            p01=v.quantile(0.01),
            q1=q1,
            median=v.median(),
            mean=v.mean(),
            q3=q3,
            p99=v.quantile(0.99),
            max=v.max(),
            std=v.std(),
            outliers_iqr=int(((v < lo) | (v > hi)).sum()) if iqr > 0 else 0,
        )
    elif s.dtype == pl.String and n - nulls > 0:
        vc = s.drop_nulls().value_counts(sort=True)
        row.update(top=vc[s.name][0], top_freq=int(vc["count"][0]))
    elif s.dtype == pl.Boolean:
        row.update(true_pct=round(100 * (s.sum() or 0) / n, 2) if n else None)
    return row


def profile_frame(frame: pl.DataFrame, columns: list[str] | None = None) -> pl.DataFrame:
    cols = columns or frame.columns
    rows = [profile_column(frame[c]) for c in cols]
    return pl.from_dicts(rows, infer_schema_length=None)


def duplicates(frame: pl.DataFrame, key: list[str]) -> int:
    return frame.height - frame.select(key).unique().height


def profile_by_type(events: pl.DataFrame, event_type: str, columns: list[str]) -> pl.DataFrame:
    """Profile only the rows of one event type: sparse columns become dense."""
    return profile_frame(events.filter(pl.col("type") == event_type), columns).with_columns(
        pl.lit(event_type).alias("event_type")
    )


def to_markdown(frame: pl.DataFrame, float_fmt: str = "{:.3g}") -> str:
    cols = frame.columns
    lines = ["| " + " | ".join(cols) + " |", "|" + "---|" * len(cols)]
    for row in frame.iter_rows():
        cells = []
        for v in row:
            if v is None:
                cells.append("")
            elif isinstance(v, float):
                cells.append(float_fmt.format(v))
            else:
                cells.append(str(v))
        lines.append("| " + " | ".join(cells) + " |")
    return "\n".join(lines)
