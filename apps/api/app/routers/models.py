"""Model Intelligence: cards, evaluation and global explanations."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app import schemas as s
from app.deps import get_db
from barca.db import models as m

router = APIRouter(prefix="/api/models", tags=["models"])


def _get(db: Session, model_id: int) -> m.ModelVersion:
    version = db.get(m.ModelVersion, model_id)
    if version is None:
        raise HTTPException(status_code=404, detail=f"model {model_id} not found")
    return version


@router.get("", response_model=list[s.ModelSummary])
def list_models(db: Session = Depends(get_db)) -> list[s.ModelSummary]:
    out = []
    for v in db.scalars(select(m.ModelVersion).order_by(m.ModelVersion.id)).all():
        headline = v.card.get("metrics", {}).get("league_holdout", {}) if v.kind == "outcome" else v.card
        out.append(s.ModelSummary(id=v.id, name=v.name, kind=v.kind, description=v.description, headline=headline))
    return out


@router.get("/{model_id}")
def model_detail(model_id: int, db: Session = Depends(get_db)) -> dict[str, Any]:
    v = _get(db, model_id)
    evaluation = dict(v.evaluation or {})
    evaluation.pop("global", None)
    return {"id": v.id, "name": v.name, "kind": v.kind, "description": v.description,
            "trained_at": v.trained_at, "card": v.card, "evaluation": evaluation}


@router.get("/{model_id}/explanation", summary="Global explanations: permutation importance, SHAP, PDP/ICE")
def model_explanation(model_id: int, db: Session = Depends(get_db)) -> dict[str, Any]:
    v = _get(db, model_id)
    if not v.evaluation or "global" not in v.evaluation:
        raise HTTPException(status_code=404, detail="no global explanation for this model")
    return v.evaluation["global"]
