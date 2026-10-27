"""API hardening: write endpoints, analyst rate limit, CORS, WebSocket limits, headers, secrets."""

import json
import os
import re

import pytest
from fastapi.testclient import TestClient

from backend import app as app_module
from backend import security
from backend.app import app

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


@pytest.fixture()
def client():
    with TestClient(app) as test_client:
        yield test_client


def _event():
    with open(os.path.join(ROOT, "data", "synthetic_events.json"), encoding="utf-8") as handle:
        return json.load(handle)[10]


# ----------------------------------------------------------------------------- ingest key
def test_ingest_is_open_without_a_configured_key(client, monkeypatch):
    monkeypatch.delenv("INGAME_API_KEY", raising=False)
    assert client.post("/api/ingest", json=_event()).status_code == 200


def test_ingest_requires_the_key_when_one_is_configured(client, monkeypatch):
    monkeypatch.setenv("INGAME_API_KEY", "correct-horse-battery")
    assert client.post("/api/ingest", json=_event()).status_code == 401
    assert client.post("/api/ingest", json=_event(), headers={"X-API-Key": "wrong"}).status_code == 401
    assert client.post("/api/events", json=[_event()]).status_code == 401
    assert client.post("/api/ingest", json=_event(), headers={"X-API-Key": "correct-horse-battery"}).status_code == 200
    assert client.post("/api/events", json=[_event()], headers={"X-API-Key": "correct-horse-battery"}).status_code == 200


def test_batch_size_is_capped(client, monkeypatch):
    monkeypatch.delenv("INGAME_API_KEY", raising=False)
    too_many = [_event()] * (security.MAX_EVENTS_PER_BATCH + 1)
    assert client.post("/api/events", json=too_many).status_code == 413


# ----------------------------------------------------------------------------- analyst limits
def test_analyst_rejects_oversized_input(client):
    response = client.post("/api/analyst/ask", json={"question": "x" * 401})
    assert response.status_code == 422


def test_analyst_is_rate_limited_per_client(client, monkeypatch):
    monkeypatch.setattr(app_module, "_analyst_client_limit", security.RateLimiter(limit=2, window=60))
    monkeypatch.setattr(app_module, "_analyst_global_limit", security.RateLimiter(limit=100, window=60))
    codes = [client.post("/api/analyst/ask", json={"question": ""}).status_code for _ in range(4)]
    assert codes[:2] == [200, 200] and codes[2:] == [429, 429]


def test_rate_limiter_window_and_memory():
    now = [0.0]
    limiter = security.RateLimiter(limit=2, window=60.0, clock=lambda: now[0])
    assert limiter.allow("a") and limiter.allow("a") and not limiter.allow("a")
    assert limiter.allow("b")  # another client has its own allowance
    now[0] = 61.0              # the window has passed
    assert limiter.allow("a")


# ----------------------------------------------------------------------------- CORS and headers
def test_cors_is_not_a_wildcard(client):
    assert "*" not in security.cors_origins()
    allowed = client.options(
        "/api/analytics",
        headers={"Origin": "http://localhost:5173", "Access-Control-Request-Method": "GET"},
    )
    assert allowed.headers.get("access-control-allow-origin") == "http://localhost:5173"
    blocked = client.options(
        "/api/analytics",
        headers={"Origin": "https://evil.example", "Access-Control-Request-Method": "GET"},
    )
    assert "access-control-allow-origin" not in blocked.headers
    assert "access-control-allow-credentials" not in allowed.headers


def test_cors_env_override_never_allows_a_wildcard(monkeypatch):
    monkeypatch.setenv("INGAME_CORS_ORIGINS", "*, https://studio.example")
    assert security.cors_origins() == ["https://studio.example"]


def test_security_headers_are_set(client):
    response = client.get("/health")
    assert response.headers["x-content-type-options"] == "nosniff"
    assert response.headers["x-frame-options"] == "SAMEORIGIN"
    assert "referrer-policy" in response.headers


# ----------------------------------------------------------------------------- websocket
def test_websocket_rejects_oversized_messages(client):
    with client.websocket_connect("/ws/match-stream") as ws:
        ws.send_text("x" * (security.MAX_WEBSOCKET_MESSAGE_BYTES + 10))
        with pytest.raises(Exception):
            for _ in range(5):
                ws.receive_text()


def test_websocket_refuses_clients_when_full(client, monkeypatch):
    monkeypatch.setattr(security, "MAX_WEBSOCKET_CLIENTS", 0)
    with pytest.raises(Exception):
        with client.websocket_connect("/ws/match-stream"):
            pass


# ----------------------------------------------------------------------------- public status leaks
def test_status_endpoints_do_not_expose_secrets(client):
    body = json.dumps(client.get("/api/llm/status").json()) + json.dumps(client.get("/api/status").json())
    assert "api_key" not in body.lower() and "last_error" not in body
    for name in ("AZURE_OPENAI_API_KEY", "COSMOS_KEY"):
        value = os.environ.get(name)
        if value:
            assert value not in body


# ----------------------------------------------------------------------------- repository hygiene
SKIP_DIRS = {"node_modules", ".venv", ".git", "dist", "__pycache__", ".pytest_cache", ".agents", "internal_notes"}
SKIP_FILES = {"narrative_cache.json", "match_clips.json", "synthetic_events.json", "package-lock.json",
              "synthetic_match_snapshot.json"}
SECRET_PATTERNS = [
    re.compile(r"AccountKey=[A-Za-z0-9+/=]{20,}"),
    re.compile(r"(?i)(api[_-]?key|secret|password)\s*[:=]\s*[\"'](?!sk-fake|test|not-a-real|<)[A-Za-z0-9+/=_\-]{24,}[\"']"),
    re.compile(r"-----BEGIN (RSA |EC )?PRIVATE KEY-----"),
]


def test_no_secret_like_strings_are_committed():
    offenders = []
    for dirpath, dirnames, filenames in os.walk(ROOT):
        dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS]
        for name in filenames:
            if name in SKIP_FILES or name == ".env" or name.endswith((".png", ".jpg", ".ico", ".map")):
                continue
            path = os.path.join(dirpath, name)
            try:
                text = open(path, encoding="utf-8").read()
            except (UnicodeDecodeError, OSError):
                continue
            for pattern in SECRET_PATTERNS:
                if pattern.search(text):
                    offenders.append(os.path.relpath(path, ROOT))
    assert not offenders, f"possible secrets in: {offenders}"


def test_gitignore_keeps_secrets_and_internal_notes_out():
    with open(os.path.join(ROOT, ".gitignore"), encoding="utf-8") as handle:
        rules = handle.read().splitlines()
    for required in (".env", ".env.*", "internal_notes/", ".agents/", ".claude/", "node_modules/"):
        assert required in rules, f".gitignore must ignore {required}"
    assert "!.env.example" in rules


def test_workflow_does_not_paste_secrets_into_shell_commands():
    with open(os.path.join(ROOT, ".github", "workflows", "deploy-azure.yml"), encoding="utf-8") as handle:
        text = handle.read()
    for line in text.splitlines():
        if "secrets." in line:
            assert line.strip().startswith(("-", "env", "client-id", "tenant-id", "subscription-id")) or ":" in line.split("secrets.")[0], line
    # Secrets are referenced only on 'KEY: ${{ secrets.X }}' style lines, not inside run scripts.
    run_blocks = re.findall(r"run: \|\n((?:\s{10,}.*\n)+)", text)
    assert not any("secrets." in block for block in run_blocks)
    assert text.count("id-token: write") == 1, "only the deploy job may request the OIDC token"
