from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

pytestmark = pytest.mark.integration


def test_health(client: TestClient) -> None:
    assert client.get("/health").json() == {"status": "ok"}


def test_overview_defaults_to_last_fixture(client: TestClient) -> None:
    body = client.get("/api/overview").json()
    assert body["next_match"]["id"] == 2
    assert body["next_match"]["opponent"]["code"] == "RMA"
    assert [m["id"] for m in body["form"]] == [1]
    assert body["readiness"]["score"] >= 0


def test_overview_as_of_picks_the_next_fixture(client: TestClient) -> None:
    assert client.get("/api/overview", params={"as_of": "2015-10-25"}).json()["next_match"]["id"] == 1


@pytest.mark.parametrize("match_id", [1, 2])
def test_probabilities_sum_to_one(client: TestClient, match_id: int) -> None:
    p = client.get(f"/api/predictions/match/{match_id}").json()["probabilities"]
    assert p["win"] + p["draw"] + p["loss"] == pytest.approx(1.0, abs=1e-6)
    assert all(0 <= v <= 1 for v in p.values())


def test_match_detail_schema(client: TestClient) -> None:
    body = client.get("/api/matches/1").json()
    assert body["match"]["result"] == "W"
    assert set(body["comparison"]) == {"barca", "opponent"}
    assert body["stats"]["barca"]["xg"] == pytest.approx(1.8)
    assert body["lineup"]["formation"] == "433"
    xi = body["lineup"]["predicted_xi"]
    assert len(xi) == 1 and xi[0]["reasons"][0]["text"].startswith("Started")
    assert body["lineup"]["correct"] == 1


def test_opponent_shots_are_mirrored(client: TestClient) -> None:
    shots = {s["team"]: s for s in client.get("/api/matches/1/shots").json()}
    assert shots["barca"]["x"] == pytest.approx(108.0)
    assert shots["opponent"]["x"] == pytest.approx(20.0)  # 120 - 100
    assert shots["opponent"]["y"] == pytest.approx(50.0)  # 80 - 30
    assert shots["barca"]["goal"] is True


def test_heatmap_grid_is_a_distribution(client: TestClient) -> None:
    body = client.get("/api/players/10/heatmap", params={"window": "match", "match_id": 1, "family": "all"}).json()
    total = sum(sum(row) for row in body["grid"])
    assert body["events"] > 0
    assert total == pytest.approx(1.0, abs=1e-3)
    assert len(body["zones"]) == 15
    assert sum(z["total"] for z in body["zones"]) == body["events"]


def test_heatmap_family_filter(client: TestClient) -> None:
    params = {"window": "match", "match_id": 1}
    passes = client.get("/api/players/10/heatmap", params={**params, "family": "passes"}).json()
    carries = client.get("/api/players/10/heatmap", params={**params, "family": "carries"}).json()
    assert passes["events"] == 20 and carries["events"] == 20


def test_player_profile_and_workload(client: TestClient) -> None:
    profile = client.get("/api/players/10").json()
    assert profile["totals"]["goals"] == 2
    assert profile["form"] == [7.4, 7.4]
    workload = client.get("/api/players/10/workload").json()
    assert [p["workload_index"] for p in workload["series"]] == [55.0, 55.0]
    # components recompute the index from the seeded minutes/streak/rest:
    # 0.30*94/180 + 0.25*188/360 + 0.15*376/630 + 0.15*4/8 + 0.15*(7-6)/5 = 0.483
    assert sum(workload["latest_components"].values()) == pytest.approx(48.3, abs=0.1)


def test_pass_network(client: TestClient) -> None:
    net = client.get("/api/matches/1/passes", params={"min_count": 1}).json()
    assert {n["player_id"] for n in net["nodes"]} >= {10}
    assert net["edges"][0]["count"] == 20


def test_models_endpoints(client: TestClient) -> None:
    models = client.get("/api/models").json()
    assert models[0]["headline"]["log_loss"] == pytest.approx(0.97)
    assert "global" not in client.get("/api/models/1").json()["evaluation"]
    assert "permutation" in client.get("/api/models/1/explanation").json()


@pytest.mark.parametrize("url", ["/api/matches/999", "/api/players/999", "/api/models/9", "/api/predictions/match/999"])
def test_not_found(client: TestClient, url: str) -> None:
    assert client.get(url).status_code == 404


def test_openapi_documents_every_route(client: TestClient) -> None:
    paths = client.get("/openapi.json").json()["paths"]
    for route in ("/api/overview", "/api/matches/{match_id}", "/api/players/{player_id}/heatmap",
                  "/api/predictions/lineup/{match_id}", "/api/models/{model_id}/explanation", "/api/teams/{team_id}/form"):
        assert route in paths
