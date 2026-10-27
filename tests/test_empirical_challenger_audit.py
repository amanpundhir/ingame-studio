"""InGame Studio - Empirical Challenger Adversarial Verification Suite.
Author: challenger_empirical_verifier
Parent Orchestrator: 74564700-d4e6-43dc-86ae-1cc5f74f0d95

Executes adversarial stress testing, boundary condition checks, and independent
empirical verification across all 6 core challenge areas:
1. Goal Events (authentic narratives, grounding score >= 0.95, no pass claims)
2. Physical Alerts (sprint >32 km/h, shot >100 km/h, distance marks 5km/10km, 15s cooldowns)
3. Recap Endpoint (GET /api/recap before/after match, completeness of all required fields)
4. Ingestion Endpoints (POST /api/ingest & POST /api/events, 422 details, schema bounds, WS broadcast)
5. English and Spanish dictionaries across all personas
6. MCP Server & Foundry Adapter (JSON-RPC 2.0 protocol, all 7 tools, local fallback)
"""

import json
import math
import os
import random
from unittest.mock import patch, MagicMock
import pytest
from fastapi.testclient import TestClient

from backend.app import app
from backend.math_engine import TacticalMathEngine, MatchAnalyticsTracker
from backend.agents.models import FactPack, DraftNarrative, VerifiedInsight
from backend.agents.tactician_agent import TacticianAgent
from backend.agents.pundit_agent import PunditAgent
from backend.agents.verifier_agent import VerifierAgent
from backend.agents.director_agent import StudioDirectorAgent
from backend.agents.orchestrator import MatchIntelligenceOrchestrator
from backend.agents.foundry_adapter import AzureFoundryAdapter
from backend.mcp_server import InGameMCPServer
from backend.match_recap import generate_match_recap


@pytest.fixture(scope="module")
def client():
    """FastAPI TestClient instance."""
    with TestClient(app) as c:
        yield c


@pytest.fixture(scope="module")
def synthetic_events():
    """Loads calibrated 90-minute synthetic events."""
    repo_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    events_path = os.path.join(repo_root, "data", "synthetic_events.json")
    with open(events_path, "r", encoding="utf-8") as f:
        return json.load(f)


# ==============================================================================
# CHALLENGE AREA 1: GOAL EVENTS ADVERSARIAL VERIFICATION
# ==============================================================================

class TestGoalEventsAdversarialVerification:
    """Verifies goals produce authentic narratives, >=0.95 grounding, and NEVER mention pass."""

    def test_canonical_goals_verified_as_goals(self, synthetic_events):
        """Tests generated goal events, independent of scorer or event IDs."""
        orchestrator = MatchIntelligenceOrchestrator()
        goals = [e for e in synthetic_events if e.get("event_type") == "goal"]
        assert goals, "The generated full match should contain goal events"

        for g in goals:
            insight = orchestrator.process_event(g)
            assert isinstance(insight, VerifiedInsight)
            assert insight.verification_status == "VERIFIED"
            assert insight.grounding_score >= 0.95

            # Assert strict anti-pass guarantees
            for text in (
                insight.casual_story,
                insight.tactical_analysis,
                insight.club_loyalist_story,
                insight.player_lock_story,
                insight.lower_third_ticker,
            ):
                lower = text.lower()
                assert "pass to" not in lower, f"Goal {g['event_id']} contains 'pass to': {text}"
                assert "pass straight to" not in lower, f"Goal {g['event_id']} contains 'pass straight to': {text}"
                assert "completed a" not in lower, f"Goal {g['event_id']} contains 'completed a': {text}"

            # Assert goal identification
            assert "⚽ GOAL!" in insight.casual_story
            assert "GOAL" in insight.lower_third_ticker
            assert "GOAL" in insight.player_lock_story

    def test_adversarial_synthetic_goals_50_iterations(self):
        """Stress-tests 50 randomized synthetic goal variations across extremes."""
        rng = random.Random(42)
        tactician = TacticianAgent()
        pundit = PunditAgent()
        verifier = VerifierAgent()

        scorers = [("Kofi Sarpong", "Northbridge Lions"), ("Anders Hagen", "Harbourside City"), ("Kai Halvorsen", "Northbridge Lions"), ("Phil Fenton", "Harbourside City")]
        goalkeepers = {"Northbridge Lions": "Enzo Barreto", "Harbourside City": "Daniel Roark"}

        for i in range(50):
            scorer, team = rng.choice(scorers)
            opp_gk = goalkeepers[team]
            opp_team = "Harbourside City" if team == "Northbridge Lions" else "Northbridge Lions"
            dist = rng.uniform(2.0, 55.0)
            speed = rng.uniform(60.0, 140.0)
            pdr = rng.uniform(40.0, 99.0)
            xt = rng.uniform(0.15, 0.85)

            goal_evt = {
                "event_id": f"EVT_STRESS_GOAL_{i}",
                "event_type": "goal",
                "clock": f"{rng.randint(1, 90):02d}:{rng.randint(0, 59):02d}",
                "team": team,
                "player_name": scorer,
                "receiver_name": opp_gk,
                "opponent": opp_team,
                "start_x": 88.0 if team == "Northbridge Lions" else 17.0,
                "start_y": 34.0,
                "end_x": 105.0 if team == "Northbridge Lions" else 0.0,
                "end_y": 34.0,
                "tactical_metrics": {
                    "pass_difficulty": pdr,
                    "ball_speed_kmh": speed,
                    "xt_gained": xt,
                },
            }

            facts = tactician.extract_facts(goal_evt)
            assert facts.event_type == "goal"
            assert facts.passer_name == scorer
            assert facts.receiver_name == opp_gk

            draft = pundit.generate_narrative(facts)
            assert "pass to" not in draft.narrative.lower()
            assert "pass straight to" not in draft.narrative.lower()

            v_res = verifier.verify(facts, draft)
            assert v_res.is_valid is True, f"Iteration {i} failed verification: {v_res.critique}"
            assert v_res.grounding_score >= 0.95

    def test_verifier_rejects_hallucinated_goal_on_pass(self):
        """Asserts verifier catches an agent hallucinating a goal on a pass event when using 'scored a goal'."""
        verifier = VerifierAgent()
        facts = FactPack(
            event_id="EVT_FAKE_PASS",
            match_minute="15:00",
            period=1,
            event_type="pass",
            passer_name="Declan Rowe",
            receiver_name="Kofi Sarpong",
            team_name="Northbridge Lions",
            opponent_name="Harbourside City",
            start_x=50.0,
            start_y=30.0,
            end_x=70.0,
            end_y=30.0,
            pass_distance_m=20.0,
            pass_difficulty=45.0,
            ball_speed_kmh=50.0,
            chaos_index=40.0,
            xt_gained=0.08,
            defenders_in_corridor=1,
            defenders_in_cone=0,
            tactical_context="Midfield progression",
        )
        fake_narrative = (
            "In minute 15:00, Declan Rowe scored a goal for Northbridge Lions beating Kofi Sarpong "
            "with a 20.0m strike clocked at 50.0 km/h! Overcoming a 45.0% difficulty rating, this finish generated +0.08 xT."
        )
        res = verifier.verify(facts, fake_narrative)
        assert res.is_valid is False
        assert any("goal" in d.lower() for d in res.discrepancies)

    def test_adversarial_vulnerability_adjective_bypasses_verifier_hallucination_guard(self):
        """Empirically demonstrates that inserting an adjective ('scored a sensational goal')
        bypasses VerifierAgent._check_hallucinated_outcomes because of exact static substring matching.
        """
        verifier = VerifierAgent()
        facts = FactPack(
            event_id="EVT_FAKE_PASS_ADV",
            match_minute="15:00",
            period=1,
            event_type="pass",
            passer_name="Declan Rowe",
            receiver_name="Kofi Sarpong",
            team_name="Northbridge Lions",
            opponent_name="Harbourside City",
            start_x=50.0,
            start_y=30.0,
            end_x=70.0,
            end_y=30.0,
            pass_distance_m=20.0,
            pass_difficulty=45.0,
            ball_speed_kmh=50.0,
            chaos_index=40.0,
            xt_gained=0.08,
            defenders_in_corridor=1,
            defenders_in_cone=0,
            tactical_context="Midfield progression",
        )
        # Adversarial bypass: adding 'sensational' between 'scored a' and 'goal'
        adversarial_narrative = (
            "In minute 15:00, Declan Rowe scored a sensational goal for Northbridge Lions beating Kofi Sarpong "
            "with a 20.0m strike clocked at 50.0 km/h! Overcoming a 45.0% difficulty rating, this finish generated +0.08 xT."
        )
        res = verifier.verify(facts, adversarial_narrative)
        # VERIFIED: Hallucination guard catches and rejects adjective-modified goal claims
        assert res.is_valid is False
        assert res.checked_citations.get("outcome_consistency") is False
        assert any("goal" in d.lower() for d in res.discrepancies)

    def test_foundry_adapter_goal_misclassification_bug(self):
        """Verifies that AzureFoundryAdapter in local fallback mode correctly generates
        a goal narrative for goal events and is verified cleanly by VerifierAgent.
        """
        tactician = TacticianAgent()
        verifier = VerifierAgent()
        adapter = AzureFoundryAdapter()

        goal_evt = {
            "event_id": "EVT_1035",
            "event_type": "goal",
            "clock": "28:15",
            "team": "Northbridge Lions",
            "player_name": "Kofi Sarpong",
            "receiver_name": "Enzo Barreto",
            "start_x": 88.0,
            "start_y": 34.0,
            "end_x": 105.0,
            "end_y": 34.0,
            "tactical_metrics": {
                "pass_difficulty": 88.0,
                "ball_speed_kmh": 98.0,
                "xt_gained": 0.42,
            },
        }
        facts = tactician.extract_facts(goal_evt)
        draft = adapter.generate_narrative(facts)

        # VERIFIED: AzureFoundryAdapter generates goal narrative for a goal
        assert any(term in draft.narrative.lower() for term in ["goal", "scored", "strike", "finish"])
        res = verifier.verify(facts, draft)
        # VERIFIED: Verifier approves the goal narrative
        assert res.is_valid is True
        assert res.grounding_score >= 0.95

    def test_match_recap_turning_points_match_generated_goal_events(self, synthetic_events):
        """Every generated goal is represented by its own recap turning point."""
        recap = generate_match_recap(events=synthetic_events)
        goals = {e["event_id"] for e in synthetic_events if e.get("event_type") == "goal"}
        recap_goals = {
            point.get("event_id") for point in recap["turning_points"]
            if point.get("type") == "goal"
        }
        assert goals
        assert goals <= recap_goals



# ==============================================================================
# CHALLENGE AREA 2: PHYSICAL ALERTS ADVERSARIAL VERIFICATION
# ==============================================================================

class TestPhysicalAlertsAdversarialVerification:
    """Stress-tests sprint speed, shot speed, distance marks, and 15s cooldowns."""

    def test_sprint_threshold_strictly_greater_than_32(self):
        """32.0 km/h must not trigger; 32.01 km/h must trigger."""
        tracker = MatchAnalyticsTracker()

        # Exactly 32.0 km/h
        frame_at_threshold = {
            "clock": "05:00",
            "players": [{"player_id": "NBL_07", "name": "Kofi Sarpong", "team": "home", "x": 60.0, "y": 20.0, "speed_kmh": 32.0}],
            "ball": {"speed_kmh": 20.0},
        }
        tracker.add_telemetry_frame(frame_at_threshold)
        assert len(tracker.pop_pending_alerts()) == 0, "Sprint alert fired at exactly 32.0 km/h"

        # 32.05 km/h -> should fire
        frame_above_threshold = {
            "clock": "05:01",
            "players": [{"player_id": "NBL_07", "name": "Kofi Sarpong", "team": "home", "x": 60.5, "y": 20.0, "speed_kmh": 32.05}],
            "ball": {"speed_kmh": 20.0},
        }
        tracker.add_telemetry_frame(frame_above_threshold)
        alerts = tracker.pop_pending_alerts()
        assert len(alerts) == 1
        assert alerts[0]["alert_type"] == "sprint_speed"
        assert alerts[0]["threshold"] == 32.0

    def test_sprint_15s_cooldown_boundary_precision(self):
        """Tests cooldown exactly at 14s (blocked) and 15s (allowed)."""
        tracker = MatchAnalyticsTracker()

        # Alert 1 at 10:00 (600s)
        f1 = {
            "clock": "10:00",
            "players": [{"player_id": "HSC_09", "name": "Anders Hagen", "team": "away", "x": 50.0, "y": 30.0, "speed_kmh": 34.0}],
            "ball": {"speed_kmh": 15.0},
        }
        tracker.add_telemetry_frame(f1)
        assert len(tracker.pop_pending_alerts()) == 1

        # At 10:14 (614s, 14s later) -> blocked by cooldown
        f2 = {
            "clock": "10:14",
            "players": [{"player_id": "HSC_09", "name": "Anders Hagen", "team": "away", "x": 55.0, "y": 30.0, "speed_kmh": 34.5}],
            "ball": {"speed_kmh": 15.0},
        }
        tracker.add_telemetry_frame(f2)
        assert len(tracker.pop_pending_alerts()) == 0

        # At 10:15 (615s, exactly 15s later) -> cooldown expired, should fire!
        f3 = {
            "clock": "10:15",
            "players": [{"player_id": "HSC_09", "name": "Anders Hagen", "team": "away", "x": 60.0, "y": 30.0, "speed_kmh": 35.0}],
            "ball": {"speed_kmh": 15.0},
        }
        tracker.add_telemetry_frame(f3)
        fired = tracker.pop_pending_alerts()
        assert len(fired) == 1
        assert fired[0]["metric_value"] == 35.0

    def test_concurrent_sprints_different_players(self):
        """If Sarpong and Hagen both sprint in the same frame, both alerts must trigger."""
        tracker = MatchAnalyticsTracker()
        frame = {
            "clock": "20:00",
            "players": [
                {"player_id": "NBL_07", "name": "Kofi Sarpong", "team": "home", "x": 70.0, "y": 20.0, "speed_kmh": 33.2},
                {"player_id": "HSC_09", "name": "Anders Hagen", "team": "away", "x": 72.0, "y": 22.0, "speed_kmh": 34.8},
            ],
            "ball": {"speed_kmh": 25.0},
        }
        tracker.add_telemetry_frame(frame)
        alerts = tracker.pop_pending_alerts()
        assert len(alerts) == 2
        pids = {a["player_id"] for a in alerts}
        assert pids == {"NBL_07", "HSC_09"}

    def test_shot_velocity_threshold_strictly_greater_than_100(self):
        """100.0 km/h must not trigger; 100.1 km/h must trigger."""
        tracker = MatchAnalyticsTracker()

        ev_100 = {
            "event_id": "EVT_SHOT_100",
            "event_type": "shot",
            "clock": "30:00",
            "team": "Harbourside City",
            "player_id": "HSC_09",
            "player_name": "Anders Hagen",
            "tactical_metrics": {"ball_speed_kmh": 100.0},
        }
        tracker.record_event(ev_100)
        assert len(tracker.pop_pending_alerts()) == 0

        ev_101 = {
            "event_id": "EVT_SHOT_101",
            "event_type": "shot",
            "clock": "30:05",
            "team": "Harbourside City",
            "player_id": "HSC_09",
            "player_name": "Anders Hagen",
            "tactical_metrics": {"ball_speed_kmh": 100.5},
        }
        tracker.record_event(ev_101)
        alerts = tracker.pop_pending_alerts()
        assert len(alerts) == 1
        assert alerts[0]["alert_type"] == "shot_velocity"
        assert alerts[0]["metric_value"] == 100.5

    def test_distance_marks_and_teleportation_guard(self):
        """Reaching 5000m and 10000m triggers alerts, while teleportation is rejected."""
        tracker = MatchAnalyticsTracker()
        pid = "NBL_41"
        p = tracker.players[pid]

        # Teleportation jump of 50m in one step -> should NOT increase distance
        p.last_x, p.last_y = 50.0, 30.0
        p.update_tracking(100.0, 30.0, 20.0)  # Jump of 50m > 1.5m
        assert p.distance_meters == 0.0

        # Normal increments up to 5000m
        p.distance_meters = 4999.5
        p.last_x, p.last_y = 50.0, 30.0
        frame = {
            "clock": "40:00",
            "players": [{"player_id": pid, "name": "Declan Rowe", "team": "home", "x": 50.8, "y": 30.0, "speed_kmh": 12.0}],
            "ball": {"speed_kmh": 10.0},
        }
        tracker.add_telemetry_frame(frame)
        alerts = tracker.pop_pending_alerts()
        assert len(alerts) == 1
        assert alerts[0]["alert_type"] == "distance_mark"
        assert alerts[0]["threshold"] == 5000.0

        # Second frame at 5005m -> no repeat alert
        p.last_x, p.last_y = 50.8, 30.0
        frame2 = {
            "clock": "40:01",
            "players": [{"player_id": pid, "name": "Declan Rowe", "team": "home", "x": 51.2, "y": 30.0, "speed_kmh": 12.0}],
            "ball": {"speed_kmh": 10.0},
        }
        tracker.add_telemetry_frame(frame2)
        assert len(tracker.pop_pending_alerts()) == 0


# ==============================================================================
# CHALLENGE AREA 3: RECAP ENDPOINT ADVERSARIAL VERIFICATION
# ==============================================================================

class TestRecapEndpointAdversarialVerification:
    """Tests GET /api/recap before match, after simulation, and validates all required fields."""

    def test_recap_before_match_simulation(self, client):
        """Before kickoff the recap reports the fixture without inventing match results."""
        resp = client.get("/api/recap")
        assert resp.status_code == 200
        data = resp.json()

        # Structural completeness
        required_fields = [
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
        for field in required_fields:
            assert field in data, f"Missing required field in recap: {field}"

        assert data["status"] in {"NOT_STARTED", "LIVE"}
        assert data["clock"] == "00:00"
        assert data["fixture"] == "Northbridge Lions vs Harbourside City"
        score = data["final_score"]
        assert score["home"] == 0 and score["away"] == 0
        assert (data["winner"] == "draw") == (score["home"] == score["away"])
        assert len(data["match_story"]) > 50

        # xG balance
        xgb = data["xg_balance"]
        assert "home_xg" in xgb and "away_xg" in xgb and "xg_delta" in xgb
        assert xgb["home_goals"] == score["home"] and xgb["away_goals"] == score["away"]

        # Turning points
        tp = data["turning_points"]
        assert isinstance(tp, list)
        for p in tp:
            assert "minute" in p and "player" in p and "team" in p and "description" in p

        # MOTM
        motm = data["man_of_the_match"]
        assert motm["name"]
        assert 0.0 <= motm["rating"] <= 10.0
        assert motm["bps"] >= 0

        # No phase-level measurements should be fabricated before play begins.
        assert data["tactical_entropy_shifts"] == []

        # English and Spanish summaries
        loc = data["localized_summaries"]
        for lang in ("en", "es"):
            assert lang in loc
            assert len(loc[lang]) > 20

    def test_recap_after_simulate_full_control_action(self, client):
        """POST /api/control with simulate_full then GET /api/recap must remain synchronized."""
        ctrl_resp = client.post("/api/control", json={"action": "simulate_full"})
        assert ctrl_resp.status_code == 200
        ctrl_data = ctrl_resp.json()
        assert ctrl_data["status"] == "simulated_full"
        assert "recap" in ctrl_data

        recap_resp = client.get("/api/recap")
        assert recap_resp.status_code == 200
        recap_data = recap_resp.json()
        assert recap_data["final_score"]["home"] >= 0
        assert recap_data["final_score"]["away"] >= 0
        assert recap_data["man_of_the_match"]["name"]


# ==============================================================================
# CHALLENGE AREA 4: INGESTION ENDPOINTS ADVERSARIAL VERIFICATION
# ==============================================================================

class TestIngestionEndpointsAdversarialVerification:
    """Tests schema enforcement, boundary violations, HTTP 422 error details, and WS broadcasts."""

    @pytest.fixture
    def base_event(self):
        return {
            "event_id": "EVT_TEST_BASE_001",
            "match_id": "IGS_2026_NBL_HSC",
            "event_type": "pass",
            "period": 1,
            "clock": "10:15",
            "frame_index": 15000,
            "team": "Northbridge Lions",
            "player_id": "NBL_08",
            "player_name": "Martin Olsvik",
            "location_x": 55.0,
            "location_y": 30.0,
            "outcome": "completed",
        }

    def test_ingest_schema_rejection_out_of_bounds_x(self, client, base_event):
        """X < 0 or X > 105 must be rejected with 422."""
        e_neg = dict(base_event, location_x=-0.5)
        r_neg = client.post("/api/ingest", json=e_neg)
        assert r_neg.status_code == 422
        assert "location_x" in r_neg.text

        e_over = dict(base_event, location_x=105.1)
        r_over = client.post("/api/ingest", json=e_over)
        assert r_over.status_code == 422
        assert "location_x" in r_over.text

    def test_ingest_schema_rejection_out_of_bounds_y(self, client, base_event):
        """Y < 0 or Y > 68 must be rejected with 422."""
        e_neg = dict(base_event, location_y=-1.0)
        r_neg = client.post("/api/ingest", json=e_neg)
        assert r_neg.status_code == 422
        assert "location_y" in r_neg.text

        e_over = dict(base_event, location_y=68.5)
        r_over = client.post("/api/ingest", json=e_over)
        assert r_over.status_code == 422
        assert "location_y" in r_over.text

    def test_ingest_schema_rejection_invalid_event_type(self, client, base_event):
        """Unknown event_type enum must return 422."""
        e_bad = dict(base_event, event_type="unregistered_type")
        r_bad = client.post("/api/ingest", json=e_bad)
        assert r_bad.status_code == 422
        assert "event_type" in r_bad.text

    def test_ingest_schema_rejection_missing_required_fields(self, client, base_event):
        """Missing mandatory fields must return 422 citing the missing property."""
        for req_field in ["event_id", "player_id", "team", "location_x", "location_y"]:
            e_missing = dict(base_event)
            del e_missing[req_field]
            r = client.post("/api/ingest", json=e_missing)
            assert r.status_code == 422, f"Failed to reject missing field '{req_field}'"
            assert req_field in r.text

    def test_batch_ingest_identifies_exact_invalid_index(self, client, base_event):
        """Batch endpoint must identify which specific event failed validation in 422 message."""
        e_good1 = dict(base_event, event_id="EVT_BATCH_G1")
        e_good2 = dict(base_event, event_id="EVT_BATCH_G2")
        e_bad = dict(base_event, event_id="EVT_BATCH_B", location_x=999.0)

        # e_bad is at index 2
        payload = {"events": [e_good1, e_good2, e_bad]}
        r = client.post("/api/events", json=payload)
        assert r.status_code == 422
        assert "event[2]" in r.text
        assert "location_x" in r.text

    def test_websocket_broadcast_on_ingest(self, client, base_event):
        """Ingesting an event triggers WebSocket broadcast of 'event' and 'insight'."""
        with client.websocket_connect("/ws/match-stream") as ws:
            test_ev = dict(base_event, event_id="EVT_WS_TEST_INGEST")
            resp = client.post("/api/ingest", json=test_ev)
            assert resp.status_code == 200

            received_types = set()
            for _ in range(8):
                try:
                    raw = ws.receive_text()
                    msg = json.loads(raw)
                    received_types.add(msg.get("type"))
                    if "event" in received_types and "insight" in received_types:
                        break
                except Exception:
                    break

            assert "event" in received_types
            assert "insight" in received_types


# ==============================================================================
# CHALLENGE AREA 5: 5-LANGUAGE DICTIONARIES ADVERSARIAL VERIFICATION
# ==============================================================================

class TestFiveLanguageDictionariesAdversarialVerification:
    """Verifies non-empty strings and genuine vocabulary across all personas."""

    @pytest.mark.parametrize("evt_type", ["goal", "shot", "tackle", "turnover", "foul", "pass"])
    def test_all_languages_and_personas_complete(self, evt_type):
        director = StudioDirectorAgent()
        facts = FactPack(
            event_id=f"EVT_LANG_{evt_type}",
            match_minute="33:20",
            period=1,
            event_type=evt_type,
            passer_name="Kofi Sarpong" if evt_type == "goal" else "Declan Rowe",
            receiver_name="Enzo Barreto" if evt_type == "goal" else "Kai Halvorsen",
            team_name="Northbridge Lions",
            opponent_name="Harbourside City",
            start_x=85.0,
            start_y=30.0,
            end_x=105.0 if evt_type in ("goal", "shot") else 90.0,
            end_y=34.0,
            pass_distance_m=20.0,
            pass_difficulty=85.0,
            ball_speed_kmh=95.0,
            chaos_index=55.0,
            xt_gained=0.35,
            defenders_in_corridor=2,
            defenders_in_cone=1,
            tactical_context=f"Tactical {evt_type} sequence",
        )

        translations = director.generate_translations(facts)

        assert set(translations) == {"en", "es"}
        for lang in ("en", "es"):
            assert lang in translations, f"Missing language: {lang}"
            ldict = translations[lang]

            for persona_key in ("casual", "tactical", "club", "loyalist", "player", "fantasy", "player_lock", "ticker"):
                assert persona_key in ldict, f"Missing persona '{persona_key}' in language '{lang}'"
                val = ldict[persona_key]
                assert val is not None
                assert isinstance(val, str)
                assert len(val.strip()) > 15, f"String suspiciously short for {lang}.{persona_key}: '{val}'"
                assert "undefined" not in val.lower()
                assert "null" not in val.lower()


# ==============================================================================
# CHALLENGE AREA 6: MCP SERVER & FOUNDRY ADAPTER ADVERSARIAL VERIFICATION
# ==============================================================================

class TestMCPServerAndFoundryAdapterAdversarialVerification:
    """Verifies all 7 tools, JSON-RPC 2.0 error handling, and local fallback reliability."""

    def test_mcp_all_seven_tools_callable(self):
        server = InGameMCPServer()

        # Tool 1: get_live_telemetry
        t1 = server.call_tool("get_live_telemetry", {"frame_index": 2})
        assert "players" in t1 and len(t1["players"]) == 22

        # Tool 2: calculate_pass_difficulty
        t2 = server.call_tool("calculate_pass_difficulty", {"distance_m": 25.0, "defenders_in_cone": 1, "ball_speed_kmh": 40.0})
        assert 0.0 <= t2["pass_difficulty_rating"] <= 100.0

        # Tool 3: calculate_chaos_control_index
        t3 = server.call_tool("calculate_chaos_control_index", {"recent_turnovers": 3, "ball_speed_variance": 30.0})
        assert 0.0 <= t3["chaos_control_index"] <= 100.0

        # Tool 4: get_player_metrics
        t4 = server.call_tool("get_player_metrics", {"player_id": "NBL_07"})
        assert t4["name"] == "Kofi Sarpong"

        # Tool 5: get_match_analytics_overview
        t5 = server.call_tool("get_match_analytics_overview", {})
        assert "score" in t5 and "xg" in t5

        # Tool 6: get_match_recap
        t6 = server.call_tool("get_match_recap", {})
        assert t6["status"] == "FT"
        assert t6["final_score"]["home"] == t5["score"]["home"]
        assert t6["final_score"]["away"] == t5["score"]["away"]

        # Tool 7: verify_narrative_grounding
        fp = {
            "event_id": "EVT_MCP_TEST",
            "match_minute": "10:00",
            "period": 1,
            "event_type": "pass",
            "passer_name": "Declan Rowe",
            "receiver_name": "Kofi Sarpong",
            "team_name": "Northbridge Lions",
            "opponent_name": "Harbourside City",
            "start_x": 50.0,
            "start_y": 30.0,
            "end_x": 70.0,
            "end_y": 30.0,
            "pass_distance_m": 20.0,
            "pass_difficulty": 50.0,
            "ball_speed_kmh": 60.0,
            "chaos_index": 40.0,
            "xt_gained": 0.10,
            "defenders_in_corridor": 1,
            "defenders_in_cone": 0,
            "tactical_context": "Midfield pass",
        }
        good_text = "In minute 10:00, Declan Rowe completed a 20.0m pass to Kofi Sarpong at 60.0 km/h with 50.0% difficulty."
        t7_good = server.call_tool("verify_narrative_grounding", {"fact_pack": fp, "draft_narrative": good_text})
        assert t7_good["is_valid"] is True

        bad_text = "In minute 10:00, Declan Rowe completed a 99.0m pass to Kofi Sarpong at 120.0 km/h with 10.0% difficulty."
        t7_bad = server.call_tool("verify_narrative_grounding", {"fact_pack": fp, "draft_narrative": bad_text})
        assert t7_bad["is_valid"] is False

    def test_mcp_protocol_error_codes(self):
        server = InGameMCPServer()

        # -32600 Invalid request
        r1 = server.handle_request("not a dict")
        assert r1["error"]["code"] == -32600

        # -32601 Method not found
        r2 = server.handle_request({"jsonrpc": "2.0", "id": 1, "method": "non_existent"})
        assert r2["error"]["code"] == -32601

        # -32602 Invalid params
        r3 = server.handle_request({"jsonrpc": "2.0", "id": 2, "method": "tools/call", "params": {"name": "calculate_pass_difficulty", "arguments": {}}})
        assert r3["error"]["code"] == -32602

    def test_foundry_adapter_guaranteed_local_fallback(self):
        """Adapter without credentials operates in local_fallback mode and passes verification."""
        adapter = AzureFoundryAdapter()
        assert adapter.is_cloud_connected() is False
        assert adapter.get_status()["mode"] == "local_fallback"

        facts = FactPack(
            event_id="EVT_FOUNDRY_FALLBACK",
            match_minute="25:30",
            period=1,
            event_type="pass",
            passer_name="Martin Olsvik",
            receiver_name="Kofi Sarpong",
            team_name="Northbridge Lions",
            opponent_name="Harbourside City",
            start_x=60.0,
            start_y=35.0,
            end_x=85.0,
            end_y=45.0,
            pass_distance_m=26.9,
            pass_difficulty=72.0,
            ball_speed_kmh=64.0,
            chaos_index=45.0,
            xt_gained=0.16,
            defenders_in_corridor=2,
            defenders_in_cone=1,
            tactical_context="Penetrative key pass",
        )

        draft = adapter.generate_narrative(facts)
        assert draft.model_used == "deterministic-foundry-fallback"
        assert facts.passer_name in draft.narrative
        assert facts.receiver_name in draft.narrative

        # Verifier checks
        v_res = adapter.evaluate_grounding(facts, draft)
        assert v_res.is_valid is True
        assert v_res.grounding_score >= 0.95
