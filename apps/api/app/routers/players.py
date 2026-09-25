"""Player profiles, heatmaps and workload."""

from __future__ import annotations

from datetime import date
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import desc, func, select
from sqlalchemy.orm import Session

from app import schemas as s
from app.deps import barca_team_id, get_db
from app.services import spatial
from barca.analytics import workload as workload_mod
from barca.db import models as m

router = APIRouter(prefix="/api/players", tags=["players"])
Window = Literal["match", "last5", "last10", "season"]
Family = Literal["all", "touches", "passes", "carries", "attacking", "defending"]


def _player(db: Session, player_id: int) -> m.Player:
    player = db.get(m.Player, player_id)
    if player is None:
        raise HTTPException(status_code=404, detail=f"player {player_id} not found")
    return player


def _player_matches(db: Session, player_id: int, barca_id: int):  # noqa: ANN202
    return (
        select(m.PlayerMatchStats, m.Match)
        .join(m.Match, m.Match.id == m.PlayerMatchStats.match_id)
        .where(m.PlayerMatchStats.player_id == player_id, m.PlayerMatchStats.team_id == barca_id)
    )


@router.get("", response_model=list[s.PlayerListItem], summary="Barcelona players, optionally for one season")
def list_players(season: str | None = None, min_minutes: float = 0, db: Session = Depends(get_db),
                 barca_id: int = Depends(barca_team_id)) -> list[s.PlayerListItem]:
    q = (
        select(m.Player.id, m.Player.display_name, m.Player.position_family,
               func.count(m.PlayerMatchStats.match_id), func.sum(m.PlayerMatchStats.minutes),
               func.sum(m.PlayerMatchStats.goals), func.sum(m.PlayerMatchStats.assists))
        .join(m.PlayerMatchStats, m.PlayerMatchStats.player_id == m.Player.id)
        .join(m.Match, m.Match.id == m.PlayerMatchStats.match_id)
        .where(m.PlayerMatchStats.team_id == barca_id)
        .group_by(m.Player.id, m.Player.display_name, m.Player.position_family)
    )
    season_id = None
    if season:
        season_id = db.scalar(select(m.Season.id).where(m.Season.label == season))
        q = q.where(m.Match.season_id == season_id)
    ratings = {}
    if season_id is not None:
        ratings = dict(db.execute(select(m.PlayerSeasonRating.player_id, m.PlayerSeasonRating.overall)
                                  .where(m.PlayerSeasonRating.season_id == season_id)).all())
    out = [
        s.PlayerListItem(id=pid, name=name, position_family=fam, appearances=apps, minutes=round(mins or 0, 1),
                         goals=goals or 0, assists=assists or 0, overall=ratings.get(pid))
        for pid, name, fam, apps, mins, goals, assists in db.execute(q).all() if (mins or 0) >= min_minutes
    ]
    return sorted(out, key=lambda p: -p.minutes)


@router.get("/{player_id}", response_model=s.PlayerProfile, summary="Player profile")
def profile(player_id: int, db: Session = Depends(get_db), barca_id: int = Depends(barca_team_id)) -> s.PlayerProfile:
    player = _player(db, player_id)
    rows = db.execute(_player_matches(db, player_id, barca_id).order_by(m.Match.date)).all()
    totals = {
        "appearances": len(rows), "starts": sum(r[0].started for r in rows),
        "minutes": round(sum(r[0].minutes for r in rows), 1), "goals": sum(r[0].goals for r in rows),
        "assists": sum(r[0].assists for r in rows), "xg": round(sum(r[0].xg for r in rows), 2),
        "xa": round(sum(r[0].xa for r in rows), 2),
    }
    seasons = db.execute(
        select(m.PlayerSeasonRating, m.Season.label).join(m.Season, m.Season.id == m.PlayerSeasonRating.season_id)
        .where(m.PlayerSeasonRating.player_id == player_id).order_by(m.Season.start_year)
    ).all()
    ratings = [r[0].match_rating for r in rows if r[0].match_rating is not None]
    wl = db.execute(
        select(m.PlayerFixture, m.Match.date).join(m.Match, m.Match.id == m.PlayerFixture.match_id)
        .where(m.PlayerFixture.player_id == player_id).order_by(desc(m.Match.date)).limit(1)
    ).first()
    recent = [
        s.PlayerMatchRow(
            match_id=mt.id, date=mt.date, season=mt.season.label,
            opponent=(mt.away_team if mt.barca_home else mt.home_team).name, barca_home=mt.barca_home,
            result=mt.barca_result, started=pm.started, minutes=round(pm.minutes, 1), goals=pm.goals, assists=pm.assists,
            xg=round(pm.xg, 3), xa=round(pm.xa, 3), xt=round(pm.xt, 3), progressive_passes=pm.progressive_passes,
            progressive_carries=pm.progressive_carries, pressures=pm.pressures, match_rating=pm.match_rating,
        )
        for pm, mt in rows[-60:]
    ]
    return s.PlayerProfile(
        id=player.id, name=player.name, display_name=player.display_name, country=player.country,
        position_family=player.position_family, position_group=player.position_group, totals=totals,
        seasons=[s.SeasonRating(season=label, appearances=r.appearances, starts=r.starts, minutes=r.minutes,
                                overall=r.overall, overall_pct=r.overall_pct, reliable=r.reliable, pillars=r.pillars,
                                per90=r.per90) for r, label in seasons],
        form=ratings[-5:],
        workload=({"date": wl[1], "index": wl[0].workload_index, "band": wl[0].workload_band,
                   "minutes_7d": wl[0].minutes_7d, "minutes_14d": wl[0].minutes_14d, "minutes_30d": wl[0].minutes_30d,
                   "consecutive_starts": wl[0].consecutive_starts, "days_since_last_app": wl[0].days_since_last_app}
                  if wl else None),
        recent_matches=list(reversed(recent)),
    )


@router.get("/{player_id}/stats", response_model=list[s.PlayerMatchRow], summary="Match-by-match statistics")
def stats(player_id: int, season: str | None = None, db: Session = Depends(get_db),
          barca_id: int = Depends(barca_team_id)) -> list[s.PlayerMatchRow]:
    _player(db, player_id)
    q = _player_matches(db, player_id, barca_id).order_by(m.Match.date)
    if season:
        q = q.join(m.Season, m.Season.id == m.Match.season_id).where(m.Season.label == season)
    return [
        s.PlayerMatchRow(
            match_id=mt.id, date=mt.date, season=mt.season.label,
            opponent=(mt.away_team if mt.barca_home else mt.home_team).name, barca_home=mt.barca_home,
            result=mt.barca_result, started=pm.started, minutes=round(pm.minutes, 1), goals=pm.goals, assists=pm.assists,
            xg=round(pm.xg, 3), xa=round(pm.xa, 3), xt=round(pm.xt, 3), progressive_passes=pm.progressive_passes,
            progressive_carries=pm.progressive_carries, pressures=pm.pressures, match_rating=pm.match_rating,
        )
        for pm, mt in db.execute(q).all()
    ]


@router.get("/{player_id}/heatmap", response_model=s.Heatmap, summary="Event heatmap with action and time filters")
def heatmap(
    player_id: int,
    family: Family = "all",
    window: Window = "season",
    season: str | None = Query(None, description="for window=season; default: the player's latest season"),
    match_id: int | None = Query(None, description="for window=match; default: the latest match"),
    as_of: date | None = Query(None, description="only matches before this date"),
    db: Session = Depends(get_db),
    barca_id: int = Depends(barca_team_id),
) -> s.Heatmap:
    _player(db, player_id)
    q = (select(m.Match.id, m.Match.date, m.Season.label)
         .join(m.PlayerMatchStats, m.PlayerMatchStats.match_id == m.Match.id)
         .join(m.Season, m.Season.id == m.Match.season_id)
         .where(m.PlayerMatchStats.player_id == player_id, m.PlayerMatchStats.team_id == barca_id)
         .order_by(m.Match.date))
    if as_of:
        q = q.where(m.Match.date < as_of)
    played = db.execute(q).all()
    if not played:
        raise HTTPException(status_code=404, detail="no matches for this player in the window")
    if window == "match":
        ids = [match_id] if match_id else [played[-1][0]]
    elif window in ("last5", "last10"):
        ids = [r[0] for r in played[-(5 if window == "last5" else 10):]]
    else:
        target = season or played[-1][2]
        ids = [r[0] for r in played if r[2] == target]
    return spatial.heatmap(db, player_id, ids, family, window)


@router.get("/{player_id}/workload", response_model=s.Workload, summary="Workload index before each fixture")
def workload(player_id: int, season: str | None = None, db: Session = Depends(get_db)) -> s.Workload:
    _player(db, player_id)
    q = (select(m.PlayerFixture, m.Match).join(m.Match, m.Match.id == m.PlayerFixture.match_id)
         .where(m.PlayerFixture.player_id == player_id).order_by(m.Match.date))
    if season:
        q = q.join(m.Season, m.Season.id == m.Match.season_id).where(m.Season.label == season)
    rows = db.execute(q).all()
    series = [
        s.WorkloadPoint(match_id=mt.id, date=mt.date, opponent=(mt.away_team if mt.barca_home else mt.home_team).name,
                        workload_index=pf.workload_index, band=pf.workload_band, minutes_7d=pf.minutes_7d,
                        minutes_14d=pf.minutes_14d, minutes_30d=pf.minutes_30d, consecutive_starts=pf.consecutive_starts,
                        days_since_last_app=pf.days_since_last_app, started=pf.started)
        for pf, mt in rows
    ]
    latest = workload_mod.components(series[-1].model_dump()) if series else None
    return s.Workload(player_id=player_id, series=series, latest_components=latest)
