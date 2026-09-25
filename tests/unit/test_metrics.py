from __future__ import annotations

import numpy as np
import pytest

from barca.models import metrics


def test_perfect_forecast_scores_zero() -> None:
    y = np.array([0, 1, 2])
    p = np.eye(3)
    assert metrics.brier(y, p) == pytest.approx(0)
    assert metrics.rps(y, p) == pytest.approx(0)
    assert metrics.log_loss(y, p) == pytest.approx(0, abs=1e-9)
    assert metrics.accuracy(y, p) == 1


def test_rps_respects_outcome_order() -> None:
    y = np.array([0])  # a win
    predicts_draw = np.array([[0.0, 1.0, 0.0]])
    predicts_loss = np.array([[0.0, 0.0, 1.0]])
    assert metrics.rps(y, predicts_draw) < metrics.rps(y, predicts_loss)
    # Brier does not care about order
    assert metrics.brier(y, predicts_draw) == pytest.approx(metrics.brier(y, predicts_loss))


def test_uniform_forecast_log_loss_is_log3() -> None:
    y = np.array([0, 1, 2, 0])
    assert metrics.log_loss(y, np.full((4, 3), 1 / 3)) == pytest.approx(np.log(3))


def test_calibration_error_is_zero_for_calibrated_bins() -> None:
    rng = np.random.default_rng(0)
    p = np.tile([0.5, 0.3, 0.2], (20000, 1))
    y = rng.choice(3, size=20000, p=[0.5, 0.3, 0.2])
    assert metrics.ece(y, p) < 0.01
