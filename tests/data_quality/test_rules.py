"""Run every data-quality rule against the processed tables."""

from __future__ import annotations

import pytest

from barca import pipeline
from barca.data import validate


@pytest.fixture(scope="module")
def results() -> list[validate.Result]:
    return validate.run(pipeline.processed_tables())


@pytest.mark.parametrize("rule", validate.RULES, ids=lambda r: f"{r.code} {r.description}")
def test_rule(results: list[validate.Result], rule: validate.Rule) -> None:
    result = next((r for r in results if r.code == rule.code), None)
    if result is None:
        pytest.skip(f"table {rule.table!r} not available")
    assert result.passed, f"{rule.code}: {result.violations} violations (tolerance {rule.tolerance}): {result.sample}"
