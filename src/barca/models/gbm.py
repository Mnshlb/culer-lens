"""Tree ensembles: random forest, XGBoost and LightGBM, with nested tuning.

Hyperparameters are tuned *inside* each training window: the last season of
the window is held out as validation, Optuna searches on it, and the model is
then refitted on the whole window. No test season ever influences a
hyperparameter (walk-forward, D-018).
"""

from __future__ import annotations

import logging
from typing import ClassVar

import lightgbm as lgb
import numpy as np
import optuna
import pandas as pd
import xgboost as xgb
from scipy.optimize import minimize_scalar
from sklearn.ensemble import RandomForestClassifier

from barca.config import RANDOM_SEED
from barca.models import metrics
from barca.models.data import Dataset

optuna.logging.set_verbosity(optuna.logging.WARNING)
log = logging.getLogger(__name__)


def _split_last_seasons(ds: Dataset, k: int = 1) -> tuple[Dataset, Dataset]:
    """Hold out the last ``k`` seasons of a training window for early stopping, tuning and calibration."""
    cut = np.sort(np.unique(ds.season))[-k]
    return ds.rows(ds.season < cut), ds.rows(ds.season >= cut)


class Temperature:
    """Single-parameter calibration: p ∝ p_raw ** (1 / T), fitted on held-out predictions."""

    def __init__(self) -> None:
        self.t = 1.0

    def fit(self, p: np.ndarray, y: np.ndarray) -> Temperature:
        def nll(t: float) -> float:
            return metrics.log_loss(y, self.apply(p, t))

        self.t = float(minimize_scalar(nll, bounds=(0.3, 3.0), method="bounded").x)
        return self

    def apply(self, p: np.ndarray, t: float | None = None) -> np.ndarray:
        z = np.log(np.clip(p, 1e-12, 1)) / (t or self.t)
        z = np.exp(z - z.max(axis=1, keepdims=True))
        return z / z.sum(axis=1, keepdims=True)


class RandomForestModel:
    name = "random_forest"

    def __init__(
        self, n_estimators: int = 600, min_samples_leaf: int = 25, max_features: float = 0.3
    ):
        self.kw = {
            "n_estimators": n_estimators,
            "min_samples_leaf": min_samples_leaf,
            "max_features": max_features,
        }

    def fit(self, ds: Dataset) -> RandomForestModel:
        self.model_ = RandomForestClassifier(**self.kw, n_jobs=-1, random_state=RANDOM_SEED).fit(
            ds.X, ds.y
        )
        return self

    def predict_proba(self, X: pd.DataFrame) -> np.ndarray:
        return self.model_.predict_proba(X)


class LightGBMModel:
    name = "lightgbm"

    DEFAULTS: ClassVar[dict[str, float]] = {
        "learning_rate": 0.03,
        "num_leaves": 8,
        "min_child_samples": 60,
        "subsample": 0.8,
        "subsample_freq": 1,
        "colsample_bytree": 0.5,
        "reg_lambda": 1.0,
    }

    def __init__(
        self,
        n_trials: int = 0,
        calibrate: bool = True,
        params: dict | None = None,
        val_seasons: int = 1,
    ):
        self.n_trials = n_trials
        self.calibrate = calibrate
        self.params = params
        self.val_seasons = val_seasons

    def _estimator(self, params: dict, n_estimators: int) -> lgb.LGBMClassifier:
        return lgb.LGBMClassifier(
            objective="multiclass",
            n_estimators=n_estimators,
            random_state=RANDOM_SEED,
            verbose=-1,
            n_jobs=4,
            **params,
        )

    def _fit_early(
        self, params: dict, tr: Dataset, va: Dataset
    ) -> tuple[lgb.LGBMClassifier, float]:
        est = self._estimator(params, 3000)
        est.fit(
            tr.X,
            tr.y,
            eval_X=va.X,
            eval_y=va.y,
            eval_metric="multi_logloss",
            callbacks=[lgb.early_stopping(150, verbose=False)],
        )
        return est, metrics.log_loss(va.y, np.asarray(est.predict_proba(va.X)))

    def fit(self, ds: Dataset) -> LightGBMModel:
        tr, va = _split_last_seasons(ds, self.val_seasons)
        params = dict(self.params or self.DEFAULTS)
        if self.n_trials:

            def objective(trial: optuna.Trial) -> float:
                p = {
                    "learning_rate": trial.suggest_float("learning_rate", 0.01, 0.1, log=True),
                    "num_leaves": trial.suggest_int("num_leaves", 4, 32),
                    "min_child_samples": trial.suggest_int("min_child_samples", 20, 300, log=True),
                    "subsample": trial.suggest_float("subsample", 0.5, 1.0),
                    "subsample_freq": 1,
                    "colsample_bytree": trial.suggest_float("colsample_bytree", 0.2, 1.0),
                    "reg_lambda": trial.suggest_float("reg_lambda", 1e-3, 30.0, log=True),
                }
                return self._fit_early(p, tr, va)[1]

            study = optuna.create_study(
                direction="minimize", sampler=optuna.samplers.TPESampler(seed=RANDOM_SEED)
            )
            study.optimize(objective, n_trials=self.n_trials)
            params = {**study.best_params, "subsample_freq": 1}
            self.study_value_ = study.best_value
        est, _ = self._fit_early(params, tr, va)
        self.n_estimators_ = max(int(est.best_iteration_ or 100), 20)
        self.temperature_ = (
            Temperature().fit(np.asarray(est.predict_proba(va.X)), va.y) if self.calibrate else None
        )
        self.params_ = params
        self.model_ = self._estimator(params, self.n_estimators_).fit(ds.X, ds.y)
        return self

    def predict_proba(self, X: pd.DataFrame) -> np.ndarray:
        p = np.asarray(self.model_.predict_proba(X))
        return self.temperature_.apply(p) if self.temperature_ else p


class XGBoostModel:
    name = "xgboost"

    DEFAULTS: ClassVar[dict[str, float]] = {
        "learning_rate": 0.03,
        "max_depth": 3,
        "min_child_weight": 10.0,
        "subsample": 0.8,
        "colsample_bytree": 0.5,
        "reg_lambda": 1.0,
    }

    def __init__(
        self,
        n_trials: int = 0,
        calibrate: bool = True,
        params: dict | None = None,
        val_seasons: int = 1,
    ):
        self.n_trials = n_trials
        self.calibrate = calibrate
        self.params = params
        self.val_seasons = val_seasons

    def _estimator(self, params: dict, n_estimators: int, early: bool) -> xgb.XGBClassifier:
        return xgb.XGBClassifier(
            objective="multi:softprob",
            n_estimators=n_estimators,
            tree_method="hist",
            random_state=RANDOM_SEED,
            n_jobs=4,
            eval_metric="mlogloss",
            early_stopping_rounds=150 if early else None,
            **params,
        )

    def _fit_early(self, params: dict, tr: Dataset, va: Dataset) -> tuple[xgb.XGBClassifier, float]:
        est = self._estimator(params, 3000, early=True)
        est.fit(tr.X, tr.y, eval_set=[(va.X, va.y)], verbose=False)
        return est, metrics.log_loss(va.y, est.predict_proba(va.X))

    def fit(self, ds: Dataset) -> XGBoostModel:
        tr, va = _split_last_seasons(ds, self.val_seasons)
        params = dict(self.params or self.DEFAULTS)
        if self.n_trials:

            def objective(trial: optuna.Trial) -> float:
                p = {
                    "learning_rate": trial.suggest_float("learning_rate", 0.01, 0.1, log=True),
                    "max_depth": trial.suggest_int("max_depth", 2, 6),
                    "min_child_weight": trial.suggest_float(
                        "min_child_weight", 1.0, 50.0, log=True
                    ),
                    "subsample": trial.suggest_float("subsample", 0.5, 1.0),
                    "colsample_bytree": trial.suggest_float("colsample_bytree", 0.2, 1.0),
                    "reg_lambda": trial.suggest_float("reg_lambda", 1e-3, 30.0, log=True),
                }
                return self._fit_early(p, tr, va)[1]

            study = optuna.create_study(
                direction="minimize", sampler=optuna.samplers.TPESampler(seed=RANDOM_SEED)
            )
            study.optimize(objective, n_trials=self.n_trials)
            params = study.best_params
            self.study_value_ = study.best_value
        est, _ = self._fit_early(params, tr, va)
        self.n_estimators_ = max(int(est.best_iteration or 100) + 1, 20)
        self.temperature_ = (
            Temperature().fit(est.predict_proba(va.X), va.y) if self.calibrate else None
        )
        self.params_ = params
        self.model_ = self._estimator(params, self.n_estimators_, early=False).fit(ds.X, ds.y)
        return self

    def predict_proba(self, X: pd.DataFrame) -> np.ndarray:
        p = self.model_.predict_proba(X)
        return self.temperature_.apply(p) if self.temperature_ else p
