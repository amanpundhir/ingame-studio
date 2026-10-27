"""InGame Studio - one match per viewer.

Every browser (tab) gets its own ``MatchSession``: its own simulation, clock, play state, analytics
and live insight, so one viewer pressing Play or Pause never affects another. The browser makes up
a random session id, keeps it in ``sessionStorage`` and sends it on every request (``X-Session-Id``
header, ``?session=`` on the WebSocket).

* Requests that carry no id use the *default* session: the one shared match that API clients, the
  tests and external event feeds (``/api/ingest``) have always used.
* Read-only things stay shared by every session: the model's cached narratives, the replay clips and
  the match data files. All sessions play the same seeded match, so those are valid for everyone.
* Sessions are capped (``MAX_SESSIONS``) because each running session runs its own 25 Hz simulation,
  and removed after ``IDLE_SECONDS`` with no viewer connected.
"""

import asyncio
import json
import logging
import re
import threading
import time
from typing import Any, Callable, Dict, List, Optional, Set

from fastapi import WebSocket

from backend.math_engine import MatchAnalyticsTracker
from generator.telemetry_streamer import TelemetryStreamer

logger = logging.getLogger("ingame.sessions")

SESSION_ID_PATTERN = re.compile(r"^[A-Za-z0-9_-]{8,64}$")
FULL_TIME_SECONDS = 5670  # 94:30 - the match ends here; nothing is generated after it
MAX_SESSIONS = 40
IDLE_SECONDS = 15 * 60


class SessionLimitReached(Exception):
    """Too many viewers are active at once."""


class ConnectionManager:
    """The WebSocket clients of one session, with slow-client protection."""

    def __init__(self) -> None:
        self.active_connections: Set[WebSocket] = set()

    async def connect(self, websocket: WebSocket) -> None:
        await websocket.accept()
        self.active_connections.add(websocket)

    def disconnect(self, websocket: WebSocket) -> None:
        self.active_connections.discard(websocket)

    async def broadcast(self, payload: Dict[str, Any]) -> None:
        """Sends a JSON payload to every client of this session."""
        if not self.active_connections:
            return
        dead = set()
        message = json.dumps(payload)
        for connection in list(self.active_connections):
            try:
                await connection.send_text(message)
            except Exception as exc:  # noqa: BLE001 - one slow or closed client must not stop the others
                logger.warning("Error sending to a client, queuing removal: %s", exc)
                dead.add(connection)
        for connection in dead:
            self.disconnect(connection)


class MatchSession:
    """Everything that belongs to one viewer's match."""

    def __init__(self, session_id: str, streamer: TelemetryStreamer, tracker: MatchAnalyticsTracker, is_default: bool = False):
        self.id = session_id
        self.is_default = is_default
        self.streamer = streamer
        self.tracker = tracker
        self.manager = ConnectionManager()
        self.latest_insight: Optional[Dict[str, Any]] = None
        self.latest_frame: Optional[Dict[str, Any]] = None
        self.latest_recap: Optional[Dict[str, Any]] = None
        self.last_triggered_event_id: Optional[str] = None
        # True when the match was paused only because its viewer left; a reload then resumes it.
        self.paused_by_disconnect = False
        self.task: Optional["asyncio.Task[Any]"] = None
        self.analyst: Any = None  # the Match Analyst agent bound to this match, created on first question
        self.moments_cache: Dict[str, Any] = {"key": None, "moments": []}
        self.highlights_cache: Dict[str, Any] = {"key": None, "highlights": []}
        self.derived_lock = threading.Lock()
        self.analyst_lock = threading.Lock()
        self.created = time.monotonic()
        self.last_seen = time.monotonic()

    def touch(self) -> None:
        self.last_seen = time.monotonic()

    # ------------------------------------------------------------------ match clock
    @property
    def full_time_frame(self) -> int:
        return int(FULL_TIME_SECONDS * self.streamer.frame_rate)

    def is_over(self) -> bool:
        return self.streamer.generator.frame_index >= self.full_time_frame

    def reset(self) -> None:
        """Back to kick-off: simulation, analytics and every cached live value."""
        self.streamer.reset()
        self.tracker.reset()
        self.last_triggered_event_id = None
        self.latest_frame = None
        self.latest_insight = None
        self.latest_recap = None
        self.moments_cache = {"key": None, "moments": []}
        self.highlights_cache = {"key": None, "highlights": []}

    def is_idle(self, now: float, idle_seconds: float) -> bool:
        return not self.manager.active_connections and now - self.last_seen > idle_seconds


class SessionRegistry:
    """All sessions of the server: the shared default match plus one per viewer."""

    def __init__(
        self,
        factory: Callable[[str], MatchSession],
        max_sessions: int = MAX_SESSIONS,
        idle_seconds: float = IDLE_SECONDS,
    ) -> None:
        self._factory = factory
        self.max_sessions = max_sessions
        self.idle_seconds = idle_seconds
        self._lock = threading.Lock()
        self._sessions: Dict[str, MatchSession] = {}
        self.default: MatchSession = factory("default")
        self.default.is_default = True

    @staticmethod
    def is_valid_id(session_id: str) -> bool:
        return bool(SESSION_ID_PATTERN.match(session_id or ""))

    def get_or_create(self, session_id: str) -> MatchSession:
        with self._lock:
            session = self._sessions.get(session_id)
            if session is not None:
                return session
            if len(self._sessions) >= self.max_sessions:
                self._evict_idle_locked()
            if len(self._sessions) >= self.max_sessions:
                raise SessionLimitReached()
            session = self._factory(session_id)
            self._sessions[session_id] = session
            logger.info("Created match session %s (%d active)", session_id[:8], len(self._sessions))
            return session

    def _evict_idle_locked(self) -> List[MatchSession]:
        now = time.monotonic()
        removed = [s for s in self._sessions.values() if s.is_idle(now, self.idle_seconds)]
        # When the table is full, a session without a viewer is also fair game after a short grace period.
        if not removed and len(self._sessions) >= self.max_sessions:
            removed = [s for s in self._sessions.values() if s.is_idle(now, 60.0)][:1]
        for session in removed:
            self._sessions.pop(session.id, None)
            if session.task is not None:
                session.task.cancel()
        return removed

    def cleanup_idle(self) -> int:
        with self._lock:
            return len(self._evict_idle_locked())

    def count(self) -> int:
        with self._lock:
            return len(self._sessions)

    def total_connections(self) -> int:
        with self._lock:
            sessions = list(self._sessions.values())
        return len(self.default.manager.active_connections) + sum(len(s.manager.active_connections) for s in sessions)

    def all_sessions(self) -> List[MatchSession]:
        with self._lock:
            return [self.default] + list(self._sessions.values())
