"""Train the production outcome model walk-forward and store its predictions.

For every season 2008/09-2020/21 the ensemble is trained on all earlier
La Liga seasons (from 2005/06) and predicts every fixture of that season.
These out-of-sample predictions are what the app shows for each fixture: the
prediction it would have made that morning. The fitted model of each season
is kept so that explanations (SHAP) can be computed for exactly the model that
made the prediction.
"""

from __future__ import annotations

import json
import logging
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import joblib
import numpy as np
import polars as pl

from barca import config
from barca.data import store
from barca.models import backtest, data, metrics
from barca.models.ensemble import EnsembleModel

log = logging.getLogger(__name__)

MODEL_DIR = config.MODELS / "match_outcome"
DEV_SEASONS = tuple(range(2008, 2014))
HOLDOUT_SEASONS = tuple(range(2014, 2021))
TOP_SCORES = 8
MODEL_VERSION = "match-outcome-ensemble-v1"


def _barca_view(pred: pl.DataFrame) -> pl.DataFrame:
    """Re-express home-perspective predictions for Barcelona fixtures as W/D/L."""
    b = pred.filter((pl.col("home") == "Barcelona") | (pl.col("away") == "Barcelona"))
    home = pl.col("home") == "Barcelona"
    return b.select(
        "fixture_id",
        "date",
        "season",
        "season_start",
        home.alias("is_home"),
        pl.when(home).then(pl.col("away")).otherwise(pl.col("home")).alias("opponent"),
        pl.when(home)
        .then(pl.col("home_goals"))
        .otherwise(pl.col("away_goals"))
        .alias("barca_goals"),
        pl.when(home).then(pl.col("away_goals")).otherwise(pl.col("home_goals")).alias("opp_goals"),
        pl.when(home).then(pl.col("p_w")).otherwise(pl.col("p_l")).alias("p_win"),
        pl.col("p_d").alias("p_draw"),
        pl.when(home).then(pl.col("p_l")).otherwise(pl.col("p_w")).alias("p_loss"),
        pl.when(home).then(pl.col("xg_home")).otherwise(pl.col("xg_away")).alias("exp_goals_barca"),
        pl.when(home).then(pl.col("xg_away")).otherwise(pl.col("xg_home")).alias("exp_goals_opp"),
        pl.when(home).then(pl.col("mkt_avg_h")).otherwise(pl.col("mkt_avg_a")).alias("mkt_win"),
        pl.col("mkt_avg_d").alias("mkt_draw"),
        pl.when(home).then(pl.col("mkt_avg_a")).otherwise(pl.col("mkt_avg_h")).alias("mkt_loss"),
        "scores",
        "result",
    ).with_columns(
        pl.when(pl.col("barca_goals") > pl.col("opp_goals"))
        .then(pl.lit("W"))
        .when(pl.col("barca_goals") == pl.col("opp_goals"))
        .then(pl.lit("D"))
        .otherwise(pl.lit("L"))
        .alias("barca_result")
    )


def _top_scores(
    matrix: np.ndarray, barca_home: bool | None = None, k: int = TOP_SCORES
) -> list[dict]:
    flat = matrix.reshape(-1)
    order = np.argsort(flat)[::-1][:k]
    n = matrix.shape[1]
    out = []
    for idx in order:
        h, a = divmod(int(idx), n)
        out.append({"home": h, "away": a, "p": round(float(flat[idx]), 4)})
    return out


def train(track: bool = True) -> dict[str, Any]:
    fixtures = store.features("fixtures")
    ds = data.league_dataset(fixtures)
    pred, models = backtest.walk_forward(ds, EnsembleModel, keep_models=True)

    # score distributions and expected goals from the Poisson member of each season's model
    scores, xg_h, xg_a = [], [], []
    for season, model in models.items():
        test = ds.rows(ds.season == season)
        m = model.score_matrix(test.X)
        lam, mu = model.expected_goals(test.X)
        scores += [json.dumps(_top_scores(mi)) for mi in m]
        xg_h += list(lam)
        xg_a += list(mu)
    pred = pred.with_columns(
        pl.Series("scores", scores), pl.Series("xg_home", xg_h), pl.Series("xg_away", xg_a)
    )
    barca = _barca_view(pred)

    MODEL_DIR.mkdir(parents=True, exist_ok=True)
    for season, model in models.items():
        joblib.dump(model, MODEL_DIR / f"ensemble_{season}.joblib")
    pred.write_parquet(MODEL_DIR / "predictions_league.parquet")
    barca.write_parquet(MODEL_DIR / "predictions_barca.parquet")

    y_b = (
        barca["barca_result"]
        .replace_strict({"W": 0, "D": 1, "L": 2}, return_dtype=pl.Int64)
        .to_numpy()
    )
    p_b = barca.select("p_win", "p_draw", "p_loss").to_numpy()

    def split(frame: pl.DataFrame, y: np.ndarray, p: np.ndarray, seasons: tuple[int, ...]) -> dict:
        mask = np.isin(frame["season_start"].to_numpy(), seasons)
        return metrics.summary(y[mask], p[mask])

    card: dict[str, Any] = {
        "version": MODEL_VERSION,
        "trained_at": datetime.now(UTC).isoformat(timespec="seconds"),
        "model": "Equal-weight ensemble: Elo ordered logit + Poisson goals model + LightGBM",
        "training": "walk-forward: for each season S, trained on La Liga 2005/06..S-1 (every club)",
        "features": ds.features,
        "dev_seasons": [f"{s}/{s + 1}" for s in DEV_SEASONS],
        "holdout_seasons": [f"{s}/{s + 1}" for s in HOLDOUT_SEASONS],
        "metrics": {
            "league_dev": split(pred, pred["y"].to_numpy(), backtest.probs(pred), DEV_SEASONS),
            "league_holdout": split(
                pred, pred["y"].to_numpy(), backtest.probs(pred), HOLDOUT_SEASONS
            ),
            "barca_dev": split(barca, y_b, p_b, DEV_SEASONS),
            "barca_holdout": split(barca, y_b, p_b, HOLDOUT_SEASONS),
        },
    }
    (MODEL_DIR / "model_card.json").write_text(json.dumps(card, indent=1))
    if track:
        backtest.track(
            pred,
            experiment="match-outcome",
            run_name=MODEL_VERSION,
            params={"members": "elo,poisson,lightgbm", "train_start": data.TRAIN_START},
            features=ds.features,
            tags={"stage": "production"},
        )
    log.info("production model: %s", card["metrics"])
    return card


LINEUP_DIR = config.MODELS / "lineup"


def train_lineups() -> dict[str, Any]:
    from barca.models import lineup

    seasons = [f"{y}/{y + 1}" for y in data.TEST_SEASONS]
    out = lineup.build(
        store.features("player_fixture"),
        store.tactics(),
        store.matches(),
        store.appearances(),
        seasons,
    )
    LINEUP_DIR.mkdir(parents=True, exist_ok=True)
    out.write_parquet(LINEUP_DIR / "predictions.parquet")
    actual = (
        store.appearances()
        .filter(pl.col("team") == "Barcelona", pl.col("started"))
        .select("match_id", "player_id")
    )
    acc = lineup.xi_accuracy(out.filter(pl.col("match_id").is_not_null()), actual)
    summary = {
        "fixtures": out["date"].n_unique(),
        "evaluated": acc.height,
        "mean_correct": float(acc["correct"].to_numpy().mean()),
        "dev_mean_correct": float(
            acc.join(out.select("match_id", "season").unique(), on="match_id")
            .filter(pl.col("season").str.slice(0, 4).cast(pl.Int32).is_in(DEV_SEASONS))["correct"]
            .to_numpy()
            .mean()
        ),
        "holdout_mean_correct": float(
            acc.join(out.select("match_id", "season").unique(), on="match_id")
            .filter(pl.col("season").str.slice(0, 4).cast(pl.Int32).is_in(HOLDOUT_SEASONS))[
                "correct"
            ]
            .to_numpy()
            .mean()
        ),
    }
    (LINEUP_DIR / "summary.json").write_text(json.dumps(summary, indent=1))
    return summary


def load(season: int) -> EnsembleModel:
    return joblib.load(MODEL_DIR / f"ensemble_{season}.joblib")


def model_path(season: int) -> Path:
    return MODEL_DIR / f"ensemble_{season}.joblib"
