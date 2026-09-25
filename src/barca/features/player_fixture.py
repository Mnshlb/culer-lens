"""One row per (Barcelona fixture, candidate player), with pre-match features only.

This table feeds three things: the workload index, the starting-XI model and
the app's player panels. For each Barcelona fixture on date d:

* **Candidates.** If the matchday squad is recorded (every match from 2015/16,
  some before), the candidates are that squad. The club publishes it the day
  before the match, so it is legitimately known at prediction time.
  Otherwise the candidates are every player who appeared in a recorded
  Barcelona match in the previous 60 days.
* **Features** use only recorded matches strictly before d.
* **Label** ``started`` is known for fixtures that have event data.
"""

from __future__ import annotations

from datetime import date, timedelta

import numpy as np
import polars as pl

from barca.analytics import workload

POOL_DAYS = 60


def _team_matches(appearances: pl.DataFrame, matches: pl.DataFrame) -> pl.DataFrame:
    barca = matches.filter(pl.col("is_barca")).select("match_id", "date", "kickoff", "season", "competition")
    listed = appearances.filter(pl.col("team") == "Barcelona").group_by("match_id").agg(
        (~pl.col("played")).any().alias("squad_known")
    )
    return barca.join(listed, on="match_id", how="left").sort("kickoff")


def fixtures_frame(barca_matches: pl.DataFrame, matches: pl.DataFrame) -> pl.DataFrame:
    """League fixtures from football-data plus Barcelona's non-league StatsBomb matches (finals)."""
    league = barca_matches.filter(pl.col("season_start") >= 2004).select(
        "fixture_id", pl.col("sb_match_id").alias("match_id"), "date", "season", "opponent", "is_home",
        pl.col("barca_elo"), pl.col("opp_elo"), pl.col("elo_diff"), pl.col("barca_days_rest").alias("team_days_rest"),
        pl.lit("La Liga").alias("competition"),
    )
    finals = matches.filter(pl.col("is_barca"), pl.col("competition") != "La Liga").select(
        pl.lit(None, dtype=pl.UInt32).alias("fixture_id"), "match_id", "date", "season", "opponent",
        (pl.col("barca_venue") == "H").alias("is_home"), pl.lit(None, dtype=pl.Float64).alias("barca_elo"),
        pl.lit(None, dtype=pl.Float64).alias("opp_elo"), pl.lit(None, dtype=pl.Float64).alias("elo_diff"),
        pl.lit(None, dtype=pl.Float64).alias("team_days_rest"), "competition",
    )
    return pl.concat([league, finals], how="vertical_relaxed").sort("date")


def build(
    barca_matches: pl.DataFrame,
    matches: pl.DataFrame,
    appearances: pl.DataFrame,
    player_match: pl.DataFrame,
    player_ratings: pl.DataFrame,
) -> pl.DataFrame:
    fixtures = fixtures_frame(barca_matches, matches)
    team = _team_matches(appearances, matches)
    apps = (
        appearances.filter(pl.col("team") == "Barcelona")
        .join(player_match.select("match_id", "player_id", "match_rating"), on=["match_id", "player_id"], how="left")
        .select("match_id", "date", "kickoff", "season", "player_id", "display_name", "started", "played", "minutes",
                "position_family", "position_group", "match_minutes", "match_rating")
    )
    team_dates = team["date"].to_numpy()
    team_ids = team["match_id"].to_numpy()
    team_season = team["season"].to_numpy()

    # per player: status in every recorded Barcelona match (absent = not in the squad list)
    players = apps.select("player_id", "display_name").unique("player_id")
    status: dict[int, dict[str, np.ndarray]] = {}
    for pid in players["player_id"].to_list():
        p = apps.filter(pl.col("player_id") == pid)
        idx = {mid: i for i, mid in enumerate(team_ids)}
        n = len(team_ids)
        arr = {k: np.zeros(n) for k in ("listed", "started", "played", "minutes")}
        rating = np.full(n, np.nan)
        family = np.array([None] * n, dtype=object)
        group = np.array([None] * n, dtype=object)
        for r in p.iter_rows(named=True):
            i = idx[r["match_id"]]
            arr["listed"][i] = 1
            arr["started"][i] = float(r["started"])
            arr["played"][i] = float(r["played"])
            arr["minutes"][i] = r["minutes"] or 0.0
            rating[i] = r["match_rating"] if r["match_rating"] is not None else np.nan
            family[i] = r["position_family"]
            group[i] = r["position_group"]
        status[pid] = {**arr, "rating": rating, "family": family, "group": group}

    prev_rating = (
        player_ratings.filter(pl.col("team") == "Barcelona", pl.col("rating_reliable"))
        .select("player_id", "season", "overall")
    )
    prev_lookup = {(r[0], r[1]): r[2] for r in prev_rating.iter_rows()}
    squad_by_match = {
        mid: set(g["player_id"].to_list())
        for (mid,), g in apps.group_by(["match_id"])
    }
    squad_known = dict(zip(team["match_id"].to_list(), team["squad_known"].fill_null(False).to_list(), strict=True))
    started_by_match = {
        mid: set(g.filter(pl.col("started"))["player_id"].to_list()) for (mid,), g in apps.group_by(["match_id"])
    }

    rows = []
    for fx in fixtures.iter_rows(named=True):
        d: date = fx["date"]
        before = np.where(team_dates < np.datetime64(d))[0]
        mid = fx["match_id"]
        known = bool(mid is not None and squad_known.get(mid, False))
        if known:
            candidates = squad_by_match[mid]
        else:
            recent = [i for i in before if team_dates[i] >= np.datetime64(d - timedelta(days=POOL_DAYS))]
            candidates = {pid for pid, s in status.items() if recent and s["played"][recent].any()}
        season_idx = [i for i in before if team_season[i] == fx["season"]]
        for pid in candidates:
            s = status[pid]
            last = before[-10:]
            played_idx = [i for i in before if s["played"][i]]
            last_app = team_dates[played_idx[-1]] if played_idx else None
            last_start_idx = [i for i in before if s["started"][i]]
            day = np.datetime64(d)

            def minutes_within(days: int, s=s, day=day) -> float:
                mask = (team_dates[before] >= day - np.timedelta64(days, "D"))
                return float(s["minutes"][before][mask].sum())

            streak = 0
            for i in before[::-1]:
                if s["started"][i]:
                    streak += 1
                else:
                    break
            fam_hist = [f for f in s["family"][last] if f is not None] or [f for f in s["family"][before] if f is not None]
            grp_hist = [g for g in s["group"][last] if g is not None] or [g for g in s["group"][before] if g is not None]
            ratings = s["rating"][[i for i in before if s["played"][i] and not np.isnan(s["rating"][i])][-5:]] if len(before) else np.array([])
            weights = s["minutes"][[i for i in before if s["played"][i] and not np.isnan(s["rating"][i])][-5:]] if len(before) else np.array([])
            prev_season = f"{int(fx['season'][:4]) - 1}/{fx['season'][:4]}"
            rows.append({
                "fixture_id": fx["fixture_id"], "match_id": mid, "date": d, "season": fx["season"],
                "competition": fx["competition"], "opponent": fx["opponent"], "is_home": fx["is_home"],
                "opp_elo": fx["opp_elo"], "elo_diff": fx["elo_diff"], "team_days_rest": fx["team_days_rest"],
                "squad_known": known, "player_id": pid,
                "position_family": max(set(fam_hist), key=fam_hist.count) if fam_hist else None,
                "position_group": max(set(grp_hist), key=grp_hist.count) if grp_hist else None,
                "minutes_7d": minutes_within(7), "minutes_14d": minutes_within(14), "minutes_30d": minutes_within(30),
                "apps_14d": int(sum(s["played"][before][team_dates[before] >= day - np.timedelta64(14, "D")])),
                "days_since_last_app": int((day - last_app).astype(int)) if last_app is not None else None,
                "days_since_last_start": int((day - team_dates[last_start_idx[-1]]).astype(int)) if last_start_idx else None,
                "consecutive_starts": streak,
                "started_last1": float(s["started"][before[-1]]) if len(before) else 0.0,
                "listed_last1": float(s["listed"][before[-1]]) if len(before) else 0.0,
                "starts_last3": float(s["started"][before[-3:]].sum()),
                "starts_last5": float(s["started"][before[-5:]].sum()),
                "starts_last10": float(s["started"][before[-10:]].sum()),
                "minutes_last5": float(s["minutes"][before[-5:]].mean()) if len(before) else 0.0,
                "subbed_off_last5": float(((s["started"][before[-5:]] == 1) & (s["minutes"][before[-5:]] < 75)).sum()),
                "came_on_last5": float(((s["played"][before[-5:]] == 1) & (s["started"][before[-5:]] == 0)).sum()),
                "season_start_share": float(s["started"][season_idx].mean()) if season_idx else None,
                "season_matches_before": len(season_idx),
                "form_rating": float(np.average(ratings, weights=weights)) if len(ratings) and weights.sum() > 0 else None,
                "prev_season_overall": prev_lookup.get((pid, prev_season)),
                "started": (pid in started_by_match.get(mid, set())) if mid is not None else None,
            })

    out = pl.DataFrame(rows, infer_schema_length=None).join(players, on="player_id", how="left")
    out = out.with_columns(workload.index_expr().alias("workload_index")).with_columns(
        workload.band_expr().alias("workload_band")
    )
    # rank within position family among this fixture's candidates: 1 = most regular starter
    out = out.with_columns(
        pl.col("starts_last10").rank("ordinal", descending=True).over("date", "position_family").alias("family_rank"),
        pl.len().over("date", "position_family").alias("family_candidates"),
    )
    return out.sort("date", "family_rank")
