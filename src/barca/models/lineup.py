"""Starting-XI prediction.

Three stages:

1. **Start probability.** For every candidate (``player_fixture`` table) a
   LightGBM classifier estimates P(start) from selection history, workload,
   form, position competition and match context. It is trained walk-forward:
   a season is predicted by a model trained on earlier seasons.
2. **Formation.** The expected formation is the one Barcelona used most in
   their last five recorded matches. Its slots (positions and pitch
   coordinates) come from the most recent Starting XI with that formation.
3. **Assignment.** Candidates are matched to slots by maximising
   ``log P(start) + λ log(eligibility)``, where eligibility is the share of a
   player's recent starts in the slot's position family (Hungarian
   algorithm). This yields exactly one goalkeeper, a plausible back line and
   so on, instead of the eleven highest probabilities, which could be three
   goalkeepers.
"""

from __future__ import annotations

from collections import Counter
from datetime import date
from typing import Any

import lightgbm as lgb
import numpy as np
import pandas as pd
import polars as pl
from scipy.optimize import linear_sum_assignment

from barca.config import RANDOM_SEED
from barca.data.normalize import POSITION_FAMILY, POSITION_GROUP

FEATURES = [
    "started_last1",
    "listed_last1",
    "starts_last3",
    "starts_last5",
    "starts_last10",
    "minutes_last5",
    "season_start_share",
    "season_matches_before",
    "days_since_last_start",
    "family_rank",
    "family_candidates",
    "subbed_off_last5",
    "came_on_last5",
    "minutes_7d",
    "minutes_14d",
    "minutes_30d",
    "apps_14d",
    "days_since_last_app",
    "consecutive_starts",
    "workload_index",
    "form_rating",
    "prev_season_overall",
    "is_home",
    "opp_elo",
    "elo_diff",
    "team_days_rest",
    "squad_known",
    "fam_GK",
    "fam_CB",
    "fam_FB",
    "fam_MF",
    "fam_AM",
    "fam_FW",
]

# Pitch coordinates (StatsBomb frame, attacking towards x = 120) for each position name.
POSITION_XY = {
    "Goalkeeper": (6, 40),
    "Right Back": (32, 70),
    "Right Center Back": (25, 53),
    "Center Back": (23, 40),
    "Left Center Back": (25, 27),
    "Left Back": (32, 10),
    "Right Wing Back": (48, 72),
    "Left Wing Back": (48, 8),
    "Right Defensive Midfield": (44, 52),
    "Center Defensive Midfield": (42, 40),
    "Left Defensive Midfield": (44, 28),
    "Right Midfield": (62, 70),
    "Right Center Midfield": (58, 54),
    "Center Midfield": (56, 40),
    "Left Center Midfield": (58, 26),
    "Left Midfield": (62, 10),
    "Right Wing": (86, 68),
    "Right Attacking Midfield": (76, 54),
    "Center Attacking Midfield": (74, 40),
    "Left Attacking Midfield": (76, 26),
    "Left Wing": (86, 12),
    "Right Center Forward": (96, 50),
    "Center Forward": (100, 40),
    "Left Center Forward": (96, 30),
    "Secondary Striker": (88, 40),
}
LAMBDA = 0.25  # chosen on the development seasons (notebook 16): stronger weights cost accuracy
ELIGIBILITY_FLOOR = 0.02
# Left/right preference: a tie-breaker far below λ, so it decides which flank a player takes
# within his position family but (almost) never who is picked.
SIDE_WEIGHT = 0.01


def prepare(pf: pl.DataFrame) -> pl.DataFrame:
    fam = [
        (pl.col("position_family") == f).cast(pl.Int8).alias(f"fam_{f}")
        for f in ("GK", "CB", "FB", "MF", "AM", "FW")
    ]
    return pf.with_columns(
        *fam, pl.col("is_home").cast(pl.Int8), pl.col("squad_known").cast(pl.Int8)
    )


def matrix(pf: pl.DataFrame) -> pd.DataFrame:
    return pf.select([pl.col(c).cast(pl.Float64) for c in FEATURES]).to_pandas()


class StartModel:
    """LightGBM with early stopping on the last training season."""

    name = "lightgbm"

    def fit(self, train: pl.DataFrame) -> StartModel:
        seasons = sorted(train["season"].unique().to_list())
        tr = train.filter(pl.col("season") != seasons[-1]) if len(seasons) > 1 else train
        va = train.filter(pl.col("season") == seasons[-1])
        params: dict[str, Any] = {
            "objective": "binary",
            "learning_rate": 0.03,
            "num_leaves": 12,
            "min_child_samples": 40,
            "subsample": 0.8,
            "subsample_freq": 1,
            "colsample_bytree": 0.6,
            "reg_lambda": 1.0,
            "random_state": RANDOM_SEED,
            "verbose": -1,
            "n_jobs": 4,
        }
        est = lgb.LGBMClassifier(n_estimators=2000, **params)
        est.fit(
            matrix(tr),
            tr["started"].to_numpy(),
            eval_X=matrix(va),
            eval_y=va["started"].to_numpy(),
            callbacks=[lgb.early_stopping(100, verbose=False)],
        )
        n = max(int(est.best_iteration_ or 100), 30)
        self.model_ = lgb.LGBMClassifier(n_estimators=n, **params).fit(
            matrix(train), train["started"].to_numpy()
        )
        return self

    def predict(self, frame: pl.DataFrame) -> np.ndarray:
        return np.asarray(self.model_.predict_proba(matrix(frame)))[:, 1]


def labelled(pf: pl.DataFrame) -> pl.DataFrame:
    return (
        prepare(pf)
        .filter(pl.col("started").is_not_null())
        .with_columns(pl.col("started").cast(pl.Int8))
    )


def walk_forward(
    pf: pl.DataFrame, test_seasons: list[str], keep_models: bool = False
) -> tuple[pl.DataFrame, dict]:
    data = labelled(pf)
    out, models = [], {}
    for season in test_seasons:
        train = data.filter(pl.col("season") < season)
        test = prepare(pf).filter(pl.col("season") == season)
        if train.height == 0 or test.height == 0:
            continue
        model = StartModel().fit(train)
        out.append(test.with_columns(pl.Series("p_start", model.predict(test))))
        if keep_models:
            models[season] = model
    return pl.concat(out, how="diagonal_relaxed"), models


# Formation and eligibility ---------------------------------------------------------------


def xi_history(tactics: pl.DataFrame, matches: pl.DataFrame, team_id: int = 217) -> pl.DataFrame:
    """Barcelona's recorded Starting XIs: one row per player per match with position and formation."""
    xi = tactics.filter(pl.col("event_type") == "Starting XI", pl.col("team_id") == team_id)
    return (
        xi.join(matches.select("match_id", "date"), on="match_id")
        .with_columns(
            pl.col("position").replace_strict(POSITION_GROUP, default=None).alias("group"),
        )
        .with_columns(pl.col("group").replace_strict(POSITION_FAMILY, default=None).alias("family"))
        .sort("date")
    )


def expected_formation(
    history: pl.DataFrame, before: date, window: int = 5
) -> tuple[str | None, list[str]]:
    """Most used formation in the last ``window`` matches and the slot positions of its latest use."""
    past = history.filter(pl.col("date") < before)
    if past.height == 0:
        return None, []
    recent = (
        past.select("match_id", "date", "formation").unique("match_id").sort("date").tail(window)
    )
    formation = Counter(recent["formation"].to_list()).most_common(1)[0][0]
    last_id = recent.filter(pl.col("formation") == formation)["match_id"][-1]
    positions = past.filter(pl.col("match_id") == last_id)["position"].to_list()
    return formation, positions


def eligibility(
    history: pl.DataFrame, player_id: int, before: date, fallback_family: str | None, n: int = 20
) -> dict[str, float]:
    past = history.filter(pl.col("player_id") == player_id, pl.col("date") < before).tail(n)
    counts = Counter(f for f in past["family"].to_list() if f)
    total = sum(counts.values())
    if total == 0:
        return {fallback_family: 1.0} if fallback_family else {}
    return {f: c / total for f, c in counts.items()}


def side_of(position: str | None) -> str:
    """'Left Back' -> 'left', 'Right Wing' -> 'right', anything central -> 'centre'."""
    if position and position.startswith("Left"):
        return "left"
    if position and position.startswith("Right"):
        return "right"
    return "centre"


def side_preference(
    history: pl.DataFrame, player_id: int, before: date, n: int = 20
) -> dict[str, float]:
    """Share of a player's recent starts on the left, in the centre and on the right."""
    past = history.filter(pl.col("player_id") == player_id, pl.col("date") < before).tail(n)
    counts = Counter(side_of(pos) for pos in past["position"].to_list())
    total = sum(counts.values())
    return {k: c / total for k, c in counts.items()} if total else {}


def assign(
    candidates: pl.DataFrame,
    slots: list[str],
    elig: dict[int, dict[str, float]],
    sides: dict[int, dict[str, float]] | None = None,
) -> list[tuple[int, str]]:
    """Choose 11 players and their slots by maximising log P(start) + λ log(eligibility),
    with a small left/right preference to put each player on his usual flank."""
    ids = candidates["player_id"].to_list()
    p = np.clip(candidates["p_start"].to_numpy(), 1e-4, 1.0)
    cost = np.zeros((len(ids), len(slots)))
    for i, pid in enumerate(ids):
        for j, pos in enumerate(slots):
            fam = POSITION_FAMILY.get(POSITION_GROUP.get(pos, ""), "")
            e = elig.get(pid, {}).get(fam, 0.0)
            side = (sides or {}).get(pid, {}).get(side_of(pos), 0.0)
            cost[i, j] = -(
                np.log(p[i])
                + LAMBDA * np.log(max(e, ELIGIBILITY_FLOOR))
                + SIDE_WEIGHT * np.log(max(side, ELIGIBILITY_FLOOR))
            )
    rows, cols = linear_sum_assignment(cost)
    return [(ids[r], slots[c]) for r, c in zip(rows, cols, strict=True)]


def predict_lineups(pred: pl.DataFrame, history: pl.DataFrame) -> pl.DataFrame:
    """Add ``in_xi``, ``slot`` and ``slot_x/slot_y`` to candidate predictions, fixture by fixture."""
    frames = []
    for (d,), cand in pred.group_by(["date"], maintain_order=True):
        formation, slots = expected_formation(history, d)
        cand = cand.sort("p_start", descending=True)
        if len(slots) != 11 or cand.height < 11:
            chosen: dict[int, str | None] = dict.fromkeys(cand.head(11)["player_id"].to_list())
        else:
            elig = {
                pid: eligibility(history, pid, d, fam)
                for pid, fam in cand.select("player_id", "position_family").iter_rows()
            }
            sides = {pid: side_preference(history, pid, d) for pid in cand["player_id"].to_list()}
            chosen = dict(assign(cand, slots, elig, sides))
        frames.append(
            cand.with_columns(
                pl.col("player_id").is_in(list(chosen)).alias("in_xi"),
                pl.col("player_id")
                .replace_strict(chosen, default=None, return_dtype=pl.String)
                .alias("slot"),
                pl.lit(formation).alias("formation"),
            )
        )
    out = pl.concat(frames, how="diagonal_relaxed")
    return out.with_columns(
        pl.col("slot")
        .replace_strict(
            {k: v[0] for k, v in POSITION_XY.items()}, default=None, return_dtype=pl.Float64
        )
        .alias("slot_x"),
        pl.col("slot")
        .replace_strict(
            {k: v[1] for k, v in POSITION_XY.items()}, default=None, return_dtype=pl.Float64
        )
        .alias("slot_y"),
    )


def xi_accuracy(pred: pl.DataFrame, actual: pl.DataFrame, flag: str = "in_xi") -> pl.DataFrame:
    """Per fixture: how many of the 11 predicted starters actually started (actual XIs from appearances)."""
    picked = pred.filter(pl.col(flag)).group_by("match_id").agg(pl.col("player_id").alias("picked"))
    true = actual.group_by("match_id").agg(pl.col("player_id").alias("true"))
    joined = picked.join(true, on="match_id", how="inner")
    return joined.with_columns(
        pl.col("picked").list.set_intersection(pl.col("true")).list.len().alias("correct"),
        pl.col("picked").list.len().alias("n_picked"),
    )


# Explanations ---------------------------------------------------------------------------

REASON_TEMPLATES = {
    "starts_last5": "Started {v:.0f} of the last 5",
    "starts_last3": "Started {v:.0f} of the last 3",
    "starts_last10": "Started {v:.0f} of the last 10",
    "started_last1": "{started_last}",
    "listed_last1": "{listed_last}",
    "consecutive_starts": "{v:.0f} consecutive starts",
    "season_start_share": "Started {v:.0%} of matches this season",
    "minutes_last5": "{v:.0f} minutes per match recently",
    "days_since_last_start": "{v:.0f} days since last start",
    "days_since_last_app": "{v:.0f} days since last appearance",
    "family_rank": "#{v:.0f} in the position group by recent starts",
    "family_candidates": "{v:.0f} candidates for the position group",
    "workload_index": "Workload index {v:.0f}",
    "minutes_7d": "{v:.0f} minutes in the last 7 days",
    "minutes_14d": "{v:.0f} minutes in the last 14 days",
    "minutes_30d": "{v:.0f} minutes in the last 30 days",
    "form_rating": "Form rating {v:.1f}",
    "prev_season_overall": "Last season's rating {v:.0f}",
    "subbed_off_last5": "Substituted early {v:.0f} times in the last 5",
    "came_on_last5": "Came off the bench {v:.0f} times in the last 5",
    "opp_elo": "Opponent strength (Elo {v:.0f})",
    "elo_diff": "Elo gap {v:+.0f}",
    "is_home": "{home}",
    "squad_known": "{squad}",
    "season_matches_before": "{v:.0f} matches into the season",
    "team_days_rest": "{v:.0f} days since the team's last match",
    "apps_14d": "{v:.0f} appearances in the last 14 days",
}


MISSING_TEXT = {
    "form_rating": "No recent match rating (goalkeepers are not rated)",
    "prev_season_overall": "No reliable rating last season",
    "days_since_last_start": "No recorded start yet",
    "days_since_last_app": "No recorded appearance yet",
    "season_start_share": "First match of the season",
    "opp_elo": "Opponent strength unknown",
    "elo_diff": "Opponent strength unknown",
    "team_days_rest": "Team rest unknown",
}


def reason_text(feature: str, value: float | None) -> str:
    template = REASON_TEMPLATES.get(feature)
    if feature.startswith("fam_"):
        return f"Plays as {feature[4:]}" if value else f"Not a {feature[4:]}"
    if value is None or (isinstance(value, float) and np.isnan(value)):
        return MISSING_TEXT.get(feature, feature.replace("_", " ") + " unknown")
    if template is None:
        return feature.replace("_", " ")
    return template.format(
        v=value,
        started_last="Started the last match" if value else "Did not start the last match",
        listed_last="In the squad for the last match" if value else "Not in the last squad",
        home="Home match" if value else "Away match",
        squad="Named in the published squad" if value else "Squad not yet known",
    )


def reasons(model: StartModel, frame: pl.DataFrame, k: int = 4) -> list[list[dict]]:
    """Top TreeSHAP contributions (log-odds) per candidate, as short sentences."""
    import shap

    X = matrix(frame)
    values = np.asarray(shap.TreeExplainer(model.model_).shap_values(X))
    if values.ndim == 3:  # older shap returns [neg, pos]
        values = values[1] if values.shape[0] == 2 else values[..., 1]
    out = []
    for i in range(len(X)):
        order = np.argsort(-np.abs(values[i]))[:k]
        out.append(
            [
                {
                    "feature": FEATURES[j],
                    "text": reason_text(
                        FEATURES[j], None if pd.isna(X.iloc[i, j]) else float(X.iloc[i, j])
                    ),
                    "shap": round(float(values[i, j]), 3),
                }
                for j in order
            ]
        )
    return out


def build(
    pf: pl.DataFrame,
    tactics: pl.DataFrame,
    matches: pl.DataFrame,
    appearances: pl.DataFrame,
    seasons: list[str],
) -> pl.DataFrame:
    """Walk-forward predictions, lineups and reasons for every fixture in ``seasons``."""
    import json

    pred, models = walk_forward(pf, seasons, keep_models=True)
    hist = xi_history(tactics, matches)
    lu = predict_lineups(pred, hist)
    parts = []
    for season, model in models.items():
        part = lu.filter(pl.col("season") == season)
        parts.append(
            part.with_columns(pl.Series("reasons", [json.dumps(r) for r in reasons(model, part)]))
        )
    return pl.concat(parts, how="diagonal_relaxed").sort(
        "date", "in_xi", "p_start", descending=[False, True, True]
    )
