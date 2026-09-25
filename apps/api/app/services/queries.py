"""Queries shared by the routers."""

from __future__ import annotations

from datetime import date
from typing import Any

from sqlalchemy import and_, desc, or_, select
from sqlalchemy.orm import Session

from app import schemas as s
from barca.db import models as m

READINESS_METHOD = (
    "UI summary, not a model: 0.6 × form score (mean form rating of the predicted XI, 5.5 → 0 and 8.0 → 100) "
    "+ 0.4 × freshness (100 − mean workload index of the predicted XI)."
)


def team_ref(team: m.Team) -> s.TeamRef:
    return s.TeamRef(id=team.id, name=team.name, short_name=team.short_name, code=team.code)


def prediction_row(db: Session, match_id: int) -> m.Prediction | None:
    return db.scalar(select(m.Prediction).where(m.Prediction.match_id == match_id))


def summary(db: Session, match: m.Match, with_prediction: bool = True) -> s.MatchSummary:
    opponent = match.away_team if match.barca_home else match.home_team
    bg, og = (
        (match.home_score, match.away_score)
        if match.barca_home
        else (match.away_score, match.home_score)
    )
    pred = prediction_row(db, match.id) if with_prediction else None
    return s.MatchSummary(
        id=match.id,
        date=match.date,
        season=match.season.label,
        competition=match.competition.name,
        opponent=team_ref(opponent),
        barca_home=match.barca_home,
        barca_goals=bg,
        opponent_goals=og,
        result=match.barca_result,
        era=match.era,
        has_events=match.has_events,
        prediction=s.Probabilities(win=pred.p_win, draw=pred.p_draw, loss=pred.p_loss)
        if pred
        else None,
    )


def prediction_out(db: Session, match_id: int) -> s.PredictionOut | None:
    pred = prediction_row(db, match_id)
    if pred is None:
        return None
    version = db.get(m.ModelVersion, pred.model_version_id)
    exp = pred.explanation or {}
    market = pred.market or {}
    market_ok = all(market.get(k) is not None for k in ("win", "draw", "loss"))
    return s.PredictionOut(
        model=version.name if version else "unknown",
        probabilities=s.Probabilities(win=pred.p_win, draw=pred.p_draw, loss=pred.p_loss),
        expected_goals={"barca": pred.exp_goals_barca, "opponent": pred.exp_goals_opp},
        top_scores=[s.ScoreProbability(**d) for d in (pred.top_scores or [])],
        market=s.Probabilities(**{k: market[k] for k in ("win", "draw", "loss")})
        if market_ok
        else None,
        explanation=s.Explanation(
            base_value=exp.get("base_value"),
            contributions=[s.Contribution(**c) for c in exp.get("contributions", [])],
            groups=exp.get("groups", {}),
        )
        if exp
        else None,
    )


def _lineup_player(pf: m.PlayerFixture, name: str) -> s.LineupPlayer:
    return s.LineupPlayer(
        player_id=pf.player_id,
        name=name,
        position_family=pf.position_family,
        p_start=pf.p_start,
        in_xi=pf.in_xi,
        slot=pf.slot,
        x=pf.slot_x,
        y=pf.slot_y,
        started=pf.started,
        workload_index=pf.workload_index,
        workload_band=pf.workload_band,
        form_rating=pf.form_rating,
        minutes_last5=pf.minutes_last5,
        starts_last5=pf.starts_last5,
        reasons=[s.Reason(**r) for r in (pf.reasons or [])],
    )


def lineup_out(db: Session, match: m.Match, barca_id: int) -> s.LineupOut | None:
    rows = db.execute(
        select(m.PlayerFixture, m.Player.display_name)
        .join(m.Player, m.Player.id == m.PlayerFixture.player_id)
        .where(m.PlayerFixture.match_id == match.id)
        .order_by(desc(m.PlayerFixture.in_xi), desc(m.PlayerFixture.p_start))
    ).all()
    if not rows:
        return None
    pred = prediction_row(db, match.id)
    players = [_lineup_player(pf, name) for pf, name in rows]
    actual = db.scalars(
        select(m.Lineup.player_id).where(
            m.Lineup.match_id == match.id, m.Lineup.team_id == barca_id, m.Lineup.started
        )
    ).all()
    xi = [p for p in players if p.in_xi]
    correct = sum(1 for p in xi if p.player_id in set(actual)) if actual else None
    return s.LineupOut(
        formation=pred.formation if pred else None,
        predicted_xi=xi,
        others=[p for p in players if not p.in_xi],
        actual_xi=list(actual),
        correct=correct,
    )


def recent_results(db: Session, team_id: int, before: date, n: int = 5) -> list[m.TeamFeatures]:
    rows = db.scalars(
        select(m.TeamFeatures)
        .where(m.TeamFeatures.team_id == team_id, m.TeamFeatures.date < before)
        .order_by(desc(m.TeamFeatures.date))
        .limit(n)
    ).all()
    return list(reversed(rows))


def side(db: Session, team: m.Team, match_date: date) -> s.SideComparison:
    row = db.scalar(
        select(m.TeamFeatures).where(
            m.TeamFeatures.team_id == team.id, m.TeamFeatures.date == match_date
        )
    )
    recent = recent_results(db, team.id, match_date, 5)
    return s.SideComparison(
        team=team_ref(team),
        elo=row.elo if row else None,
        form=[r.result for r in recent],
        points_5=row.points_5 if row else None,
        goals_10=row.goals_10 if row else None,
        goals_against_10=row.goals_against_10 if row else None,
        sot_10=row.sot_10 if row else None,
        sot_against_10=row.sot_against_10 if row else None,
        points_per_game_season=row.points_std if row else None,
        days_rest=row.days_rest if row else None,
    )


def stats(db: Session, match: m.Match, barca_id: int) -> dict[str, s.MatchStatsSide] | None:
    rows = db.scalars(select(m.TeamMatchStats).where(m.TeamMatchStats.match_id == match.id)).all()
    if len(rows) != 2:
        return None
    out = {}
    for r in rows:
        key = "barca" if r.team_id == barca_id else "opponent"
        out[key] = s.MatchStatsSide(
            goals=r.goals,
            xg=r.xg,
            shots=r.shots,
            shots_on_target=r.shots_on_target,
            big_chances=r.big_chances,
            possession=r.possession,
            passes=r.passes,
            pass_completion=r.pass_completion,
            progressive_passes=r.progressive_passes,
            box_entries=r.box_entries,
            pressures=r.pressures,
            ppda=r.ppda,
            field_tilt=r.field_tilt,
            xt=r.xt,
        )
    return out


def readiness(lineup: s.LineupOut | None) -> dict[str, Any] | None:
    if lineup is None or not lineup.predicted_xi:
        return None
    forms = [p.form_rating for p in lineup.predicted_xi if p.form_rating is not None]
    loads = [p.workload_index for p in lineup.predicted_xi]
    form_score = (
        max(0.0, min(100.0, (sum(forms) / len(forms) - 5.5) / 2.5 * 100)) if forms else 50.0
    )
    freshness = 100 - sum(loads) / len(loads)
    return {
        "score": round(0.6 * form_score + 0.4 * freshness),
        "form_score": round(form_score),
        "freshness": round(freshness),
        "method": READINESS_METHOD,
    }


def barca_matches(db: Session, barca_id: int):
    return select(m.Match).where(
        or_(m.Match.home_team_id == barca_id, m.Match.away_team_id == barca_id)
    )


def next_match(db: Session, barca_id: int, as_of: date | None) -> m.Match | None:
    q = barca_matches(db, barca_id)
    if as_of is None:
        return db.scalar(q.where(m.Match.competition_id == 1).order_by(desc(m.Match.date)).limit(1))
    return db.scalar(q.where(m.Match.date >= as_of).order_by(m.Match.date).limit(1)) or db.scalar(
        q.order_by(desc(m.Match.date)).limit(1)
    )


def previous_matches(db: Session, barca_id: int, before: date, n: int = 5) -> list[m.Match]:
    rows = db.scalars(
        barca_matches(db, barca_id)
        .where(m.Match.date < before)
        .order_by(desc(m.Match.date))
        .limit(n)
    ).all()
    return list(reversed(rows))


def season_record(db: Session, barca_id: int, season_id: int, before: date) -> dict[str, Any]:
    rows = db.scalars(
        select(m.TeamFeatures).where(
            and_(
                m.TeamFeatures.team_id == barca_id,
                m.TeamFeatures.season_id == season_id,
                m.TeamFeatures.date < before,
            )
        )
    ).all()
    w = sum(r.result == "W" for r in rows)
    d = sum(r.result == "D" for r in rows)
    lo = sum(r.result == "L" for r in rows)
    return {
        "played": len(rows),
        "won": w,
        "drawn": d,
        "lost": lo,
        "points": 3 * w + d,
        "goals_for": sum(r.goals for r in rows),
        "goals_against": sum(r.goals_against for r in rows),
    }
