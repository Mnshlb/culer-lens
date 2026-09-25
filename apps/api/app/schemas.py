"""Response models. Everything the frontend consumes is typed here (OpenAPI at /docs)."""

from __future__ import annotations

from datetime import date
from typing import Any

from pydantic import BaseModel, Field


class TeamRef(BaseModel):
    id: int
    name: str
    short_name: str
    code: str


class Probabilities(BaseModel):
    win: float = Field(ge=0, le=1)
    draw: float = Field(ge=0, le=1)
    loss: float = Field(ge=0, le=1)


class ScoreProbability(BaseModel):
    barca: int
    opponent: int
    p: float


class MatchSummary(BaseModel):
    id: int
    date: date
    season: str
    competition: str
    opponent: TeamRef
    barca_home: bool
    barca_goals: int
    opponent_goals: int
    result: str
    era: str | None
    has_events: bool
    prediction: Probabilities | None = None


class Contribution(BaseModel):
    feature: str
    label: str
    value: float | None
    shap: float


class Explanation(BaseModel):
    base_value: float | None
    contributions: list[Contribution]
    groups: dict[str, float]


class PredictionOut(BaseModel):
    model: str
    probabilities: Probabilities
    expected_goals: dict[str, float | None]
    top_scores: list[ScoreProbability]
    market: Probabilities | None
    explanation: Explanation | None


class Reason(BaseModel):
    feature: str
    text: str
    shap: float


class LineupPlayer(BaseModel):
    player_id: int
    name: str
    position_family: str | None
    p_start: float | None
    in_xi: bool
    slot: str | None
    x: float | None
    y: float | None
    started: bool | None
    workload_index: float
    workload_band: str
    form_rating: float | None
    minutes_last5: float
    starts_last5: float
    reasons: list[Reason]


class LineupOut(BaseModel):
    formation: str | None
    predicted_xi: list[LineupPlayer]
    others: list[LineupPlayer]
    actual_xi: list[int]
    correct: int | None


class SideComparison(BaseModel):
    team: TeamRef
    elo: float | None
    form: list[str]
    points_5: float | None
    goals_10: float | None
    goals_against_10: float | None
    sot_10: float | None
    sot_against_10: float | None
    points_per_game_season: float | None
    days_rest: float | None


class MatchStatsSide(BaseModel):
    goals: int
    xg: float
    shots: int
    shots_on_target: int
    big_chances: int
    possession: float
    passes: int
    pass_completion: float
    progressive_passes: int
    box_entries: int
    pressures: int
    ppda: float
    field_tilt: float
    xt: float | None


class MatchDetail(BaseModel):
    match: MatchSummary
    prediction: PredictionOut | None
    lineup: LineupOut | None
    comparison: dict[str, SideComparison]
    stats: dict[str, MatchStatsSide] | None
    readiness: dict[str, Any] | None


class Shot(BaseModel):
    team: str
    player: str | None
    minute: int
    x: float
    y: float
    xg: float
    outcome: str | None
    body_part: str | None
    goal: bool


class PassNode(BaseModel):
    player_id: int
    name: str
    x: float
    y: float
    passes: int


class PassEdge(BaseModel):
    source: int
    target: int
    count: int


class PassNetwork(BaseModel):
    until_minute: float
    nodes: list[PassNode]
    edges: list[PassEdge]


class Overview(BaseModel):
    as_of: date
    next_match: MatchSummary
    prediction: PredictionOut | None
    form: list[MatchSummary]
    season_record: dict[str, Any]
    readiness: dict[str, Any] | None
    high_workload: list[LineupPlayer]
    elo: float | None


class PlayerListItem(BaseModel):
    id: int
    name: str
    position_family: str | None
    appearances: int
    minutes: float
    goals: int
    assists: int
    overall: float | None


class SeasonRating(BaseModel):
    season: str
    appearances: int
    starts: int
    minutes: float
    overall: float | None
    overall_pct: float | None
    reliable: bool
    pillars: dict[str, float | None] | None
    per90: dict[str, float | None] | None


class PlayerMatchRow(BaseModel):
    match_id: int
    date: date
    season: str
    opponent: str
    barca_home: bool
    result: str
    started: bool
    minutes: float
    goals: int
    assists: int
    xg: float
    xa: float
    xt: float
    progressive_passes: int
    progressive_carries: int
    pressures: int
    match_rating: float | None


class PlayerProfile(BaseModel):
    id: int
    name: str
    display_name: str
    country: str | None
    position_family: str | None
    position_group: str | None
    totals: dict[str, float]
    seasons: list[SeasonRating]
    form: list[float]
    workload: dict[str, Any] | None
    recent_matches: list[PlayerMatchRow]


class Zone(BaseModel):
    third: str
    channel: str
    total: int
    breakdown: dict[str, int]


class Heatmap(BaseModel):
    player_id: int
    family: str
    window: str
    matches: int
    events: int
    grid: list[list[float]]
    bins: tuple[int, int]
    zones: list[Zone]
    summary: dict[str, float | None]


class WorkloadPoint(BaseModel):
    match_id: int
    date: date
    opponent: str
    workload_index: float
    band: str
    minutes_7d: float
    minutes_14d: float
    minutes_30d: float
    consecutive_starts: int
    days_since_last_app: int | None
    started: bool | None


class Workload(BaseModel):
    player_id: int
    series: list[WorkloadPoint]
    latest_components: dict[str, float] | None


class ModelSummary(BaseModel):
    id: int
    name: str
    kind: str
    description: str
    headline: dict[str, Any]
