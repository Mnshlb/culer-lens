"""Application database schema (SQLAlchemy 2.0).

The analytical pipeline lives in Parquet. This schema holds what the web app
serves: entities, per-match statistics, pre-match features, predictions and
model metadata. Types are portable (JSON rather than JSONB) so that the same
models run on PostgreSQL in production and on SQLite locally and in tests.
"""

from __future__ import annotations

from datetime import date, datetime

from sqlalchemy import (
    JSON,
    Boolean,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    SmallInteger,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


class Competition(Base):
    __tablename__ = "competitions"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(80), unique=True)


class Season(Base):
    __tablename__ = "seasons"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    label: Mapped[str] = mapped_column(String(9), unique=True)  # 2015/2016
    start_year: Mapped[int] = mapped_column(SmallInteger, index=True)


class Team(Base):
    __tablename__ = "teams"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    statsbomb_id: Mapped[int | None] = mapped_column(Integer, unique=True)
    name: Mapped[str] = mapped_column(String(80), unique=True)
    short_name: Mapped[str] = mapped_column(String(40))
    code: Mapped[str] = mapped_column(String(3))


class Player(Base):
    __tablename__ = "players"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)  # StatsBomb player id
    name: Mapped[str] = mapped_column(String(120))
    display_name: Mapped[str] = mapped_column(String(80), index=True)
    country: Mapped[str | None] = mapped_column(String(60))
    position_family: Mapped[str | None] = mapped_column(String(2))
    position_group: Mapped[str | None] = mapped_column(String(2))
    barca_minutes: Mapped[float] = mapped_column(Float, default=0.0)


class Match(Base):
    """A Barcelona fixture (league or final), with or without event data."""

    __tablename__ = "matches"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    statsbomb_id: Mapped[int | None] = mapped_column(Integer, unique=True)
    fixture_id: Mapped[int | None] = mapped_column(Integer, unique=True)
    date: Mapped[date] = mapped_column(Date, index=True)
    kickoff: Mapped[datetime | None] = mapped_column(DateTime)
    season_id: Mapped[int] = mapped_column(ForeignKey("seasons.id"), index=True)
    competition_id: Mapped[int] = mapped_column(ForeignKey("competitions.id"))
    home_team_id: Mapped[int] = mapped_column(ForeignKey("teams.id"))
    away_team_id: Mapped[int] = mapped_column(ForeignKey("teams.id"))
    home_score: Mapped[int] = mapped_column(SmallInteger)
    away_score: Mapped[int] = mapped_column(SmallInteger)
    barca_home: Mapped[bool] = mapped_column(Boolean)
    barca_result: Mapped[str] = mapped_column(String(1))
    era: Mapped[str | None] = mapped_column(String(40))
    match_week: Mapped[int | None] = mapped_column(SmallInteger)
    stadium: Mapped[str | None] = mapped_column(String(120))
    referee: Mapped[str | None] = mapped_column(String(120))
    has_events: Mapped[bool] = mapped_column(Boolean, default=False)

    season: Mapped[Season] = relationship()
    competition: Mapped[Competition] = relationship()
    home_team: Mapped[Team] = relationship(foreign_keys=[home_team_id])
    away_team: Mapped[Team] = relationship(foreign_keys=[away_team_id])


class Lineup(Base):
    __tablename__ = "lineups"
    match_id: Mapped[int] = mapped_column(ForeignKey("matches.id"), primary_key=True)
    player_id: Mapped[int] = mapped_column(ForeignKey("players.id"), primary_key=True)
    team_id: Mapped[int] = mapped_column(ForeignKey("teams.id"))
    jersey_number: Mapped[int | None] = mapped_column(SmallInteger)
    started: Mapped[bool] = mapped_column(Boolean)
    played: Mapped[bool] = mapped_column(Boolean)
    minutes: Mapped[float] = mapped_column(Float)
    position: Mapped[str | None] = mapped_column(String(40))
    position_group: Mapped[str | None] = mapped_column(String(2))
    on_minute: Mapped[float | None] = mapped_column(Float)
    off_minute: Mapped[float | None] = mapped_column(Float)


class Event(Base):
    """Barcelona players' on-pitch events plus every shot by either side."""

    __tablename__ = "events"
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    match_id: Mapped[int] = mapped_column(ForeignKey("matches.id"))
    index: Mapped[int] = mapped_column(Integer)
    period: Mapped[int] = mapped_column(SmallInteger)
    minute: Mapped[int] = mapped_column(SmallInteger)
    second: Mapped[int] = mapped_column(SmallInteger)
    type: Mapped[str] = mapped_column(String(24))
    team_id: Mapped[int] = mapped_column(ForeignKey("teams.id"))
    player_id: Mapped[int | None] = mapped_column(ForeignKey("players.id"))
    x: Mapped[float | None] = mapped_column(Float)
    y: Mapped[float | None] = mapped_column(Float)
    end_x: Mapped[float | None] = mapped_column(Float)
    end_y: Mapped[float | None] = mapped_column(Float)
    outcome: Mapped[str | None] = mapped_column(String(32))
    subtype: Mapped[str | None] = mapped_column(String(32))
    recipient_id: Mapped[int | None] = mapped_column(Integer)
    xg: Mapped[float | None] = mapped_column(Float)
    xt: Mapped[float | None] = mapped_column(Float)
    body_part: Mapped[str | None] = mapped_column(String(20))
    play_pattern: Mapped[str | None] = mapped_column(String(24))
    is_touch: Mapped[bool] = mapped_column(Boolean, default=False)
    is_pass: Mapped[bool] = mapped_column(Boolean, default=False)
    is_complete_pass: Mapped[bool] = mapped_column(Boolean, default=False)
    is_carry: Mapped[bool] = mapped_column(Boolean, default=False)
    is_attacking: Mapped[bool] = mapped_column(Boolean, default=False)
    is_defending: Mapped[bool] = mapped_column(Boolean, default=False)
    is_shot: Mapped[bool] = mapped_column(Boolean, default=False)

    __table_args__ = (
        Index("ix_events_player_match", "player_id", "match_id"),
        Index("ix_events_match_type", "match_id", "type"),
    )


class TeamMatchStats(Base):
    __tablename__ = "team_match_stats"
    match_id: Mapped[int] = mapped_column(ForeignKey("matches.id"), primary_key=True)
    team_id: Mapped[int] = mapped_column(ForeignKey("teams.id"), primary_key=True)
    goals: Mapped[int] = mapped_column(SmallInteger)
    xg: Mapped[float] = mapped_column(Float)
    npxg: Mapped[float] = mapped_column(Float)
    shots: Mapped[int] = mapped_column(SmallInteger)
    shots_on_target: Mapped[int] = mapped_column(SmallInteger)
    big_chances: Mapped[int] = mapped_column(SmallInteger)
    possession: Mapped[float] = mapped_column(Float)
    passes: Mapped[int] = mapped_column(Integer)
    pass_completion: Mapped[float] = mapped_column(Float)
    progressive_passes: Mapped[int] = mapped_column(SmallInteger)
    progressive_carries: Mapped[int] = mapped_column(SmallInteger)
    box_entries: Mapped[int] = mapped_column(SmallInteger)
    final_third_entries: Mapped[int] = mapped_column(SmallInteger)
    pressures: Mapped[int] = mapped_column(SmallInteger)
    counterpresses: Mapped[int] = mapped_column(SmallInteger)
    high_recoveries: Mapped[int] = mapped_column(SmallInteger)
    ppda: Mapped[float] = mapped_column(Float)
    field_tilt: Mapped[float] = mapped_column(Float)
    defensive_action_height: Mapped[float | None] = mapped_column(Float)
    xt: Mapped[float | None] = mapped_column(Float)
    yellow_cards: Mapped[int] = mapped_column(SmallInteger)
    red_cards: Mapped[int] = mapped_column(SmallInteger)


class PlayerMatchStats(Base):
    __tablename__ = "player_match_stats"
    match_id: Mapped[int] = mapped_column(ForeignKey("matches.id"), primary_key=True)
    player_id: Mapped[int] = mapped_column(ForeignKey("players.id"), primary_key=True)
    team_id: Mapped[int] = mapped_column(ForeignKey("teams.id"))
    started: Mapped[bool] = mapped_column(Boolean)
    minutes: Mapped[float] = mapped_column(Float)
    position: Mapped[str | None] = mapped_column(String(40))
    position_family: Mapped[str | None] = mapped_column(String(2))
    goals: Mapped[int] = mapped_column(SmallInteger)
    assists: Mapped[int] = mapped_column(SmallInteger)
    xg: Mapped[float] = mapped_column(Float)
    npxg: Mapped[float] = mapped_column(Float)
    xa: Mapped[float] = mapped_column(Float)
    xt: Mapped[float] = mapped_column(Float)
    shots: Mapped[int] = mapped_column(SmallInteger)
    key_passes: Mapped[int] = mapped_column(SmallInteger)
    touches: Mapped[int] = mapped_column(SmallInteger)
    touches_in_box: Mapped[int] = mapped_column(SmallInteger)
    passes: Mapped[int] = mapped_column(SmallInteger)
    passes_completed: Mapped[int] = mapped_column(SmallInteger)
    progressive_passes: Mapped[int] = mapped_column(SmallInteger)
    progressive_carries: Mapped[int] = mapped_column(SmallInteger)
    dribbles_completed: Mapped[int] = mapped_column(SmallInteger)
    pressures: Mapped[int] = mapped_column(SmallInteger)
    tackles_won: Mapped[int] = mapped_column(SmallInteger)
    interceptions: Mapped[int] = mapped_column(SmallInteger)
    recoveries: Mapped[int] = mapped_column(SmallInteger)
    match_rating: Mapped[float | None] = mapped_column(Float)


class TeamFeatures(Base):
    """Pre-match form and strength for every club at every league fixture."""

    __tablename__ = "team_features"
    team_id: Mapped[int] = mapped_column(ForeignKey("teams.id"), primary_key=True)
    date: Mapped[date] = mapped_column(Date, primary_key=True)
    season_id: Mapped[int] = mapped_column(ForeignKey("seasons.id"))
    opponent_id: Mapped[int] = mapped_column(ForeignKey("teams.id"))
    is_home: Mapped[bool] = mapped_column(Boolean)
    goals: Mapped[int] = mapped_column(SmallInteger)
    goals_against: Mapped[int] = mapped_column(SmallInteger)
    result: Mapped[str] = mapped_column(String(1))
    elo: Mapped[float] = mapped_column(Float)
    elo_post: Mapped[float] = mapped_column(Float)
    points_5: Mapped[float | None] = mapped_column(Float)
    goals_10: Mapped[float | None] = mapped_column(Float)
    goals_against_10: Mapped[float | None] = mapped_column(Float)
    sot_10: Mapped[float | None] = mapped_column(Float)
    sot_against_10: Mapped[float | None] = mapped_column(Float)
    points_std: Mapped[float | None] = mapped_column(Float)
    matches_played: Mapped[int] = mapped_column(SmallInteger)
    days_rest: Mapped[float | None] = mapped_column(Float)


class PlayerSeasonRating(Base):
    __tablename__ = "player_season_ratings"
    player_id: Mapped[int] = mapped_column(ForeignKey("players.id"), primary_key=True)
    season_id: Mapped[int] = mapped_column(ForeignKey("seasons.id"), primary_key=True)
    team_id: Mapped[int] = mapped_column(ForeignKey("teams.id"), primary_key=True)
    position_family: Mapped[str | None] = mapped_column(String(2))
    appearances: Mapped[int] = mapped_column(SmallInteger)
    starts: Mapped[int] = mapped_column(SmallInteger)
    minutes: Mapped[float] = mapped_column(Float)
    overall: Mapped[float | None] = mapped_column(Float)
    overall_pct: Mapped[float | None] = mapped_column(Float)
    pillars: Mapped[dict | None] = mapped_column(JSON)
    per90: Mapped[dict | None] = mapped_column(JSON)
    reliable: Mapped[bool] = mapped_column(Boolean)


class PlayerFixture(Base):
    """Pre-match workload, selection features and the lineup prediction for a candidate."""

    __tablename__ = "player_fixtures"
    match_id: Mapped[int] = mapped_column(ForeignKey("matches.id"), primary_key=True)
    player_id: Mapped[int] = mapped_column(ForeignKey("players.id"), primary_key=True)
    position_family: Mapped[str | None] = mapped_column(String(2))
    minutes_7d: Mapped[float] = mapped_column(Float)
    minutes_14d: Mapped[float] = mapped_column(Float)
    minutes_30d: Mapped[float] = mapped_column(Float)
    consecutive_starts: Mapped[int] = mapped_column(SmallInteger)
    days_since_last_app: Mapped[int | None] = mapped_column(SmallInteger)
    starts_last5: Mapped[float] = mapped_column(Float)
    minutes_last5: Mapped[float] = mapped_column(Float)
    form_rating: Mapped[float | None] = mapped_column(Float)
    workload_index: Mapped[float] = mapped_column(Float)
    workload_band: Mapped[str] = mapped_column(String(10))
    p_start: Mapped[float | None] = mapped_column(Float)
    in_xi: Mapped[bool] = mapped_column(Boolean, default=False)
    slot: Mapped[str | None] = mapped_column(String(40))
    slot_x: Mapped[float | None] = mapped_column(Float)
    slot_y: Mapped[float | None] = mapped_column(Float)
    reasons: Mapped[list | None] = mapped_column(JSON)
    started: Mapped[bool | None] = mapped_column(Boolean)


class ModelVersion(Base):
    __tablename__ = "model_versions"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(60), unique=True)
    kind: Mapped[str] = mapped_column(String(20))  # outcome | lineup
    description: Mapped[str] = mapped_column(String(300))
    trained_at: Mapped[datetime | None] = mapped_column(DateTime)
    card: Mapped[dict] = mapped_column(JSON)
    evaluation: Mapped[dict | None] = mapped_column(JSON)


class Prediction(Base):
    __tablename__ = "predictions"
    match_id: Mapped[int] = mapped_column(ForeignKey("matches.id"), primary_key=True)
    model_version_id: Mapped[int] = mapped_column(ForeignKey("model_versions.id"), primary_key=True)
    p_win: Mapped[float] = mapped_column(Float)
    p_draw: Mapped[float] = mapped_column(Float)
    p_loss: Mapped[float] = mapped_column(Float)
    exp_goals_barca: Mapped[float | None] = mapped_column(Float)
    exp_goals_opp: Mapped[float | None] = mapped_column(Float)
    top_scores: Mapped[list | None] = mapped_column(JSON)
    market: Mapped[dict | None] = mapped_column(JSON)
    formation: Mapped[str | None] = mapped_column(String(8))
    explanation: Mapped[dict | None] = mapped_column(JSON)

    __table_args__ = (UniqueConstraint("match_id", "model_version_id"),)
