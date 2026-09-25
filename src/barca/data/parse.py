"""Flatten raw StatsBomb JSON into tabular rows.

This module only restructures data; it does not interpret it. Nested event
sub-objects (``pass``, ``shot``, ``duel``...) are folded into a single wide
schema with a few unified columns (``end_x``, ``outcome``, ``subtype``,
``body_part``) so that the same column means the same thing across event
types. Anything semantic (units, names, flags derived from outcomes) happens in
``normalize`` and ``clean``.
"""

from __future__ import annotations

from typing import Any

import polars as pl

# The key of an event's sub-object is its type name in snake case.
SUBOBJECT_KEY = {
    "Pass": "pass",
    "Carry": "carry",
    "Shot": "shot",
    "Dribble": "dribble",
    "Duel": "duel",
    "Interception": "interception",
    "Ball Receipt*": "ball_receipt",
    "Ball Recovery": "ball_recovery",
    "Clearance": "clearance",
    "Goal Keeper": "goalkeeper",
    "Foul Committed": "foul_committed",
    "Foul Won": "foul_won",
    "Bad Behaviour": "bad_behaviour",
    "Substitution": "substitution",
    "Block": "block",
    "50/50": "50_50",
    "Miscontrol": "miscontrol",
    "Injury Stoppage": "injury_stoppage",
    "Half Start": "half_start",
    "Half End": "half_end",
    "Player Off": "player_off",
    "Dribbled Past": "dribbled_past",
    "Pressure": "pressure",
}

EVENT_SCHEMA: dict[str, Any] = {
    "match_id": pl.Int64,
    "event_id": pl.String,
    "index": pl.Int32,
    "period": pl.Int8,
    "timestamp": pl.String,
    "minute": pl.Int16,
    "second": pl.Int16,
    "type": pl.String,
    "possession": pl.Int32,
    "possession_team_id": pl.Int32,
    "possession_team": pl.String,
    "play_pattern": pl.String,
    "team_id": pl.Int32,
    "team": pl.String,
    "player_id": pl.Int32,
    "player": pl.String,
    "position_id": pl.Int16,
    "position": pl.String,
    "x": pl.Float32,
    "y": pl.Float32,
    "end_x": pl.Float32,
    "end_y": pl.Float32,
    "end_z": pl.Float32,
    "duration": pl.Float32,
    "under_pressure": pl.Boolean,
    "counterpress": pl.Boolean,
    "off_camera": pl.Boolean,
    "out": pl.Boolean,
    "outcome": pl.String,
    "subtype": pl.String,
    "body_part": pl.String,
    "technique": pl.String,
    "pass_height": pl.String,
    "pass_length": pl.Float32,
    "pass_angle": pl.Float32,
    "recipient_id": pl.Int32,
    "recipient": pl.String,
    "pass_cross": pl.Boolean,
    "pass_switch": pl.Boolean,
    "pass_through_ball": pl.Boolean,
    "pass_cut_back": pl.Boolean,
    "pass_shot_assist": pl.Boolean,
    "pass_goal_assist": pl.Boolean,
    "pass_assisted_shot_id": pl.String,
    "pass_deflected": pl.Boolean,
    "shot_xg": pl.Float32,
    "shot_key_pass_id": pl.String,
    "shot_first_time": pl.Boolean,
    "shot_one_on_one": pl.Boolean,
    "shot_open_goal": pl.Boolean,
    "shot_freeze_frame_n": pl.Int16,
    "dribble_nutmeg": pl.Boolean,
    "recovery_failure": pl.Boolean,
    "card": pl.String,
    "foul_penalty": pl.Boolean,
    "replacement_id": pl.Int32,
    "replacement": pl.String,
    "formation": pl.String,
    "aerial_won": pl.Boolean,
    "related_events": pl.List(pl.String),
}

LINEUP_SCHEMA: dict[str, Any] = {
    "match_id": pl.Int64,
    "team_id": pl.Int32,
    "team": pl.String,
    "player_id": pl.Int32,
    "player": pl.String,
    "nickname": pl.String,
    "jersey_number": pl.Int16,
    "country": pl.String,
    "n_positions": pl.Int8,
    "n_yellow": pl.Int8,
    "n_red": pl.Int8,
}

POSITION_SCHEMA: dict[str, Any] = {
    "match_id": pl.Int64,
    "team_id": pl.Int32,
    "player_id": pl.Int32,
    "spell": pl.Int8,
    "position_id": pl.Int16,
    "position": pl.String,
    "from_clock": pl.String,
    "to_clock": pl.String,
    "from_period": pl.Int8,
    "to_period": pl.Int8,
    "start_reason": pl.String,
    "end_reason": pl.String,
}

TACTICS_SCHEMA: dict[str, Any] = {
    "match_id": pl.Int64,
    "event_id": pl.String,
    "index": pl.Int32,
    "period": pl.Int8,
    "minute": pl.Int16,
    "second": pl.Int16,
    "event_type": pl.String,
    "team_id": pl.Int32,
    "formation": pl.String,
    "player_id": pl.Int32,
    "position_id": pl.Int16,
    "position": pl.String,
    "jersey_number": pl.Int16,
}

FREEZE_FRAME_SCHEMA: dict[str, Any] = {
    "match_id": pl.Int64,
    "event_id": pl.String,
    "player_id": pl.Int32,
    "position": pl.String,
    "teammate": pl.Boolean,
    "x": pl.Float32,
    "y": pl.Float32,
}

MATCH_SCHEMA: dict[str, Any] = {
    "match_id": pl.Int64,
    "match_date": pl.String,
    "kick_off": pl.String,
    "competition_id": pl.Int32,
    "competition": pl.String,
    "season_id": pl.Int32,
    "season": pl.String,
    "home_team_id": pl.Int32,
    "home_team": pl.String,
    "away_team_id": pl.Int32,
    "away_team": pl.String,
    "home_score": pl.Int16,
    "away_score": pl.Int16,
    "home_manager": pl.String,
    "away_manager": pl.String,
    "match_week": pl.Int16,
    "competition_stage": pl.String,
    "stadium": pl.String,
    "referee": pl.String,
    "match_status": pl.String,
    "match_status_360": pl.String,
    "data_version": pl.String,
    "shot_fidelity_version": pl.String,
    "xy_fidelity_version": pl.String,
}


def _name(obj: dict[str, Any] | None) -> str | None:
    return obj.get("name") if obj else None


def _id(obj: dict[str, Any] | None) -> int | None:
    return obj.get("id") if obj else None


def _managers(team: dict[str, Any]) -> str | None:
    managers = team.get("managers") or []
    names = [m.get("nickname") or m.get("name") for m in managers]
    return " / ".join(n for n in names if n) or None


def match_row(match: dict[str, Any]) -> dict[str, Any]:
    home, away = match["home_team"], match["away_team"]
    meta = match.get("metadata") or {}
    return {
        "match_id": match["match_id"],
        "match_date": match["match_date"],
        "kick_off": match.get("kick_off"),
        "competition_id": match["competition"]["competition_id"],
        "competition": match["competition"]["competition_name"],
        "season_id": match["season"]["season_id"],
        "season": match["season"]["season_name"],
        "home_team_id": home["home_team_id"],
        "home_team": home["home_team_name"],
        "away_team_id": away["away_team_id"],
        "away_team": away["away_team_name"],
        "home_score": match.get("home_score"),
        "away_score": match.get("away_score"),
        "home_manager": _managers(home),
        "away_manager": _managers(away),
        "match_week": match.get("match_week"),
        "competition_stage": _name(match.get("competition_stage")),
        "stadium": _name(match.get("stadium")),
        "referee": _name(match.get("referee")),
        "match_status": match.get("match_status"),
        "match_status_360": match.get("match_status_360"),
        "data_version": meta.get("data_version"),
        "shot_fidelity_version": meta.get("shot_fidelity_version"),
        "xy_fidelity_version": meta.get("xy_fidelity_version"),
    }


def matches_frame(matches: list[dict[str, Any]]) -> pl.DataFrame:
    return pl.from_dicts([match_row(m) for m in matches], schema=MATCH_SCHEMA)


def _xy(loc: list[float] | None) -> tuple[float | None, float | None, float | None]:
    if not loc:
        return None, None, None
    z = loc[2] if len(loc) > 2 else None
    return loc[0], loc[1], z


def event_row(match_id: int, ev: dict[str, Any]) -> dict[str, Any]:
    type_name = ev["type"]["name"]
    sub = ev.get(SUBOBJECT_KEY.get(type_name, "")) or {}
    x, y, _ = _xy(ev.get("location"))
    end_x, end_y, end_z = _xy(sub.get("end_location"))

    row: dict[str, Any] = {
        "match_id": match_id,
        "event_id": ev["id"],
        "index": ev["index"],
        "period": ev["period"],
        "timestamp": ev["timestamp"],
        "minute": ev["minute"],
        "second": ev["second"],
        "type": type_name,
        "possession": ev.get("possession"),
        "possession_team_id": _id(ev.get("possession_team")),
        "possession_team": _name(ev.get("possession_team")),
        "play_pattern": _name(ev.get("play_pattern")),
        "team_id": _id(ev.get("team")),
        "team": _name(ev.get("team")),
        "player_id": _id(ev.get("player")),
        "player": _name(ev.get("player")),
        "position_id": _id(ev.get("position")),
        "position": _name(ev.get("position")),
        "x": x,
        "y": y,
        "end_x": end_x,
        "end_y": end_y,
        "end_z": end_z,
        "duration": ev.get("duration"),
        "under_pressure": ev.get("under_pressure"),
        "counterpress": ev.get("counterpress"),
        "off_camera": ev.get("off_camera"),
        "out": ev.get("out"),
        "outcome": _name(sub.get("outcome")),
        "subtype": _name(sub.get("type")),
        "body_part": _name(sub.get("body_part")),
        "technique": _name(sub.get("technique")),
        "aerial_won": sub.get("aerial_won"),
        "related_events": ev.get("related_events"),
    }

    if type_name == "Pass":
        row.update(
            pass_height=_name(sub.get("height")),
            pass_length=sub.get("length"),
            pass_angle=sub.get("angle"),
            recipient_id=_id(sub.get("recipient")),
            recipient=_name(sub.get("recipient")),
            pass_cross=sub.get("cross"),
            pass_switch=sub.get("switch"),
            pass_through_ball=sub.get("through_ball")
            or (_name(sub.get("technique")) == "Through Ball")
            or None,
            pass_cut_back=sub.get("cut_back"),
            pass_shot_assist=sub.get("shot_assist"),
            pass_goal_assist=sub.get("goal_assist"),
            pass_assisted_shot_id=sub.get("assisted_shot_id"),
            pass_deflected=sub.get("deflected"),
        )
    elif type_name == "Shot":
        frame = sub.get("freeze_frame")
        row.update(
            shot_xg=sub.get("statsbomb_xg"),
            shot_key_pass_id=sub.get("key_pass_id"),
            shot_first_time=sub.get("first_time"),
            shot_one_on_one=sub.get("one_on_one"),
            shot_open_goal=sub.get("open_goal"),
            shot_freeze_frame_n=len(frame) if frame is not None else None,
        )
    elif type_name == "Dribble":
        row["dribble_nutmeg"] = sub.get("nutmeg")
    elif type_name == "Ball Recovery":
        row["recovery_failure"] = sub.get("recovery_failure")
    elif type_name in ("Foul Committed", "Bad Behaviour"):
        row["card"] = _name(sub.get("card"))
        if type_name == "Foul Committed":
            row["foul_penalty"] = sub.get("penalty")
    elif type_name == "Foul Won":
        row["foul_penalty"] = sub.get("penalty")
    elif type_name == "Substitution":
        row["replacement_id"] = _id(sub.get("replacement"))
        row["replacement"] = _name(sub.get("replacement"))
    elif type_name in ("Starting XI", "Tactical Shift"):
        formation = (ev.get("tactics") or {}).get("formation")
        row["formation"] = str(formation) if formation is not None else None
    return row


def tactics_rows(match_id: int, ev: dict[str, Any]) -> list[dict[str, Any]]:
    tactics = ev.get("tactics") or {}
    formation = tactics.get("formation")
    return [
        {
            "match_id": match_id,
            "event_id": ev["id"],
            "index": ev["index"],
            "period": ev["period"],
            "minute": ev["minute"],
            "second": ev["second"],
            "event_type": ev["type"]["name"],
            "team_id": _id(ev.get("team")),
            "formation": str(formation) if formation is not None else None,
            "player_id": _id(slot.get("player")),
            "position_id": _id(slot.get("position")),
            "position": _name(slot.get("position")),
            "jersey_number": slot.get("jersey_number"),
        }
        for slot in tactics.get("lineup", [])
    ]


def freeze_frame_rows(match_id: int, ev: dict[str, Any]) -> list[dict[str, Any]]:
    frame = (ev.get("shot") or {}).get("freeze_frame") or []
    rows = []
    for p in frame:
        x, y, _ = _xy(p.get("location"))
        rows.append(
            {
                "match_id": match_id,
                "event_id": ev["id"],
                "player_id": _id(p.get("player")),
                "position": _name(p.get("position")),
                "teammate": p.get("teammate"),
                "x": x,
                "y": y,
            }
        )
    return rows


def parse_events(match_id: int, events: list[dict[str, Any]]) -> dict[str, pl.DataFrame]:
    event_rows, tactic_rows, frame_rows = [], [], []
    for ev in events:
        event_rows.append(event_row(match_id, ev))
        if ev["type"]["name"] in ("Starting XI", "Tactical Shift"):
            tactic_rows.extend(tactics_rows(match_id, ev))
        elif ev["type"]["name"] == "Shot":
            frame_rows.extend(freeze_frame_rows(match_id, ev))
    return {
        "events": pl.from_dicts(event_rows, schema=EVENT_SCHEMA),
        "tactics": pl.from_dicts(tactic_rows, schema=TACTICS_SCHEMA),
        "freeze_frames": pl.from_dicts(frame_rows, schema=FREEZE_FRAME_SCHEMA),
    }


def parse_lineups(match_id: int, lineups: list[dict[str, Any]]) -> dict[str, pl.DataFrame]:
    players, spells = [], []
    for team in lineups:
        for p in team["lineup"]:
            cards = p.get("cards") or []
            positions = p.get("positions") or []
            players.append(
                {
                    "match_id": match_id,
                    "team_id": team["team_id"],
                    "team": team["team_name"],
                    "player_id": p["player_id"],
                    "player": p["player_name"],
                    "nickname": p.get("player_nickname"),
                    "jersey_number": p.get("jersey_number"),
                    "country": _name(p.get("country")),
                    "n_positions": len(positions),
                    "n_yellow": sum(c.get("card_type") == "Yellow Card" for c in cards),
                    "n_red": sum(
                        c.get("card_type") in ("Red Card", "Second Yellow") for c in cards
                    ),
                }
            )
            for i, pos in enumerate(positions):
                spells.append(
                    {
                        "match_id": match_id,
                        "team_id": team["team_id"],
                        "player_id": p["player_id"],
                        "spell": i,
                        "position_id": pos.get("position_id"),
                        "position": pos.get("position"),
                        "from_clock": pos.get("from"),
                        "to_clock": pos.get("to"),
                        "from_period": pos.get("from_period"),
                        "to_period": pos.get("to_period"),
                        "start_reason": pos.get("start_reason"),
                        "end_reason": pos.get("end_reason"),
                    }
                )
    return {
        "lineups": pl.from_dicts(players, schema=LINEUP_SCHEMA),
        "positions": pl.from_dicts(spells, schema=POSITION_SCHEMA),
    }


def three_sixty_frame(match_id: int, frames: list[dict[str, Any]]) -> pl.DataFrame:
    """One row per visible player per 360 frame."""
    rows = []
    for frame in frames:
        for p in frame.get("freeze_frame", []):
            x, y, _ = _xy(p.get("location"))
            rows.append(
                {
                    "match_id": match_id,
                    "event_id": frame["event_uuid"],
                    "teammate": p.get("teammate"),
                    "actor": p.get("actor"),
                    "keeper": p.get("keeper"),
                    "x": x,
                    "y": y,
                }
            )
    return pl.from_dicts(
        rows,
        schema={
            "match_id": pl.Int64,
            "event_id": pl.String,
            "teammate": pl.Boolean,
            "actor": pl.Boolean,
            "keeper": pl.Boolean,
            "x": pl.Float32,
            "y": pl.Float32,
        },
    )


def football_data_frame(raw_csv: bytes, season_label: str) -> pl.DataFrame:
    """Read a football-data.co.uk CSV as strings; typing happens in normalize.

    Older files carry trailing empty columns and blank lines, and the column set
    changes over the years (odds providers come and go), so everything is read
    as text and only the columns the project needs are kept downstream.
    """
    text = raw_csv.decode("latin-1").lstrip("﻿")
    frame = pl.read_csv(
        text.encode(),
        infer_schema=False,
        truncate_ragged_lines=True,
        ignore_errors=True,
    )
    frame = frame.select([c for c in frame.columns if c and not c.startswith("_duplicated")])
    frame = frame.filter(pl.col("HomeTeam").is_not_null() & (pl.col("HomeTeam") != ""))
    return frame.with_columns(pl.lit(season_label).alias("season"))
