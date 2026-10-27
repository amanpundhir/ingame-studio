"""InGame Studio - Milestone Tracking & Physical Threshold Alerts Test Suite.

Validates:
1. Team and player milestone tracking in MatchAnalyticsTracker:
   - Team completed passes (e.g. 50th, 100th)
   - Player completed passes (e.g. 25th, 50th)
   - Defensive interventions / tackles won (e.g. 5th, 10th)
   - Shots on target (e.g. 3rd, 5th)
   - Opening match goal & equalizer
2. Milestone surfacing in FactPack, Pundit narratives, and broadcast ticker straps.
3. Physical threshold alerts (metric_alert):
   - Sprint speed > 32 km/h with 15s per-player cooldown
   - Shot velocity > 100 km/h
   - Distance marks (5km, 10km)
4. Schema validation for BroadcastPayload with type="metric_alert".
5. REST endpoint GET /api/alerts.
"""

import json
import os
import pytest
from fastapi.testclient import TestClient
from jsonschema import Draft7Validator

from backend.app import app
from backend.math_engine import MatchAnalyticsTracker
from backend.agents.tactician_agent import TacticianAgent
from backend.agents.pundit_agent import PunditAgent
from backend.agents.director_agent import StudioDirectorAgent


@pytest.fixture(scope="module")
def schema():
    """Loads authoritative data/schema.json."""
    repo_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    schema_path = os.path.join(repo_root, "data", "schema.json")
    with open(schema_path, "r", encoding="utf-8") as f:
        return json.load(f)


@pytest.fixture(scope="module")
def synthetic_events():
    """Loads calibrated match events."""
    repo_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    events_path = os.path.join(repo_root, "data", "synthetic_events.json")
    with open(events_path, "r", encoding="utf-8") as f:
        return json.load(f)


class TestMilestoneTracking:
    """Tests milestone detection in MatchAnalyticsTracker and propagation into narratives."""

    def test_opening_goal_milestone_detection(self):
        """Asserts the first goal of the match triggers an opening goal milestone."""
        tracker = MatchAnalyticsTracker()
        goal_evt = {
            "event_id": "EVT_TEST_GOAL",
            "event_type": "goal",
            "clock": "12:30",
            "team": "Northbridge Lions",
            "player_id": "NBL_07",
            "player_name": "Kofi Sarpong",
            "outcome": "goal",
            "location_x": 92.0,
            "location_y": 34.0,
        }
        milestone = tracker.record_event(goal_evt)
        assert milestone is not None
        assert "Opening Match Goal" in milestone
        assert "Kofi Sarpong" in milestone

        milestones = tracker.get_milestones()
        assert len(milestones) == 1
        assert milestones[0]["event_id"] == "EVT_TEST_GOAL"

    def test_team_pass_milestone_detection(self):
        """Asserts completed passes trigger 25th/50th pass milestones."""
        tracker = MatchAnalyticsTracker()
        milestone_triggered = None

        # Simulate 25 completed passes
        for i in range(25):
            ev = {
                "event_id": f"EVT_PASS_{i+1}",
                "event_type": "pass",
                "clock": f"0{i//2}:30",
                "team": "Northbridge Lions",
                "player_id": "NBL_41",
                "player_name": "Declan Rowe",
                "outcome": "complete",
            }
            m = tracker.record_event(ev)
            if m:
                milestone_triggered = m

        assert milestone_triggered is not None
        assert "25th completed pass" in milestone_triggered
        assert tracker.get_latest_milestone() == milestone_triggered

    def test_milestone_surfaces_in_factpack_and_narratives(self):
        """Asserts milestone is incorporated into FactPack and Pundit/Director narratives."""
        tactician = TacticianAgent()
        pundit = PunditAgent()
        director = StudioDirectorAgent()

        event_with_milestone = {
            "event_id": "EVT_MILESTONE",
            "event_type": "pass",
            "clock": "34:10",
            "team": "Northbridge Lions",
            "player_name": "Declan Rowe",
            "secondary_player_name": "Kofi Sarpong",
            "milestone": "Northbridge Lions 50th completed pass",
            "tactical_metrics": {
                "pass_difficulty": 45.0,
                "ball_speed_kmh": 60.0,
                "xt_gained": 0.05,
            },
        }

        facts = tactician.extract_facts(event_with_milestone)
        assert facts.milestone == "Northbridge Lions 50th completed pass"
        assert "[Milestone: Northbridge Lions 50th completed pass]" in facts.tactical_context

        draft = pundit.generate_narrative(facts)
        assert "[Milestone: Northbridge Lions 50th completed pass]" in draft.narrative

        personas = director.adapt_personas(facts, draft.narrative)
        assert "[Milestone: Northbridge Lions 50th completed pass]" in personas.casual_story
        assert "MILESTONE: NORTHBRIDGE LIONS 50TH COMPLETED PASS" in personas.lower_third_ticker


class TestPhysicalThresholdAlerts:
    """Tests sprint speed, shot speed, and distance thresholds with debouncing/cooldowns."""

    def test_sprint_speed_alert_and_15s_cooldown(self):
        """Asserts sprint > 32 km/h triggers metric_alert with 15s cooldown per player."""
        tracker = MatchAnalyticsTracker()

        # Frame 1 at 10:00 - Sarpong sprints at 33.5 km/h -> Alert 1 should fire
        frame_1 = {
            "timestamp": "2026-04-18T16:40:00Z",
            "clock": "10:00",
            "players": [
                {"player_id": "NBL_07", "name": "Kofi Sarpong", "team": "home", "x": 75.0, "y": 30.0, "speed_kmh": 33.5}
            ],
            "ball": {"speed_kmh": 20.0},
        }
        tracker.add_telemetry_frame(frame_1)

        pending = tracker.pop_pending_alerts()
        assert len(pending) == 1
        alert = pending[0]
        assert alert["alert_type"] == "sprint_speed"
        assert alert["player_id"] == "NBL_07"
        assert alert["threshold"] == 32.0
        assert alert["metric_value"] == 33.5

        # Frame 2 at 10:05 (5 seconds later) - Sarpong still sprinting at 34.0 km/h -> Should NOT fire (cooldown)
        frame_2 = {
            "timestamp": "2026-04-18T16:40:05Z",
            "clock": "10:05",
            "players": [
                {"player_id": "NBL_07", "name": "Kofi Sarpong", "team": "home", "x": 85.0, "y": 30.0, "speed_kmh": 34.0}
            ],
            "ball": {"speed_kmh": 20.0},
        }
        tracker.add_telemetry_frame(frame_2)
        assert len(tracker.pop_pending_alerts()) == 0

        # Frame 3 at 10:16 (16 seconds after Frame 1) - Sarpong sprints again -> Alert 2 should fire
        frame_3 = {
            "timestamp": "2026-04-18T16:40:16Z",
            "clock": "10:16",
            "players": [
                {"player_id": "NBL_07", "name": "Kofi Sarpong", "team": "home", "x": 95.0, "y": 30.0, "speed_kmh": 33.8}
            ],
            "ball": {"speed_kmh": 20.0},
        }
        tracker.add_telemetry_frame(frame_3)
        pending_after_cooldown = tracker.pop_pending_alerts()
        assert len(pending_after_cooldown) == 1
        assert pending_after_cooldown[0]["metric_value"] == 33.8

    def test_shot_velocity_alert(self):
        """Asserts shot velocity > 100 km/h emits shot_velocity alert."""
        tracker = MatchAnalyticsTracker()

        rocket_shot_evt = {
            "event_id": "EVT_ROCKET",
            "event_type": "shot",
            "clock": "22:15",
            "team": "Harbourside City",
            "player_id": "HSC_09",
            "player_name": "Anders Hagen",
            "location_x": 88.0,
            "location_y": 34.0,
            "tactical_metrics": {
                "ball_speed_kmh": 104.5,
                "pass_difficulty": 85.0,
            },
        }
        tracker.record_event(rocket_shot_evt)

        pending = tracker.pop_pending_alerts()
        assert len(pending) == 1
        alert = pending[0]
        assert alert["alert_type"] == "shot_velocity"
        assert alert["player_name"] == "Anders Hagen"
        assert alert["threshold"] == 100.0
        assert alert["metric_value"] == 104.5

    def test_distance_mark_alert(self):
        """Asserts reaching 5000m (5km) triggers a single distance_mark alert."""
        tracker = MatchAnalyticsTracker()
        pid = "NBL_41"  # Declan Rowe

        # Simulate small steps accumulating distance up to 5001m
        tracker.players[pid].distance_meters = 4999.0
        frame = {
            "timestamp": "2026-04-18T17:15:00Z",
            "clock": "45:00",
            "players": [
                {"player_id": pid, "name": "Declan Rowe", "team": "home", "x": 50.0, "y": 34.0, "speed_kmh": 12.0}
            ],
            "ball": {"speed_kmh": 10.0},
        }
        tracker.players[pid].last_x = 50.0
        tracker.players[pid].last_y = 33.0  # 1m away -> total 5000.0m

        tracker.add_telemetry_frame(frame)
        pending = tracker.pop_pending_alerts()

        assert len(pending) == 1
        assert pending[0]["alert_type"] == "distance_mark"
        assert pending[0]["player_name"] == "Declan Rowe"
        assert pending[0]["threshold"] == 5000.0

        # Subsequent frame should NOT duplicate 5000m alert
        tracker.add_telemetry_frame(frame)
        assert len(tracker.pop_pending_alerts()) == 0


class TestAlertsSchemaAndREST:
    """Tests schema validity of metric_alert envelopes and GET /api/alerts endpoint."""

    def test_metric_alert_conforms_to_broadcast_payload_schema(self, schema):
        """Asserts metric_alert wraps cleanly into schema.json BroadcastPayload."""
        validator = Draft7Validator(schema["definitions"]["BroadcastPayload"])

        payload = {
            "type": "metric_alert",
            "timestamp": "2026-04-18T16:30:00Z",
            "data": {
                "alert_id": "ALT_SPRINT_1_NBL_07",
                "alert_type": "sprint_speed",
                "player_id": "NBL_07",
                "player_name": "Kofi Sarpong",
                "metric_value": 33.8,
                "threshold": 32.0,
            },
        }
        validator.validate(payload)

    def test_get_alerts_rest_endpoint(self):
        """Asserts GET /api/alerts returns 200 and list of recorded alerts."""
        client = TestClient(app)
        response = client.get("/api/alerts")
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
