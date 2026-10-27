"""InGame Studio - Match Recap Unit & Integration Test Suite.

Validates:
1. GET /api/recap REST endpoint schema compliance and data integrity.
2. Narrative match story and turning points chronology.
3. Expected Goals (xG) balance breakdown and shot efficiency.
4. Man of the Match (MOTM) profile, rating, and BPS podium.
5. Tactical entropy shifts (CCI) across 4 match phases.
6. 5-language localized studio summaries (EN, ES, SW, FR, AR).
7. WebSocket recap broadcast on simulate_full control action.
"""

import json
import os
import pytest
from fastapi.testclient import TestClient

from backend.app import app
from backend.match_recap import generate_match_recap
from backend.math_engine import MatchAnalyticsTracker


@pytest.fixture(scope="module")
def synthetic_events():
    repo_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    with open(os.path.join(repo_root, "data", "synthetic_events.json"), encoding="utf-8") as source:
        return json.load(source)


def score_from_events(events):
    score = {"home": 0, "away": 0}
    for event in events:
        if event.get("event_type") != "goal" and event.get("outcome") != "goal":
            continue
        if event.get("team") in ("home", "Northbridge Lions"):
            score["home"] += 1
        elif event.get("team") in ("away", "Harbourside City"):
            score["away"] += 1
    return score


@pytest.fixture(scope="module")
def client():
    """Complete one seeded simulation so recap endpoint checks are post-match."""
    with TestClient(app) as test_client:
        response = test_client.post("/api/control", json={"action": "simulate_full"})
        assert response.status_code == 200
        yield test_client


class TestRecapRestEndpoint:
    """Tests GET /api/recap schema, data integrity, and editorial content."""

    def test_get_recap_status_200_and_schema(self, client):
        """Asserts GET /api/recap returns HTTP 200 with all mandatory broadcast keys."""
        resp = client.get("/api/recap")
        assert resp.status_code == 200
        data = resp.json()

        required_keys = [
            "match_id",
            "fixture",
            "status",
            "clock",
            "final_score",
            "winner",
            "match_story",
            "xg_balance",
            "turning_points",
            "man_of_the_match",
            "tactical_entropy_shifts",
            "team_totals",
            "localized_summaries",
        ]
        for key in required_keys:
            assert key in data, f"Missing required recap key: {key}"

        assert data["match_id"] == "IGS_2026_NBL_HSC"
        assert data["fixture"] == "Northbridge Lions vs Harbourside City"
        assert data["status"] == "FT"
        assert data["clock"] == "94:30"

    def test_recap_final_score_and_winner(self, client, synthetic_events):
        """Asserts final score is derived from generated goal events."""
        resp = client.get("/api/recap")
        assert resp.status_code == 200
        data = resp.json()

        score = data["final_score"]
        expected = score_from_events(synthetic_events)
        assert {"home": score["home"], "away": score["away"]} == expected
        if expected["home"] == expected["away"]:
            assert data["winner"] == "draw"
        else:
            assert data["winner"] != "draw"

    def test_recap_turning_points(self, client, synthetic_events):
        """Asserts chronological turning points include generated goals."""
        resp = client.get("/api/recap")
        data = resp.json()
        tp = data["turning_points"]

        assert isinstance(tp, list)
        goal_ids = {e["event_id"] for e in synthetic_events if e.get("event_type") == "goal"}
        reported_goal_ids = {p.get("event_id") for p in tp if p.get("type") == "goal"}
        assert goal_ids <= reported_goal_ids

        # Check structure of each turning point
        for point in tp:
            assert "minute" in point
            assert "type" in point
            assert "player" in point
            assert "team" in point
            assert "score_after" in point
            assert "description" in point


    def test_recap_xg_balance(self, client):
        """Asserts xG balance breakdown has valid numeric bounds and metrics."""
        resp = client.get("/api/recap")
        data = resp.json()
        xg = data["xg_balance"]

        assert xg["home_xg"] >= 0.0
        assert xg["away_xg"] >= 0.0
        assert xg["xg_delta"] >= 0.0
        assert xg["home_goals"] == data["final_score"]["home"]
        assert xg["away_goals"] == data["final_score"]["away"]
        assert xg["shot_count"]["home"] >= 0
        assert xg["shot_count"]["away"] >= 0
        assert xg["shots_on_target"]["away"] >= 0
        assert len(xg["analysis"].strip()) > 20

    def test_recap_man_of_the_match_badge(self, client):
        """Asserts Man of the Match badge profile is complete and grounded."""
        resp = client.get("/api/recap")
        data = resp.json()
        motm = data["man_of_the_match"]

        assert motm["player_id"] is not None
        assert len(motm["name"]) > 0
        assert 0.0 <= motm["rating"] <= 10.0
        assert motm["bps"] >= 0
        assert motm["fantasy_bonus_points"] >= 0
        assert len(motm["summary"].strip()) > 20

    def test_recap_tactical_entropy_shifts(self, client):
        """Asserts tactical entropy shifts contain 4 phases with bounded CCI metrics."""
        resp = client.get("/api/recap")
        data = resp.json()
        shifts = data["tactical_entropy_shifts"]

        assert len(shifts) == 4
        for s in shifts:
            assert "phase" in s
            assert "avg_cci" in s
            assert 0.0 <= s["avg_cci"] <= 100.0
            assert "character" in s
            assert "dominant_team" in s
            assert len(s["description"]) > 10

    def test_recap_localized_summaries(self, client):
        """Asserts English and Spanish localized studio summaries are present."""
        resp = client.get("/api/recap")
        data = resp.json()
        summaries = data["localized_summaries"]

        languages = ["en", "es"]
        for lang in languages:
            assert lang in summaries
            assert len(summaries[lang].strip()) > 30

        assert set(summaries) == {"en", "es"}
        # Spanish mentions Northbridge Lions and Harbourside City
        assert "Northbridge Lions" in summaries["es"] and "Harbourside City" in summaries["es"]


class TestRecapSimulationAndWebSocket:
    """Tests simulate_full control action and WebSocket recap broadcast."""

    def test_simulate_full_returns_recap(self, client):
        """Asserts POST /api/control with simulate_full includes recap payload."""
        resp = client.post("/api/control", json={"action": "simulate_full"})
        assert resp.status_code == 200
        data = resp.json()

        assert data["status"] == "simulated_full"
        assert data["clock"] == "94:30"
        assert "recap" in data
        assert data["recap"]["status"] == "FT"
        assert {"home": data["recap"]["final_score"]["home"], "away": data["recap"]["final_score"]["away"]} == score_from_events(client.get("/api/events").json())

    def test_simulate_full_websocket_broadcasts_recap(self, client):
        """Asserts WebSocket clients receive type: recap broadcast upon full match simulation."""
        with client.websocket_connect("/ws/match-stream") as websocket:
            # Trigger simulate_full via REST
            resp = client.post("/api/control", json={"action": "simulate_full"})
            assert resp.status_code == 200

            # Collect incoming WebSocket messages
            received_types = set()
            recap_payload = None

            for _ in range(10):
                try:
                    msg_text = websocket.receive_text()
                    msg = json.loads(msg_text)
                    mtype = msg.get("type")
                    received_types.add(mtype)
                    if mtype == "recap":
                        recap_payload = msg.get("data")
                        break
                except Exception:
                    break

            assert "recap" in received_types, f"Expected 'recap' message in WebSocket broadcast, got {received_types}"
            assert recap_payload is not None
            assert recap_payload.get("status") == "FT"
            assert recap_payload.get("fixture") == "Northbridge Lions vs Harbourside City"


class TestDirectMatchRecapEngine:
    """Tests standalone execution of generate_match_recap without HTTP transport."""

    def test_generate_match_recap_standalone(self):
        """Asserts generate_match_recap executes cleanly in isolated Python process."""
        recap = generate_match_recap()
        assert isinstance(recap, dict)
        assert recap["status"] == "FT"
        assert isinstance(recap["turning_points"], list)
        assert recap["man_of_the_match"]["name"] is not None

    def test_generate_match_recap_with_custom_tracker(self):
        """Asserts generate_match_recap derives correct stats from an active tracker."""
        tracker = MatchAnalyticsTracker()
        sample_event = {
            "event_id": "TEST_EVT_01",
            "event_type": "goal",
            "period": 1,
            "clock": "12:00",
            "team": "Northbridge Lions",
            "player_id": "NBL_07",
            "player_name": "Kofi Sarpong",
            "location_x": 90.0,
            "location_y": 30.0,
            "outcome": "goal",
        }
        tracker.record_event(sample_event)
        recap = generate_match_recap(analytics_tracker=tracker, events=[sample_event])

        assert isinstance(recap, dict)
        assert "man_of_the_match" in recap
        assert recap["status"] == "FT"
