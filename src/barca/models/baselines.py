"""Baseline outcome models, from trivial to statistical.

Every model follows the same small interface: ``fit(dataset)`` and
``predict_proba(X)`` returning probabilities for ``[win, draw, loss]`` of the
reference side (home team or Barcelona).
"""

from __future__ import annotations

import numpy as np
import pandas as pd
from scipy.optimize import minimize_scalar
from scipy.stats import poisson
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression, PoissonRegressor
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler
from statsmodels.miscmodels.ordinal_model import OrderedModel

from barca.models.data import Dataset


class NaiveModel:
    """Predicts the training-set frequency of each outcome, for every match."""

    name = "naive"

    def fit(self, ds: Dataset) -> NaiveModel:
        self.p_ = np.bincount(ds.y, minlength=3) / len(ds.y)
        return self

    def predict_proba(self, X: pd.DataFrame) -> np.ndarray:
        return np.tile(self.p_, (len(X), 1))


class EloModel:
    """Ordered logit of the outcome on the pre-match Elo difference.

    Outcomes are ordinal (loss < draw < win), so one latent strength
    difference and two thresholds give all three probabilities. Home
    advantage is absorbed by the thresholds for league fixtures and by an
    explicit home indicator for Barcelona's matches.
    """

    name = "elo"

    def __init__(self, columns: tuple[str, ...] = ("elo_diff",)):
        self.columns = columns

    def _x(self, X: pd.DataFrame) -> pd.DataFrame:
        cols = [c for c in self.columns if c in X.columns]
        return X[cols].fillna(0.0)

    def fit(self, ds: Dataset) -> EloModel:
        # OrderedModel expects increasing categories: loss (0) < draw (1) < win (2)
        y = 2 - ds.y
        self.model_ = OrderedModel(y, self._x(ds.X), distr="logit").fit(method="bfgs", disp=False)
        return self

    def predict_proba(self, X: pd.DataFrame) -> np.ndarray:
        p = np.asarray(self.model_.predict(self._x(X)))  # columns: loss, draw, win
        return p[:, ::-1]


class LogisticModel:
    """Regularised multinomial logistic regression on every feature."""

    name = "logistic"

    def __init__(self, C: float = 0.05):
        self.C = C

    def fit(self, ds: Dataset) -> LogisticModel:
        self.pipe_ = make_pipeline(
            SimpleImputer(strategy="median"), StandardScaler(),
            LogisticRegression(C=self.C, max_iter=2000),
        )
        self.pipe_.fit(ds.X, ds.y)
        return self

    def predict_proba(self, X: pd.DataFrame) -> np.ndarray:
        return self.pipe_.predict_proba(X)


POISSON_FEATURES = [
    "elo_diff", "h_elo", "a_elo", "h_goals_10", "h_goals_against_10", "a_goals_10", "a_goals_against_10",
    "h_sot_10", "h_sot_against_10", "a_sot_10", "a_sot_against_10", "h_points_std", "a_points_std",
]
POISSON_FEATURES_BARCA = [
    "elo_diff", "barca_elo", "opp_elo", "is_home", "barca_goals_10", "barca_goals_against_10", "opp_goals_10",
    "opp_goals_against_10", "barca_sot_10", "barca_sot_against_10", "opp_sot_10", "opp_sot_against_10",
    "barca_points_std", "opp_points_std",
]
MAX_GOALS = 10


def dixon_coles_tau(x: np.ndarray, y: np.ndarray, lam: np.ndarray, mu: np.ndarray, rho: float) -> np.ndarray:
    """Dixon-Coles adjustment for the four low scores independent Poissons get wrong."""
    tau = np.ones_like(lam, dtype=float)
    tau = np.where((x == 0) & (y == 0), 1 - lam * mu * rho, tau)
    tau = np.where((x == 0) & (y == 1), 1 + lam * rho, tau)
    tau = np.where((x == 1) & (y == 0), 1 + mu * rho, tau)
    tau = np.where((x == 1) & (y == 1), 1 - rho, tau)
    return tau


class PoissonModel:
    """Goals model: two Poisson regressions plus a Dixon-Coles low-score correction.

    Predicts expected goals for each side (lambda, mu) from pre-match
    features, builds the full score distribution, and reads win/draw/loss off
    it. It is also the score model used by the app (likely scorelines).
    """

    name = "poisson"

    def __init__(self, features: list[str] | None = None, alpha: float = 1e-3, dixon_coles: bool = True):
        self.features = features
        self.alpha = alpha
        self.dixon_coles = dixon_coles

    def _cols(self, X: pd.DataFrame) -> list[str]:
        cand = self.features or (POISSON_FEATURES if "h_elo" in X.columns else POISSON_FEATURES_BARCA)
        return [c for c in cand if c in X.columns]

    def fit(self, ds: Dataset) -> PoissonModel:
        cols = self._cols(ds.X)
        self.cols_ = cols
        gf, ga = ds.goals()

        def model() -> object:
            return make_pipeline(SimpleImputer(strategy="median"), StandardScaler(),
                                 PoissonRegressor(alpha=self.alpha, max_iter=1000))

        self.for_ = model().fit(ds.X[cols], gf)
        self.against_ = model().fit(ds.X[cols], ga)
        self.rho_ = 0.0
        if self.dixon_coles:
            lam, mu = self.rates(ds.X)

            def nll(rho: float) -> float:
                tau = dixon_coles_tau(gf, ga, lam, mu, rho)
                return -np.sum(np.log(np.clip(tau, 1e-9, None)))

            self.rho_ = float(minimize_scalar(nll, bounds=(-0.3, 0.3), method="bounded").x)
        return self

    def rates(self, X: pd.DataFrame) -> tuple[np.ndarray, np.ndarray]:
        return self.for_.predict(X[self.cols_]), self.against_.predict(X[self.cols_])

    def score_matrix(self, X: pd.DataFrame) -> np.ndarray:
        """P(goals_for = i, goals_against = j), shape (n, MAX_GOALS + 1, MAX_GOALS + 1)."""
        lam, mu = self.rates(X)
        g = np.arange(MAX_GOALS + 1)
        pf = poisson.pmf(g[None, :], lam[:, None])
        pa = poisson.pmf(g[None, :], mu[:, None])
        m = pf[:, :, None] * pa[:, None, :]
        if self.rho_:
            for i in (0, 1):
                for j in (0, 1):
                    m[:, i, j] *= dixon_coles_tau(np.array(i), np.array(j), lam, mu, self.rho_)
        return m / m.sum(axis=(1, 2), keepdims=True)

    def predict_proba(self, X: pd.DataFrame) -> np.ndarray:
        m = self.score_matrix(X)
        win = np.tril(np.ones((MAX_GOALS + 1, MAX_GOALS + 1)), -1)
        draw = np.eye(MAX_GOALS + 1)
        loss = np.triu(np.ones((MAX_GOALS + 1, MAX_GOALS + 1)), 1)
        return np.stack([(m * win).sum(axis=(1, 2)), (m * draw).sum(axis=(1, 2)), (m * loss).sum(axis=(1, 2))], axis=1)
