"""Load the application database from the feature store and model outputs.

Run with ``barca db``. The schema is created by Alembic migrations
(``apps/api/migrations``); this module only fills it. Every table is emptied and
reloaded, so a load is idempotent.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime
from typing import Any

import numpy as np
import polars as pl
from sqlalchemy import Engine, delete, insert

from barca.analytics import definitions as D
from barca.analytics import xt as xt_mod
from barca.data import normalize, store
from barca.db import models as m
from barca.models import backtest, data, metrics, production
from barca.models.baselines import EloModel
from barca.xai import errors as xerrors

log = logging.getLogger(__name__)
CHUNK = 5000


# Bulk insert -------------------------------------------------------------------------------


def _finite(v: Any) -> Any:
    """NaN and infinities become NULL, recursively: they are not valid JSON."""
    if isinstance(v, float) and not np.isfinite(v):
        return None
    if isinstance(v, dict):
        return {k: _finite(x) for k, x in v.items()}
    if isinstance(v, list):
        return [_finite(x) for x in v]
    return v


def _rows(frame: pl.DataFrame, json_cols: set[str]) -> list[list[Any]]:
    """Frame rows as Python values, JSON columns decoded and every value finite or NULL."""
    is_json = [c in json_cols for c in frame.columns]
    return [
        [
            _finite(json.loads(v) if j and isinstance(v, str) else v)
            for v, j in zip(row, is_json, strict=True)
        ]
        for row in frame.iter_rows()
    ]


def _insert(engine: Engine, table: Any, frame: pl.DataFrame) -> int:
    cols = [c.name for c in table.__table__.columns]
    frame = frame.select([c for c in cols if c in frame.columns])
    json_cols = {c.name for c in table.__table__.columns if c.type.__class__.__name__ == "JSON"}
    if frame.height == 0:
        return 0
    rows = _rows(frame, json_cols)
    if engine.dialect.name == "postgresql":
        is_json = [c in json_cols for c in frame.columns]
        raw = engine.raw_connection()
        # psycopg 3 cursor: COPY with its own escaping and type adaptation
        pg_cursor: Any = raw.cursor()
        try:
            with (
                pg_cursor as cur,
                cur.copy(
                    f"COPY {table.__tablename__} ({', '.join(frame.columns)}) FROM STDIN"
                ) as cp,
            ):
                for row in rows:
                    cp.write_row(
                        [
                            json.dumps(v, allow_nan=False) if j and v is not None else v
                            for v, j in zip(row, is_json, strict=True)
                        ]
                    )
            raw.commit()
        finally:
            raw.close()
        return frame.height
    records = [dict(zip(frame.columns, row, strict=True)) for row in rows]
    with engine.begin() as conn:
        for i in range(0, len(records), CHUNK):
            conn.execute(insert(table.__table__), records[i : i + CHUNK])
    return frame.height


def _clear(engine: Engine) -> None:
    with engine.begin() as conn:
        for table in reversed(m.Base.metadata.sorted_tables):
            conn.execute(delete(table))


# Builders ----------------------------------------------------------------------------------


def _teams(results: pl.DataFrame, matches: pl.DataFrame) -> pl.DataFrame:
    ref = normalize.team_reference()
    names = sorted(
        set(results["home"]) | set(results["away"]) | set(matches["home"]) | set(matches["away"])
    )
    sb_ids = dict(zip(matches["home"], matches["home_team_id"], strict=True)) | dict(
        zip(matches["away"], matches["away_team_id"], strict=True)
    )
    short = dict(zip(ref["name"], ref["short_name"], strict=True))
    code = dict(zip(ref["name"], ref["code"], strict=True))
    return pl.DataFrame(
        {
            "id": list(range(1, len(names) + 1)),
            "name": names,
            "statsbomb_id": [sb_ids.get(n) for n in names],
            "short_name": [short.get(n, n) for n in names],
            "code": [code.get(n, n[:3].upper()) for n in names],
        },
        schema_overrides={"statsbomb_id": pl.Int64},
    )


def _matches(
    barca: pl.DataFrame, sb: pl.DataFrame, team_id: dict[str, int], comp_id: dict[str, int]
) -> pl.DataFrame:
    league = barca.filter(pl.col("season_start") >= 2004).select(
        "fixture_id",
        pl.col("sb_match_id").alias("statsbomb_id"),
        "date",
        "season",
        "is_home",
        "opponent",
        "barca_goals",
        "opp_goals",
        "result",
        pl.lit("La Liga").alias("competition"),
    )
    finals = sb.filter(pl.col("is_barca"), pl.col("competition") != "La Liga").select(
        pl.lit(None, dtype=pl.UInt32).alias("fixture_id"),
        pl.col("match_id").alias("statsbomb_id"),
        "date",
        "season",
        (pl.col("barca_venue") == "H").alias("is_home"),
        "opponent",
        "barca_goals",
        pl.col("opponent_goals").alias("opp_goals"),
        pl.col("barca_result").alias("result"),
        "competition",
    )
    allm = (
        pl.concat([league, finals], how="vertical_relaxed")
        .sort("date")
        .with_row_index("id", offset=1)
    )
    meta = sb.select(
        pl.col("match_id").alias("statsbomb_id"), "kickoff", "match_week", "stadium", "referee"
    )
    allm = allm.join(meta, on="statsbomb_id", how="left")
    era = normalize.barca_era(allm["date"])
    return allm.with_columns(
        pl.col("id").cast(pl.Int64),
        era.alias("era"),
        pl.col("season").str.slice(0, 4).cast(pl.Int64).alias("season_id"),
        pl.col("competition").replace_strict(comp_id).alias("competition_id"),
        pl.when(pl.col("is_home"))
        .then(pl.lit(team_id["Barcelona"]))
        .otherwise(pl.col("opponent").replace_strict(team_id))
        .alias("home_team_id"),
        pl.when(pl.col("is_home"))
        .then(pl.col("opponent").replace_strict(team_id))
        .otherwise(pl.lit(team_id["Barcelona"]))
        .alias("away_team_id"),
        pl.when(pl.col("is_home"))
        .then(pl.col("barca_goals"))
        .otherwise(pl.col("opp_goals"))
        .alias("home_score"),
        pl.when(pl.col("is_home"))
        .then(pl.col("opp_goals"))
        .otherwise(pl.col("barca_goals"))
        .alias("away_score"),
        pl.col("is_home").alias("barca_home"),
        pl.col("result").alias("barca_result"),
        pl.col("statsbomb_id").is_not_null().alias("has_events"),
    )


def _evaluation(pred_league: pl.DataFrame, pred_barca: pl.DataFrame, card: dict) -> dict:
    ds = data.league_dataset(store.features("fixtures"))
    hold = np.isin(ds.season, production.HOLDOUT_SEASONS)
    lp = pred_league.filter(pl.col("season_start").is_in(production.HOLDOUT_SEASONS))
    y, p = lp["y"].to_numpy(), backtest.probs(lp)
    mk = data.market_probs(ds.rows(hold).meta, "avg", ds.classes)
    calib = {
        name: {"model": metrics.reliability(y, p, k), "market": metrics.reliability(y, mk, k)}
        for k, name in enumerate(["home_win", "draw", "away_win"])
    }
    elo_pred, _ = backtest.walk_forward(ds, EloModel)
    seasons = []
    for s in data.TEST_SEASONS:
        r = ds.rows(ds.season == s)
        ens = pred_league.filter(pl.col("season_start") == s)
        seasons.append(
            {
                "season": f"{s}/{s + 1}",
                "split": "development" if s in production.DEV_SEASONS else "holdout",
                "ensemble": metrics.log_loss(ens["y"].to_numpy(), backtest.probs(ens)),
                "elo": metrics.log_loss(
                    r.y, backtest.probs(elo_pred.filter(pl.col("season_start") == s))
                ),
                "market": metrics.log_loss(r.y, data.market_probs(r.meta, "avg", ds.classes)),
            }
        )
    by_model = [
        {"model": "Production ensemble", **metrics.summary(y, p)},
        {
            "model": "Elo baseline",
            **metrics.summary(
                y,
                backtest.probs(
                    elo_pred.filter(pl.col("season_start").is_in(production.HOLDOUT_SEASONS))
                ),
            ),
        },
        {"model": "Market (average odds)", **metrics.summary(y, mk)},
        {
            "model": "Naive (base rates)",
            **metrics.summary(
                y,
                np.tile(
                    np.bincount(ds.y[ds.season < 2014], minlength=3) / (ds.season < 2014).sum(),
                    (len(y), 1),
                ),
            ),
        },
    ]
    errs = xerrors.match_context(
        xerrors.high_confidence_errors(pred_barca, 0.7),
        store.features("barca_matches"),
        store.features("team_match"),
        store.appearances(),
    ).select(
        "fixture_id",
        "date",
        "opponent",
        "is_home",
        "barca_goals",
        "opp_goals",
        "p_win",
        "p_draw",
        "p_loss",
        "barca_result",
        "predicted",
        "confidence",
        "barca_xg",
        "opp_xg",
        "barca_reds",
        "opp_reds",
    )
    glob = json.loads((production.MODEL_DIR / "global_explanations.json").read_text())
    return {
        "holdout_models": by_model,
        "calibration": calib,
        "confusion": metrics.confusion(y, p).tolist(),
        "seasons": seasons,
        "errors": [
            {k: (str(v) if k == "date" else v) for k, v in r.items()} for r in errs.to_dicts()
        ],
        "global": glob,
        "metrics": card["metrics"],
    }


def load(engine: Engine) -> dict[str, int]:
    sb = store.matches()
    results = store.results()
    barca = store.features("barca_matches")
    appearances = store.appearances()
    counts: dict[str, int] = {}

    _clear(engine)
    teams = _teams(results, sb)
    team_id = dict(zip(teams["name"], teams["id"], strict=True))
    sb_team = {
        r["statsbomb_id"]: r["id"] for r in teams.to_dicts() if r["statsbomb_id"] is not None
    }
    comps = pl.DataFrame({"id": [1, 2], "name": ["La Liga", "Champions League"]})
    comp_id = dict(zip(comps["name"], comps["id"], strict=True))
    seasons = pl.DataFrame({"start_year": list(range(1995, 2021))}).with_columns(
        pl.col("start_year").alias("id"),
        (
            pl.col("start_year").cast(pl.String) + "/" + (pl.col("start_year") + 1).cast(pl.String)
        ).alias("label"),
    )
    counts["competitions"] = _insert(engine, m.Competition, comps)
    counts["seasons"] = _insert(engine, m.Season, seasons)
    counts["teams"] = _insert(engine, m.Team, teams)

    matches = _matches(barca, sb, team_id, comp_id)
    sb_to_id = {
        r["statsbomb_id"]: r["id"]
        for r in matches.select("statsbomb_id", "id").to_dicts()
        if r["statsbomb_id"]
    }
    fx_to_id = {
        r["fixture_id"]: r["id"]
        for r in matches.select("fixture_id", "id").to_dicts()
        if r["fixture_id"] is not None
    }
    date_to_id = dict(zip(matches["date"], matches["id"], strict=True))

    barca_sb_ids = list(sb_to_id)
    app = appearances.filter(pl.col("match_id").is_in(barca_sb_ids))
    pm = store.features("player_match").filter(pl.col("match_id").is_in(barca_sb_ids))
    barca_minutes = (
        pm.filter(pl.col("team") == "Barcelona")
        .group_by("player_id")
        .agg(pl.col("minutes").sum().alias("barca_minutes"))
    )
    fam = (
        pm.group_by("player_id", "position_family", "position_group")
        .agg(pl.col("minutes").sum().alias("_m"))
        .sort("_m", descending=True)
        .unique("player_id", keep="first")
    )
    players = (
        app.group_by("player_id")
        .agg(
            pl.col("player").last().alias("name"),
            pl.col("display_name").last(),
            pl.col("country").last(),
        )
        .join(fam.drop("_m"), on="player_id", how="left")
        .join(barca_minutes, on="player_id", how="left")
        .with_columns(pl.col("barca_minutes").fill_null(0.0))
        .rename({"player_id": "id"})
    )
    counts["players"] = _insert(engine, m.Player, players)
    counts["matches"] = _insert(engine, m.Match, matches)

    lineups = app.with_columns(
        pl.col("match_id").replace_strict(sb_to_id).alias("match_id"),
        pl.col("team_id").replace_strict(sb_team).alias("team_id"),
        pl.col("start_position").alias("position"),
    )
    counts["lineups"] = _insert(engine, m.Lineup, lineups)

    # events: Barcelona players' on-pitch actions + every shot, with action-family flags and xT
    ev = (
        store.events()
        .filter(pl.col("match_id").is_in(barca_sb_ids))
        .filter(
            (
                (pl.col("team") == "Barcelona")
                & pl.col("player_id").is_not_null()
                & pl.col("x").is_not_null()
                & D.ACTION_FAMILIES["all"]
            )
            | D.SHOT
        )
        .collect()
    )
    grid = xt_mod.fit(store.events().filter(pl.col("season") == "2015/2016"))
    xtv = xt_mod.action_values(ev, grid).select("event_id", pl.col("xt_added").alias("xt"))
    events = ev.join(xtv, on="event_id", how="left").select(
        pl.col("event_id").alias("id"),
        pl.col("match_id").replace_strict(sb_to_id).alias("match_id"),
        "index",
        "period",
        "minute",
        "second",
        "type",
        pl.col("team_id").replace_strict(sb_team).alias("team_id"),
        "player_id",
        "x",
        "y",
        "end_x",
        "end_y",
        "outcome",
        "subtype",
        "recipient_id",
        pl.col("shot_xg").alias("xg"),
        "xt",
        "body_part",
        "play_pattern",
        D.ACTION_FAMILIES["touches"].alias("is_touch"),
        D.PASS.alias("is_pass"),
        D.PASS_COMPLETE.alias("is_complete_pass"),
        D.CARRY.alias("is_carry"),
        D.ACTION_FAMILIES["attacking"].alias("is_attacking"),
        D.ACTION_FAMILIES["defending"].alias("is_defending"),
        D.SHOT.alias("is_shot"),
    )
    counts["events"] = _insert(engine, m.Event, events)

    tms = (
        store.features("team_match")
        .filter(pl.col("match_id").is_in(barca_sb_ids))
        .with_columns(
            pl.col("match_id").replace_strict(sb_to_id), pl.col("team_id").replace_strict(sb_team)
        )
    )
    counts["team_match_stats"] = _insert(engine, m.TeamMatchStats, tms)
    pms = pm.with_columns(
        pl.col("match_id").replace_strict(sb_to_id),
        pl.col("team_id").replace_strict(sb_team),
        pl.col("start_position").alias("position"),
    )
    counts["player_match_stats"] = _insert(engine, m.PlayerMatchStats, pms)

    from barca.features import elo as elo_mod

    form = store.features("team_form").filter(pl.col("season_start") >= 2004)
    ratings = elo_mod.long_ratings(store.features("elo")).select("date", "team", "elo", "elo_post")
    tf = form.join(ratings, on=["date", "team"], how="left").with_columns(
        pl.col("team").replace_strict(team_id).alias("team_id"),
        pl.col("opponent").replace_strict(team_id).alias("opponent_id"),
        pl.col("season_start").cast(pl.Int64).alias("season_id"),
    )
    counts["team_features"] = _insert(engine, m.TeamFeatures, tf)

    pr = store.features("player_ratings").filter(
        pl.col("team") == "Barcelona", pl.col("season").str.slice(0, 4).cast(pl.Int32) >= 2004
    )
    pillar_cols = [c for c in pr.columns if c.startswith("pillar_")]
    per90_cols = [c for c in pr.columns if c.endswith("_p90")] + ["pass_completion"]
    prs = pr.with_columns(
        pl.col("season").str.slice(0, 4).cast(pl.Int64).alias("season_id"),
        pl.lit(team_id["Barcelona"]).alias("team_id"),
        pl.struct([pl.col(c).alias(c.removeprefix("pillar_")) for c in pillar_cols])
        .map_elements(json.dumps, return_dtype=pl.String)
        .alias("pillars"),
        pl.struct([pl.col(c) for c in per90_cols])
        .map_elements(json.dumps, return_dtype=pl.String)
        .alias("per90"),
        pl.col("rating_reliable").alias("reliable"),
    )
    counts["player_season_ratings"] = _insert(engine, m.PlayerSeasonRating, prs)

    lineup_pred = pl.read_parquet(production.LINEUP_DIR / "predictions.parquet").select(
        "date", "player_id", "p_start", "in_xi", "slot", "slot_x", "slot_y", "reasons", "formation"
    )
    pf = store.features("player_fixture").join(
        lineup_pred.drop("formation"), on=["date", "player_id"], how="left"
    )
    pf = pf.filter(pl.col("date").is_in(list(date_to_id))).with_columns(
        pl.col("date").replace_strict(date_to_id).alias("match_id"),
        pl.col("in_xi").fill_null(False),
    )
    counts["player_fixtures"] = _insert(engine, m.PlayerFixture, pf)

    card = json.loads((production.MODEL_DIR / "model_card.json").read_text())
    pred_league = pl.read_parquet(production.MODEL_DIR / "predictions_league.parquet")
    pred_barca = pl.read_parquet(production.MODEL_DIR / "predictions_barca.parquet")
    lineup_summary = json.loads((production.LINEUP_DIR / "summary.json").read_text())
    versions = pl.DataFrame(
        [
            {
                "id": 1,
                "name": card["version"],
                "kind": "outcome",
                "description": card["model"],
                "trained_at": datetime.fromisoformat(card["trained_at"]).replace(tzinfo=None),
                "card": json.dumps(card),
                "evaluation": json.dumps(_evaluation(pred_league, pred_barca, card)),
            },
            {
                "id": 2,
                "name": "starting-xi-lightgbm-v1",
                "kind": "lineup",
                "description": "LightGBM start probabilities + formation-aware assignment (λ = 0.25)",
                "trained_at": datetime.fromisoformat(card["trained_at"]).replace(tzinfo=None),
                "card": json.dumps(lineup_summary),
                "evaluation": None,
            },
        ]
    )
    counts["model_versions"] = _insert(engine, m.ModelVersion, versions)

    expl = pl.read_parquet(production.MODEL_DIR / "explanations_barca.parquet")
    formation = lineup_pred.select("date", "formation").unique("date")
    preds = (
        pred_barca.join(
            expl.select("fixture_id", "base_value", "contributions", "groups"),
            on="fixture_id",
            how="left",
        )
        .join(formation, on="date", how="left")
        .filter(pl.col("fixture_id").is_in(list(fx_to_id)))
        .with_columns(
            pl.col("fixture_id").replace_strict(fx_to_id).alias("match_id"),
            pl.lit(1).alias("model_version_id"),
            pl.col("scores").alias("top_scores"),
            pl.struct(win="mkt_win", draw="mkt_draw", loss="mkt_loss")
            .map_elements(json.dumps, return_dtype=pl.String)
            .alias("market"),
            pl.struct("base_value", "contributions", "groups")
            .map_elements(
                lambda s: json.dumps(
                    {
                        "base_value": s["base_value"],
                        "contributions": json.loads(s["contributions"])
                        if s["contributions"]
                        else [],
                        "groups": json.loads(s["groups"]) if s["groups"] else {},
                    }
                ),
                return_dtype=pl.String,
            )
            .alias("explanation"),
        )
    )
    # top scores are stored from the home side's perspective; express them for Barcelona
    preds = preds.with_columns(
        pl.struct("top_scores", "is_home")
        .map_elements(
            lambda s: json.dumps(
                [
                    {
                        "barca": d["home"] if s["is_home"] else d["away"],
                        "opponent": d["away"] if s["is_home"] else d["home"],
                        "p": d["p"],
                    }
                    for d in json.loads(s["top_scores"])
                ]
            ),
            return_dtype=pl.String,
        )
        .alias("top_scores")
    )
    counts["predictions"] = _insert(engine, m.Prediction, preds)
    log.info("database: %s", counts)
    return counts
