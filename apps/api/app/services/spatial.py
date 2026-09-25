"""Heatmaps, zones, shot maps and pass networks from the events table."""

from __future__ import annotations

from collections import Counter, defaultdict

import numpy as np
import polars as pl
from sqlalchemy import and_, select
from sqlalchemy.orm import Session

from app import schemas as s
from barca.analytics import spatial
from barca.db import models as m

FAMILY_COLUMN = {
    "all": None, "touches": m.Event.is_touch, "passes": m.Event.is_pass, "carries": m.Event.is_carry,
    "attacking": m.Event.is_attacking, "defending": m.Event.is_defending,
}
BINS = (24, 16)


def _zone(x: float, y: float) -> tuple[str, str]:
    third = spatial.THIRDS[min(int(x // 40), 2)]
    edges = spatial.CHANNEL_EDGES
    ci = next(i for i in range(5) if y < edges[i + 1] or i == 4)
    return third, spatial.CHANNELS[ci]


def _kind(t: str) -> str:
    return {"Pass": "passes", "Carry": "carries", "Pressure": "pressures", "Shot": "shots",
            "Ball Receipt*": "receptions", "Dribble": "dribbles"}.get(t, "other")


def heatmap(db: Session, player_id: int, match_ids: list[int], family: str, window: str) -> s.Heatmap:
    q = select(m.Event.x, m.Event.y, m.Event.type).where(
        m.Event.player_id == player_id, m.Event.match_id.in_(match_ids), m.Event.x.is_not(None))
    col = FAMILY_COLUMN[family]
    if col is not None:
        q = q.where(col)
    rows = db.execute(q).all()
    xs = np.array([r.x for r in rows], dtype=float)
    ys = np.array([r.y for r in rows], dtype=float)
    grid = spatial.heatmap_grid(xs, ys, BINS) if len(rows) else np.zeros(BINS)
    total = grid.sum()
    norm = (grid / total).round(5).tolist() if total else grid.tolist()

    zones: dict[tuple[str, str], Counter] = defaultdict(Counter)
    for r in rows:
        zones[_zone(r.x, r.y)][_kind(r.type)] += 1
    zone_list = [
        s.Zone(third=t, channel=c, total=sum(zones[(t, c)].values()), breakdown=dict(zones[(t, c)]))
        for t in spatial.THIRDS for c in spatial.CHANNELS
    ]
    prof = spatial.spatial_profile(pl.DataFrame({"x": xs, "y": ys})) if len(rows) else {"n": 0}
    summary = {k: (None if v is None else round(float(v), 4)) for k, v in prof.items() if k != "n"}
    return s.Heatmap(player_id=player_id, family=family, window=window, matches=len(match_ids), events=len(rows),
                     grid=norm, bins=BINS, zones=zone_list, summary=summary)


def shots(db: Session, match_id: int, barca_id: int) -> list[s.Shot]:
    rows = db.execute(
        select(m.Event, m.Player.display_name).outerjoin(m.Player, m.Player.id == m.Event.player_id)
        .where(m.Event.match_id == match_id, m.Event.is_shot).order_by(m.Event.index)
    ).all()
    out = []
    for ev, name in rows:
        barca = ev.team_id == barca_id
        # every event is recorded attacking left to right: mirror the opponent onto the other half
        x, y = (ev.x, ev.y) if barca else (120 - ev.x, 80 - ev.y)
        out.append(s.Shot(team="barca" if barca else "opponent", player=name, minute=ev.minute, x=x, y=y,
                          xg=ev.xg or 0.0, outcome=ev.outcome, body_part=ev.body_part, goal=ev.outcome == "Goal"))
    return out


def pass_network(db: Session, match_id: int, barca_id: int, min_count: int = 3) -> s.PassNetwork:
    """Average positions and completed-pass links for Barcelona until the first substitution."""
    subs = db.scalars(
        select(m.Lineup.on_minute).where(m.Lineup.match_id == match_id, m.Lineup.team_id == barca_id,
                                         m.Lineup.started.is_(False), m.Lineup.played)
    ).all()
    until = min([x for x in subs if x], default=200.0)
    rows = db.execute(
        select(m.Event.player_id, m.Event.recipient_id, m.Event.x, m.Event.y, m.Event.end_x, m.Event.end_y,
               m.Event.minute, m.Event.second)
        .where(and_(m.Event.match_id == match_id, m.Event.team_id == barca_id, m.Event.is_complete_pass))
    ).all()
    pos: dict[int, list[tuple[float, float]]] = defaultdict(list)
    counts: Counter = Counter()
    links: Counter = Counter()
    for r in rows:
        if r.minute + r.second / 60 > until:
            continue
        pos[r.player_id].append((r.x, r.y))
        counts[r.player_id] += 1
        if r.recipient_id:
            pos[r.recipient_id].append((r.end_x, r.end_y))
            links[tuple(sorted((r.player_id, r.recipient_id)))] += 1
    names = dict(db.execute(select(m.Player.id, m.Player.display_name).where(m.Player.id.in_(list(pos)))).all())
    nodes = [
        s.PassNode(player_id=pid, name=names.get(pid, str(pid)), x=float(np.mean([p[0] for p in pts])),
                   y=float(np.mean([p[1] for p in pts])), passes=counts[pid])
        for pid, pts in pos.items() if pid in names and counts[pid] > 0
    ]
    edges = [s.PassEdge(source=a, target=b, count=c) for (a, b), c in links.items() if c >= min_count]
    return s.PassNetwork(until_minute=round(until, 1), nodes=nodes, edges=edges)
