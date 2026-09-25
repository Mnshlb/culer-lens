"""The production outcome model: an equal-weight ensemble.

Chosen on the development seasons (2008/09-2013/14, D-026): Elo's ordered
logit, the Poisson goals model and a regularised LightGBM each capture a
different view of the same signal (strength, scoring rates, non-linear form
interactions), and their average beat every single model. The Poisson member
also supplies the score distribution. The Dixon-Coles low-score correction
was tested and did not help on the development seasons, so the goals are
modelled as independent Poissons.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from barca.models.baselines import EloModel, PoissonModel
from barca.models.data import Dataset
from barca.models.gbm import LightGBMModel


class EnsembleModel:
    name = "ensemble"

    def __init__(self) -> None:
        self.members: list[EloModel | PoissonModel | LightGBMModel] = [
            EloModel(),
            PoissonModel(dixon_coles=False),
            LightGBMModel(),
        ]

    def fit(self, ds: Dataset) -> EnsembleModel:
        for m in self.members:
            m.fit(ds)
        return self

    def predict_proba(self, X: pd.DataFrame) -> np.ndarray:
        return np.mean([m.predict_proba(X) for m in self.members], axis=0)

    def member_probas(self, X: pd.DataFrame) -> dict[str, np.ndarray]:
        return {m.name: m.predict_proba(X) for m in self.members}

    @property
    def poisson(self) -> PoissonModel:
        return next(m for m in self.members if isinstance(m, PoissonModel))

    @property
    def lightgbm(self) -> LightGBMModel:
        return next(m for m in self.members if isinstance(m, LightGBMModel))

    def score_matrix(self, X: pd.DataFrame) -> np.ndarray:
        return self.poisson.score_matrix(X)

    def expected_goals(self, X: pd.DataFrame) -> tuple[np.ndarray, np.ndarray]:
        return self.poisson.rates(X)
