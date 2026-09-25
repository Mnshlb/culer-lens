"""Types, names and units.

Everything here is a deterministic, lossless re-expression of the interim
tables: parse dates and clock strings, attach canonical team names, add the
Barcelona perspective to matches, and compute minutes played from lineup
spells. Error correction lives in ``clean``.
"""

from __future__ import annotations

from functools import lru_cache

import polars as pl

from barca import config
from barca.data import sources

# football-data spells a few clubs differently across seasons.
FOOTBALL_DATA_NAME_FIXES = {"Villareal": "Villarreal"}

# Clock value (seconds) at which each period starts on StatsBomb's match clock.
PERIOD_START_S = {1: 0, 2: 45 * 60, 3: 90 * 60, 4: 105 * 60, 5: 120 * 60}

POSITION_GROUP = {
    "Goalkeeper": "GK",
    "Right Back": "FB",
    "Left Back": "FB",
    "Right Wing Back": "FB",
    "Left Wing Back": "FB",
    "Right Center Back": "CB",
    "Left Center Back": "CB",
    "Center Back": "CB",
    "Right Defensive Midfield": "DM",
    "Left Defensive Midfield": "DM",
    "Center Defensive Midfield": "DM",
    "Right Center Midfield": "CM",
    "Left Center Midfield": "CM",
    "Center Midfield": "CM",
    "Right Midfield": "W",
    "Left Midfield": "W",
    "Right Attacking Midfield": "AM",
    "Left Attacking Midfield": "AM",
    "Center Attacking Midfield": "AM",
    "Right Wing": "W",
    "Left Wing": "W",
    "Right Center Forward": "ST",
    "Left Center Forward": "ST",
    "Center Forward": "ST",
    "Secondary Striker": "ST",
}

# Coarser families used where sample sizes are small (ratings, lineup slots).
POSITION_FAMILY = {
    "GK": "GK",
    "CB": "CB",
    "FB": "FB",
    "DM": "MF",
    "CM": "MF",
    "AM": "AM",
    "W": "AM",
    "ST": "FW",
}


@lru_cache
def team_reference() -> pl.DataFrame:
    return pl.read_csv(config.REFERENCE / "teams.csv")


def _lookup(source_column: str, target: str) -> dict[str, str]:
    ref = team_reference().drop_nulls(source_column)
    return dict(zip(ref[source_column], ref[target], strict=True))


def statsbomb_team_name(expr: pl.Expr) -> pl.Expr:
    return expr.replace(_lookup("statsbomb_name", "name"))


def football_data_team_name(expr: pl.Expr) -> pl.Expr:
    return expr.replace(FOOTBALL_DATA_NAME_FIXES).replace(_lookup("football_data_name", "name"))


def clock_to_seconds(expr: pl.Expr) -> pl.Expr:
    """'MM:SS' (lineups) or 'HH:MM:SS.mmm' (event timestamps) -> seconds."""
    parts = expr.str.split(":")
    n = parts.list.len()
    hours = pl.when(n == 3).then(parts.list.get(0, null_on_oob=True).cast(pl.Float64)).otherwise(0.0)
    minutes = pl.when(n == 3).then(parts.list.get(1, null_on_oob=True)).otherwise(parts.list.get(0, null_on_oob=True))
    seconds = parts.list.get(-1, null_on_oob=True)
    return hours * 3600 + minutes.cast(pl.Float64) * 60 + seconds.cast(pl.Float64)


def season_start_year(expr: pl.Expr) -> pl.Expr:
    return expr.str.slice(0, 4).cast(pl.Int16)


# Matches --------------------------------------------------------------------------


def matches(raw: pl.DataFrame) -> pl.DataFrame:
    out = raw.with_columns(
        pl.col("match_date").str.to_date().alias("date"),
        (pl.col("match_date") + " " + pl.col("kick_off").fill_null("00:00:00.000"))
        .str.to_datetime("%Y-%m-%d %H:%M:%S%.f", strict=False)
        .alias("kickoff"),
        season_start_year(pl.col("season")).alias("season_start"),
        statsbomb_team_name(pl.col("home_team")).alias("home"),
        statsbomb_team_name(pl.col("away_team")).alias("away"),
    )
    is_home = pl.col("home_team") == sources.BARCELONA
    is_away = pl.col("away_team") == sources.BARCELONA
    barca_goals = pl.when(is_home).then(pl.col("home_score")).otherwise(pl.col("away_score"))
    opp_goals = pl.when(is_home).then(pl.col("away_score")).otherwise(pl.col("home_score"))
    out = out.with_columns(
        (is_home | is_away).alias("is_barca"),
        pl.when(is_home).then(pl.lit("H")).when(is_away).then(pl.lit("A")).alias("barca_venue"),
        pl.when(is_home).then(pl.col("away")).when(is_away).then(pl.col("home")).alias("opponent"),
        pl.when(is_home | is_away).then(barca_goals).alias("barca_goals"),
        pl.when(is_home | is_away).then(opp_goals).alias("opponent_goals"),
    )
    return out.with_columns(
        pl.when(pl.col("barca_goals") > pl.col("opponent_goals"))
        .then(pl.lit("W"))
        .when(pl.col("barca_goals") == pl.col("opponent_goals"))
        .then(pl.lit("D"))
        .when(pl.col("barca_goals") < pl.col("opponent_goals"))
        .then(pl.lit("L"))
        .alias("barca_result"),
        pl.when(pl.col("barca_venue") == "H")
        .then(pl.col("home_manager"))
        .when(pl.col("barca_venue") == "A")
        .then(pl.col("away_manager"))
        .alias("barca_manager"),
    ).sort("kickoff", "match_id")


# football-data --------------------------------------------------------------------

_FD_INT = ["FTHG", "FTAG", "HTHG", "HTAG", "HS", "AS", "HST", "AST", "HC", "AC", "HF", "AF", "HY", "AY", "HR", "AR"]
_FD_ODDS = {
    "b365": ("B365H", "B365D", "B365A"),
    "ps_close": ("PSCH", "PSCD", "PSCA"),
    "avg": ("BbAvH", "BbAvD", "BbAvA"),
    "avg_new": ("AvgH", "AvgD", "AvgA"),
}


def football_data_date(expr: pl.Expr) -> pl.Expr:
    """Dates switch from dd/mm/yy to dd/mm/yyyy in 2018. Parsing a two-digit
    year with %Y silently yields year 00xx, so the format is chosen by length."""
    return (
        pl.when(expr.str.len_chars() == 8)
        .then(expr.str.strptime(pl.Date, "%d/%m/%y", strict=False))
        .otherwise(expr.str.strptime(pl.Date, "%d/%m/%Y", strict=False))
    )


def football_data_results(raw: pl.DataFrame) -> pl.DataFrame:
    frame = raw
    for col in _FD_INT + [c for cols in _FD_ODDS.values() for c in cols]:
        if col not in frame.columns:
            frame = frame.with_columns(pl.lit(None, dtype=pl.String).alias(col))
    frame = frame.with_columns(
        football_data_date(pl.col("Date")).alias("date"),
        football_data_team_name(pl.col("HomeTeam")).alias("home"),
        football_data_team_name(pl.col("AwayTeam")).alias("away"),
        *[pl.col(c).cast(pl.Float64, strict=False).cast(pl.Int16, strict=False) for c in _FD_INT],
        *[pl.col(c).cast(pl.Float64, strict=False) for cols in _FD_ODDS.values() for c in cols],
    )
    avg = [
        pl.coalesce(pl.col(a), pl.col(b)).alias(f"odds_avg_{s}")
        for a, b, s in zip(_FD_ODDS["avg"], _FD_ODDS["avg_new"], "hda", strict=True)
    ]
    return frame.select(
        "season",
        season_start_year(pl.col("season")).alias("season_start"),
        "date",
        "home",
        "away",
        pl.col("FTHG").alias("home_goals"),
        pl.col("FTAG").alias("away_goals"),
        pl.col("HTHG").alias("home_goals_ht"),
        pl.col("HTAG").alias("away_goals_ht"),
        pl.col("HS").alias("home_shots"),
        pl.col("AS").alias("away_shots"),
        pl.col("HST").alias("home_sot"),
        pl.col("AST").alias("away_sot"),
        pl.col("HC").alias("home_corners"),
        pl.col("AC").alias("away_corners"),
        pl.col("HF").alias("home_fouls"),
        pl.col("AF").alias("away_fouls"),
        pl.col("HY").alias("home_yellow"),
        pl.col("AY").alias("away_yellow"),
        pl.col("HR").alias("home_red"),
        pl.col("AR").alias("away_red"),
        pl.col("B365H").alias("odds_b365_h"),
        pl.col("B365D").alias("odds_b365_d"),
        pl.col("B365A").alias("odds_b365_a"),
        pl.col("PSCH").alias("odds_psc_h"),
        pl.col("PSCD").alias("odds_psc_d"),
        pl.col("PSCA").alias("odds_psc_a"),
        *avg,
    ).sort("date", "home")


# Events ---------------------------------------------------------------------------


def events(raw: pl.LazyFrame) -> pl.LazyFrame:
    return raw.with_columns(
        clock_to_seconds(pl.col("timestamp")).alias("period_seconds"),
        (pl.col("minute").cast(pl.Float64) + pl.col("second").cast(pl.Float64) / 60).alias("clock_minute"),
        statsbomb_team_name(pl.col("team")).alias("team_name"),
        (pl.col("team") == sources.BARCELONA).alias("is_barca"),
        pl.col("position").replace_strict(POSITION_GROUP, default=None).alias("position_group"),
    )


def period_bounds(events_lf: pl.LazyFrame) -> pl.DataFrame:
    """Per match and period: start clock, end clock and duration in seconds.

    The end of a period is the latest event clock in it (the Half End event),
    so durations include stoppage time. Penalty shoot-outs (period 5) are
    excluded because they are not playing time.
    """
    starts = pl.DataFrame(
        {"period": list(PERIOD_START_S), "start_s": list(PERIOD_START_S.values())},
        schema={"period": pl.Int8, "start_s": pl.Float64},
    )
    bounds = (
        events_lf.filter(pl.col("period") <= 4)
        .group_by("match_id", "period")
        .agg((pl.col("minute").cast(pl.Float64) * 60 + pl.col("second")).max().alias("end_s"))
        .collect()
        .join(starts, on="period", how="left")
        .with_columns((pl.col("end_s") - pl.col("start_s")).clip(lower_bound=0).alias("duration_s"))
        .sort("match_id", "period")
        .with_columns(
            (pl.col("duration_s").cum_sum().over("match_id") - pl.col("duration_s")).alias("elapsed_before_s")
        )
    )
    return bounds


def _elapsed(clock_s: pl.Expr, period: pl.Expr, prefix: str) -> pl.Expr:
    return (
        pl.col(f"{prefix}elapsed_before_s") + (clock_s - pl.col(f"{prefix}start_s"))
    ).clip(lower_bound=pl.col(f"{prefix}elapsed_before_s"))


def player_minutes(positions: pl.DataFrame, bounds: pl.DataFrame) -> pl.DataFrame:
    """Minutes on the pitch per player-match, including stoppage time.

    Lineup spells use the match clock (the second half restarts at 45:00), which
    overlaps with first-half stoppage time. Each clock value is therefore mapped
    to elapsed playing time using the period it belongs to.
    """
    total = bounds.group_by("match_id").agg(pl.col("duration_s").sum().alias("match_s"))
    b = bounds.select("match_id", "period", "start_s", "elapsed_before_s")
    spells = (
        positions.with_columns(
            clock_to_seconds(pl.col("from_clock")).alias("from_s"),
            clock_to_seconds(pl.col("to_clock")).alias("to_s"),
        )
        .join(b.rename({"period": "from_period"}), on=["match_id", "from_period"], how="left")
        .with_columns(_elapsed(pl.col("from_s"), pl.col("from_period"), "").alias("from_elapsed"))
        .drop("start_s", "elapsed_before_s")
        .join(
            b.rename({"period": "to_period", "start_s": "to_start_s", "elapsed_before_s": "to_elapsed_before_s"}),
            on=["match_id", "to_period"],
            how="left",
        )
        .join(total, on="match_id", how="left")
        .with_columns(
            pl.when(pl.col("to_s").is_null())
            .then(pl.col("match_s"))
            .otherwise(_elapsed(pl.col("to_s"), pl.col("to_period"), "to_"))
            .alias("to_elapsed")
        )
        .with_columns(((pl.col("to_elapsed") - pl.col("from_elapsed")) / 60).clip(lower_bound=0).alias("minutes"))
    )
    return (
        spells.sort("spell")
        .group_by("match_id", "team_id", "player_id")
        .agg(
            pl.col("minutes").sum(),
            (pl.col("start_reason").first() == "Starting XI").alias("started"),
            pl.col("position").first().alias("start_position"),
            pl.col("position").alias("positions"),
            (pl.col("from_elapsed").first() / 60).alias("on_minute"),
            (pl.col("to_elapsed").last() / 60).alias("off_minute"),
            pl.col("end_reason").last().alias("end_reason"),
            pl.col("match_s").first().truediv(60).alias("match_minutes"),
        )
        .with_columns(
            pl.col("start_position").replace_strict(POSITION_GROUP, default=None).alias("position_group"),
        )
        .with_columns(
            pl.col("position_group").replace_strict(POSITION_FAMILY, default=None).alias("position_family"),
        )
    )
