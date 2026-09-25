"""Precompute explanations for the app and the Model Intelligence page.

* Local: permutation-SHAP of P(Barcelona win) for every Barcelona fixture in
  the backtest, computed with the season-specific model that made the
  prediction.
* Global: grouped permutation importance on the holdout seasons, and mean
  |TreeSHAP| of the LightGBM member.
* Partial dependence and ICE of P(Barcelona win) on the opponent's Elo.
"""

from __future__ import annotations

import json
import logging

import numpy as np
import polars as pl

from barca.data import store
from barca.models import data, production
from barca.xai import audit, ice, labels, pdp, permutation
from barca.xai import shap as xshap

log = logging.getLogger(__name__)
BACKGROUND = 100
TOP_K = 10


def _groups(features: list[str]) -> dict[str, list[str]]:
    out: dict[str, list[str]] = {}
    for f in features:
        out.setdefault(labels.group_of(f), []).append(f)
    return out


def build(max_evals: int = 400, seasons: tuple[int, ...] | None = None) -> dict[str, int]:
    ds = data.league_dataset(store.features("fixtures"))
    barca_mask = ((ds.meta["home"] == "Barcelona") | (ds.meta["away"] == "Barcelona")).to_numpy()
    rng = np.random.default_rng(0)
    records = []
    seasons = seasons or data.TEST_SEASONS
    models = {s: production.load(s) for s in data.TEST_SEASONS}

    for season in seasons:
        model = models[season]
        train = ds.X[ds.season < season]
        background = train.iloc[rng.choice(len(train), size=min(BACKGROUND, len(train)), replace=False)]
        rows = np.where(barca_mask & (ds.season == season))[0]
        X = ds.X.iloc[rows].reset_index(drop=True)
        meta = ds.meta[rows]
        home = (meta["home"] == "Barcelona").to_numpy()
        cls = np.where(home, 0, 2)
        values, base = xshap.explain_probability(model.predict_proba, X, background, cls, max_evals=max_evals)
        p = model.predict_proba(X)
        for i in range(len(rows)):
            contrib = xshap.top_contributions(
                values[i], X.iloc[[i]], lambda f, v, h=bool(home[i]): labels.barca_view(f, v, h), k=TOP_K
            )
            groups: dict[str, float] = {}
            for j, f in enumerate(X.columns):
                g = labels.group_of(f)
                groups[g] = groups.get(g, 0.0) + float(values[i, j])
            records.append({
                "fixture_id": int(meta["fixture_id"][i]), "season_start": season,
                "base_value": float(base[i]), "p_win": float(p[i, cls[i]]),
                "contributions": json.dumps(contrib), "groups": json.dumps(groups),
            })
        log.info("explained %d fixtures of %d", len(rows), season)

    out = pl.DataFrame(records)
    production.MODEL_DIR.mkdir(parents=True, exist_ok=True)
    existing = production.MODEL_DIR / "explanations_barca.parquet"
    if existing.exists() and seasons != data.TEST_SEASONS:
        old = pl.read_parquet(existing).filter(~pl.col("season_start").is_in(list(seasons)))
        out = pl.concat([old, out])
    out.sort("fixture_id").write_parquet(existing)
    return {"explained": out.height}


def build_global(n_repeats: int = 5) -> dict[str, object]:
    ds = data.league_dataset(store.features("fixtures"))
    models = {s: production.load(s) for s in production.HOLDOUT_SEASONS}
    per_season = {s: (ds.X[ds.season == s].reset_index(drop=True), ds.y[ds.season == s]) for s in models}
    groups = _groups(ds.features)
    perm = permutation.permutation_importance(models, per_season, groups, n_repeats=n_repeats)

    # mean |TreeSHAP| of the LightGBM member, holdout seasons, all classes
    shap_rows = []
    for s, (X, _) in per_season.items():
        v = xshap.tree_shap(models[s].lightgbm.model_, X)
        shap_rows.append(np.abs(v).mean(axis=2).sum(axis=0))
    mean_abs = np.sum(shap_rows, axis=0) / sum(len(X) for X, _ in per_season.values())
    tree_imp = sorted(
        ({"feature": f, "label": labels.fixture_label(f), "group": labels.group_of(f), "mean_abs_shap": float(v)}
         for f, v in zip(ds.features, mean_abs, strict=True)),
        key=lambda r: -r["mean_abs_shap"],
    )
    flagged = audit.check_top_features({r["feature"]: r["mean_abs_shap"] for r in tree_imp})

    # PDP / ICE: P(Barcelona win) against the opponent's Elo, Barcelona home fixtures of the last holdout season
    last = max(models)
    rows = np.where((ds.season == last) & (ds.meta["home"] == "Barcelona").to_numpy())[0]
    X = ds.X.iloc[rows].reset_index(drop=True)
    grid = np.linspace(1400, 1750, 36)
    setter = pdp.set_opponent_elo(barca_home=True)
    curves = ice.ice(lambda d: models[last].predict_proba(d)[:, 0], X, grid, setter)
    payload = {
        "permutation": perm.to_dict(orient="records"),
        "tree_shap": tree_imp,
        "audit_flags": flagged,
        "pdp": {"feature": "opponent Elo", "season": f"{last}/{last + 1}", "grid": grid.tolist(),
                "average": curves.mean(axis=0).tolist(), "ice": curves.tolist(),
                "opponents": ds.meta[rows]["away"].to_list()},
    }
    (production.MODEL_DIR / "global_explanations.json").write_text(json.dumps(payload))
    return {"groups": len(perm), "audit_flags": flagged}
