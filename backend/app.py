"""InGame Studio - FastAPI WebSocket & REST Streaming Server.

Broadcasting 25Hz tracking telemetry, synchronized event triggers,
real-time tactical metrics, and verified 4-agent match insights.
"""

import asyncio
import threading
import json
import logging
import os
import time
from contextlib import asynccontextmanager
from typing import Any, Dict, List, Optional, Set, Union
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


class ConnectionManager:
    """Manages active broadcast WebSocket connections with slow-client protection."""

    def __init__(self):
        self.active_connections: Set[WebSocket] = set()

    async def connect(self, websocket: WebSocket) -> bool:
        """Accepts the client unless the server is full. Returns False when it refused."""
        if len(self.active_connections) >= security.MAX_WEBSOCKET_CLIENTS:
            await websocket.close(code=1013)  # try again later
            return False
        await websocket.accept()
        self.active_connections.add(websocket)
        logger.info(f"WebSocket client connected. Total clients: {len(self.active_connections)}")
        return True

    def disconnect(self, websocket: WebSocket) -> None:
        self.active_connections.discard(websocket)
        logger.info(f"WebSocket client disconnected. Total clients: {len(self.active_connections)}")

    async def broadcast(self, payload: Dict[str, Any]) -> None:
        """Broadcasts a JSON payload to all connected clients."""
        if not self.active_connections:
            return

        dead_connections = set()
        msg_str = json.dumps(payload)
        for connection in self.active_connections:
            try:
                await connection.send_text(msg_str)
            except Exception as e:
                logger.warning(f"Error sending frame to client, queuing removal: {e}")
                dead_connections.add(connection)

        for dead in dead_connections:
            self.disconnect(dead)


# Global server singletons
manager = ConnectionManager()
streamer: Optional[TelemetryStreamer] = None
orchestrator: Optional[MatchIntelligenceOrchestrator] = None
analytics_tracker: Optional[MatchAnalyticsTracker] = None
background_stream_task: Optional[asyncio.Task] = None
latest_insight: Optional[Dict[str, Any]] = None
latest_frame: Optional[Dict[str, Any]] = None
latest_recap: Optional[Dict[str, Any]] = None
last_triggered_event_id: Optional[str] = None


FULL_TIME_SECONDS = 5670  # 94:30 - the match ends here; nothing is generated after it


def _full_time_frame() -> int:
    return int(FULL_TIME_SECONDS * (streamer.frame_rate if streamer else 25))


def _match_is_over() -> bool:
    return bool(streamer) and streamer.generator.frame_index >= _full_time_frame()


def _reset_match_state() -> None:
    """Back to kick-off: simulation, analytics and every cached live value."""
    global last_triggered_event_id, latest_insight, latest_frame, latest_recap
    streamer.reset()
    if analytics_tracker:
        analytics_tracker.reset()
    last_triggered_event_id = None
    latest_frame = None
    latest_insight = None
    latest_recap = None


async def _restart_if_match_over() -> bool:
    """Pressing Play after full time starts a new run of the match from kick-off."""
    if not _match_is_over():
        return False
    _reset_match_state()
    await manager.broadcast({"type": "control", "timestamp": "00:00", "data": {"action": "reset"}})
    return True


async def broadcast_loop():
    """Background 25Hz streaming worker loop with adaptive frame stepping."""
    global latest_frame, latest_insight, last_triggered_event_id
    logger.info("Starting InGame 25Hz broadcast loop...")

    try:
        while True:
            if streamer.is_paused:
                await asyncio.sleep(0.04)
                continue

            t_start = time.perf_counter()
            # Never step past full time, whatever the playback speed.
            steps = min(streamer.get_steps_for_tick(), max(0, _full_time_frame() - streamer.generator.frame_index))
            if steps <= 0:
                streamer.pause()
                continue
            frame = None

            # Advance simulation by K frames per broadcast tick and ingest into analytics
            for _ in range(steps):
                frame = streamer.generator.step()
                if analytics_tracker:
                    analytics_tracker.add_telemetry_frame(frame)
                    pending_alerts = analytics_tracker.pop_pending_alerts()
                    for alert in pending_alerts:
                        await manager.broadcast({
                            "type": "metric_alert",
                            "timestamp": frame.get("timestamp") if frame else "00:00",
                            "data": alert,
                        })

                # Detect key event triggers in intermediate frames
                active_evt_id = frame.get("active_event_id")
                if active_evt_id and active_evt_id != last_triggered_event_id:
                    last_triggered_event_id = active_evt_id
                    # Events are created by the simulation as actions happen,
                    # so resolve against its current event list rather than a
                    # startup-time snapshot.
                    event_data = next(
                        (ev for ev in streamer.generator.get_events() if ev.get("event_id") == active_evt_id),
                        None,
                    )
                    if event_data:
                        milestone = None
                        if analytics_tracker:
                            milestone = analytics_tracker.record_event(event_data)
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
                            latest_insight = insight_dict

                            # Broadcast event and insight messages
                            await manager.broadcast({
                                "type": "event",
                                "timestamp": frame.get("timestamp"),
                                "data": event_data,
                            })
                            await manager.broadcast({
                                "type": "insight",
                                "timestamp": frame.get("timestamp"),
                                "data": insight_dict,
                            })
                        except Exception as err:
                            logger.error(f"Error processing event through multi-agent workflow: {err}")

            latest_frame = frame

            # Broadcast 25Hz telemetry frame
            if frame is not None:
                await manager.broadcast({
                    "type": "telemetry",
                    "timestamp": frame.get("timestamp"),
                    "data": frame,
                })

            if _match_is_over():
                # Full time: stop here. The final frame stays on screen until Play restarts the match.
                streamer.pause()
                if frame is not None:
                    frame["ball"] = dict(frame.get("ball") or {}, status="stopped")
                await manager.broadcast({
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
        logger.info("Broadcast loop cancelled.")
    except Exception as e:
        logger.error(f"Fatal error in broadcast loop: {e}", exc_info=True)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """FastAPI startup and shutdown lifecycle manager."""
    global streamer, orchestrator, analytics_tracker, background_stream_task

    logger.info("Initializing InGame Studio services...")
    events_file = settings.synthetic_events_file
    if events_file and not os.path.isabs(events_file):
        events_file = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", events_file))

    streamer = TelemetryStreamer(
        match_id="IGS_2026_NBL_HSC",
        frame_rate=settings.fps,
        real_time=True,
        events_file=events_file,
        seed=settings.simulation_seed,
    )
    orchestrator = MatchIntelligenceOrchestrator()
    analytics_tracker = MatchAnalyticsTracker()

    # Match events are emitted as the deterministic simulation runs. There is
    # no pre-authored first event to process at startup.

    background_stream_task = asyncio.create_task(broadcast_loop())
    yield

    # Teardown
    if background_stream_task:
        background_stream_task.cancel()
        try:
            await background_stream_task
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
    allow_headers=["Content-Type", "X-API-Key"],
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
async def get_status():
    """Returns real-time match studio status."""
    frame_index = streamer.generator.frame_index if streamer else 0
    clock = streamer.generator.get_clock_string() if streamer else "00:00"
    return {
        "match_id": streamer.match_id if streamer else "IGS_2026_NBL_HSC",
        "frame_index": frame_index,
        "clock": clock,
        "is_paused": streamer.is_paused if streamer else False,
        "speed_multiplier": streamer.speed_multiplier if streamer else 1.0,
        "connected_clients": len(manager.active_connections),
        "has_insight": latest_insight is not None,
        "latest_event_id": last_triggered_event_id,
    }


def _get_current_frame() -> Dict[str, Any]:
    """Retrieves or builds the current 25Hz telemetry frame."""
    global latest_frame
    if latest_frame is not None:
        return latest_frame
    if streamer:
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
    return {}


@app.get("/api/state")
async def get_state():
    """Returns a full state snapshot for the live match dashboard."""
    curr_frame = _get_current_frame()
    clock = curr_frame.get("clock") or (streamer.generator.get_clock_string() if streamer else "00:00")
    period = curr_frame.get("period") or (streamer.generator.period if streamer else 1)
    stats = analytics_tracker.get_match_stats() if analytics_tracker else {}
    score = stats.get("score", {"home": 0, "away": 0})
    return {
        "match_id": streamer.match_id if streamer else "IGS_2026_NBL_HSC",
        "clock": clock,
        "period": period,
        "is_paused": streamer.is_paused if streamer else False,
        "speed_multiplier": streamer.speed_multiplier if streamer else 1.0,
        "score": score,
        "frame": curr_frame,
        "match_stats": stats,
        "latest_insight": latest_insight,
    }


@app.post("/api/control")
async def post_control(cmd: ControlCommand):
    """Controls studio playback (play, pause, reset, trigger, speed, jump, simulate_full)."""
    global last_triggered_event_id, latest_insight, latest_frame, latest_recap
    action = cmd.action.lower()

    if action in ("play", "resume"):
        restarted = await _restart_if_match_over()
        streamer.resume()
        return {"status": "resumed", "is_paused": False, "restarted": restarted}
    elif action == "pause":
        streamer.pause()
        return {"status": "paused", "is_paused": True}
    elif action == "reset":
        _reset_match_state()
        return {"status": "reset", "frame_index": 0}
    elif action == "speed":
        if cmd.multiplier is None or cmd.multiplier <= 0:
            raise HTTPException(status_code=400, detail="Invalid multiplier, must be positive float")
        new_speed = streamer.set_speed(cmd.multiplier)
        clock = streamer.generator.get_clock_string() if streamer else "00:00"
        await manager.broadcast({
            "type": "control",
            "timestamp": latest_frame.get("timestamp") if latest_frame else "00:00",
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
        latest_frame = frame
        last_triggered_event_id = cmd.event_id
        if analytics_tracker:
            analytics_tracker.seek_to_event(event_data)
            analytics_tracker.record_event(event_data)

        insight = await asyncio.to_thread(
            orchestrator.process_event, event_data, telemetry_frame=frame, allow_live=True
        )
        latest_insight = insight.model_dump()

        await manager.broadcast({
            "type": "jump",
            "timestamp": frame.get("timestamp"),
            "data": {
                "event_id": cmd.event_id,
                "clock": frame.get("clock"),
                "frame_index": frame.get("frame_id"),
            },
        })
        await manager.broadcast({
            "type": "event",
            "timestamp": frame.get("timestamp"),
            "data": event_data,
        })
        await manager.broadcast({
            "type": "insight",
            "timestamp": frame.get("timestamp"),
            "data": latest_insight,
        })
        await manager.broadcast({
            "type": "telemetry",
            "timestamp": frame.get("timestamp"),
            "data": frame,
        })
        return {
            "status": "jumped",
            "event_id": cmd.event_id,
            "clock": frame.get("clock"),
            "frame_index": frame.get("frame_id"),
            "insight": latest_insight,
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

        if analytics_tracker:
            analytics_tracker.reset()
        if cached_snapshot and cached_events is not None:
            frame = streamer.simulate_full_match(
                snapshot=cached_snapshot.get("final_frame"),
                events=cached_events,
            )
            if analytics_tracker:
                analytics_tracker.load_snapshot(
                    events=cached_events,
                    match_stats=cached_snapshot.get("match_stats", {}),
                    player_stats=cached_snapshot.get("player_stats", []),
                )
        else:
            frame = streamer.simulate_full_match(
                on_frame=analytics_tracker.add_telemetry_frame if analytics_tracker else None
            )
            if analytics_tracker:
                for event in streamer.generator.get_events():
                    analytics_tracker.record_event(event)

        latest_frame = frame
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
                latest_insight = closing_insight.model_dump()
                last_triggered_event_id = closing_event.get("event_id")
                await manager.broadcast({
                    "type": "insight",
                    "timestamp": frame.get("timestamp"),
                    "data": latest_insight,
                })
            except Exception as err:
                logger.warning(f"Could not build closing insight: {err}")

        recap = generate_match_recap(analytics_tracker, events=all_events)
        recap["status"] = "FT"
        recap["clock"] = frame.get("clock", "94:30")
        latest_recap = recap

        match_stats = analytics_tracker.get_match_stats() if analytics_tracker else {}
        player_stats = analytics_tracker.get_all_player_stats() if analytics_tracker else []

        await manager.broadcast({
            "type": "simulate_full",
            "timestamp": frame.get("timestamp"),
            "data": {
                "clock": frame.get("clock", "94:30"),
                "frame_index": frame.get("frame_id"),
                "score": analytics_tracker.get_match_stats().get("score", {"home": 0, "away": 0}) if analytics_tracker else {"home": 0, "away": 0},
            },
        })
        await manager.broadcast({
            "type": "recap",
            "timestamp": frame.get("clock", "94:30"),
            "data": recap,
        })
        await manager.broadcast({
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
        milestone = None
        if analytics_tracker:
            milestone = analytics_tracker.record_event(event_data)
        if milestone:
            event_data = dict(event_data)
            event_data["milestone"] = milestone
        insight = await asyncio.to_thread(
            orchestrator.process_event, event_data, telemetry_frame=latest_frame, allow_live=True
        )
        latest_insight = insight.model_dump()
        last_triggered_event_id = cmd.event_id

        await manager.broadcast({
            "type": "event",
            "timestamp": latest_frame.get("timestamp") if latest_frame else "00:00",
            "data": event_data,
        })
        await manager.broadcast({
            "type": "insight",
            "timestamp": latest_frame.get("timestamp") if latest_frame else "00:00",
            "data": latest_insight,
        })
        return {"status": "triggered", "event_id": cmd.event_id, "insight": latest_insight}
    else:
        raise HTTPException(status_code=400, detail=f"Unsupported action: {cmd.action}")


@app.post("/api/simulate_full")
async def post_simulate_full():
    """Direct alias to simulate_full control action."""
    return await post_control(ControlCommand(action="simulate_full"))


@app.get("/api/alerts")
async def get_alerts():
    """Returns all detected physical threshold and tactical metric alerts."""
    if not analytics_tracker:
        return []
    return analytics_tracker.get_all_alerts()


@app.get("/api/insights/latest")
async def get_latest_insight():
    """Returns the most recent verified insight."""
    if not latest_insight:
        return JSONResponse(status_code=204, content=None)
    return latest_insight


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
async def get_recap():
    """Returns the current match report; it becomes a full-time recap at 94:30."""
    global latest_recap
    all_events = streamer.generator.get_events() if streamer else None
    current_clock = (
        latest_frame.get("clock") if latest_frame
        else streamer.generator.get_clock_string() if streamer
        else "00:00"
    )
    recap = generate_match_recap(analytics_tracker, events=all_events, clock=current_clock)
    is_full_time = bool(
        streamer
        and streamer.generator.frame_index >= int(5670 * streamer.frame_rate)
    )
    recap["status"] = "FT" if is_full_time else "LIVE" if streamer and streamer.generator.frame_index else "NOT_STARTED"
    recap["highlights"] = await asyncio.to_thread(_get_highlights)
    latest_recap = recap
    return recap


@app.post("/api/ingest", dependencies=[Depends(security.require_ingest_key)])
async def post_ingest(event: Dict[str, Any]):
    """Accepts and ingests a single external MatchEvent conforming to data/schema.json."""
    global latest_insight, last_triggered_event_id
    _validate_match_event(event)

    milestone = None
    if analytics_tracker:
        milestone = analytics_tracker.record_event(event)
    if milestone:
        event = dict(event)
        event["milestone"] = milestone

    insight_dict = {}
    if orchestrator:
        insight = await asyncio.to_thread(
            orchestrator.process_event, event, telemetry_frame=latest_frame, allow_live=True
        )
        insight_dict = insight.model_dump()
        latest_insight = insight_dict
        last_triggered_event_id = event.get("event_id")

    clock_ts = event.get("clock") or (latest_frame.get("timestamp") if latest_frame else "00:00")
    await manager.broadcast({
        "type": "event",
        "timestamp": clock_ts,
        "data": event,
    })
    if insight_dict:
        await manager.broadcast({
            "type": "insight",
            "timestamp": clock_ts,
            "data": insight_dict,
        })

    return {
        "status": "ingested",
        "event_id": event.get("event_id"),
        "insight": insight_dict,
    }


@app.post("/api/events", dependencies=[Depends(security.require_ingest_key)])
async def post_events(payload: Union[BatchEventsPayload, Dict[str, Any], List[Dict[str, Any]]]):
    """Accepts a batch of MatchEvents conforming to data/schema.json and ingests them sequentially."""
    global latest_insight, last_triggered_event_id
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
        milestone = None
        if analytics_tracker:
            milestone = analytics_tracker.record_event(ev)
        if milestone:
            ev = dict(ev)
            ev["milestone"] = milestone

        if orchestrator:
            insight = await asyncio.to_thread(
                orchestrator.process_event, ev, telemetry_frame=latest_frame, allow_live=True
            )
            latest_insight = insight.model_dump()
            last_triggered_event_id = ev.get("event_id")

        clock_ts = ev.get("clock") or (latest_frame.get("timestamp") if latest_frame else "00:00")
        await manager.broadcast({
            "type": "event",
            "timestamp": clock_ts,
            "data": ev,
        })
        if latest_insight:
            await manager.broadcast({
                "type": "insight",
                "timestamp": clock_ts,
                "data": latest_insight,
            })

    return {
        "status": "batch_ingested",
        "count": len(events_list),
    }


@app.get("/api/events")
async def get_events():
    """Returns all calibrated synthetic match events."""
    if not streamer:
        return []
    return streamer.generator.get_events()


@app.get("/api/analytics")
async def get_analytics():
    """Returns 22-player and match statistics."""
    if not analytics_tracker:
        return {"match_stats": {}, "player_stats": []}
    return {
        "match_stats": analytics_tracker.get_match_stats(),
        "player_stats": analytics_tracker.get_all_player_stats(),
    }


def _load_all_match_events() -> List[Dict[str, Any]]:
    """Events played so far in the running simulation (falls back to the exported default-seed file)."""
    if streamer:
        live_events = streamer.generator.get_events()
        if live_events:
            return live_events
    events_path = os.path.join(os.path.dirname(__file__), "..", "data", "synthetic_events.json")
    if settings.synthetic_events_file is None and not streamer and os.path.isfile(events_path):
        try:
            with open(events_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return []


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


def _squad_with_used_substitutes(starters: List[Dict[str, Any]], bench: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Starting eleven plus any substitute who has come on so far."""
    used = analytics_tracker.players if analytics_tracker else {}
    return list(starters) + [p for p in bench if p["player_id"] in used]


@app.get("/api/players")
async def get_players():
    """Returns the rosters for Northbridge Lions and Harbourside City (starters and used substitutes) with full player profiles."""
    from generator.match_generator import NORTHBRIDGE_BENCH, NORTHBRIDGE_ROSTER, AWAY_BENCH, AWAY_ROSTER

    all_events = _load_all_match_events()
    home_profiles = []
    away_profiles = []
    all_profiles = []

    for p in _squad_with_used_substitutes(NORTHBRIDGE_ROSTER, NORTHBRIDGE_BENCH):
        pid = p["player_id"]
        stats = analytics_tracker.get_player_stats(pid) if analytics_tracker else {}
        if not stats and analytics_tracker and pid in analytics_tracker.players:
            stats = analytics_tracker.players[pid].to_dict()
        profile = _build_player_profile(pid, {**p, "team": "home"}, stats or {}, all_events)
        home_profiles.append(profile)
        all_profiles.append(profile)

    for p in _squad_with_used_substitutes(AWAY_ROSTER, AWAY_BENCH):
        pid = p["player_id"]
        stats = analytics_tracker.get_player_stats(pid) if analytics_tracker else {}
        if not stats and analytics_tracker and pid in analytics_tracker.players:
            stats = analytics_tracker.players[pid].to_dict()
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
async def get_player_by_id(player_id: str):
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
    all_events = _load_all_match_events()
    stats = analytics_tracker.get_player_stats(pid) if analytics_tracker else {}
    if not stats and analytics_tracker and pid in analytics_tracker.players:
        stats = analytics_tracker.players[pid].to_dict()

    return _build_player_profile(pid, {**target_p, "team": team_side}, stats or {}, all_events)


_moments_cache: Dict[str, Any] = {"key": None, "moments": []}
_highlights_cache: Dict[str, Any] = {"key": None, "highlights": []}
_derived_lock = threading.Lock()


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


def _get_tactical_moments(language: str = "en") -> List[Dict[str, Any]]:
    """Key turning points from the events played so far, explained in the requested language.

    Blocking (may call the model); the model text is cached per moment, persona and language.
    """
    events = streamer.generator.get_events() if streamer else []
    key = f"{_events_signature(events)}:{language}"
    service = orchestrator.narrative_service if orchestrator else None
    with _derived_lock:
        if _moments_cache["key"] == key:
            return _moments_cache["moments"]
        moments = moments_lib.build_tactical_moments(
            events,
            explain=lambda moment, ev: story_lib.analyse_moment(moment, ev, service, language),
        )
        _moments_cache.update(key=key, moments=moments)
        return moments


def _get_highlights() -> List[Dict[str, Any]]:
    events = streamer.generator.get_events() if streamer else []
    signature = _events_signature(events)
    with _derived_lock:
        if _highlights_cache["key"] == signature:
            return _highlights_cache["highlights"]
        highlights = moments_lib.build_highlights(events, narrative_lookup=_cached_narrative_for)
        _highlights_cache.update(key=signature, highlights=highlights)
        return highlights


@app.get("/api/tactical")
async def get_tactical(language: str = "en"):
    """Returns key turning points with freeze-frame coordinates and spatial layer overlays."""
    moments = await asyncio.to_thread(_get_tactical_moments, language)
    return {"moments": moments}


clip_store = ClipStore()


@app.get("/api/clips/{event_id}")
async def get_clip(event_id: str):
    """Replay clip (10 s before and after an event). 202 while a missing clip is being recorded."""
    seed = streamer.seed if streamer else settings.simulation_seed
    clip = clip_store.get(event_id, seed)
    if clip is not None:
        return clip
    status = await asyncio.to_thread(lambda: clip_store.request(seed, _load_all_match_events(), event_id))
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


_analyst = None
_analyst_lock = threading.Lock()


def _live_match() -> Dict[str, Any]:
    """The match exactly as it stands now: the live tracker, the events so far, the clock and status."""
    clock = (
        latest_frame.get("clock") if latest_frame
        else streamer.generator.get_clock_string() if streamer
        else "00:00"
    )
    frame_index = streamer.generator.frame_index if streamer else 0
    if not frame_index:
        status = "NOT_STARTED"
    elif _match_is_over():
        status = "FT"
    else:
        status = "LIVE"
    stats = analytics_tracker.get_match_stats() if analytics_tracker else {}
    return {
        "tracker": analytics_tracker,
        "events": streamer.generator.get_events() if streamer else [],
        "clock": clock,
        "status": status,
        "score": stats.get("score", {"home": 0, "away": 0}),
    }


def _get_analyst():
    """The Match Analyst agent (Agent Framework + MCP tools), created on first use."""
    global _analyst
    with _analyst_lock:
        if _analyst is None:
            from backend.agents.analyst_agent import MatchAnalystAgent
            from backend.mcp_server import InGameMCPServer
            from generator.match_generator import AWAY_BENCH, AWAY_ROSTER, NORTHBRIDGE_BENCH, NORTHBRIDGE_ROSTER

            rosters = [dict(p, team="Northbridge Lions") for p in NORTHBRIDGE_ROSTER + NORTHBRIDGE_BENCH]
            rosters += [dict(p, team="Harbourside City") for p in AWAY_ROSTER + AWAY_BENCH]
            _analyst = MatchAnalystAgent(
                InGameMCPServer(live_source=_live_match), rosters=rosters, live_context=_live_match,
            )
        return _analyst


@app.post("/api/analyst/ask")
async def ask_analyst(body: AnalystQuestion, request: Request):
    """Answers a viewer's question with an Agent Framework agent that calls the MCP analytics tools.

    The agent sees the match as it stands at the current clock (not the whole match), answers in the
    viewer's persona (and, for the club persona, as a fan of the chosen club), and the answer is
    verified against the tool results. The response lists the tools the agent used.
    """
    if not (
        _analyst_client_limit.allow(security.client_id(request)) and _analyst_global_limit.allow("all")
    ):
        raise HTTPException(status_code=429, detail="Too many questions. Please wait a moment and try again.")
    analyst = await asyncio.to_thread(_get_analyst)
    return await asyncio.to_thread(analyst.ask, body.question, body.language, body.persona, body.club)


@app.get("/api/story")
async def get_story(persona: str = "tactical", language: str = "en", club: str = "Northbridge Lions"):
    """Match story for a persona and language, written by the model and cached."""
    recap_payload = await get_recap()
    service = orchestrator.narrative_service if orchestrator else None
    return await asyncio.to_thread(story_lib.generate_story, recap_payload, persona, language, club, service)


@app.websocket("/ws/match-stream")
async def websocket_match_stream(websocket: WebSocket):
    """Primary WebSocket stream delivering 25Hz telemetry and tactical insights."""
    if not await manager.connect(websocket):
        return

    # Immediately push latest insight on connect so UI populates without waiting for next event
    if latest_insight:
        try:
            await websocket.send_text(json.dumps({
                "type": "insight",
                "timestamp": latest_frame.get("timestamp") if latest_frame else "00:00",
                "data": latest_insight,
            }))
        except Exception:
            pass

    try:
        while True:
            # Handle incoming client messages (heartbeat pings, playback commands)
            text = await websocket.receive_text()
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
                        await _restart_if_match_over()
                        streamer.resume()
                    elif action == "reset":
                        _reset_match_state()
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
        manager.disconnect(websocket)
    except Exception as e:
        logger.warning(f"WebSocket client error: {e}")
        manager.disconnect(websocket)


# Mount static frontend build if directory exists
frontend_dist = os.path.join(os.path.dirname(__file__), "..", "frontend", "dist")
if os.path.exists(frontend_dist):
    app.mount("/", StaticFiles(directory=frontend_dist, html=True), name="static")
