"""InGame Studio - small security helpers for the API.

* ``RateLimiter``: an in-memory sliding-window limiter. The Match Analyst spends model tokens
  for every question, so it is limited per client and, as a backstop, for everyone together.
* ``require_ingest_key``: when ``INGAME_API_KEY`` is set, the endpoints that write events into
  the shared match (``/api/ingest`` and ``/api/events``) need the matching ``X-API-Key``
  header. With no key set (local development, the tests) they stay open.
* ``cors_origins``: the browser origins allowed to call the API from another site. The packaged
  app is served from the same origin and needs none.
"""

import hmac
import os
import threading
import time
from collections import deque
from typing import Deque, Dict, List, Optional

from fastapi import HTTPException, Request

DEFAULT_DEV_ORIGINS = ["http://localhost:5173", "http://127.0.0.1:5173"]

# Limits that protect the shared match and the model quota.
MAX_EVENTS_PER_BATCH = 500
MAX_WEBSOCKET_CLIENTS = 200
MAX_WEBSOCKET_MESSAGE_BYTES = 64 * 1024


class RateLimiter:
    """Allows ``limit`` calls per ``window`` seconds for each key."""

    def __init__(self, limit: int, window: float = 60.0, clock=time.monotonic):
        self.limit = limit
        self.window = window
        self._clock = clock
        self._hits: Dict[str, Deque[float]] = {}
        self._lock = threading.Lock()

    def allow(self, key: str) -> bool:
        now = self._clock()
        with self._lock:
            hits = self._hits.setdefault(key, deque())
            while hits and now - hits[0] > self.window:
                hits.popleft()
            if len(hits) >= self.limit:
                return False
            hits.append(now)
            if len(self._hits) > 5000:  # forget idle clients so the table cannot grow without bound
                for stale in [k for k, v in self._hits.items() if not v or now - v[-1] > self.window]:
                    self._hits.pop(stale, None)
            return True


def client_id(request: Request) -> str:
    """The caller's address. Behind a proxy the first X-Forwarded-For hop is used."""
    forwarded = request.headers.get("x-forwarded-for", "")
    if forwarded:
        return forwarded.split(",")[0].strip()[:64]
    return request.client.host if request.client else "unknown"


def require_ingest_key(request: Request) -> None:
    """Rejects the call unless it carries the configured key (when one is configured)."""
    expected = os.environ.get("INGAME_API_KEY", "")
    if not expected:
        return
    supplied = request.headers.get("x-api-key", "")
    if not hmac.compare_digest(supplied.encode("utf-8"), expected.encode("utf-8")):
        raise HTTPException(status_code=401, detail="A valid X-API-Key header is required.")


def cors_origins() -> List[str]:
    """Allowed cross-origin callers: INGAME_CORS_ORIGINS (comma separated), else the local dev server only."""
    configured = os.environ.get("INGAME_CORS_ORIGINS", "").strip()
    if configured:
        return [origin.strip() for origin in configured.split(",") if origin.strip() and origin.strip() != "*"]
    return list(DEFAULT_DEV_ORIGINS)


def security_headers() -> Dict[str, str]:
    return {
        "X-Content-Type-Options": "nosniff",
        "Referrer-Policy": "strict-origin-when-cross-origin",
        "X-Frame-Options": "SAMEORIGIN",
        "Permissions-Policy": "camera=(), microphone=(), geolocation=()",
    }
