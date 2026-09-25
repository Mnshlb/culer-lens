"""Team form and strength."""

from __future__ import annotations

from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import desc, select
from sqlalchemy.orm import Session

from app.deps import get_db
from app.services import queries
from barca.db import models as m

router = APIRouter(prefix="/api/teams", tags=["teams"])


@router.get("/{team_id}/form", summary="Recent results and Elo trajectory of any club")
def form(team_id: int, as_of: date | None = None, n: int = Query(10, ge=1, le=60), db: Session = Depends(get_db)) -> dict:
    team = db.get(m.Team, team_id)
    if team is None:
        raise HTTPException(status_code=404, detail=f"team {team_id} not found")
    before = as_of or date.max
    recent = queries.recent_results(db, team_id, before, n)
    names = dict(db.execute(select(m.Team.id, m.Team.name)).all())
    elo = db.execute(
        select(m.TeamFeatures.date, m.TeamFeatures.elo_post).where(m.TeamFeatures.team_id == team_id,
                                                                   m.TeamFeatures.date < before)
        .order_by(desc(m.TeamFeatures.date)).limit(380)
    ).all()
    return {
        "team": queries.team_ref(team).model_dump(),
        "results": [{"date": r.date, "opponent": names.get(r.opponent_id), "home": r.is_home, "goals": r.goals,
                     "goals_against": r.goals_against, "result": r.result, "elo_before": r.elo} for r in recent],
        "elo": [{"date": d, "elo": e} for d, e in reversed(elo)],
    }


@router.get("", summary="All clubs")
def teams(db: Session = Depends(get_db)) -> list[dict]:
    return [queries.team_ref(t).model_dump() for t in db.scalars(select(m.Team).order_by(m.Team.name)).all()]
