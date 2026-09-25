"""Alembic environment: the schema is defined in ``barca.db.models``; the URL comes from DATABASE_URL."""

from __future__ import annotations

from alembic import context

from barca.db.models import Base
from barca.db.session import make_engine

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    from barca.db.session import database_url

    context.configure(
        url=database_url(),
        target_metadata=target_metadata,
        literal_binds=True,
        render_as_batch=True,
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    engine = context.config.attributes.get("engine") or make_engine()
    with engine.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            render_as_batch=connection.dialect.name == "sqlite",
        )
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
