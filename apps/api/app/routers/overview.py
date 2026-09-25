"""The dashboard: what is happening with Barcelona as of a date."""

from __future__ import annotations

from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from app import schemas as s
from app.deps import barca_team_id, get_db
from app.services import queries
from barca.db import models as m

router = APIRouter(prefix="/api", tags=["overview"])


@router.get(
    "/overview",
    response_model=s.Overview,
    summary="Next fixture as of a date, form, readiness, workload",
)
def overview(
    as_of: date | None = Query(
        None, description="Show the platform as it looked on this date (default: last fixture)"
    ),
    db: Session = Depends(get_db),
    barca_id: int = Depends(barca_team_id),
) -> s.Overview:
    match = queries.next_match(db, barca_id, as_of)
    if match is None:
        raise HTTPException(status_code=404, detail="no fixtures")
    lineup = queries.lineup_out(db, match, barca_id)
    candidates = (lineup.predicted_xi + lineup.others) if lineup else []
    high = sorted(candidates, key=lambda p: -p.workload_index)[:5]
    tf = db.scalar(
        select(m.TeamFeatures).where(
            m.TeamFeatures.team_id == barca_id, m.TeamFeatures.date == match.date
        )
    )
    return s.Overview(
        as_of=as_of or match.date,
        next_match=queries.summary(db, match),
        prediction=queries.prediction_out(db, match.id),
        form=[
            queries.summary(db, x) for x in queries.previous_matches(db, barca_id, match.date, 5)
        ],
        season_record=queries.season_record(db, barca_id, match.season_id, match.date),
        readiness=queries.readiness(lineup),
        high_workload=high,
        elo=tf.elo if tf else None,
    )


@router.get("/seasons", summary="Seasons with Barcelona fixtures")
def seasons(db: Session = Depends(get_db), barca_id: int = Depends(barca_team_id)) -> list[dict]:
    rows = db.execute(
        select(m.Season.label, m.Season.start_year)
        .join(m.Match, m.Match.season_id == m.Season.id)
        .where((m.Match.home_team_id == barca_id) | (m.Match.away_team_id == barca_id))
        .group_by(m.Season.label, m.Season.start_year)
        .order_by(m.Season.start_year)
    ).all()
    return [{"label": label, "start_year": year} for label, year in rows]
