"""Football-aware data-quality rules.

Missing values in event data are mostly *structural*: a completed pass has
no outcome, a pressure has no end location, a Half Start has no player. A
blanket ``dropna()`` would delete most of the dataset. Instead, each rule
states which field is *expected* for which event type (derived from the field
matrix in notebook 01) or which relationship must hold between tables.

Every rule returns the violating rows. ``error`` rules gate the pipeline:
the features stage refuses to run unless they all pass. ``warning`` rules are
reported with a tolerance for known, harmless quirks of the source.
"""

from __future__ import annotations

import json
from collections.abc import Callable
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Literal

import polars as pl

Frame = pl.DataFrame | pl.LazyFrame
Tables = dict[str, Frame]
Severity = Literal["error", "warning"]

EVENT_TYPES = {
    "Pass",
    "Ball Receipt*",
    "Carry",
    "Pressure",
    "Ball Recovery",
    "Duel",
    "Clearance",
    "Dribble",
    "Block",
    "Foul Committed",
    "Foul Won",
    "Goal Keeper",
    "Dribbled Past",
    "Interception",
    "Miscontrol",
    "Dispossessed",
    "Shot",
    "Substitution",
    "Half End",
    "Half Start",
    "Injury Stoppage",
    "Starting XI",
    "Tactical Shift",
    "50/50",
    "Bad Behaviour",
    "Shield",
    "Player Off",
    "Player On",
    "Referee Ball-Drop",
    "Error",
    "Offside",
    "Camera On",
    "Own Goal For",
    "Own Goal Against",
    "Camera off",
}
OUTCOMES = {
    "Pass": {"Incomplete", "Out", "Pass Offside", "Unknown", "Injury Clearance"},
    "Shot": {
        "Goal",
        "Saved",
        "Saved to Post",
        "Saved Off Target",
        "Off T",
        "Post",
        "Wayward",
        "Blocked",
    },
    "Dribble": {"Complete", "Incomplete"},
    "Duel": {"Won", "Lost In Play", "Lost Out", "Success In Play", "Success Out"},
    "Interception": {"Won", "Lost In Play", "Lost Out", "Success In Play", "Success Out"},
}
ON_BALL_TYPES = [
    "Pass",
    "Carry",
    "Shot",
    "Dribble",
    "Ball Receipt*",
    "Clearance",
    "Interception",
    "Ball Recovery",
]


@dataclass(frozen=True)
class Rule:
    code: str
    table: str
    description: str
    severity: Severity
    check: Callable[[Tables], Frame]
    tolerance: int = 0


@dataclass
class Result:
    code: str
    table: str
    description: str
    severity: Severity
    violations: int
    tolerance: int
    passed: bool
    sample: list[dict[str, Any]] = field(default_factory=list)


def _collect(frame: Frame) -> pl.DataFrame:
    return frame.collect() if isinstance(frame, pl.LazyFrame) else frame


def _lazy(frame: Frame) -> pl.LazyFrame:
    return frame.lazy() if isinstance(frame, pl.DataFrame) else frame


# Event rules ------------------------------------------------------------------------


def _unique_event_ids(t: Tables) -> Frame:
    return _lazy(t["events"]).group_by("event_id").agg(pl.len()).filter(pl.col("len") > 1)


def _contiguous_index(t: Tables) -> Frame:
    return (
        _lazy(t["events"])
        .group_by("match_id")
        .agg(
            pl.col("index").min().alias("first"),
            pl.col("index").max().alias("last"),
            pl.len().alias("n"),
        )
        .filter((pl.col("first") != 1) | (pl.col("last") != pl.col("n")))
    )


def _valid_period(t: Tables) -> Frame:
    return (
        _lazy(t["events"])
        .filter(~pl.col("period").is_between(1, 5))
        .select("match_id", "event_id", "period")
    )


def _valid_clock(t: Tables) -> Frame:
    ev = _lazy(t["events"])
    bad = (
        ~pl.col("second").is_between(0, 59)
        | (pl.col("minute") < 0)
        | ((pl.col("period") == 1) & (pl.col("minute") > 65))
        | ((pl.col("period") == 2) & ~pl.col("minute").is_between(45, 110))
    )
    return ev.filter(bad).select("match_id", "event_id", "period", "minute", "second")


def _period_order(t: Tables) -> Frame:
    return (
        _lazy(t["events"])
        .select("match_id", "index", "period", "type")
        .sort("match_id", "index")
        .filter(pl.col("period") < pl.col("period").shift(1).over("match_id"))
    )


def _timestamp_order(t: Tables) -> Frame:
    return (
        _lazy(t["events"])
        .select("match_id", "index", "period", "timestamp")
        .sort("match_id", "index")
        .filter(pl.col("timestamp") < pl.col("timestamp").shift(1).over("match_id", "period"))
    )


def _inside_pitch(t: Tables) -> Frame:
    cond = pl.lit(False)
    for c, hi in (("x", 120), ("end_x", 120), ("y", 80), ("end_y", 80)):
        cond = cond | (pl.col(c) < 0) | (pl.col(c) > hi)
    return (
        _lazy(t["events"])
        .filter(cond)
        .select("match_id", "event_id", "type", "x", "y", "end_x", "end_y")
    )


def _shot_xg(t: Tables) -> Frame:
    return (
        _lazy(t["events"])
        .filter(
            (pl.col("type") == "Shot")
            & (pl.col("shot_xg").is_null() | ~pl.col("shot_xg").is_between(0, 1, closed="none"))
        )
        .select("match_id", "event_id", "shot_xg")
    )


def _shot_fields(t: Tables) -> Frame:
    return (
        _lazy(t["events"])
        .filter(
            (pl.col("type") == "Shot")
            & (pl.col("outcome").is_null() | pl.col("end_x").is_null() | pl.col("x").is_null())
        )
        .select("match_id", "event_id", "outcome", "x", "end_x")
    )


def _pass_locations(t: Tables) -> Frame:
    return (
        _lazy(t["events"])
        .filter((pl.col("type") == "Pass") & (pl.col("x").is_null() | pl.col("end_x").is_null()))
        .select("match_id", "event_id")
    )


def _carry_end(t: Tables) -> Frame:
    return (
        _lazy(t["events"])
        .filter((pl.col("type") == "Carry") & pl.col("end_x").is_null())
        .select("match_id", "event_id")
    )


def _pass_recipient(t: Tables) -> Frame:
    return (
        _lazy(t["events"])
        .filter(
            (pl.col("type") == "Pass")
            & pl.col("outcome").is_null()
            & pl.col("recipient_id").is_null()
        )
        .select("match_id", "event_id")
    )


def _substitution_replacement(t: Tables) -> Frame:
    subs = (
        _lazy(t["events"])
        .filter(pl.col("type") == "Substitution")
        .select("match_id", "event_id", "team_id", pl.col("replacement_id").alias("player_id"))
    )
    squad = _lazy(t["appearances"]).select("match_id", "team_id", "player_id")
    missing_field = subs.filter(pl.col("player_id").is_null())
    not_in_squad = subs.drop_nulls("player_id").join(
        squad, on=["match_id", "team_id", "player_id"], how="anti"
    )
    return pl.concat([missing_field, not_in_squad])


def _on_ball_actor(t: Tables) -> Frame:
    return (
        _lazy(t["events"])
        .filter(
            pl.col("type").is_in(ON_BALL_TYPES)
            & (pl.col("player_id").is_null() | pl.col("team_id").is_null())
        )
        .select("match_id", "event_id", "type")
    )


def _team_in_match(t: Tables) -> Frame:
    m = _lazy(t["matches"]).select("match_id", "home_team_id", "away_team_id")
    return (
        _lazy(t["events"])
        .select("match_id", "team_id")
        .unique()
        .join(m, on="match_id", how="left")
        .filter(
            (pl.col("team_id") != pl.col("home_team_id"))
            & (pl.col("team_id") != pl.col("away_team_id"))
        )
    )


def _player_in_lineup(t: Tables) -> Frame:
    players = (
        _lazy(t["events"])
        .filter(pl.col("player_id").is_not_null())
        .select("match_id", "team_id", "player_id")
        .unique()
    )
    squad = _lazy(t["appearances"]).select("match_id", "team_id", "player_id")
    return players.join(squad, on=["match_id", "team_id", "player_id"], how="anti")


def _related_exist(t: Tables) -> Frame:
    ev = _lazy(t["events"])
    rel = (
        ev.select("match_id", "event_id", "related_events")
        .explode("related_events")
        .drop_nulls("related_events")
    )
    ids = ev.select("match_id", pl.col("event_id").alias("related_events"))
    return rel.join(ids, on=["match_id", "related_events"], how="anti")


def _key_pass_exists(t: Tables) -> Frame:
    ev = _lazy(t["events"])
    shots = ev.filter(pl.col("shot_key_pass_id").is_not_null()).select(
        "match_id", "event_id", pl.col("shot_key_pass_id").alias("pass_id")
    )
    passes = ev.filter(pl.col("type") == "Pass").select(
        "match_id", pl.col("event_id").alias("pass_id")
    )
    return shots.join(passes, on=["match_id", "pass_id"], how="anti")


def _known_types(t: Tables) -> Frame:
    return (
        _lazy(t["events"])
        .filter(~pl.col("type").is_in(list(EVENT_TYPES)))
        .select("match_id", "event_id", "type")
    )


def _known_outcomes(t: Tables) -> Frame:
    ev = _lazy(t["events"])
    parts = [
        ev.filter(
            (pl.col("type") == typ)
            & pl.col("outcome").is_not_null()
            & ~pl.col("outcome").is_in(list(allowed))
        ).select("match_id", "event_id", "type", "outcome")
        for typ, allowed in OUTCOMES.items()
    ]
    return pl.concat(parts)


def _starting_xi(t: Tables) -> Frame:
    xi = _lazy(t["tactics"]).filter(pl.col("event_type") == "Starting XI")
    per_team = xi.group_by("match_id", "team_id").agg(
        pl.col("event_id").n_unique().alias("events"),
        pl.col("player_id").n_unique().alias("players"),
    )
    return per_team.filter((pl.col("events") != 1) | (pl.col("players") != 11))


def _goals_match_score(t: Tables) -> Frame:
    ev = _lazy(t["events"])
    goals = (
        ev.filter(
            ((pl.col("type") == "Shot") & (pl.col("outcome") == "Goal") & (pl.col("period") <= 4))
            | (pl.col("type") == "Own Goal For")
        )
        .group_by("match_id", "team_id")
        .agg(pl.len().cast(pl.Int32).alias("goals"))
    )
    m = _lazy(t["matches"]).select(
        "match_id", "home_team_id", "away_team_id", "home_score", "away_score"
    )
    return (
        m.join(
            goals.rename({"team_id": "home_team_id", "goals": "hg"}),
            on=["match_id", "home_team_id"],
            how="left",
        )
        .join(
            goals.rename({"team_id": "away_team_id", "goals": "ag"}),
            on=["match_id", "away_team_id"],
            how="left",
        )
        .with_columns(pl.col("hg").fill_null(0), pl.col("ag").fill_null(0))
        .filter((pl.col("hg") != pl.col("home_score")) | (pl.col("ag") != pl.col("away_score")))
    )


# Match rules ------------------------------------------------------------------------


def _unique_matches(t: Tables) -> Frame:
    return _lazy(t["matches"]).group_by("match_id").agg(pl.len()).filter(pl.col("len") > 1)


def _distinct_teams(t: Tables) -> Frame:
    return (
        _lazy(t["matches"])
        .filter(pl.col("home_team_id") == pl.col("away_team_id"))
        .select("match_id")
    )


def _valid_scores(t: Tables) -> Frame:
    return (
        _lazy(t["matches"])
        .filter((pl.col("home_score") < 0) | (pl.col("away_score") < 0))
        .select("match_id")
    )


def _date_in_season(t: Tables) -> Frame:
    m = _lazy(t["matches"])
    start = pl.col("season").str.slice(0, 4).cast(pl.Int32)
    year = pl.col("date").dt.year()
    month = pl.col("date").dt.month()
    ok = ((year == start) & (month >= 7)) | ((year == start + 1) & (month <= 7))
    return m.filter(~ok).select("match_id", "date", "season")


def _reconciles_with_results(t: Tables) -> Frame:
    league = (
        _lazy(t["matches"])
        .filter(pl.col("competition") == "La Liga")
        .select("match_id", "date", "home", "away", "home_score", "away_score")
    )
    res = _lazy(t["results"]).select("date", "home", "away", "home_goals", "away_goals")
    return league.join(res, on=["date", "home", "away"], how="left").filter(
        pl.col("home_goals").is_null()
        | (pl.col("home_goals") != pl.col("home_score"))
        | (pl.col("away_goals") != pl.col("away_score"))
    )


# Lineup / minutes rules ---------------------------------------------------------------


def _minutes_range(t: Tables) -> Frame:
    return (
        _lazy(t["appearances"])
        .filter(
            pl.col("minutes").is_not_null()
            & ((pl.col("minutes") < 0) | (pl.col("minutes") > pl.col("match_minutes") + 0.5))
        )
        .select("match_id", "player_id", "minutes", "match_minutes")
    )


def _eleven_starters(t: Tables) -> Frame:
    return (
        _lazy(t["appearances"])
        .group_by("match_id", "team_id")
        .agg(pl.col("started").sum().alias("starters"))
        .filter(pl.col("starters") != 11)
    )


def _one_team_per_player(t: Tables) -> Frame:
    return (
        _lazy(t["appearances"])
        .group_by("match_id", "player_id")
        .agg(pl.col("team_id").n_unique().alias("teams"))
        .filter(pl.col("teams") > 1)
    )


def _team_minutes(t: Tables) -> Frame:
    return (
        _lazy(t["appearances"])
        .group_by("match_id", "team_id")
        .agg(
            pl.col("minutes").sum().alias("team_minutes"),
            pl.col("match_minutes").max().alias("match_minutes"),
        )
        .filter(
            (pl.col("team_minutes") > 11 * pl.col("match_minutes") + 1)
            | (pl.col("team_minutes") < 9 * pl.col("match_minutes"))
        )
    )


# Results (football-data) rules -------------------------------------------------------


def _unique_fixtures(t: Tables) -> Frame:
    return (
        _lazy(t["results"])
        .group_by("season", "home", "away")
        .agg(pl.len())
        .filter(pl.col("len") > 1)
    )


def _double_round_robin(t: Tables) -> Frame:
    r = _lazy(t["results"])
    teams = r.group_by("season").agg(
        pl.col("home").n_unique().alias("teams"), pl.len().alias("fixtures")
    )
    return teams.filter(pl.col("fixtures") != pl.col("teams") * (pl.col("teams") - 1))


def _halftime_le_fulltime(t: Tables) -> Frame:
    return (
        _lazy(t["results"])
        .filter(
            (pl.col("home_goals_ht") > pl.col("home_goals"))
            | (pl.col("away_goals_ht") > pl.col("away_goals"))
        )
        .select("date", "home", "away")
    )


def _shots_ge_on_target(t: Tables) -> Frame:
    return (
        _lazy(t["results"])
        .filter(
            (pl.col("home_shots") < pl.col("home_sot"))
            | (pl.col("away_shots") < pl.col("away_sot"))
        )
        .select("date", "home", "away", "home_shots", "home_sot", "away_shots", "away_sot")
    )


def _odds_valid(t: Tables) -> Frame:
    cond = pl.lit(False)
    for c in ("odds_b365_h", "odds_b365_d", "odds_b365_a"):
        cond = cond | (pl.col(c) <= 1.0)
    return _lazy(t["results"]).filter(cond).select("date", "home", "away")


def _results_complete(t: Tables) -> Frame:
    return (
        _lazy(t["results"])
        .filter(
            pl.col("date").is_null()
            | pl.col("home_goals").is_null()
            | pl.col("away_goals").is_null()
        )
        .select("season", "home", "away")
    )


def _one_match_per_day(t: Tables) -> Frame:
    r = _lazy(t["results"])
    teams = pl.concat(
        [
            r.select("date", pl.col("home").alias("team")),
            r.select("date", pl.col("away").alias("team")),
        ]
    )
    return teams.group_by("date", "team").agg(pl.len()).filter(pl.col("len") > 1)


RULES: list[Rule] = [
    Rule("E01", "events", "event ids are unique", "error", _unique_event_ids),
    Rule("E02", "events", "event index runs 1..n within every match", "error", _contiguous_index),
    Rule("E03", "events", "period is 1-5", "error", _valid_period),
    Rule("E04", "events", "minute/second are valid for the period", "error", _valid_clock),
    Rule(
        "E05",
        "events",
        "periods never go backwards in index order",
        "warning",
        _period_order,
        tolerance=5,
    ),
    Rule(
        "E06",
        "events",
        "timestamps rarely go backwards within a period (related events can be recorded out of order)",
        "warning",
        _timestamp_order,
        tolerance=1000,
    ),
    Rule("E07", "events", "locations lie on the 120 x 80 pitch", "error", _inside_pitch),
    Rule("E08", "events", "every shot has an xG in (0, 1)", "error", _shot_xg),
    Rule(
        "E09",
        "events",
        "every shot has an outcome, a start and an end location",
        "error",
        _shot_fields,
    ),
    Rule("E10", "events", "every pass has a start and an end location", "error", _pass_locations),
    Rule("E11", "events", "every carry has an end location", "error", _carry_end),
    Rule("E12", "events", "completed passes name a recipient", "warning", _pass_recipient),
    Rule(
        "E13",
        "events",
        "substitutions name a replacement from the same squad",
        "error",
        _substitution_replacement,
    ),
    Rule("E14", "events", "on-ball events have a player and a team", "error", _on_ball_actor),
    Rule(
        "E15", "events", "event team is one of the two teams in the match", "error", _team_in_match
    ),
    Rule(
        "E16",
        "events",
        "every event player is in that team's matchday lineup",
        "error",
        _player_in_lineup,
    ),
    Rule(
        "E17", "events", "related_events point to events in the same match", "error", _related_exist
    ),
    Rule(
        "E18",
        "events",
        "shot key-pass ids point to a pass in the same match",
        "error",
        _key_pass_exists,
    ),
    Rule("E19", "events", "event types come from the known vocabulary", "error", _known_types),
    Rule(
        "E20",
        "events",
        "outcomes come from the known vocabulary for their type",
        "warning",
        _known_outcomes,
    ),
    Rule(
        "E21",
        "events",
        "one Starting XI per team per match, with 11 players",
        "error",
        _starting_xi,
    ),
    Rule(
        "E22",
        "events",
        "goals reconstructed from events equal the official score",
        "error",
        _goals_match_score,
    ),
    Rule("M01", "matches", "match ids are unique", "error", _unique_matches),
    Rule("M02", "matches", "home and away teams differ", "error", _distinct_teams),
    Rule("M03", "matches", "scores are non-negative", "error", _valid_scores),
    Rule("M04", "matches", "match date falls inside its season", "error", _date_in_season),
    Rule(
        "M05",
        "matches",
        "every league match reconciles with football-data (date, teams, score)",
        "error",
        _reconciles_with_results,
    ),
    Rule(
        "L01",
        "appearances",
        "minutes played lie between 0 and match length",
        "error",
        _minutes_range,
    ),
    Rule("L02", "appearances", "exactly 11 starters per team per match", "error", _eleven_starters),
    Rule(
        "L03",
        "appearances",
        "a player belongs to one team per match",
        "error",
        _one_team_per_player,
    ),
    # Temporary injury exits (Player Off/On) occasionally overlap with a substitution in the
    # lineup spells, inflating one player's minutes: 12 of 1,738 team-matches (0.7%).
    Rule(
        "L04",
        "appearances",
        "team minutes are consistent with 9-11 players on the pitch",
        "warning",
        _team_minutes,
        tolerance=15,
    ),
    Rule("R01", "results", "one fixture per (season, home, away)", "error", _unique_fixtures),
    Rule(
        "R02",
        "results",
        "every season is a complete double round robin",
        "error",
        _double_round_robin,
    ),
    Rule(
        "R03",
        "results",
        "half-time goals never exceed full-time goals",
        "error",
        _halftime_le_fulltime,
    ),
    Rule(
        "R04", "results", "shots are never fewer than shots on target", "error", _shots_ge_on_target
    ),
    Rule("R05", "results", "bookmaker odds are above 1.0", "error", _odds_valid),
    Rule(
        "R06",
        "results",
        "every fixture has a date and a full-time score",
        "error",
        _results_complete,
    ),
    # Rolling features and Elo assume a club's matches are strictly ordered in time.
    Rule("R07", "results", "a club plays at most one match per date", "error", _one_match_per_day),
]


def run(tables: Tables, rules: list[Rule] | None = None, sample_size: int = 5) -> list[Result]:
    results = []
    for rule in rules or RULES:
        if rule.table not in tables:
            continue
        violations = _collect(rule.check(tables))
        n = violations.height
        passed = n <= rule.tolerance
        sample = [
            {
                k: (str(v) if not isinstance(v, int | float | bool | type(None)) else v)
                for k, v in row.items()
            }
            for row in violations.head(sample_size).to_dicts()
        ]
        results.append(
            Result(
                rule.code,
                rule.table,
                rule.description,
                rule.severity,
                n,
                rule.tolerance,
                passed,
                sample,
            )
        )
    return results


def summary(results: list[Result]) -> pl.DataFrame:
    return pl.DataFrame([{k: v for k, v in asdict(r).items() if k != "sample"} for r in results])


def gate_passed(results: list[Result]) -> bool:
    return all(r.passed for r in results if r.severity == "error")


def write_report(results: list[Result], path: Path, title: str = "Data quality report") -> None:
    lines = [
        f"# {title}",
        "",
        "| Rule | Table | Check | Severity | Violations | Tolerance | Status |",
        "|---|---|---|---|---|---|---|",
    ]
    for r in results:
        status = "pass" if r.passed else ("FAIL" if r.severity == "error" else "warn")
        lines.append(
            f"| {r.code} | {r.table} | {r.description} | {r.severity} | {r.violations:,} | {r.tolerance} | {status} |"
        )
    failing = [r for r in results if r.violations and r.sample]
    if failing:
        lines += ["", "## Samples of violating rows", ""]
        for r in failing:
            lines += [
                f"**{r.code}** ({r.violations:,} rows)",
                "",
                "```",
                json.dumps(r.sample, indent=1, default=str),
                "```",
                "",
            ]
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n")


def write_stamp(results: list[Result], path: Path) -> None:
    payload = {
        "passed": gate_passed(results),
        "rules": [{k: v for k, v in asdict(r).items() if k != "sample"} for r in results],
    }
    path.write_text(json.dumps(payload, indent=1))


def require_stamp(path: Path) -> None:
    if not path.exists():
        raise RuntimeError(
            f"{path} not found: run `barca build` so the processed data is validated first"
        )
    if not json.loads(path.read_text())["passed"]:
        raise RuntimeError(f"processed data failed validation, see {path}")
