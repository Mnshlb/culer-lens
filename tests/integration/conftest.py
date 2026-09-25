"""A small synthetic application database, so API tests run without the StatsBomb data."""

from __future__ import annotations

import sys
from collections.abc import Iterator
from datetime import date, datetime

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import Engine
from sqlalchemy.orm import Session

from barca import config
from barca.db import models as m
from barca.db.session import make_engine, session_factory

sys.path.insert(0, str(config.ROOT / "apps" / "api"))


def _seed(session: Session) -> None:
    session.add_all([m.Competition(id=1, name="La Liga"), m.Season(id=2015, label="2015/2016", start_year=2015)])
    session.add_all([
        m.Team(id=1, statsbomb_id=217, name="Barcelona", short_name="Barça", code="BAR"),
        m.Team(id=2, statsbomb_id=220, name="Real Madrid", short_name="Real Madrid", code="RMA"),
    ])
    session.add_all([
        m.Player(id=10, name="Player Ten", display_name="Ten", country="Spain", position_family="MF", position_group="CM"),
        m.Player(id=11, name="Player Eleven", display_name="Eleven", country="Spain", position_family="FW", position_group="ST"),
        m.Player(id=20, name="Opponent Striker", display_name="Striker", country="France", position_family="FW"),
    ])
    session.flush()
    session.add_all([
        m.Match(id=1, statsbomb_id=100, fixture_id=5000, date=date(2015, 11, 1), season_id=2015, competition_id=1,
                home_team_id=1, away_team_id=2, home_score=2, away_score=1, barca_home=True, barca_result="W",
                era="Luis Enrique", has_events=True),
        m.Match(id=2, statsbomb_id=101, fixture_id=5001, date=date(2015, 11, 21), season_id=2015, competition_id=1,
                home_team_id=2, away_team_id=1, home_score=0, away_score=4, barca_home=False, barca_result="W",
                era="Luis Enrique", has_events=True),
    ])
    session.flush()
    for mid in (1, 2):
        session.add_all([
            m.Lineup(match_id=mid, player_id=10, team_id=1, started=True, played=True, minutes=94.0, position="Center Midfield",
                     position_group="CM", on_minute=0.0, off_minute=94.0),
            m.Lineup(match_id=mid, player_id=11, team_id=1, started=False, played=True, minutes=30.0, position="Center Forward",
                     position_group="ST", on_minute=64.0, off_minute=94.0),
            m.PlayerMatchStats(match_id=mid, player_id=10, team_id=1, started=True, minutes=94.0, position="Center Midfield",
                               position_family="MF", goals=1, assists=0, xg=0.4, npxg=0.4, xa=0.2, xt=0.3, shots=2,
                               key_passes=1, touches=80, touches_in_box=2, passes=60, passes_completed=55,
                               progressive_passes=8, progressive_carries=3, dribbles_completed=1, pressures=15,
                               tackles_won=2, interceptions=1, recoveries=5, match_rating=7.4),
            m.PlayerFixture(match_id=mid, player_id=10, position_family="MF", minutes_7d=94.0, minutes_14d=188.0,
                            minutes_30d=376.0, consecutive_starts=4, days_since_last_app=6, starts_last5=5.0,
                            minutes_last5=92.0, form_rating=7.3, workload_index=55.0, workload_band="Moderate",
                            p_start=0.91, in_xi=True, slot="Center Midfield", slot_x=56.0, slot_y=40.0,
                            reasons=[{"feature": "starts_last5", "text": "Started 5 of the last 5", "shap": 1.2}],
                            started=True),
            m.PlayerFixture(match_id=mid, player_id=11, position_family="FW", minutes_7d=30.0, minutes_14d=30.0,
                            minutes_30d=90.0, consecutive_starts=0, days_since_last_app=6, starts_last5=1.0,
                            minutes_last5=25.0, form_rating=None, workload_index=12.0, workload_band="Low",
                            p_start=0.2, in_xi=False, reasons=[], started=False),
        ])
        for team_id, goals, xg in ((1, 2, 1.8), (2, 1, 0.9)):
            session.add(m.TeamMatchStats(
                match_id=mid, team_id=team_id, goals=goals, xg=xg, npxg=xg, shots=12, shots_on_target=5, big_chances=2,
                possession=0.6 if team_id == 1 else 0.4, passes=500, pass_completion=0.88, progressive_passes=80,
                progressive_carries=30, box_entries=20, final_third_entries=50, pressures=130, counterpresses=30,
                high_recoveries=8, ppda=9.5, field_tilt=0.7 if team_id == 1 else 0.3, defensive_action_height=54.0,
                xt=1.2, yellow_cards=1, red_cards=0))
    events = []
    for i in range(40):
        events.append(m.Event(id=f"e{i}", match_id=1, index=i, period=1, minute=i, second=0,
                              type="Pass" if i % 2 else "Carry", team_id=1, player_id=10, x=20.0 + i * 2, y=10.0 + i,
                              end_x=30.0 + i * 2, end_y=12.0 + i, recipient_id=11 if i % 2 else None,
                              is_touch=True, is_pass=bool(i % 2), is_complete_pass=bool(i % 2), is_carry=not i % 2))
    events += [
        m.Event(id="s1", match_id=1, index=100, period=2, minute=60, second=0, type="Shot", team_id=1, player_id=10,
                x=108.0, y=38.0, xg=0.35, outcome="Goal", is_shot=True, is_touch=True, is_attacking=True),
        m.Event(id="s2", match_id=1, index=101, period=2, minute=70, second=0, type="Shot", team_id=2, player_id=20,
                x=100.0, y=30.0, xg=0.10, outcome="Saved", is_shot=True),
    ]
    session.add_all(events)
    for d, result, elo in ((date(2015, 10, 20), "W", 1740.0), (date(2015, 11, 1), "W", 1745.0), (date(2015, 11, 21), "W", 1748.0)):
        session.add(m.TeamFeatures(team_id=1, date=d, season_id=2015, opponent_id=2, is_home=True, goals=2, goals_against=1,
                                   result=result, elo=elo, elo_post=elo + 3, points_5=2.4, goals_10=2.5,
                                   goals_against_10=0.8, sot_10=7.0, sot_against_10=3.0, points_std=2.5,
                                   matches_played=10, days_rest=6))
        session.add(m.TeamFeatures(team_id=2, date=d, season_id=2015, opponent_id=1, is_home=False, goals=1, goals_against=2,
                                   result="L", elo=1735.0, elo_post=1732.0, points_5=2.2, goals_10=2.4,
                                   goals_against_10=1.0, sot_10=6.5, sot_against_10=3.5, points_std=2.3,
                                   matches_played=10, days_rest=6))
    session.add(m.ModelVersion(id=1, name="match-outcome-test", kind="outcome", description="test ensemble",
                               trained_at=datetime(2026, 1, 1), card={"metrics": {"league_holdout": {"log_loss": 0.97}}},
                               evaluation={"seasons": [], "global": {"permutation": [], "tree_shap": [], "pdp": {}}}))
    session.flush()
    for mid, (pw, pd_, pl_) in ((1, (0.62, 0.22, 0.16)), (2, (0.35, 0.22, 0.43))):
        session.add(m.Prediction(match_id=mid, model_version_id=1, p_win=pw, p_draw=pd_, p_loss=pl_, exp_goals_barca=1.9,
                                 exp_goals_opp=1.1, top_scores=[{"barca": 2, "opponent": 1, "p": 0.11}],
                                 market={"win": 0.6, "draw": 0.22, "loss": 0.18}, formation="433",
                                 explanation={"base_value": 0.47, "groups": {"Team strength (Elo)": 0.1},
                                              "contributions": [{"feature": "elo_diff", "label": "Elo gap", "value": 10.0,
                                                                 "shap": 0.1}]}))
    session.commit()


@pytest.fixture(scope="session")
def engine(tmp_path_factory: pytest.TempPathFactory) -> Engine:
    path = tmp_path_factory.mktemp("db") / "test.db"
    eng = make_engine(f"sqlite:///{path}")
    from barca.db import migrate

    migrate.upgrade(eng)
    with session_factory(eng)() as session:
        _seed(session)
    return eng


@pytest.fixture(scope="session")
def client(engine: Engine) -> Iterator[TestClient]:
    from app import deps
    from app.main import app

    def override() -> Iterator[Session]:
        session = session_factory(engine)()
        try:
            yield session
        finally:
            session.close()

    app.dependency_overrides[deps.get_db] = override
    yield TestClient(app)
    app.dependency_overrides.clear()
