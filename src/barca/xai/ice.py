"""Individual conditional expectation: one partial-dependence curve per match.

PDP shows the average effect of a feature; ICE shows whether that average
hides different behaviour for different matches. Curves are usually centred at
the first grid point (c-ICE), so they can be compared on shape alone.
"""

from __future__ import annotations

from collections.abc import Callable

import numpy as np
import pandas as pd

from barca.xai.pdp import Setter, curves


def ice(
    predict: Callable[[pd.DataFrame], np.ndarray],
    X: pd.DataFrame,
    grid: np.ndarray,
    setter: Setter,
    centred: bool = False,
) -> np.ndarray:
    c = curves(predict, X, grid, setter)
    return c - c[:, [0]] if centred else c


def heterogeneity(c: np.ndarray) -> float:
    """Spread of centred ICE curves at the end of the grid: 0 means every match reacts identically."""
    centred = c - c[:, [0]]
    return float(np.std(centred[:, -1]))
