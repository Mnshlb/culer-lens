from __future__ import annotations

import pytest
from sqlalchemy import Engine, inspect

from barca.db.models import Base

pytestmark = pytest.mark.integration


def test_migrations_create_the_orm_schema(engine: Engine) -> None:
    insp = inspect(engine)
    for table in Base.metadata.sorted_tables:
        assert insp.has_table(table.name), table.name
        db_cols = {c["name"] for c in insp.get_columns(table.name)}
        assert db_cols == {c.name for c in table.columns}, table.name
