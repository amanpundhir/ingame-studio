"""InGame Studio - External Telemetry Ingestion API Test Suite (R4).

Validates:
1. POST /api/ingest: Single MatchEvent schema validation, tracker ingestion, multi-agent processing, and response.
2. POST /api/events: Batch MatchEvent ingestion, sequential processing, and batch count response.
3. Schema violations: Detection and rejection of out-of-bounds coordinates, invalid event types, and missing required fields (HTTP 422).
4. Real-time WebSocket broadcasting: Verification that ingested events and generated insights are broadcast to connected clients.
5. Tracker state synchronization: Verification that event ingestion updates match statistics and player counters.
"""

import json
import pytest
from fastapi.testclient import TestClient

from backend.app import app


@pytest.fixture(scope="module")
def client():
    """TestClient instance for InGame FastAPI application."""
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture
def valid_match_event():
    """Sample valid MatchEvent conforming to data/schema.json."""
    return {
        "event_id": "EVT_INGEST_TEST_01",
        "match_id": "IGS_2026_NBL_HSC",
        "event_type": "pass",
        "sub_type": "line_breaking_pass",
        "period": 1,
        "clock": "14:22",
        "frame_index": 21550,
        "team": "Northbridge Lions",
        "player_id": "NBL_08",
        "player_name": "Martin Olsvik",
        "secondary_player_id": "NBL_07",
        "secondary_player_name": "Kofi Sarpong",
        "location_x": 62.5,
        "location_y": 44.0,
        "end_x": 82.0,
        "end_y": 55.0,
        "outcome": "completed",
        "tactical_metrics": {
            "pass_difficulty": 74.5,
            "ball_speed_kmh": 68.2,
            "chaos_index": 48.0,
            "xt_gained": 0.14,
        },
        "context": "Progressive pass through midfield channels",
    }


@pytest.fixture
def valid_goal_event():
    """Sample valid goal MatchEvent conforming to data/schema.json."""
    return {
        "event_id": "EVT_INGEST_GOAL_01",
        "match_id": "IGS_2026_NBL_HSC",
        "event_type": "goal",
        "period": 1,
        "clock": "28:15",
        "frame_index": 42375,
        "team": "Northbridge Lions",
        "player_id": "NBL_07",
        "player_name": "Kofi Sarpong",
        "secondary_player_id": "HSC_31",
        "secondary_player_name": "Enzo Barreto",
        "location_x": 94.0,
        "location_y": 30.0,
        "outcome": "goal",
        "tactical_metrics": {
            "pass_difficulty": 88.0,
            "ball_speed_kmh": 102.5,
            "chaos_index": 78.0,
            "xt_gained": 0.42,
        },
    }


class TestSingleEventIngestion:
    """Tests POST /api/ingest for single MatchEvent ingestion."""

    def test_post_ingest_valid_event(self, client, valid_match_event):
        """Asserts valid event payload ingests successfully with HTTP 200 and insight artifact."""
        resp = client.post("/api/ingest", json=valid_match_event)
        assert resp.status_code == 200
        data = resp.json()

        assert data["status"] == "ingested"
        assert data["event_id"] == valid_match_event["event_id"]
        assert "insight" in data

        insight = data["insight"]
        assert insight["event_id"] == valid_match_event["event_id"]
        assert "casual_story" in insight
        assert "tactical_analysis" in insight
        assert "club_loyalist_story" in insight
        assert "player_lock_story" in insight
        assert "lower_third_ticker" in insight
        assert "telestrator_vectors" in insight
        assert "translations" in insight
        assert set(insight["translations"].keys()) == {"en", "es"}

    def test_post_ingest_updates_tracker_state(self, client, valid_goal_event):
        """Asserts ingesting an event records into match statistics and tracker."""
        # Get baseline match stats
        resp_before = client.get("/api/analytics")
        assert resp_before.status_code == 200

        # Ingest goal event
        resp_ingest = client.post("/api/ingest", json=valid_goal_event)
        assert resp_ingest.status_code == 200

        # Verify analytics tracker recorded event
        resp_after = client.get("/api/analytics")
        assert resp_after.status_code == 200
        stats_after = resp_after.json()["match_stats"]

        # Ensure goal was registered in score or shots
        assert stats_after["score"]["home"] >= 1 or stats_after["shots"]["home"]["total"] >= 1

    def test_post_ingest_websocket_broadcast(self, client, valid_match_event):
        """Asserts ingesting an event broadcasts 'event' and 'insight' payloads to WebSockets."""
        with client.websocket_connect("/ws/match-stream") as websocket:
            # Modify event_id to ensure unique trigger
            test_evt = dict(valid_match_event)
            test_evt["event_id"] = "EVT_WS_BROADCAST_TEST"

            resp = client.post("/api/ingest", json=test_evt)
            assert resp.status_code == 200

            received_types = set()
            for _ in range(10):
                try:
                    msg_text = websocket.receive_text()
                    msg = json.loads(msg_text)
                    mtype = msg.get("type")
                    received_types.add(mtype)
                    if "event" in received_types and "insight" in received_types:
                        break
                except Exception:
                    break

            assert "event" in received_types
            assert "insight" in received_types


class TestBatchEventsIngestion:
    """Tests POST /api/events for batch telemetry event ingestion."""

    def test_post_events_valid_batch_payload(self, client, valid_match_event, valid_goal_event):
        """Asserts batch payload {"events": [...]} ingests successfully with count."""
        evt1 = dict(valid_match_event)
        evt1["event_id"] = "EVT_BATCH_01"
        evt2 = dict(valid_goal_event)
        evt2["event_id"] = "EVT_BATCH_02"

        batch_payload = {"events": [evt1, evt2]}
        resp = client.post("/api/events", json=batch_payload)
        assert resp.status_code == 200
        data = resp.json()

        assert data["status"] == "batch_ingested"
        assert data["count"] == 2

    def test_post_events_accepts_list_payload(self, client, valid_match_event):
        """Asserts batch endpoint also accepts raw list array for maximum client flexibility."""
        evt = dict(valid_match_event)
        evt["event_id"] = "EVT_BATCH_LIST_01"

        resp = client.post("/api/events", json=[evt])
        assert resp.status_code == 200
        data = resp.json()

        assert data["status"] == "batch_ingested"
        assert data["count"] == 1


class TestSchemaViolationsAndErrorHandling:
    """Tests rejection of invalid payloads conforming to data/schema.json."""

    def test_ingest_missing_required_field(self, client, valid_match_event):
        """Asserts payload missing required field returns HTTP 422 Unprocessable Entity."""
        bad_evt = dict(valid_match_event)
        del bad_evt["event_id"]

        resp = client.post("/api/ingest", json=bad_evt)
        assert resp.status_code == 422
        assert "event_id" in resp.text

    def test_ingest_out_of_bounds_x_coordinate(self, client, valid_match_event):
        """Asserts location_x > 105.0 is rejected with HTTP 422."""
        bad_evt = dict(valid_match_event)
        bad_evt["location_x"] = 150.0  # Out of pitch bounds [0, 105]

        resp = client.post("/api/ingest", json=bad_evt)
        assert resp.status_code == 422
        assert "location_x" in resp.text

    def test_ingest_out_of_bounds_y_coordinate(self, client, valid_match_event):
        """Asserts location_y > 68.0 is rejected with HTTP 422."""
        bad_evt = dict(valid_match_event)
        bad_evt["location_y"] = 90.0  # Out of pitch bounds [0, 68]

        resp = client.post("/api/ingest", json=bad_evt)
        assert resp.status_code == 422
        assert "location_y" in resp.text

    def test_ingest_invalid_event_type(self, client, valid_match_event):
        """Asserts unsupported event_type is rejected with HTTP 422."""
        bad_evt = dict(valid_match_event)
        bad_evt["event_type"] = "kung_fu_kick"  # Not in allowed enum

        resp = client.post("/api/ingest", json=bad_evt)
        assert resp.status_code == 422
        assert "event_type" in resp.text

    def test_ingest_non_dict_payload(self, client):
        """Asserts non-dict scalar/string payload is rejected with HTTP 422."""
        resp = client.post("/api/ingest", json="not_a_json_object")
        assert resp.status_code == 422

    def test_batch_events_with_invalid_sub_event(self, client, valid_match_event):
        """Asserts batch payload where one event violates schema returns HTTP 422 with event index."""
        evt1 = dict(valid_match_event)
        evt1["event_id"] = "EVT_VALID_01"

        evt2 = dict(valid_match_event)
        evt2["location_x"] = 250.0  # Invalid coordinate

        resp = client.post("/api/events", json={"events": [evt1, evt2]})
        assert resp.status_code == 422
        assert "event[1]" in resp.text

    def test_batch_events_missing_events_key(self, client):
        """Asserts batch payload missing 'events' key returns HTTP 422."""
        resp = client.post("/api/events", json={"wrong_key": []})
        assert resp.status_code == 422
        assert "Missing 'events' list" in resp.text
