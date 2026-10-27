"""InGame Studio - FastAPI WebSocket & REST Streaming Server.

Broadcasting 25Hz tracking telemetry, synchronized event triggers,
real-time tactical metrics, and verified 4-agent match insights.

Every viewer (browser tab) has its own match: see ``backend/sessions.py``. A request that carries no
session id uses the default shared match, which is what API clients and external feeds use.
"""

import asyncio
import threading
import json
import logging
import os
import time
from contextlib import asynccontextmanager
from typing import Any, Dict, List, Optional, Union
from jsonschema import Draft7Validator

from fastapi import Depends, FastAPI, Request, WebSocket, WebSocketDisconnect, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from backend.clips import ClipStore
from backend import security
from pydantic import BaseModel, Field

from backend.config import settings
from backend.agents.orchestrator import MatchIntelligenceOrchestrator
from backend.agents.models import VerifiedInsight
from backend.match_recap import generate_match_recap
from backend import moments as moments_lib
from backend import story as story_lib
from backend.agents.tactician_agent import TacticianAgent
from backend.math_engine import MatchAnalyticsTracker
from backend.sessions import (
    FULL_TIME_SECONDS,
    MatchSession,
    SessionLimitReached,
    SessionRegistry,
)
from generator.telemetry_streamer import TelemetryStreamer

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("ingame.server")

# Load MatchEvent schema validator
SCHEMA_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "schema.json")
try:
    with open(SCHEMA_PATH, "r", encoding="utf-8") as f:
        _schema_data = json.load(f)
    match_event_validator: Optional[Draft7Validator] = Draft7Validator(
        schema=_schema_data["definitions"]["MatchEvent"]
    )
except Exception as e:
    logger.warning(f"Could not load schema.json for MatchEvent validation: {e}")
    match_event_validator = None


class ControlCommand(BaseModel):
    """Studio control command payload."""
    action: str  # "play", "pause", "reset", "step", "trigger", "speed", "jump", "simulate_full"
    multiplier: Optional[float] = None
    event_id: Optional[str] = None


class BatchEventsPayload(BaseModel):
    """Studio batch match event telemetry ingestion payload."""
    events: List[Dict[str, Any]]


# Server-wide singletons. The match itself lives in a per-viewer MatchSession.
registry: Optional[SessionRegistry] = None
orchestrator: Optional[MatchIntelligenceOrchestrator] = None
janitor_task: Optional[asyncio.Task] = None
# The default shared match (used when a request carries no session id). Kept as module names for
# API clients and tests that talk to "the" match.
streamer: Optional[TelemetryStreamer] = None
analytics_tracker: Optional[MatchAnalyticsTracker] = None


def _make_session(session_id: str) -> MatchSession:
    """A fresh match for one viewer: its own seeded simulation and analytics."""
    events_file = settings.synthetic_events_file
    if events_file and not os.path.isabs(events_file):
        events_file = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", events_file))
    session_streamer = TelemetryStreamer(
        match_id="IGS_2026_NBL_HSC",
        frame_rate=settings.fps,
        real_time=True,
        events_file=events_file,
        seed=settings.simulation_seed,
    )
    return MatchSession(session_id, session_streamer, MatchAnalyticsTracker())


def _default_session() -> Optional[MatchSession]:
    return registry.default if registry else None


def _match_is_over(session: Optional[MatchSession] = None) -> bool:
    session = session or _default_session()
    return bool(session) and session.is_over()


def _reset_match_state(session: Optional[MatchSession] = None) -> None:
    """Back to kick-off for one viewer's match (the default match when none is given)."""
    (session or _default_session()).reset()


async def _restart_if_match_over(session: MatchSession) -> bool:
    """Pressing Play after full time starts a new run of the match from kick-off."""
    if not session.is_over():
        return False
    session.reset()
    await session.manager.broadcast({"type": "control", "timestamp": "00:00", "data": {"action": "reset"}})
    return True


def _ensure_loop(session: MatchSession) -> None:
    """Starts the session's 25 Hz streaming loop if it is not running."""
    if session.task is None or session.task.done():
        session.task = asyncio.get_running_loop().create_task(session_loop(session))


def _lookup_session(session_id: Optional[str]) -> MatchSession:
    """The session for an id (created on first use); the default match when there is no id."""
    if registry is None:
        raise RuntimeError("server is starting")
    if not session_id:
        session = registry.default
    else:
        if not registry.is_valid_id(session_id):
            raise ValueError("Invalid session id")
        session = registry.get_or_create(session_id)
    session.touch()
    _ensure_loop(session)
    return session


async def get_session(request: Request) -> MatchSession:
    """Request dependency: the caller's own match, identified by the X-Session-Id header."""
    try:
        return _lookup_session(request.headers.get("x-session-id"))
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid X-Session-Id header")
    except SessionLimitReached:
        raise HTTPException(status_code=503, detail="The studio is busy with too many viewers. Please try again in a few minutes.")
    except RuntimeError:
        raise HTTPException(status_code=503, detail="The studio is starting. Please try again in a moment.")


async def session_loop(session: MatchSession):
    """Background 25Hz streaming worker for one viewer's match, with adaptive frame stepping."""
    logger.info("Starting 25Hz broadcast loop for session %s", session.id[:8])
    streamer = session.streamer

    try:
        while True:
            if streamer.is_paused:
                await asyncio.sleep(0.04)
                continue

            t_start = time.perf_counter()
            # Never step past full time, whatever the playback speed.
            steps = min(streamer.get_steps_for_tick(), max(0, session.full_time_frame - streamer.generator.frame_index))
            if steps <= 0:
                streamer.pause()
                continue
            frame = None

            # Advance simulation by K frames per broadcast tick and ingest into analytics
            for _ in range(steps):
                frame = streamer.generator.step()
                session.tracker.add_telemetry_frame(frame)
                for alert in session.tracker.pop_pending_alerts():
                    await session.manager.broadcast({
                        "type": "metric_alert",
                        "timestamp": frame.get("timestamp") if frame else "00:00",
                        "data": alert,
                    })

                # Detect key event triggers in intermediate frames
                active_evt_id = frame.get("active_event_id")
                if active_evt_id and active_evt_id != session.last_triggered_event_id:
                    session.last_triggered_event_id = active_evt_id
                    # Events are created by the simulation as actions happen,
                    # so resolve against its current event list rather than a
                    # startup-time snapshot.
                    event_data = next(
                        (ev for ev in streamer.generator.get_events() if ev.get("event_id") == active_evt_id),
                        None,
                    )
                    if event_data:
                        milestone = session.tracker.record_event(event_data)
                        if milestone:
                            event_data = dict(event_data)
                            event_data["milestone"] = milestone
                        # Run 4-agent causal reasoning and verification workflow
                        try:
                            insight = orchestrator.process_event(
                                event=event_data,
                                telemetry_frame=frame,
                            )
                            insight_dict = insight.model_dump()
                            session.latest_insight = insight_dict

                            # Broadcast event and insight messages
                            await session.manager.broadcast({
                                "type": "event",
                                "timestamp": frame.get("timestamp"),
                                "data": event_data,
                            })
                            await session.manager.broadcast({
                                "type": "insight",
                                "timestamp": frame.get("timestamp"),
                                "data": insight_dict,
                            })
                        except Exception as err:
                            logger.error(f"Error processing event through multi-agent workflow: {err}")

            session.latest_frame = frame

            # Broadcast 25Hz telemetry frame
            if frame is not None:
                await session.manager.broadcast({
                    "type": "telemetry",
                    "timestamp": frame.get("timestamp"),
                    "data": frame,
                })

            if session.is_over():
                # Full time: stop here. The final frame stays on screen until Play restarts the match.
                streamer.pause()
                if frame is not None:
                    frame["ball"] = dict(frame.get("ball") or {}, status="stopped")
                await session.manager.broadcast({
                    "type": "control",
                    "timestamp": frame.get("timestamp") if frame else "00:00",
                    "data": {"action": "full_time", "clock": frame.get("clock") if frame else "94:30"},
                })
                continue

            # Precision pacing (40ms interval for 25Hz)
            elapsed = time.perf_counter() - t_start
            sleep_time = max(0.001, streamer.frame_interval - elapsed)
            await asyncio.sleep(sleep_time)

    except asyncio.CancelledError:
        logger.info("Broadcast loop for session %s cancelled.", session.id[:8])
    except Exception as e:
        logger.error(f"Fatal error in broadcast loop: {e}", exc_info=True)


async def _janitor():
    """Removes the matches of viewers who left."""
    try:
        while True:
            await asyncio.sleep(60)
            removed = registry.cleanup_idle() if registry else 0
            if removed:
                logger.info("Removed %d idle match session(s)", removed)
    except asyncio.CancelledError:
        pass


@asynccontextmanager
async def lifespan(app: FastAPI):
    """FastAPI startup and shutdown lifecycle manager."""
    global registry, streamer, orchestrator, analytics_tracker, janitor_task

    logger.info("Initializing InGame Studio services...")
    orchestrator = MatchIntelligenceOrchestrator()
    registry = SessionRegistry(_make_session)
    streamer = registry.default.streamer
    analytics_tracker = registry.default.tracker

    # Match events are emitted as the deterministic simulation runs. There is
    # no pre-authored first event to process at startup.
    _ensure_loop(registry.default)
    janitor_task = asyncio.create_task(_janitor())
    yield

    # Teardown
    for session in registry.all_sessions():
        if session.task:
            session.task.cancel()
    tasks = [s.task for s in registry.all_sessions() if s.task] + ([janitor_task] if janitor_task else [])
    if janitor_task:
        janitor_task.cancel()
    for task in tasks:
        try:
            await task
        except asyncio.CancelledError:
            pass
    if orchestrator:
        orchestrator.narrative_service.cache.flush()
    logger.info("InGame Studio services stopped.")


app = FastAPI(
    title=settings.app_name,
    version=settings.version,
    lifespan=lifespan,
)

# CORS configuration
# Only the local dev server (or INGAME_CORS_ORIGINS) may call the API from another origin; the
# packaged app is served from the same origin. No cookies are used, so credentials stay off.
app.add_middleware(
    CORSMiddleware,
    allow_origins=security.cors_origins(),
    allow_credentials=False,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["Content-Type", "X-API-Key", "X-Session-Id"],
)


@app.middleware("http")
async def add_security_headers(request: Request, call_next):
    response = await call_next(request)
    for name, value in security.security_headers().items():
        response.headers.setdefault(name, value)
    return response


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {
        "status": "ok",
        "app": settings.app_name,
        "version": settings.version,
        "fps": settings.fps,
    }


@app.get("/api/llm/status")
async def get_llm_status():
    """Reports whether Azure Foundry is connected and how the narrative cache is performing."""
    if not orchestrator:
        return {"mode": "starting"}
    status = dict(orchestrator.narrative_service.status())
    status["orchestration"] = "microsoft-agent-framework" if orchestrator.use_agent_framework else "plain"
    return status


@app.get("/api/status")
async def get_status(session: MatchSession = Depends(get_session)):
    """Returns real-time match studio status for the caller's match."""
    generator = session.streamer.generator
    return {
        "match_id": session.streamer.match_id,
        "frame_index": generator.frame_index,
        "clock": generator.get_clock_string(),
        "is_paused": session.streamer.is_paused,
        "speed_multiplier": session.streamer.speed_multiplier,
        "connected_clients": len(session.manager.active_connections),
        "active_matches": (registry.count() + 1) if registry else 1,
        "has_insight": session.latest_insight is not None,
        "latest_event_id": session.last_triggered_event_id,
    }


def _get_current_frame(session: MatchSession) -> Dict[str, Any]:
    """Retrieves or builds the current 25Hz telemetry frame."""
    if session.latest_frame is not None:
        return session.latest_frame
    streamer = session.streamer
    ball_state, player_states = streamer.generator.export_state()
    return {
        "frame_id": streamer.generator.frame_index,
        "match_id": streamer.match_id,
        "data_provenance": streamer.generator.data_provenance,
        "synthetic_data_notice": "Synthetic demonstration data. This fictional scenario does not represent a real match or real tracking feed.",
        "timestamp": streamer.generator.get_timestamp_string(),
        "period": streamer.generator.period,
        "clock": streamer.generator.get_clock_string(),
        "pitch_dimensions": {"length": 105.0, "width": 68.0},
        "ball": ball_state,
        "players": player_states,
        "active_event_id": streamer.generator.active_event_id,
    }


@app.get("/api/state")
async def get_state(session: MatchSession = Depends(get_session)):
    """Returns a full state snapshot for the live match dashboard."""
    curr_frame = _get_current_frame(session)
    streamer = session.streamer
    clock = curr_frame.get("clock") or streamer.generator.get_clock_string()
    period = curr_frame.get("period") or streamer.generator.period
    stats = session.tracker.get_match_stats()
    score = stats.get("score", {"home": 0, "away": 0})
    return {
        "match_id": streamer.match_id,
        "clock": clock,
        "period": period,
        "is_paused": streamer.is_paused,
        "speed_multiplier": streamer.speed_multiplier,
        "score": score,
        "frame": curr_frame,
        "match_stats": stats,
        "latest_insight": session.latest_insight,
    }


@app.post("/api/control")
async def post_control(cmd: ControlCommand, session: MatchSession = Depends(get_session)):
    """Controls the caller's own playback (play, pause, reset, trigger, speed, jump, simulate_full)."""
    streamer = session.streamer
    action = cmd.action.lower()

    if action in ("play", "resume"):
        restarted = await _restart_if_match_over(session)
        streamer.resume()
        return {"status": "resumed", "is_paused": False, "restarted": restarted}
    elif action == "pause":
        streamer.pause()
        return {"status": "paused", "is_paused": True}
    elif action == "reset":
        session.reset()
        return {"status": "reset", "frame_index": 0}
    elif action == "speed":
        if cmd.multiplier is None or cmd.multiplier <= 0:
            raise HTTPException(status_code=400, detail="Invalid multiplier, must be positive float")
        new_speed = streamer.set_speed(cmd.multiplier)
        clock = streamer.generator.get_clock_string()
        await session.manager.broadcast({
            "type": "control",
            "timestamp": session.latest_frame.get("timestamp") if session.latest_frame else "00:00",
            "data": {"action": "speed", "multiplier": new_speed, "clock": clock},
        })
        return {"status": "ok", "action": "speed", "multiplier": new_speed}
    elif action == "jump":
        if not cmd.event_id:
            raise HTTPException(status_code=400, detail="event_id required for jump action")
        known_events = streamer.generator.get_events()
        events = {ev.get("event_id"): ev for ev in known_events}
        event_data = events.get(cmd.event_id)
        if not event_data:
            raise HTTPException(status_code=404, detail=f"Event {cmd.event_id} not found")

        frame = streamer.jump_to_event(event_data, known_events)
        session.latest_frame = frame
        session.last_triggered_event_id = cmd.event_id
        session.tracker.seek_to_event(event_data)
        session.tracker.record_event(event_data)

        insight = await asyncio.to_thread(
            orchestrator.process_event, event_data, telemetry_frame=frame, allow_live=True
        )
        session.latest_insight = insight.model_dump()

        await session.manager.broadcast({
            "type": "jump",
            "timestamp": frame.get("timestamp"),
            "data": {
                "event_id": cmd.event_id,
                "clock": frame.get("clock"),
                "frame_index": frame.get("frame_id"),
            },
        })
        await session.manager.broadcast({
            "type": "event",
            "timestamp": frame.get("timestamp"),
            "data": event_data,
        })
        await session.manager.broadcast({
            "type": "insight",
            "timestamp": frame.get("timestamp"),
            "data": session.latest_insight,
        })
        await session.manager.broadcast({
            "type": "telemetry",
            "timestamp": frame.get("timestamp"),
            "data": frame,
        })
        return {
            "status": "jumped",
            "event_id": cmd.event_id,
            "clock": frame.get("clock"),
            "frame_index": frame.get("frame_id"),
            "insight": session.latest_insight,
        }
    elif action == "simulate_full":
        streamer.pause()
        snapshot_path = os.path.join(os.path.dirname(__file__), "..", "data", "synthetic_match_snapshot.json")
        events_path = os.path.join(os.path.dirname(__file__), "..", "data", "synthetic_events.json")
        cached_snapshot = None
        cached_events = None
        # This cache is an export of the exact seeded simulator, not an authored
        # event timeline. Reuse it for the one-click full-match action so the
        # default demo can complete immediately; alternate seeds and explicit
        # fixture replay still execute the live frame simulation.
        if settings.synthetic_events_file is None and os.path.isfile(snapshot_path) and os.path.isfile(events_path):
            try:
                with open(snapshot_path, "r", encoding="utf-8") as snapshot_file:
                    candidate = json.load(snapshot_file)
                if int(candidate.get("simulation_seed", -1)) == settings.simulation_seed:
                    with open(events_path, "r", encoding="utf-8") as events_file:
                        cached_events = json.load(events_file)
                    cached_snapshot = candidate
            except (OSError, ValueError, json.JSONDecodeError):
                cached_snapshot = None
                cached_events = None

        session.tracker.reset()
        if cached_snapshot and cached_events is not None:
            frame = streamer.simulate_full_match(
                snapshot=cached_snapshot.get("final_frame"),
                events=cached_events,
            )
            session.tracker.load_snapshot(
                events=cached_events,
                match_stats=cached_snapshot.get("match_stats", {}),
                player_stats=cached_snapshot.get("player_stats", []),
            )
        else:
            frame = streamer.simulate_full_match(on_frame=session.tracker.add_telemetry_frame)
            for event in streamer.generator.get_events():
                session.tracker.record_event(event)

        session.latest_frame = frame
        all_events = streamer.generator.get_events()

        # Refresh the commentary so it describes the final whistle, not the first minutes.
        closing_event = next(
            (ev for ev in reversed(all_events) if str(ev.get("event_type", "")).lower() == "goal"),
            all_events[-1] if all_events else None,
        )
        if closing_event and orchestrator:
            try:
                closing_insight = await asyncio.to_thread(
                    orchestrator.process_event, closing_event, telemetry_frame=frame
                )
                session.latest_insight = closing_insight.model_dump()
                session.last_triggered_event_id = closing_event.get("event_id")
                await session.manager.broadcast({
                    "type": "insight",
                    "timestamp": frame.get("timestamp"),
                    "data": session.latest_insight,
                })
            except Exception as err:
                logger.warning(f"Could not build closing insight: {err}")

        recap = generate_match_recap(session.tracker, events=all_events)
        recap["status"] = "FT"
        recap["clock"] = frame.get("clock", "94:30")
        session.latest_recap = recap

        match_stats = session.tracker.get_match_stats()
        player_stats = session.tracker.get_all_player_stats()

        await session.manager.broadcast({
            "type": "simulate_full",
            "timestamp": frame.get("timestamp"),
            "data": {
                "clock": frame.get("clock", "94:30"),
                "frame_index": frame.get("frame_id"),
                "score": match_stats.get("score", {"home": 0, "away": 0}),
            },
        })
        await session.manager.broadcast({
            "type": "recap",
            "timestamp": frame.get("clock", "94:30"),
            "data": recap,
        })
        await session.manager.broadcast({
            "type": "telemetry",
            "timestamp": frame.get("timestamp"),
            "data": frame,
        })
        return {
            "status": "simulated_full",
            "clock": frame.get("clock", "94:30"),
            "frame_index": frame.get("frame_id"),
            "score": match_stats.get("score", {"home": 0, "away": 0}),
            "match_stats": match_stats,
            "player_stats": player_stats,
            "recap": recap,
        }
    elif action == "trigger" and cmd.event_id:
        events = {ev.get("event_id"): ev for ev in streamer.generator.get_events()}
        event_data = events.get(cmd.event_id)
        if not event_data:
            raise HTTPException(status_code=404, detail=f"Event {cmd.event_id} not found")

        streamer.generator._apply_event_trigger(event_data)
        milestone = session.tracker.record_event(event_data)
        if milestone:
            event_data = dict(event_data)
            event_data["milestone"] = milestone
        insight = await asyncio.to_thread(
            orchestrator.process_event, event_data, telemetry_frame=session.latest_frame, allow_live=True
        )
        session.latest_insight = insight.model_dump()
        session.last_triggered_event_id = cmd.event_id

        stamp = session.latest_frame.get("timestamp") if session.latest_frame else "00:00"
        await session.manager.broadcast({"type": "event", "timestamp": stamp, "data": event_data})
        await session.manager.broadcast({"type": "insight", "timestamp": stamp, "data": session.latest_insight})
        return {"status": "triggered", "event_id": cmd.event_id, "insight": session.latest_insight}
    else:
        raise HTTPException(status_code=400, detail=f"Unsupported action: {cmd.action}")


@app.post("/api/simulate_full")
async def post_simulate_full(session: MatchSession = Depends(get_session)):
    """Direct alias to simulate_full control action."""
    return await post_control(ControlCommand(action="simulate_full"), session)


@app.get("/api/alerts")
async def get_alerts(session: MatchSession = Depends(get_session)):
    """Returns all detected physical threshold and tactical metric alerts."""
    return session.tracker.get_all_alerts()


@app.get("/api/insights/latest")
async def get_latest_insight(session: MatchSession = Depends(get_session)):
    """Returns the most recent verified insight."""
    if not session.latest_insight:
        return JSONResponse(status_code=204, content=None)
    return session.latest_insight


def _validate_match_event(event_dict: Dict[str, Any], prefix: str = "") -> None:
    """Validates an event payload against data/schema.json definitions.MatchEvent."""
    if not isinstance(event_dict, dict):
        raise HTTPException(status_code=422, detail=f"{prefix}Event payload must be a JSON object")
    if match_event_validator:
        errors = list(match_event_validator.iter_errors(event_dict))
        if errors:
            first_err = errors[0]
            field = ".".join(str(p) for p in first_err.path) if first_err.path else "root"
            err_msg = f"{prefix} field '{field}': {first_err.message}" if prefix else f"Field '{field}': {first_err.message}"
            raise HTTPException(
                status_code=422,
                detail=f"Schema validation error: {err_msg}",
            )


@app.get("/api/recap")
async def get_recap(session: MatchSession = Depends(get_session)):
    """Returns the current match report; it becomes a full-time recap at 94:30."""
    generator = session.streamer.generator
    all_events = generator.get_events()
    current_clock = session.latest_frame.get("clock") if session.latest_frame else generator.get_clock_string()
    recap = generate_match_recap(session.tracker, events=all_events, clock=current_clock)
    recap["status"] = "FT" if session.is_over() else "LIVE" if generator.frame_index else "NOT_STARTED"
    recap["highlights"] = await asyncio.to_thread(_get_highlights, session)
    session.latest_recap = recap
    return recap


async def _publish(session: MatchSession, event: Dict[str, Any], insight: Optional[Dict[str, Any]]) -> None:
    """Sends an ingested event (and its insight) to the viewers of the session."""
    stamp = event.get("clock") or (session.latest_frame.get("timestamp") if session.latest_frame else "00:00")
    await session.manager.broadcast({"type": "event", "timestamp": stamp, "data": event})
    if insight:
        await session.manager.broadcast({"type": "insight", "timestamp": stamp, "data": insight})


@app.post("/api/ingest", dependencies=[Depends(security.require_ingest_key)])
async def post_ingest(event: Dict[str, Any], session: MatchSession = Depends(get_session)):
    """Accepts and ingests a single external MatchEvent conforming to data/schema.json.

    It goes into the default shared match unless an X-Session-Id header names another one.
    """
    _validate_match_event(event)

    milestone = session.tracker.record_event(event)
    if milestone:
        event = dict(event)
        event["milestone"] = milestone

    insight_dict: Dict[str, Any] = {}
    if orchestrator:
        insight = await asyncio.to_thread(
            orchestrator.process_event, event, telemetry_frame=session.latest_frame, allow_live=True
        )
        insight_dict = insight.model_dump()
        session.latest_insight = insight_dict
        session.last_triggered_event_id = event.get("event_id")

    await _publish(session, event, insight_dict)
    return {
        "status": "ingested",
        "event_id": event.get("event_id"),
        "insight": insight_dict,
    }


@app.post("/api/events", dependencies=[Depends(security.require_ingest_key)])
async def post_events(
    payload: Union[BatchEventsPayload, Dict[str, Any], List[Dict[str, Any]]],
    session: MatchSession = Depends(get_session),
):
    """Accepts a batch of MatchEvents conforming to data/schema.json and ingests them sequentially."""
    if isinstance(payload, BatchEventsPayload):
        events_list = payload.events
    elif isinstance(payload, dict):
        events_list = payload.get("events")
        if events_list is None:
            raise HTTPException(status_code=422, detail="Missing 'events' list in batch payload")
    elif isinstance(payload, list):
        events_list = payload
    else:
        raise HTTPException(status_code=422, detail="Payload must be a list of events or an object with 'events' array")
    if len(events_list) > security.MAX_EVENTS_PER_BATCH:
        raise HTTPException(
            status_code=413, detail=f"At most {security.MAX_EVENTS_PER_BATCH} events per request."
        )

    if not isinstance(events_list, list):
        raise HTTPException(status_code=422, detail="'events' must be an array")

    # Validate each event against schema before ingesting
    for idx, ev in enumerate(events_list):
        _validate_match_event(ev, prefix=f"event[{idx}]")

    # Ingest events sequentially
    for ev in events_list:
        milestone = session.tracker.record_event(ev)
        if milestone:
            ev = dict(ev)
            ev["milestone"] = milestone

        if orchestrator:
            insight = await asyncio.to_thread(
                orchestrator.process_event, ev, telemetry_frame=session.latest_frame, allow_live=True
            )
            session.latest_insight = insight.model_dump()
            session.last_triggered_event_id = ev.get("event_id")

        await _publish(session, ev, session.latest_insight)

    return {
        "status": "batch_ingested",
        "count": len(events_list),
    }


@app.get("/api/events")
async def get_events(session: MatchSession = Depends(get_session)):
    """Returns the match events played so far in the caller's match."""
    return session.streamer.generator.get_events()


@app.get("/api/analytics")
async def get_analytics(session: MatchSession = Depends(get_session)):
    """Returns 22-player and match statistics."""
    return {
        "match_stats": session.tracker.get_match_stats(),
        "player_stats": session.tracker.get_all_player_stats(),
    }


def _load_all_match_events(session: MatchSession) -> List[Dict[str, Any]]:
    """Events played so far in the caller's simulation (never events from the future)."""
    return session.streamer.generator.get_events()


def _compute_player_radar(p_stats: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Computes explainable 6-axis tactical radar metrics bounded in [0.0, 100.0]."""
    passes = p_stats.get("passes", {})
    acc = passes.get("accuracy_pct", 75.0)
    tot_passes = passes.get("total", 0)
    passing_val = round(min(99.0, max(45.0, acc * 0.8 + min(20.0, tot_passes * 0.4))), 1)

    shots = p_stats.get("shots", 0)
    goals = p_stats.get("goals", 0)
    xg = p_stats.get("xg", 0.0)
    shooting_val = round(min(99.0, max(35.0, 45.0 + goals * 22.0 + shots * 5.0 + xg * 15.0)), 1)

    def_acts = (
        p_stats.get("defensive_interventions", 0)
        + p_stats.get("tackles_won", 0)
        + p_stats.get("interceptions", 0)
        + p_stats.get("saves", 0)
    )
    defending_val = round(min(99.0, max(35.0, 45.0 + def_acts * 3.8)), 1)

    spd = p_stats.get("top_speed_kmh", 28.0)
    dist = p_stats.get("distance_km", 5.0)
    physical_val = round(min(99.0, max(40.0, (spd / 36.0) * 55.0 + min(40.0, dist * 3.5))), 1)

    kp = p_stats.get("key_passes", 0)
    xt = p_stats.get("xt_created", 0.0)
    ast = p_stats.get("assists", 0)
    creativity_val = round(min(99.0, max(35.0, 42.0 + kp * 10.0 + xt * 75.0 + ast * 15.0)), 1)

    rating = p_stats.get("rating", 6.0)
    tactical_val = round(min(99.0, max(45.0, rating * 10.2)), 1)

    return [
        {"axis": "Passing", "value": passing_val, "fullMark": 100, "formattedValue": f"{passing_val:.0f}"},
        {"axis": "Shooting", "value": shooting_val, "fullMark": 100, "formattedValue": f"{shooting_val:.0f}"},
        {"axis": "Defending", "value": defending_val, "fullMark": 100, "formattedValue": f"{defending_val:.0f}"},
        {"axis": "Physical", "value": physical_val, "fullMark": 100, "formattedValue": f"{physical_val:.0f}"},
        {"axis": "Creativity", "value": creativity_val, "fullMark": 100, "formattedValue": f"{creativity_val:.0f}"},
        {"axis": "Tactical", "value": tactical_val, "fullMark": 100, "formattedValue": f"{tactical_val:.0f}"},
    ]


def _build_player_profile(
    pid: str,
    meta: Dict[str, Any],
    p_stats: Dict[str, Any],
    all_events: List[Dict[str, Any]],
) -> Dict[str, Any]:
    """Assembles rich player intelligence object with stats, radar, heatmap, and events."""
    role_titles = {
        "GK": "Goalkeeper",
        "DF": "Defender",
        "MF": "Midfielder",
        "FW": "Forward",
    }
    player_events = [
        e for e in all_events
        if e.get("player_id") == pid or e.get("secondary_player_id") == pid
    ]
    radar = p_stats.get("radar") or _compute_player_radar(p_stats)
    heatmap = p_stats.get("heatmap", [[0] * 8 for _ in range(12)])

    return {
        "player_id": pid,
        "name": meta.get("name", p_stats.get("name", "Player")),
        "team": meta.get("team", p_stats.get("team", "home")),
        "team_name": "Northbridge Lions" if meta.get("team") == "home" else "Harbourside City",
        "jersey_number": meta.get("jersey_number", p_stats.get("jersey_number", 0)),
        "role": meta.get("role", p_stats.get("role", "MF")),
        "position": role_titles.get(meta.get("role", p_stats.get("role", "MF")), "Player"),
        "rating": p_stats.get("rating", 6.0),
        "is_motm": p_stats.get("is_motm", False),
        "bps": p_stats.get("bps", 0),
        "fantasy_bonus_points": p_stats.get("fantasy_bonus_points", 0),
        "stats": p_stats,
        "radar": radar,
        "heatmap": heatmap,
        "events": player_events,
    }

def _squad_with_used_substitutes(session: MatchSession, starters: List[Dict[str, Any]], bench: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Starting eleven plus any substitute who has come on so far."""
    used = session.tracker.players
    return list(starters) + [p for p in bench if p["player_id"] in used]


@app.get("/api/players")
async def get_players(session: MatchSession = Depends(get_session)):
    """Returns the rosters for Northbridge Lions and Harbourside City (starters and used substitutes) with full player profiles."""
    from generator.match_generator import NORTHBRIDGE_BENCH, NORTHBRIDGE_ROSTER, AWAY_BENCH, AWAY_ROSTER

    tracker = session.tracker
    all_events = _load_all_match_events(session)
    home_profiles = []
    away_profiles = []
    all_profiles = []

    for p in _squad_with_used_substitutes(session, NORTHBRIDGE_ROSTER, NORTHBRIDGE_BENCH):
        pid = p["player_id"]
        stats = tracker.get_player_stats(pid)
        if not stats and pid in tracker.players:
            stats = tracker.players[pid].to_dict()
        profile = _build_player_profile(pid, {**p, "team": "home"}, stats or {}, all_events)
        home_profiles.append(profile)
        all_profiles.append(profile)

    for p in _squad_with_used_substitutes(session, AWAY_ROSTER, AWAY_BENCH):
        pid = p["player_id"]
        stats = tracker.get_player_stats(pid)
        if not stats and pid in tracker.players:
            stats = tracker.players[pid].to_dict()
        profile = _build_player_profile(pid, {**p, "team": "away"}, stats or {}, all_events)
        away_profiles.append(profile)
        all_profiles.append(profile)

    return {
        "teams": {
            "home": {
                "name": "Northbridge Lions",
                "short_name": "NBL",
                "crest": "northbridge",
                "color": "#EF0107",
                "players": home_profiles,
            },
            "away": {
                "name": "Harbourside City",
                "short_name": "HSC",
                "crest": "man_city",
                "color": "#6CABDD",
                "players": away_profiles,
            },
        },
        "players": all_profiles,
    }


@app.get("/api/players/{player_id}")
async def get_player_by_id(player_id: str, session: MatchSession = Depends(get_session)):
    """Returns detailed individual player analytics, radar, heatmap, and events feed."""
    from generator.match_generator import NORTHBRIDGE_BENCH, NORTHBRIDGE_ROSTER, AWAY_BENCH, AWAY_ROSTER

    target_p = None
    team_side = "home"
    for p in NORTHBRIDGE_ROSTER + NORTHBRIDGE_BENCH:
        if p["player_id"].upper() == player_id.upper():
            target_p = p
            team_side = "home"
            break
    if not target_p:
        for p in AWAY_ROSTER + AWAY_BENCH:
            if p["player_id"].upper() == player_id.upper():
                target_p = p
                team_side = "away"
                break

    if not target_p:
        raise HTTPException(status_code=404, detail=f"Player '{player_id}' not found")

    pid = target_p["player_id"]
    all_events = _load_all_match_events(session)
    stats = session.tracker.get_player_stats(pid)
    if not stats and pid in session.tracker.players:
        stats = session.tracker.players[pid].to_dict()

    return _build_player_profile(pid, {**target_p, "team": team_side}, stats or {}, all_events)


def _events_signature(events: List[Dict[str, Any]]) -> str:
    return f"{len(events)}:{events[-1].get('event_id') if events else ''}"


def _cached_narrative_for(event: Dict[str, Any]) -> Optional[str]:
    """Foundry narrative for this event if one is already cached (never triggers a model call)."""
    service = orchestrator.narrative_service if orchestrator else None
    if service is None or not service.enabled:
        return None
    try:
        return service.lookup(TacticianAgent().extract_facts(event))
    except Exception:
        return None


def _get_tactical_moments(session: MatchSession, language: str = "en") -> List[Dict[str, Any]]:
    """Key turning points from the events played so far, explained in the requested language.

    Blocking (may call the model); the model text is cached per moment, persona and language.
    """
    events = session.streamer.generator.get_events()
    key = f"{_events_signature(events)}:{language}"
    service = orchestrator.narrative_service if orchestrator else None
    with session.derived_lock:
        if session.moments_cache["key"] == key:
            return session.moments_cache["moments"]
        moments = moments_lib.build_tactical_moments(
            events,
            explain=lambda moment, ev: story_lib.analyse_moment(moment, ev, service, language),
        )
        session.moments_cache.update(key=key, moments=moments)
        return moments


def _get_highlights(session: MatchSession) -> List[Dict[str, Any]]:
    events = session.streamer.generator.get_events()
    signature = _events_signature(events)
    with session.derived_lock:
        if session.highlights_cache["key"] == signature:
            return session.highlights_cache["highlights"]
        highlights = moments_lib.build_highlights(events, narrative_lookup=_cached_narrative_for)
        session.highlights_cache.update(key=signature, highlights=highlights)
        return highlights


@app.get("/api/tactical")
async def get_tactical(language: str = "en", session: MatchSession = Depends(get_session)):
    """Returns key turning points with freeze-frame coordinates and spatial layer overlays."""
    moments = await asyncio.to_thread(_get_tactical_moments, session, language)
    return {"moments": moments}


clip_store = ClipStore()


@app.get("/api/clips/{event_id}")
async def get_clip(event_id: str, session: MatchSession = Depends(get_session)):
    """Replay clip (10 s before and after an event). 202 while a missing clip is being recorded.

    Clips are shared by every viewer: all matches play the same seed, so a clip is valid for all of them.
    """
    seed = session.streamer.seed
    clip = clip_store.get(event_id, seed)
    if clip is not None:
        return clip
    status = await asyncio.to_thread(lambda: clip_store.request(seed, _load_all_match_events(session), event_id))
    if status == "ready":
        return clip_store.get(event_id, seed)
    if status == "unknown":
        raise HTTPException(status_code=404, detail=f"Event {event_id} not found")
    return JSONResponse(status_code=202, content={"status": "preparing", "event_id": event_id})


class AnalystQuestion(BaseModel):
    question: str = Field(..., max_length=400)
    language: str = Field("en", max_length=8)
    persona: str = Field("tactical", max_length=16)
    club: str = Field("", max_length=40)


# Every analyst question spends model tokens: limit each client, and everyone together.
_analyst_client_limit = security.RateLimiter(limit=12, window=60.0)
_analyst_global_limit = security.RateLimiter(limit=90, window=60.0)


def _live_match(session: MatchSession) -> Dict[str, Any]:
    """One viewer's match exactly as it stands now: the live tracker, the events so far, the clock and status."""
    generator = session.streamer.generator
    clock = session.latest_frame.get("clock") if session.latest_frame else generator.get_clock_string()
    if not generator.frame_index:
        status = "NOT_STARTED"
    elif session.is_over():
        status = "FT"
    else:
        status = "LIVE"
    stats = session.tracker.get_match_stats()
    return {
        "tracker": session.tracker,
        "events": generator.get_events(),
        "clock": clock,
        "status": status,
        "score": stats.get("score", {"home": 0, "away": 0}),
    }


def _get_analyst(session: MatchSession):
    """The Match Analyst agent (Agent Framework + MCP tools) for this viewer's match, created on first use."""
    with session.analyst_lock:
        if session.analyst is None:
            from backend.agents.analyst_agent import MatchAnalystAgent
            from backend.mcp_server import InGameMCPServer
            from generator.match_generator import AWAY_BENCH, AWAY_ROSTER, NORTHBRIDGE_BENCH, NORTHBRIDGE_ROSTER

            rosters = [dict(p, team="Northbridge Lions") for p in NORTHBRIDGE_ROSTER + NORTHBRIDGE_BENCH]
            rosters += [dict(p, team="Harbourside City") for p in AWAY_ROSTER + AWAY_BENCH]
            session.analyst = MatchAnalystAgent(
                InGameMCPServer(live_source=lambda: _live_match(session)),
                rosters=rosters,
                live_context=lambda: _live_match(session),
            )
        return session.analyst


@app.post("/api/analyst/ask")
async def ask_analyst(body: AnalystQuestion, request: Request, session: MatchSession = Depends(get_session)):
    """Answers a viewer's question with an Agent Framework agent that calls the MCP analytics tools.

    The agent sees the viewer's own match as it stands at the current clock (not the whole match),
    answers in the viewer's persona (and, for the club persona, as a fan of the chosen club), and the
    answer is verified against the tool results. The response lists the tools the agent used.
    """
    if not (
        _analyst_client_limit.allow(security.client_id(request)) and _analyst_global_limit.allow("all")
    ):
        raise HTTPException(status_code=429, detail="Too many questions. Please wait a moment and try again.")
    analyst = await asyncio.to_thread(_get_analyst, session)
    return await asyncio.to_thread(analyst.ask, body.question, body.language, body.persona, body.club)


@app.get("/api/story")
async def get_story(persona: str = "tactical", language: str = "en", club: str = "Northbridge Lions",
                    session: MatchSession = Depends(get_session)):
    """Match story for a persona and language, written by the model and cached."""
    recap_payload = await get_recap(session)
    service = orchestrator.narrative_service if orchestrator else None
    return await asyncio.to_thread(story_lib.generate_story, recap_payload, persona, language, club, service)


@app.websocket("/ws/match-stream")
async def websocket_match_stream(websocket: WebSocket):
    """Primary WebSocket stream delivering 25Hz telemetry and tactical insights for the caller's match.

    The viewer's session id comes in the query string (``?session=...``); without one the socket joins
    the default shared match.
    """
    try:
        session = _lookup_session(websocket.query_params.get("session"))
    except ValueError:
        await websocket.close(code=1008)  # policy violation: bad session id
        return
    except (SessionLimitReached, RuntimeError):
        await websocket.close(code=1013)  # try again later
        return
    if registry.total_connections() >= security.MAX_WEBSOCKET_CLIENTS:
        await websocket.close(code=1013)
        return

    await session.manager.connect(websocket)
    logger.info("WebSocket client connected to session %s. Clients: %d", session.id[:8], len(session.manager.active_connections))
    streamer = session.streamer
    if session.paused_by_disconnect:
        # The viewer reloaded or came back: carry on where their match was playing.
        session.paused_by_disconnect = False
        streamer.resume()

    # Immediately push latest insight on connect so UI populates without waiting for next event
    if session.latest_insight:
        try:
            await websocket.send_text(json.dumps({
                "type": "insight",
                "timestamp": session.latest_frame.get("timestamp") if session.latest_frame else "00:00",
                "data": session.latest_insight,
            }))
        except Exception:
            pass

    try:
        while True:
            # Handle incoming client messages (heartbeat pings, playback commands)
            text = await websocket.receive_text()
            session.touch()
            if len(text) > security.MAX_WEBSOCKET_MESSAGE_BYTES:
                await websocket.close(code=1009)  # message too big
                break
            try:
                msg = json.loads(text)
                msg_type = msg.get("type")

                if msg_type == "ping":
                    # Respond with sub-millisecond pong for latency monitoring
                    client_time = msg.get("client_time", 0)
                    server_time = int(time.time() * 1000)
                    await websocket.send_text(json.dumps({
                        "type": "pong",
                        "client_time": client_time,
                        "server_time": server_time,
                    }))
                elif msg_type == "control":
                    action = msg.get("action")
                    if action == "pause":
                        streamer.pause()
                    elif action == "play":
                        await _restart_if_match_over(session)
                        streamer.resume()
                    elif action == "reset":
                        session.reset()
                    elif action == "speed":
                        mult = msg.get("multiplier", 1.0)
                        try:
                            val = float(mult)
                            if val > 0:
                                streamer.set_speed(val)
                        except (ValueError, TypeError):
                            pass

            except json.JSONDecodeError:
                pass

    except WebSocketDisconnect:
        pass
    except Exception as e:
        logger.warning(f"WebSocket client error: {e}")
    finally:
        session.manager.disconnect(websocket)
        logger.info("WebSocket client left session %s. Clients: %d", session.id[:8], len(session.manager.active_connections))
        # A viewer's own match does not keep running with nobody watching.
        if not session.is_default and not session.manager.active_connections and not streamer.is_paused:
            streamer.pause()
            session.paused_by_disconnect = True


# Mount static frontend build if directory exists
frontend_dist = os.path.join(os.path.dirname(__file__), "..", "frontend", "dist")
if os.path.exists(frontend_dist):
    app.mount("/", StaticFiles(directory=frontend_dist, html=True), name="static")
