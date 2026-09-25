"""Expected threat (xT): the value of having the ball in each part of the pitch.

Following Karun Singh's formulation, the pitch is split into a 16 x 12 grid.
For each cell z the model estimates, from open-play actions:

* s(z) - probability that the next action is a shot, and g(z) the average xG
  of those shots;
* m(z) = 1 - s(z) - probability of moving the ball, and T(z -> z') the
  probability that a move from z ends successfully in z'.

The threat of each cell solves

    xT(z) = s(z) g(z) + m(z) sum_z' T(z -> z') xT(z')

by fixed-point iteration. A successful pass or carry is then credited with
xT(end) - xT(start). Failed actions are not credited, the usual convention.

The grid is fitted once on La Liga 2015/16 (all 380 matches, every club) so
that it reflects the league, not Barcelona's own style, and is then applied
to every season. It is used descriptively (ratings, the app) and not as a
feature of the outcome models, so fitting it on one season does not leak
information into any backtest.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import polars as pl

from barca.analytics import definitions as D

NX, NY = 16, 12


@dataclass
class XTGrid:
    values: np.ndarray  # shape (NX, NY)
    shot_prob: np.ndarray
    move_prob: np.ndarray
    goal_prob: np.ndarray
    iterations: int

    def lookup(self, x: np.ndarray, y: np.ndarray) -> np.ndarray:
        ix, iy = cell_index(x, y)
        return self.values[ix, iy]


def cell_index(x: np.ndarray, y: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    ix = np.clip((np.asarray(x, dtype=float) / 120.0 * NX).astype(int), 0, NX - 1)
    iy = np.clip((np.asarray(y, dtype=float) / 80.0 * NY).astype(int), 0, NY - 1)
    return ix, iy


def _open_play(events: pl.LazyFrame | pl.DataFrame):
    return events.filter(
        ((D.PASS & ~D.SET_PIECE_PASS) | D.CARRY | (D.SHOT & (pl.col("subtype") == "Open Play")))
        & pl.col("x").is_not_null()
    )


def fit(events: pl.LazyFrame | pl.DataFrame, max_iter: int = 100, tol: float = 1e-7) -> XTGrid:
    ev = _open_play(events).select("type", "x", "y", "end_x", "end_y", "outcome", "shot_xg")
    ev = ev.collect() if isinstance(ev, pl.LazyFrame) else ev
    shots = ev.filter(pl.col("type") == "Shot")
    moves = ev.filter(pl.col("type").is_in(["Pass", "Carry"]))
    ok = moves.filter((pl.col("type") == "Carry") | pl.col("outcome").is_null())

    sx, sy = cell_index(shots["x"].to_numpy(), shots["y"].to_numpy())
    mx, my = cell_index(moves["x"].to_numpy(), moves["y"].to_numpy())
    n_shots = np.zeros((NX, NY))
    xg_sum = np.zeros((NX, NY))
    n_moves = np.zeros((NX, NY))
    np.add.at(n_shots, (sx, sy), 1)
    np.add.at(xg_sum, (sx, sy), shots["shot_xg"].to_numpy())
    np.add.at(n_moves, (mx, my), 1)

    total = n_shots + n_moves
    with np.errstate(invalid="ignore", divide="ignore"):
        shot_prob = np.where(total > 0, n_shots / total, 0.0)
        move_prob = np.where(total > 0, n_moves / total, 0.0)
        goal_prob = np.where(n_shots > 0, xg_sum / n_shots, 0.0)

    ox, oy = cell_index(ok["x"].to_numpy(), ok["y"].to_numpy())
    ex, ey = cell_index(ok["end_x"].to_numpy(), ok["end_y"].to_numpy())
    transitions = np.zeros((NX * NY, NX * NY))
    np.add.at(transitions, (ox * NY + oy, ex * NY + ey), 1)
    with np.errstate(invalid="ignore", divide="ignore"):
        transitions = np.where(n_moves.reshape(-1, 1) > 0, transitions / n_moves.reshape(-1, 1), 0.0)

    xt = np.zeros(NX * NY)
    payoff = (shot_prob * goal_prob).reshape(-1)
    mp = move_prob.reshape(-1)
    it = 0
    for it in range(1, max_iter + 1):
        new = payoff + mp * (transitions @ xt)
        if np.max(np.abs(new - xt)) < tol:
            xt = new
            break
        xt = new
    return XTGrid(xt.reshape(NX, NY), shot_prob, move_prob, goal_prob, it)


def action_values(events: pl.DataFrame, grid: XTGrid) -> pl.DataFrame:
    """xT added by every successful open-play pass and carry."""
    acts = events.filter(
        ((D.PASS_COMPLETE & ~D.SET_PIECE_PASS) | D.CARRY) & pl.col("end_x").is_not_null()
    ).select("match_id", "event_id", "team_id", "player_id", "type", "x", "y", "end_x", "end_y")
    start = grid.lookup(acts["x"].to_numpy(), acts["y"].to_numpy())
    end = grid.lookup(acts["end_x"].to_numpy(), acts["end_y"].to_numpy())
    return acts.with_columns(pl.Series("xt_added", end - start))


def player_match_xt(values: pl.DataFrame) -> pl.DataFrame:
    return values.group_by("match_id", "team_id", "player_id").agg(
        pl.col("xt_added").sum().alias("xt"),
        pl.col("xt_added").filter(pl.col("type") == "Pass").sum().alias("xt_pass"),
        pl.col("xt_added").filter(pl.col("type") == "Carry").sum().alias("xt_carry"),
    )


def team_match_xt(values: pl.DataFrame) -> pl.DataFrame:
    return values.group_by("match_id", "team_id").agg(pl.col("xt_added").sum().alias("xt"))


def grid_frame(grid: XTGrid) -> pl.DataFrame:
    """Long format for storage and the API: one row per cell."""
    ix, iy = np.meshgrid(np.arange(NX), np.arange(NY), indexing="ij")
    return pl.DataFrame({
        "ix": ix.reshape(-1), "iy": iy.reshape(-1), "xt": grid.values.reshape(-1),
        "shot_prob": grid.shot_prob.reshape(-1), "move_prob": grid.move_prob.reshape(-1),
        "goal_prob": grid.goal_prob.reshape(-1),
    })
