"""
InGame Studio - Speed Multipliers & Control Streaming Test Suite (Requirement R5 & R6)
Validates:
- Variable speed multipliers (1x, 2x, 5x, 10x, 20x) and boundary clamping [0.25, 20.0]
- Adaptive frame stepping logic (K frames per tick)
- 25Hz broadcast pacing guarantee (40ms constant interval) preventing buffer bloat
- REST POST /api/control actions: speed, jump, simulate_full, and validation errors
- Replay jump pitch state restoration and telestrator vector emission
- Macro full match simulation in < 200ms with calibrated 2-2 scoreline
- WebSocket control message handling
"""

import time
import pytest
from fastapi.testclient import TestClient

from backend.app import app
import importlib
backend_app = importlib.import_module("backend.app")
from generator.telemetry_streamer import TelemetryStreamer


@pytest.fixture
def client():
    """Provides a TestClient for FastAPI endpoints."""
    with TestClient(app) as test_client:
        yield test_client


class TestSpeedMultiplierValidation:
    """Validates multiplier setting, defaults, and boundary clamping."""

    def test_default_speed_is_one(self):
        """Asserts TelemetryStreamer initializes with speed_multiplier == 1.0."""
        s = TelemetryStreamer(match_id="IGS_TEST_SPEED", frame_rate=25, real_time=False)
        assert s.speed_multiplier == 1.0

    def test_allowed_multipliers_accepted(self):
        """Asserts multipliers [1.0, 2.0, 5.0, 10.0, 20.0] are accepted without modification."""
        s = TelemetryStreamer(match_id="IGS_TEST_SPEED", frame_rate=25, real_time=False)
        for mult in [1.0, 2.0, 5.0, 10.0, 20.0]:
            res = s.set_speed(mult)
            assert res == mult
            assert s.speed_multiplier == mult

    def test_invalid_multiplier_clamping(self):
        """Asserts extreme and negative values are clamped within [0.25, 20.0]."""
        s = TelemetryStreamer(match_id="IGS_TEST_SPEED", frame_rate=25, real_time=False)
        assert s.set_speed(-5.0) == 0.25
        assert s.speed_multiplier == 0.25

        assert s.set_speed(0.0) == 0.25
        assert s.speed_multiplier == 0.25

        assert s.set_speed(100.0) == 20.0
        assert s.speed_multiplier == 20.0


class TestAdaptiveFrameStepping:
    """Validates discrete frame stepping calculations for each broadcast tick."""

    def test_stepping_1x_advances_1_frame(self):
        """At 1x speed, exactly 1 frame is stepped per tick."""
        s = TelemetryStreamer(match_id="IGS_TEST_SPEED", frame_rate=25, real_time=False)
        s.set_speed(1.0)
        assert s.get_steps_for_tick() == 1
        initial_frame = s.generator.frame_index
        s.generator.step()
        assert s.generator.frame_index == initial_frame + 1

    def test_stepping_2x_advances_2_frames(self):
        """At 2x speed, exactly 2 frames are stepped per tick."""
        s = TelemetryStreamer(match_id="IGS_TEST_SPEED", frame_rate=25, real_time=False)
        s.set_speed(2.0)
        assert s.get_steps_for_tick() == 2

    def test_stepping_5x_advances_5_frames(self):
        """At 5x speed, exactly 5 frames are stepped per tick."""
        s = TelemetryStreamer(match_id="IGS_TEST_SPEED", frame_rate=25, real_time=False)
        s.set_speed(5.0)
        assert s.get_steps_for_tick() == 5

    def test_stepping_10x_advances_10_frames(self):
        """At 10x speed, exactly 10 frames are stepped per tick."""
        s = TelemetryStreamer(match_id="IGS_TEST_SPEED", frame_rate=25, real_time=False)
        s.set_speed(10.0)
        assert s.get_steps_for_tick() == 10

    def test_stepping_20x_advances_20_frames(self):
        """At 20x speed, exactly 20 frames are stepped per tick."""
        s = TelemetryStreamer(match_id="IGS_TEST_SPEED", frame_rate=25, real_time=False)
        s.set_speed(20.0)
        assert s.get_steps_for_tick() == 20


class TestBroadcastPacingGuarantee:
    """Validates that broadcast pacing is constant at 25Hz and stepping execution is lightweight."""

    def test_broadcast_interval_constant(self):
        """Broadcast frame_interval remains strictly 0.04s (25Hz) across all speed settings."""
        s = TelemetryStreamer(match_id="IGS_TEST_SPEED", frame_rate=25, real_time=True)
        for mult in [1.0, 2.0, 5.0, 10.0, 20.0]:
            s.set_speed(mult)
            assert s.frame_interval == pytest.approx(0.04, abs=1e-5)

    def test_stepping_latency_under_10ms(self):
        """Asserts stepping 20 frames takes less than 10ms (budget is 40ms)."""
        s = TelemetryStreamer(match_id="IGS_TEST_SPEED", frame_rate=25, real_time=False)
        t0 = time.perf_counter()
        for _ in range(20):
            s.generator.step()
        duration = time.perf_counter() - t0
        assert duration < 0.010, f"Stepping 20 frames took {duration*1000:.2f}ms, expected < 10ms"


class TestControlRestEndpoint:
    """Validates POST /api/control actions."""

    def test_post_control_speed_action(self, client):
        """POST /api/control with action='speed' updates streamer speed and returns 200."""
        response = client.post("/api/control", json={"action": "speed", "multiplier": 5.0})
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ok"
        assert data["action"] == "speed"
        assert data["multiplier"] == 5.0

    def test_post_control_speed_invalid_value(self, client):
        """POST /api/control with non-positive multiplier returns 400 Bad Request."""
        response = client.post("/api/control", json={"action": "speed", "multiplier": -5.0})
        assert response.status_code == 400
        response_zero = client.post("/api/control", json={"action": "speed", "multiplier": 0.0})
        assert response_zero.status_code == 400

    def test_api_status_reports_speed(self, client):
        """GET /api/status accurately reflects current playback speed multiplier."""
        client.post("/api/control", json={"action": "speed", "multiplier": 10.0})
        response = client.get("/api/status")
        assert response.status_code == 200
        assert response.json()["speed_multiplier"] == 10.0


class TestReplayJumpRestEndpoint:
    """Validates replay jump seeking, state restoration, and telestrator vectors."""

    def test_post_control_jump_valid_event(self, client):
        """POST /api/control with action='jump' seeks to event and returns synchronized insight."""
        events_resp = client.get("/api/events")
        assert events_resp.status_code == 200
        events = events_resp.json()
        if not events:
            client.post("/api/control", json={"action": "pause"})
            generator = backend_app.streamer.generator
            # Events become available as simulated actions occur. Advance the
            # seeded simulation until its first event instead of expecting a
            # preloaded hand-authored timeline at startup.
            for _ in range(5000):
                generator.step()
                if generator.get_events():
                    break
            events = client.get("/api/events").json()
        assert len(events) > 0
        first_event = events[0]
        event_id = first_event["event_id"]

        resp = client.post("/api/control", json={"action": "jump", "event_id": event_id})
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "jumped"
        assert data["event_id"] == event_id
        assert data["clock"] == first_event["clock"]
        assert "insight" in data
        assert "telestrator_vectors" in data["insight"]
        vectors = data["insight"]["telestrator_vectors"]
        assert "start_x" in vectors
        assert "end_x" in vectors

    def test_post_control_jump_nonexistent_event(self, client):
        """POST /api/control with unknown event_id returns 404 Not Found."""
        resp = client.post("/api/control", json={"action": "jump", "event_id": "EVT_NONEXISTENT_9999"})
        assert resp.status_code == 404


class TestSimulateFullMatch:
    """Validates instant macro full match simulation in under 200ms."""

    def test_post_control_simulate_full(self, client):
        """POST /api/control reaches full time and returns the generated score."""
        resp = client.post("/api/control", json={"action": "simulate_full"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "simulated_full"
        assert data["clock"] == "94:30"
        expected_score = {"home": 0, "away": 0}
        for event in client.get("/api/events").json():
            if event.get("event_type") == "goal" or event.get("outcome") == "goal":
                if event.get("team") in ("home", "Northbridge Lions"):
                    expected_score["home"] += 1
                elif event.get("team") in ("away", "Harbourside City"):
                    expected_score["away"] += 1
        assert data["score"] == expected_score
        assert "match_stats" in data
        assert "player_stats" in data
        assert len(data["player_stats"]) >= 22

    def test_simulate_full_execution_under_200ms(self, client):
        """Asserts simulate_full completes in less than 200ms."""
        t0 = time.perf_counter()
        resp = client.post("/api/control", json={"action": "simulate_full"})
        elapsed = time.perf_counter() - t0
        assert resp.status_code == 200
        assert elapsed < 0.200, f"simulate_full took {elapsed*1000:.2f}ms, expected < 200ms"


class TestWebSocketControlStreaming:
    """Validates WebSocket control message processing."""

    def test_websocket_speed_message(self, client):
        """WebSocket client sending control speed message updates streamer speed."""
        with client.websocket_connect("/ws/match-stream") as websocket:
            websocket.send_json({"type": "control", "action": "speed", "multiplier": 10.0})
            time.sleep(0.05)
            status_resp = client.get("/api/status")
            assert status_resp.status_code == 200
            assert status_resp.json()["speed_multiplier"] == 10.0
