"""Apply Alembic migrations programmatically."""

from __future__ import annotations

from alembic import command
from alembic.config import Config
from sqlalchemy import Engine

from barca import config

ALEMBIC_INI = config.ROOT / "apps" / "api" / "alembic.ini"


def upgrade(engine: Engine) -> None:
    cfg = Config(str(ALEMBIC_INI))
    cfg.attributes["engine"] = engine
    command.upgrade(cfg, "head")
