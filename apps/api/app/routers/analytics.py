"""Event analytics for a match (aliases kept for the documented API surface)."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app import schemas as s
from app.deps import barca_team_id, get_db
from app.services import spatial

router = APIRouter(prefix="/api/analytics", tags=["analytics"])


@router.get("/shots/{match_id}", response_model=list[s.Shot])
def shots(
    match_id: int, db: Session = Depends(get_db), barca_id: int = Depends(barca_team_id)
) -> list[s.Shot]:
    return spatial.shots(db, match_id, barca_id)


@router.get("/passes/{match_id}", response_model=s.PassNetwork)
def passes(
    match_id: int, db: Session = Depends(get_db), barca_id: int = Depends(barca_team_id)
) -> s.PassNetwork:
    return spatial.pass_network(db, match_id, barca_id)
