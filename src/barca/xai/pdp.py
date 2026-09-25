"""Partial dependence: the average effect of changing one input.

Several features are arithmetic functions of others (``elo_diff`` is
``h_elo − a_elo``; ``elo_expected`` follows from both). Varying one of them
alone would create impossible rows, so a ``setter`` rebuilds the derived
features consistently for every grid value.
"""

from __future__ import annotations

from collections.abc import Callable

import numpy as np
import pandas as pd

Setter = Callable[[pd.DataFrame, float], pd.DataFrame]


def set_opponent_elo(barca_home: bool, home_advantage: float = 80.0) -> Setter:
    """Setter that moves the opponent's Elo and keeps the Elo gap and expectation consistent."""

    def apply(X: pd.DataFrame, value: float) -> pd.DataFrame:
        X = X.copy()
        opp, own = ("a_elo", "h_elo") if barca_home else ("h_elo", "a_elo")
        X[opp] = value
        X["elo_diff"] = X["h_elo"] - X["a_elo"]
        X["elo_expected"] = 1 / (1 + 10 ** ((X["a_elo"] - X["h_elo"] - home_advantage) / 400))
        del own
        return X

    return apply


def curves(
    predict: Callable[[pd.DataFrame], np.ndarray], X: pd.DataFrame, grid: np.ndarray, setter: Setter
) -> np.ndarray:
    """Predictions for every row at every grid value, shape (rows, grid)."""
    return np.column_stack([predict(setter(X, float(v))) for v in grid])


def partial_dependence(
    predict: Callable[[pd.DataFrame], np.ndarray], X: pd.DataFrame, grid: np.ndarray, setter: Setter
) -> np.ndarray:
    return curves(predict, X, grid, setter).mean(axis=0)
