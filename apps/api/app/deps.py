"""Request-scoped dependencies."""

from __future__ import annotations

from collections.abc import Iterator
from functools import lru_cache

from fastapi import Depends, HTTPException
from sqlalchemy import Engine, select
from sqlalchemy.orm import Session

from app.settings import Settings, get_settings
from barca.db import models as m
from barca.db.session import make_engine, session_factory


@lru_cache
def get_engine(url: str | None = None) -> Engine:
    return make_engine(url or get_settings().database_url)


def get_db() -> Iterator[Session]:
    session = session_factory(get_engine())()
    try:
        yield session
    finally:
        session.close()


def barca_team_id(db: Session = Depends(get_db), settings: Settings = Depends(get_settings)) -> int:
    team_id = db.scalar(select(m.Team.id).where(m.Team.name == settings.team))
    if team_id is None:
        raise HTTPException(status_code=503, detail="database is empty: run `barca db`")
    return team_id
