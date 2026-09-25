"""Walk-forward backtesting: train on the past, predict the next season.

For every test season S in 2008/09 .. 2020/21, a fresh model is trained on
seasons before S and predicts every match of S. Nothing about S (not a
result, not a hyperparameter) is available to the model that predicts it.
"""

from __future__ import annotations

import json
import logging
import time
from collections.abc import Callable
from typing import Any, Protocol

import mlflow
import numpy as np
import polars as pl

from barca import config
from barca.models import metrics
from barca.models.data import TEST_SEASONS, Dataset

log = logging.getLogger(__name__)


class Model(Protocol):
    name: str

    def fit(self, ds: Dataset) -> Any: ...
    def predict_proba(self, X: Any) -> np.ndarray: ...


def walk_forward[M: Model](
    ds: Dataset,
    make_model: Callable[[], M],
    *,
    test_seasons: tuple[int, ...] = TEST_SEASONS,
    keep_models: bool = False,
) -> tuple[pl.DataFrame, dict[int, M]]:
    frames: list[pl.DataFrame] = []
    fitted: dict[int, M] = {}
    for season in test_seasons:
        train, test = ds.rows(ds.season < season), ds.rows(ds.season == season)
        if test.X.empty:
            continue
        model = make_model()
        model.fit(train)
        p = model.predict_proba(test.X)
        frames.append(
            test.meta.with_columns(
                pl.Series("y", test.y),
                pl.Series("p_w", p[:, 0]),
                pl.Series("p_d", p[:, 1]),
                pl.Series("p_l", p[:, 2]),
                pl.lit(model.name).alias("model"),
            )
        )
        if keep_models:
            fitted[season] = model
    return pl.concat(frames, how="diagonal_relaxed"), fitted


def probs(pred: pl.DataFrame) -> np.ndarray:
    return pred.select("p_w", "p_d", "p_l").to_numpy()


def score(pred: pl.DataFrame) -> dict[str, float]:
    return metrics.summary(pred["y"].to_numpy(), probs(pred))


def by_season(pred: pl.DataFrame) -> pl.DataFrame:
    rows = []
    for (season,), g in pred.group_by(["season_start"], maintain_order=True):
        rows.append({"season_start": season, **score(g)})
    return pl.DataFrame(rows).sort("season_start")


def track(
    pred: pl.DataFrame,
    *,
    experiment: str,
    run_name: str,
    params: dict[str, Any] | None = None,
    features: list[str] | None = None,
    tags: dict[str, str] | None = None,
) -> str:
    """Log a backtest to MLflow: parameters, overall and per-season metrics, predictions."""
    mlflow.set_tracking_uri(config.MLFLOW_URI)
    mlflow.set_experiment(experiment)
    with mlflow.start_run(run_name=run_name) as run:
        mlflow.set_tags({"model": pred["model"][0], **(tags or {})})
        if params:
            mlflow.log_params(
                {k: (json.dumps(v) if isinstance(v, dict | list) else v) for k, v in params.items()}
            )
        if features is not None:
            mlflow.log_param("n_features", len(features))
            mlflow.log_dict({"features": features}, "features.json")
        mlflow.log_metrics({k: v for k, v in score(pred).items() if k != "n"})
        for r in by_season(pred).iter_rows(named=True):
            for k in ("log_loss", "brier", "rps", "accuracy"):
                mlflow.log_metric(f"season_{k}", r[k], step=int(r["season_start"]))
        tmp = config.MODELS / "tmp" / f"{run_name}_{int(time.time())}.parquet"
        tmp.parent.mkdir(parents=True, exist_ok=True)
        pred.write_parquet(tmp)
        mlflow.log_artifact(str(tmp), artifact_path="predictions")
        tmp.unlink()
        return run.info.run_id
