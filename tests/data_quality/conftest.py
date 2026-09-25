from __future__ import annotations

import pytest

from barca import config


def pytest_collection_modifyitems(items: list[pytest.Item]) -> None:
    for item in items:
        if "data_quality" in str(item.fspath):
            item.add_marker(pytest.mark.data)


@pytest.fixture(scope="session", autouse=True)
def _require_processed_data() -> None:
    if not (config.PROCESSED / "matches.parquet").exists():
        pytest.skip("processed data not built: run `make data build`", allow_module_level=True)
