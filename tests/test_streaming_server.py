"""Tests for InGame Studio FastAPI & WebSocket Streaming Server.

Covers:
- REST endpoints: /health, /api/status, /api/control, /api/events, /api/insights/latest.
- WebSocket streaming: /ws/match-stream connection, frame reception, ping/pong latency.
- Streaming controls: pause, resume, reset.
"""

import json
from pathlib import Path
import pytest
from fastapi.testclient import TestClient
import jsonschema

from backend.app import app


@pytest.fixture
def client():
    with TestClient(app) as c:
        yield c


@pytest.fixture
def schema():
    schema_path = Path(__file__).resolve().parents[1] / "data" / "schema.json"
    with open(schema_path, "r", encoding="utf-8") as f:
        return json.load(f)


class TestServerRestEndpoints:
    """Tests HTTP REST endpoints on the streaming server."""

    def test_health_check(self, client):
        response = client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ok"
        assert data["app"] == "InGame Studio"
        assert data["version"] == "1.0.0"
        assert data["fps"] == 25

    def test_api_status(self, client):
        response = client.get("/api/status")
        assert response.status_code == 200
        data = response.json()
        assert "match_id" in data
        assert "clock" in data
        assert "frame_index" in data
        assert "is_paused" in data

    def test_api_events_list(self, client):
        response = client.get("/api/events")
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        # Generated events appear as actions occur; startup no longer preloads a
        # fixed event timeline. The initial list is therefore legitimately empty.
        assert data == []

    def test_api_control_pause_and_play(self, client):
        # Pause
        pause_resp = client.post("/api/control", json={"action": "pause"})
        assert pause_resp.status_code == 200
        assert pause_resp.json()["is_paused"] is True

        # Resume
        play_resp = client.post("/api/control", json={"action": "play"})
        assert play_resp.status_code == 200
        assert play_resp.json()["is_paused"] is False

    def test_api_control_reset(self, client):
        reset_resp = client.post("/api/control", json={"action": "reset"})
        assert reset_resp.status_code == 200
        assert reset_resp.json()["status"] == "reset"

    def test_api_insights_latest(self, client, schema):
        response = client.get("/api/insights/latest")
        if response.status_code == 200:
            data = response.json()
            insight_schema = schema["definitions"]["VerifiedInsight"]
            jsonschema.validate(instance=data, schema=insight_schema)


class TestWebSocketStreaming:
    """Tests WebSocket 25Hz live stream and interactive message handling."""

    def test_websocket_ping_pong_latency(self, client):
        with client.websocket_connect("/ws/match-stream") as ws:
            # Send ping
            client_t = 123456789
            ws.send_text(json.dumps({"type": "ping", "client_time": client_t}))

            # Read messages until we get pong
            pong_received = False
            for _ in range(10):
                msg_str = ws.receive_text()
                msg = json.loads(msg_str)
                if msg.get("type") == "pong":
                    assert msg["client_time"] == client_t
                    assert "server_time" in msg
                    pong_received = True
                    break

            assert pong_received, "Failed to receive pong response from WebSocket server"

    def test_websocket_receives_telemetry_frames(self, client, schema):
        with client.websocket_connect("/ws/match-stream") as ws:
            telemetry_received = False
            telemetry_schema = {
                "$schema": "http://json-schema.org/draft-07/schema#",
                "$ref": "#/definitions/TelemetryFrame",
                "definitions": schema["definitions"],
            }
            validator = jsonschema.Draft7Validator(schema=telemetry_schema)

            for _ in range(15):
                msg_str = ws.receive_text()
                msg = json.loads(msg_str)
                if msg.get("type") == "telemetry":
                    telemetry_received = True
                    frame_data = msg["data"]
                    validator.validate(frame_data)
                    assert len(frame_data["players"]) == 22
                    assert "ball" in frame_data
                    break

            assert telemetry_received, "Failed to receive valid TelemetryFrame from stream"
