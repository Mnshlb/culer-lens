"""Permutation importance: how much worse does the model get when a feature is scrambled?

Importance is measured out of sample, season by season: each test season is
scored by the model trained before it, then each feature (or group of
correlated features, permuted together) is shuffled within the season and
the increase in log loss is recorded. Grouping matters here because many
features are near-duplicates (the opponent's Elo and the Elo gap). Permuting
one of them alone understates the information the group carries.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

import numpy as np
import pandas as pd

from barca.models import metrics


def permutation_importance(
    models: Mapping[int, Any],
    seasons: Mapping[int, tuple[pd.DataFrame, np.ndarray]],
    groups: Mapping[str, Sequence[str]],
    n_repeats: int = 5,
    seed: int = 0,
) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    rows = []
    for season, (X, y) in seasons.items():
        model = models[season]
        base = metrics.log_loss(y, model.predict_proba(X))
        for name, cols in groups.items():
            drops = []
            for _ in range(n_repeats):
                Xp = X.copy()
                perm = rng.permutation(len(X))
                Xp[list(cols)] = X[list(cols)].to_numpy()[perm]
                drops.append(metrics.log_loss(y, model.predict_proba(Xp)) - base)
            rows.append(
                {
                    "season": season,
                    "group": name,
                    "n": len(y),
                    "increase": float(np.mean(drops)),
                    "std": float(np.std(drops)),
                }
            )
    frame = pd.DataFrame(rows)
    weighted = (
        frame.assign(w=frame["increase"] * frame["n"])
        .groupby("group")
        .agg(increase=("w", "sum"), n=("n", "sum"), std=("std", "mean"))
    )
    weighted["increase"] = weighted["increase"] / weighted["n"]
    return weighted.drop(columns="n").sort_values("increase", ascending=False).reset_index()
