"""SHAP explanations.

Two explainers, for two jobs:

* **TreeSHAP on the LightGBM member**: exact and fast, used for global
  patterns (which features drive the non-linear part of the model).
* **Permutation SHAP on the whole ensemble**: model-agnostic, used for local
  explanations of the probability the app actually shows ("why 64%?").
  Background data is a sample of the model's own training rows, and the
  explanation is always computed with the season-specific model that made the
  prediction.
"""

from __future__ import annotations

from collections.abc import Callable

import numpy as np
import pandas as pd
import shap


def tree_shap(lgbm_estimator, X: pd.DataFrame) -> np.ndarray:
    """SHAP values of the LightGBM member, shape (n, features, classes) in log-odds space."""
    values = shap.TreeExplainer(lgbm_estimator).shap_values(X)
    arr = np.asarray(values)
    if arr.ndim == 3 and arr.shape[0] == 3 and arr.shape[1] == len(X):  # list-of-classes layout
        arr = np.transpose(arr, (1, 2, 0))
    return arr


def probability_explainer(
    predict_class: Callable[[np.ndarray], np.ndarray], background: pd.DataFrame, seed: int = 0
) -> shap.Explainer:
    masker = shap.maskers.Independent(background, max_samples=len(background))
    return shap.explainers.Permutation(predict_class, masker, seed=seed)


def explain_probability(
    predict_proba: Callable[[pd.DataFrame], np.ndarray],
    X: pd.DataFrame,
    background: pd.DataFrame,
    class_index: np.ndarray,
    max_evals: int = 400,
) -> tuple[np.ndarray, np.ndarray]:
    """Per-row SHAP values of P(class_index[i]) for each row i.

    Returns (values of shape (n, features), base values of shape (n,)). Rows
    with different target classes are explained in separate batches.
    """
    values = np.zeros((len(X), X.shape[1]))
    base = np.zeros(len(X))
    for k in np.unique(class_index):
        rows = np.where(class_index == k)[0]

        def f(data: np.ndarray, k: int = int(k)) -> np.ndarray:
            return predict_proba(pd.DataFrame(data, columns=X.columns))[:, k]

        explainer = probability_explainer(f, background)
        exp = explainer(
            X.to_numpy()[rows], max_evals=max(max_evals, 2 * X.shape[1] + 1), silent=True
        )
        values[rows] = exp.values
        base[rows] = np.asarray(exp.base_values).reshape(-1)
    return values, base


def top_contributions(
    values: np.ndarray,
    X: pd.DataFrame,
    view: Callable[[str, float | None], tuple[str, float | None]],
    k: int = 8,
) -> list[dict]:
    """The k largest absolute contributions for one row, as display-ready records.

    ``view`` maps (feature, raw value) to the label and value shown to a user.
    """
    order = np.argsort(-np.abs(values))[:k]
    out = []
    for i in order:
        raw = None if pd.isna(X.iloc[0, i]) else float(X.iloc[0, i])
        label, shown = view(X.columns[i], raw)
        out.append(
            {"feature": X.columns[i], "label": label, "value": shown, "shap": float(values[i])}
        )
    return out
