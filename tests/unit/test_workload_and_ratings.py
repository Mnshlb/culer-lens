from __future__ import annotations

import numpy as np
import polars as pl
import pytest

from barca.analytics import ratings, workload
from barca.models.baselines import PoissonModel, dixon_coles_tau
from barca.models.gbm import Temperature


def index(**kw: float) -> float:
    row = {
        "minutes_7d": 0.0,
        "minutes_14d": 0.0,
        "minutes_30d": 0.0,
        "consecutive_starts": 0,
        "days_since_last_app": 30,
    }
    row.update(kw)
    return pl.DataFrame([row]).select(workload.index_expr()).item()


def test_workload_index_bounds() -> None:
    assert index() == 0
    assert (
        index(
            minutes_7d=400,
            minutes_14d=800,
            minutes_30d=1500,
            consecutive_starts=20,
            days_since_last_app=1,
        )
        == 100
    )


def test_workload_components_add_up_to_the_index() -> None:
    row = {
        "minutes_7d": 90.0,
        "minutes_14d": 270.0,
        "minutes_30d": 450.0,
        "consecutive_starts": 6,
        "days_since_last_app": 4,
    }
    assert sum(workload.components(row).values()) == pytest.approx(index(**row), abs=0.6)


@pytest.mark.parametrize(
    ("value", "band"), [(10, "Low"), (35, "Moderate"), (60, "Elevated"), (80, "High")]
)
def test_workload_bands(value: float, band: str) -> None:
    assert pl.DataFrame({"workload_index": [value]}).select(workload.band_expr()).item() == band


def test_percentiles_use_mid_ranks() -> None:
    ref = np.array([1.0, 2.0, 3.0, 4.0])
    assert ratings._pct(np.array([0.0, 2.0, 5.0]), ref).tolist() == [0.0, 37.5, 100.0]


def test_match_rating_scale_is_centred_and_shrinks_cameos() -> None:
    frame = pl.DataFrame({"pct": [50.0, 97.5, 97.5], "minutes": [90.0, 90.0, 20.0]})
    r = (
        frame.select(ratings.match_rating_scale(pl.col("pct"), pl.col("minutes")))
        .to_series()
        .to_list()
    )
    assert r[0] == pytest.approx(6.5)
    assert r[1] == pytest.approx(6.5 + 1.96, abs=0.01)
    assert 6.5 < r[2] < r[1]


def test_dixon_coles_only_touches_low_scores() -> None:
    lam, mu = np.array([1.4]), np.array([1.1])
    assert dixon_coles_tau(np.array(2), np.array(1), lam, mu, -0.05)[0] == 1.0
    assert dixon_coles_tau(np.array(0), np.array(0), lam, mu, -0.05)[0] > 1.0


def test_poisson_score_matrix_is_a_distribution(results: pl.DataFrame) -> None:
    from barca.features import elo, tables, team_form

    fx = tables.fixture_table(
        results,
        team_form.team_form(results),
        elo.run(results),
        pl.DataFrame(schema={"fixture_id": pl.UInt32, "is_home": pl.Boolean, "match_id": pl.Int64}),
    )
    from barca.models.data import league_dataset

    ds = league_dataset(fx, start=2000)
    model = PoissonModel().fit(ds.rows(ds.season < 2002))
    m = model.score_matrix(ds.X[ds.season == 2002])
    assert np.allclose(m.sum(axis=(1, 2)), 1)
    p = model.predict_proba(ds.X[ds.season == 2002])
    assert np.allclose(p.sum(axis=1), 1)


def test_temperature_scaling_keeps_probabilities_valid() -> None:
    rng = np.random.default_rng(1)
    p = rng.dirichlet([2, 1, 1], size=300)
    y = rng.integers(0, 3, 300)
    t = Temperature().fit(p, y)
    q = t.apply(p)
    assert np.allclose(q.sum(axis=1), 1)
    assert 0.3 <= t.t <= 3.0
