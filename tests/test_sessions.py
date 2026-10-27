"""Every viewer has their own match: controls, clock, analytics and analyst are isolated."""

import json
import os
import time
import uuid

import pytest
from fastapi.testclient import TestClient

from backend import app as app_module
from backend import sessions as sessions_module
from backend.app import app
from backend.sessions import SessionLimitReached, SessionRegistry


@pytest.fixture()
def client():
    with TestClient(app) as test_client:
        yield test_client


def _sid() -> str:
    return "viewer-" + uuid.uuid4().hex[:16]


def _fresh(client) -> str:
    """A new viewer whose match sits paused at kick-off (a new match starts playing on its own)."""
    sid = _sid()
    client.post("/api/control", json={"action": "pause"}, headers=_h(sid))
    client.post("/api/control", json={"action": "reset"}, headers=_h(sid))
    return sid


def _h(sid):
    return {"X-Session-Id": sid}


def _state(client, sid):
    return client.get("/api/state", headers=_h(sid)).json()


def _play_fast(client, sid, seconds=1.2):
    client.post("/api/control", json={"action": "speed", "multiplier": 20}, headers=_h(sid))
    client.post("/api/control", json={"action": "play"}, headers=_h(sid))
    time.sleep(seconds)
    client.post("/api/control", json={"action": "pause"}, headers=_h(sid))


# ----------------------------------------------------------------------------- isolation
def test_playing_in_one_session_does_not_move_another(client):
    a, b = _fresh(client), _fresh(client)
    _play_fast(client, a)

    state_a, state_b = _state(client, a), _state(client, b)
    assert state_a["frame"]["frame_id"] > 0
    assert state_b["frame"]["frame_id"] == 0 and state_b["clock"] == "00:00"
    assert state_b["is_paused"] is True


def test_pause_and_play_are_per_viewer(client):
    a, b = _fresh(client), _fresh(client)
    client.post("/api/control", json={"action": "play"}, headers=_h(a))
    assert _state(client, a)["is_paused"] is False
    assert _state(client, b)["is_paused"] is True   # B never pressed Play
    client.post("/api/control", json={"action": "pause"}, headers=_h(a))
    assert _state(client, a)["is_paused"] is True


def test_speed_and_reset_are_per_viewer(client):
    a, b = _fresh(client), _fresh(client)
    client.post("/api/control", json={"action": "speed", "multiplier": 10}, headers=_h(a))
    assert _state(client, a)["speed_multiplier"] == 10.0
    assert _state(client, b)["speed_multiplier"] != 10.0

    _play_fast(client, b, 0.6)
    _play_fast(client, a, 0.6)
    client.post("/api/control", json={"action": "reset"}, headers=_h(a))
    assert _state(client, a)["frame"]["frame_id"] == 0
    assert _state(client, b)["frame"]["frame_id"] > 0     # B kept its own match


def test_analytics_events_and_players_are_per_viewer(client):
    a, b = _fresh(client), _fresh(client)
    _play_fast(client, a, 1.5)
    events_a = client.get("/api/events", headers=_h(a)).json()
    events_b = client.get("/api/events", headers=_h(b)).json()
    assert len(events_a) > 0 and events_b == []
    stats_a = client.get("/api/analytics", headers=_h(a)).json()["match_stats"]
    stats_b = client.get("/api/analytics", headers=_h(b)).json()["match_stats"]
    assert stats_a != stats_b


def test_full_time_restart_is_per_viewer(client):
    a, b = _fresh(client), _fresh(client)
    client.post("/api/control", json={"action": "simulate_full"}, headers=_h(a))
    assert _state(client, a)["clock"].startswith("94")
    assert _state(client, b)["clock"] == "00:00"


# ----------------------------------------------------------------------------- default match
def test_requests_without_an_id_use_the_shared_default_match(client):
    client.post("/api/control", json={"action": "pause"})        # the default match: no session header
    default_before = client.get("/api/state").json()["frame"]["frame_id"]
    a = _fresh(client)
    _play_fast(client, a, 0.8)
    assert client.get("/api/state").json()["frame"]["frame_id"] == default_before  # untouched by A
    assert app_module.registry.default.streamer is app_module.streamer


def test_ingested_events_go_to_the_default_match_not_to_viewers(client):
    viewer = _sid()
    with open(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "synthetic_events.json"), encoding="utf-8") as f:
        event = json.load(f)[10]
    before = len(client.get("/api/analytics", headers=_h(viewer)).json()["player_stats"])
    assert client.post("/api/ingest", json=event).status_code == 200            # no session header: default match
    assert len(client.get("/api/analytics", headers=_h(viewer)).json()["player_stats"]) == before


# ----------------------------------------------------------------------------- validation and limits
@pytest.mark.parametrize("bad", ["x", "short", "has space here", "../../etc/passwd", "a" * 65, "id;drop table"])
def test_invalid_session_ids_are_rejected(client, bad):
    assert client.get("/api/state", headers={"X-Session-Id": bad}).status_code == 400


def test_too_many_viewers_get_a_clear_503(client, monkeypatch):
    monkeypatch.setattr(app_module.registry, "max_sessions", 0)
    response = client.get("/api/state", headers=_h(_sid()))
    assert response.status_code == 503 and "busy" in response.json()["detail"].lower()
    # The default shared match still answers.
    assert client.get("/api/state").status_code == 200


# ----------------------------------------------------------------------------- websocket
def test_each_websocket_streams_only_its_own_match(client):
    a, b = _fresh(client), _fresh(client)
    with client.websocket_connect(f"/ws/match-stream?session={a}") as ws_a, \
            client.websocket_connect(f"/ws/match-stream?session={b}") as ws_b:
        ws_a.send_text(json.dumps({"type": "control", "action": "play"}))
        ws_a.send_text(json.dumps({"type": "control", "action": "speed", "multiplier": 20}))
        frames_a = []
        deadline = time.time() + 5
        while time.time() < deadline and len(frames_a) < 5:
            message = json.loads(ws_a.receive_text())
            if message["type"] == "telemetry":
                frames_a.append(message["data"]["frame_id"])
        assert len(frames_a) >= 5 and frames_a[-1] > frames_a[0]

        # B pressed nothing, so its match stays at kick-off; ask B's own state through its own id.
        assert _state(client, b)["frame"]["frame_id"] == 0
        ws_b.send_text(json.dumps({"type": "ping", "client_time": 1}))
        assert json.loads(ws_b.receive_text())["type"] == "pong"   # B only ever receives its own messages


def test_websocket_with_a_bad_session_id_is_refused(client):
    with pytest.raises(Exception):
        with client.websocket_connect("/ws/match-stream?session=bad id"):
            pass


def test_a_viewers_match_pauses_when_they_leave_and_resumes_when_they_return(client):
    a = _fresh(client)
    with client.websocket_connect(f"/ws/match-stream?session={a}") as ws:
        ws.send_text(json.dumps({"type": "control", "action": "play"}))
        ws.send_text(json.dumps({"type": "ping", "client_time": 1}))
        while json.loads(ws.receive_text())["type"] != "pong":
            pass
        assert _state(client, a)["is_paused"] is False
    time.sleep(0.3)
    assert _state(client, a)["is_paused"] is True          # nobody is watching, so it stops

    with client.websocket_connect(f"/ws/match-stream?session={a}") as ws:   # a reload
        ws.send_text(json.dumps({"type": "ping", "client_time": 2}))
        while json.loads(ws.receive_text())["type"] != "pong":
            pass
        assert _state(client, a)["is_paused"] is False      # carries on where it was playing


def test_a_match_the_viewer_paused_stays_paused_after_a_reload(client):
    a = _fresh(client)
    with client.websocket_connect(f"/ws/match-stream?session={a}") as ws:
        ws.send_text(json.dumps({"type": "ping", "client_time": 1}))
        ws.receive_text()
    time.sleep(0.2)
    with client.websocket_connect(f"/ws/match-stream?session={a}") as ws:
        ws.send_text(json.dumps({"type": "ping", "client_time": 2}))
        ws.receive_text()
        assert _state(client, a)["is_paused"] is True


# ----------------------------------------------------------------------------- analyst follows the viewer's match
def test_analyst_context_is_the_viewers_own_match(client):
    a, b = _fresh(client), _fresh(client)
    _play_fast(client, a, 1.5)
    session_a = app_module.registry.get_or_create(a)
    session_b = app_module.registry.get_or_create(b)
    live_a, live_b = app_module._live_match(session_a), app_module._live_match(session_b)
    assert live_a["status"] == "LIVE" and live_a["clock"] != "00:00" and live_a["events"]
    assert live_b["status"] == "NOT_STARTED" and live_b["clock"] == "00:00" and live_b["events"] == []
    assert app_module._get_analyst(session_a) is not app_module._get_analyst(session_b)
    assert app_module._get_analyst(session_a) is app_module._get_analyst(session_a)


# ----------------------------------------------------------------------------- registry
def _fake_factory(session_id):
    class _Gen:
        frame_index = 0
        events = []

    class _Streamer:
        frame_rate = 25
        generator = _Gen()

        def reset(self):
            pass

        def pause(self):
            pass

    class _Tracker:
        def reset(self):
            pass

    return sessions_module.MatchSession(session_id, _Streamer(), _Tracker())


def test_registry_creates_one_session_per_id_and_caps_them():
    registry = SessionRegistry(_fake_factory, max_sessions=2, idle_seconds=3600)
    first = registry.get_or_create("viewer-aaaaaaaa")
    assert registry.get_or_create("viewer-aaaaaaaa") is first
    registry.get_or_create("viewer-bbbbbbbb")
    with pytest.raises(SessionLimitReached):
        registry.get_or_create("viewer-cccccccc")
    assert registry.count() == 2 and registry.default.is_default


def test_registry_removes_idle_sessions_and_makes_room():
    registry = SessionRegistry(_fake_factory, max_sessions=1, idle_seconds=0.05)
    registry.get_or_create("viewer-aaaaaaaa")
    time.sleep(0.1)
    assert registry.cleanup_idle() == 1 and registry.count() == 0

    stale = registry.get_or_create("viewer-bbbbbbbb")
    stale.last_seen = time.monotonic() - 3600
    # Full table: the stale session is evicted to let a new viewer in.
    registry.get_or_create("viewer-cccccccc")
    assert registry.count() == 1 and stale.id not in registry._sessions


def test_a_viewer_with_a_connection_is_never_evicted():
    registry = SessionRegistry(_fake_factory, max_sessions=1, idle_seconds=0.01)
    busy = registry.get_or_create("viewer-aaaaaaaa")
    busy.manager.active_connections.add(object())
    busy.last_seen = time.monotonic() - 3600
    time.sleep(0.05)
    assert registry.cleanup_idle() == 0
    with pytest.raises(SessionLimitReached):
        registry.get_or_create("viewer-bbbbbbbb")


def test_session_id_pattern():
    assert SessionRegistry.is_valid_id("a1b2c3d4-e5f6-4789-a012-3456789abcde")
    assert not SessionRegistry.is_valid_id("")
    assert not SessionRegistry.is_valid_id("short")
    assert not SessionRegistry.is_valid_id("bad id with spaces")
