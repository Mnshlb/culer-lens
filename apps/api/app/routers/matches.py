"""Fixtures and the match centre."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from app import schemas as s
from app.deps import barca_team_id, get_db
from app.services import queries, spatial
from barca.db import models as m

router = APIRouter(prefix="/api/matches", tags=["matches"])


def _get(db: Session, match_id: int) -> m.Match:
    match = db.get(m.Match, match_id)
    if match is None:
        raise HTTPException(status_code=404, detail=f"match {match_id} not found")
    return match


@router.get("", response_model=list[s.MatchSummary], summary="Barcelona fixtures, optionally for one season")
def list_matches(
    season: str | None = Query(None, description="e.g. 2015/2016"),
    db: Session = Depends(get_db),
    barca_id: int = Depends(barca_team_id),
) -> list[s.MatchSummary]:
    q = queries.barca_matches(db, barca_id)
    if season:
        q = q.join(m.Season).where(m.Season.label == season)
    return [queries.summary(db, match) for match in db.scalars(q.order_by(m.Match.date)).all()]


@router.get("/{match_id}", response_model=s.MatchDetail, summary="Match centre: prediction, lineup, comparison")
def match_detail(match_id: int, db: Session = Depends(get_db), barca_id: int = Depends(barca_team_id)) -> s.MatchDetail:
    match = _get(db, match_id)
    barca = match.home_team if match.barca_home else match.away_team
    opponent = match.away_team if match.barca_home else match.home_team
    lineup = queries.lineup_out(db, match, barca_id)
    return s.MatchDetail(
        match=queries.summary(db, match),
        prediction=queries.prediction_out(db, match.id),
        lineup=lineup,
        comparison={"barca": queries.side(db, barca, match.date), "opponent": queries.side(db, opponent, match.date)},
        stats=queries.stats(db, match, barca_id),
        readiness=queries.readiness(lineup),
    )


@router.get("/{match_id}/shots", response_model=list[s.Shot], summary="Shot map (opponent mirrored)")
def match_shots(match_id: int, db: Session = Depends(get_db), barca_id: int = Depends(barca_team_id)) -> list[s.Shot]:
    _get(db, match_id)
    return spatial.shots(db, match_id, barca_id)


@router.get("/{match_id}/passes", response_model=s.PassNetwork, summary="Barcelona pass network")
def match_passes(match_id: int, min_count: int = Query(3, ge=1), db: Session = Depends(get_db),
                 barca_id: int = Depends(barca_team_id)) -> s.PassNetwork:
    _get(db, match_id)
    return spatial.pass_network(db, match_id, barca_id, min_count)


@router.get("/{match_id}/events/count", include_in_schema=False)
def event_count(match_id: int, db: Session = Depends(get_db)) -> dict[str, int]:
    return {"events": len(db.scalars(select(m.Event.id).where(m.Event.match_id == match_id)).all())}
