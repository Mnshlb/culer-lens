"""Model outputs for a fixture."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app import schemas as s
from app.deps import barca_team_id, get_db
from app.services import queries
from barca.db import models as m

router = APIRouter(prefix="/api/predictions", tags=["predictions"])


@router.get("/match/{match_id}", response_model=s.PredictionOut, summary="Outcome, expected goals, scores, SHAP")
def match_prediction(match_id: int, db: Session = Depends(get_db)) -> s.PredictionOut:
    out = queries.prediction_out(db, match_id)
    if out is None:
        raise HTTPException(status_code=404, detail="no prediction for this match (finals are outside the league model)")
    return out


@router.get("/lineup/{match_id}", response_model=s.LineupOut, summary="Predicted XI with start probabilities")
def lineup_prediction(match_id: int, db: Session = Depends(get_db), barca_id: int = Depends(barca_team_id)) -> s.LineupOut:
    match = db.get(m.Match, match_id)
    out = queries.lineup_out(db, match, barca_id) if match else None
    if out is None:
        raise HTTPException(status_code=404, detail="no lineup prediction for this match")
    return out
