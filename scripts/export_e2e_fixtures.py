"""Export API responses from the synthetic test database as JSON fixtures for the Playwright tests.

The web end-to-end tests intercept every API call with these fixtures, so they
run in CI without the StatsBomb data or a running API. Only synthetic data is
written.

    uv run python scripts/export_e2e_fixtures.py
"""

from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "src"), str(ROOT / "apps" / "api"), str(ROOT)]

from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import update  # noqa: E402

from barca.db import migrate  # noqa: E402
from barca.db import models as m  # noqa: E402
from barca.db.session import make_engine, session_factory  # noqa: E402
from tests.integration.conftest import _seed  # noqa: E402

EVALUATION = {
    "metrics": {
        k: {
            "n": 2660,
            "log_loss": 0.968,
            "brier": 0.575,
            "rps": 0.194,
            "accuracy": 0.53,
            "macro_f1": 0.38,
            "ece": 0.017,
        }
        for k in ("league_dev", "league_holdout", "barca_dev", "barca_holdout")
    },
    "holdout_models": [
        {
            "model": "Production ensemble",
            "n": 2660,
            "log_loss": 0.968,
            "brier": 0.575,
            "rps": 0.194,
            "accuracy": 0.529,
            "macro_f1": 0.38,
            "ece": 0.017,
        },
        {
            "model": "Market (average odds)",
            "n": 2660,
            "log_loss": 0.953,
            "brier": 0.565,
            "rps": 0.19,
            "accuracy": 0.541,
            "macro_f1": 0.4,
            "ece": 0.019,
        },
    ],
    "calibration": {
        k: {
            "model": [
                {"bin": 1, "predicted": 0.15, "observed": 0.14, "n": 50},
                {"bin": 5, "predicted": 0.55, "observed": 0.56, "n": 80},
            ],
            "market": [
                {"bin": 1, "predicted": 0.16, "observed": 0.15, "n": 50},
                {"bin": 5, "predicted": 0.54, "observed": 0.55, "n": 80},
            ],
        }
        for k in ("home_win", "draw", "away_win")
    },
    "confusion": [[10, 0, 2], [5, 0, 3], [4, 0, 6]],
    "seasons": [
        {"season": "2014/2015", "split": "holdout", "ensemble": 0.93, "elo": 0.94, "market": 0.91}
    ],
    "errors": [
        {
            "fixture_id": 5001,
            "date": "2015-11-21",
            "opponent": "Real Madrid",
            "is_home": False,
            "barca_goals": 0,
            "opp_goals": 2,
            "p_win": 0.72,
            "p_draw": 0.18,
            "p_loss": 0.1,
            "barca_result": "L",
            "predicted": "W",
            "confidence": 0.72,
            "barca_xg": 1.9,
            "opp_xg": 0.7,
            "barca_reds": 0,
            "opp_reds": 0,
        }
    ],
    "global": {
        "permutation": [{"group": "Team strength (Elo)", "increase": 0.15, "std": 0.01}],
        "tree_shap": [
            {
                "feature": "elo_diff",
                "label": "Elo gap (home − away)",
                "group": "Team strength (Elo)",
                "mean_abs_shap": 0.08,
            }
        ],
        "audit_flags": [],
        "pdp": {
            "feature": "opponent Elo",
            "season": "2020/2021",
            "grid": [1400, 1500, 1600, 1700],
            "average": [0.85, 0.78, 0.66, 0.52],
            "ice": [[0.86, 0.79, 0.67, 0.53], [0.84, 0.77, 0.65, 0.51]],
            "opponents": ["A", "B"],
        },
    },
}

PATHS = [
    "/api/overview",
    "/api/seasons",
    "/api/matches",
    "/api/matches/1",
    "/api/matches/2",
    "/api/matches/1/shots",
    "/api/matches/1/passes",
    "/api/players",
    "/api/players/10",
    "/api/players/10/stats",
    "/api/players/10/workload",
    "/api/models",
    "/api/models/1",
    "/api/models/1/explanation",
]


def main() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        engine = make_engine(f"sqlite:///{tmp}/e2e.db")
        migrate.upgrade(engine)
        with session_factory(engine)() as session:
            _seed(session)
            card = {
                "version": "match-outcome-test",
                "model": "test ensemble",
                "metrics": EVALUATION["metrics"],
            }
            session.execute(
                update(m.ModelVersion)
                .where(m.ModelVersion.id == 1)
                .values(evaluation=EVALUATION, card=card)
            )
            session.commit()
        from app import deps
        from app.main import app

        def override():
            s = session_factory(engine)()
            try:
                yield s
            finally:
                s.close()

        app.dependency_overrides[deps.get_db] = override
        client = TestClient(app)
        out = {path: client.get(path).json() for path in PATHS}
        out["/api/players/10/heatmap"] = client.get(
            "/api/players/10/heatmap", params={"window": "match", "match_id": 1}
        ).json()
        target = ROOT / "apps" / "web" / "e2e" / "fixtures" / "api.json"
        target.write_text(json.dumps(out, indent=1, default=str))
        print(f"wrote {len(out)} responses to {target.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
