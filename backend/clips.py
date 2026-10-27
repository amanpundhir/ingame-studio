"""InGame Studio - Replay clips around key match moments.

A clip is the real tracking data for the 10 seconds before and after an event: where
all players and the ball were, sampled at 12.5 Hz, plus the events that happened in
that window. The browser replays it like a short video.

The match simulation is deterministic for a given seed, so a clip is recorded by
running the same simulation again and keeping the frames inside each window. Clips
for the key moments of the default match are stored in ``data/match_clips.json``;
a clip that is not stored yet is recorded in the background on first request.
"""

import json
import logging
import os
import threading
from typing import Any, Dict, Iterable, List, Optional

from generator.match_generator import MatchGenerator

logger = logging.getLogger("ingame.clips")

FRAME_RATE = 25
STRIDE = 2                      # keep every 2nd frame: 12.5 Hz
PRE_FRAMES = 10 * FRAME_RATE    # 10 s before the event
POST_FRAMES = 10 * FRAME_RATE   # 10 s after the event
DEFAULT_CLIPS_FILE = os.path.join(os.path.dirname(__file__), "..", "data", "match_clips.json")


def _impact(event: Dict[str, Any]) -> float:
    metrics = event.get("tactical_metrics") or {}
    return float(metrics.get("xt_gained", 0.0) or 0.0) + 0.002 * float(metrics.get("pass_difficulty", 0.0) or 0.0)


def select_clip_events(events: List[Dict[str, Any]], recoveries: int = 25) -> List[Dict[str, Any]]:
    """Every event the app may show as a key moment: goals, sendings-off, shots and the best recoveries."""
    from backend.moments import select_highlight_events, select_tactical_events

    chosen: Dict[str, Dict[str, Any]] = {}

    def add(event: Dict[str, Any]) -> None:
        chosen[str(event.get("event_id"))] = event

    for event in events:
        kind = str(event.get("event_type")).lower()
        if kind in ("goal", "shot") or (kind == "card" and str(event.get("outcome")).lower() == "red"):
            add(event)
    rec = [e for e in events if str(e.get("event_type")).lower() in ("tackle", "turnover")]
    for event in sorted(rec, key=_impact, reverse=True)[:recoveries]:
        add(event)
    for event in select_highlight_events(events):
        add(event)
    for _slug, _label, event in select_tactical_events(events):
        add(event)
    return list(chosen.values())


def _score_after(events: List[Dict[str, Any]]) -> Dict[str, List[int]]:
    scores = {"home": 0, "away": 0}
    after: Dict[str, List[int]] = {}
    for event in sorted(events, key=lambda e: (e.get("period", 1), e.get("frame_index", 0))):
        if str(event.get("event_type")).lower() == "goal":
            scores["home" if str(event.get("team")) in ("Northbridge Lions", "home") else "away"] += 1
        after[str(event.get("event_id"))] = [scores["home"], scores["away"]]
    return after


def record_clips(
    seed: int,
    events: List[Dict[str, Any]],
    wanted: Iterable[Dict[str, Any]],
    match_id: str = "IGS_2026_NBL_HSC",
) -> Dict[str, Dict[str, Any]]:
    """Runs the seeded simulation once and keeps the frames around each wanted event."""
    targets = []
    for event in wanted:
        centre = int(event.get("frame_index", 0))
        targets.append((max(1, centre - PRE_FRAMES), centre + POST_FRAMES, centre, event))
    if not targets:
        return {}
    targets.sort(key=lambda item: item[0])
    last_frame = max(item[1] for item in targets)
    scores_after = _score_after(events)
    event_scores = {str(e.get("event_id")): scores_after.get(str(e.get("event_id")), [0, 0]) for e in events}

    generator = MatchGenerator(match_id=match_id, seed=seed)
    captured: Dict[str, List[Dict[str, Any]]] = {str(t[3].get("event_id")): [] for t in targets}
    roster: Dict[str, Dict[str, Dict[str, Any]]] = {key: {} for key in captured}

    while generator.frame_index < last_frame:
        frame = generator.step()
        index = generator.frame_index
        for start, end, centre, event in targets:
            if start <= index <= end and (index - start) % STRIDE == 0:
                key = str(event.get("event_id"))
                for player in frame["players"]:
                    roster[key].setdefault(player["player_id"], {
                        "id": player["player_id"], "team": player["team"], "num": player["jersey_number"],
                        "name": player["name"], "role": player["role"],
                    })
                captured[key].append({"t": round((index - centre) / FRAME_RATE, 2), "frame": frame})

    clips: Dict[str, Dict[str, Any]] = {}
    for start, end, centre, event in targets:
        key = str(event.get("event_id"))
        ids = list(roster[key])
        frames = []
        for item in captured[key]:
            by_id = {p["player_id"]: p for p in item["frame"]["players"]}
            ball = item["frame"]["ball"]
            frames.append({
                "t": item["t"],
                "ball": [round(ball["x"], 1), round(ball["y"], 1), round(ball.get("z", 0.0), 1)],
                "p": [[round(by_id[i]["x"], 1), round(by_id[i]["y"], 1)] if i in by_id else None for i in ids],
            })
        window_events = []
        for other in events:
            offset = (int(other.get("frame_index", 0)) - centre) / FRAME_RATE
            if -10.0 <= offset <= 10.0:
                window_events.append({
                    "id": other.get("event_id"), "t": round(offset, 2), "type": other.get("event_type"),
                    "sub_type": other.get("sub_type"), "outcome": other.get("outcome"), "team": other.get("team"),
                    "player_id": other.get("player_id"), "player": other.get("player_name"),
                    "secondary_id": other.get("secondary_player_id"), "secondary": other.get("secondary_player_name"),
                    "x": other.get("location_x"), "y": other.get("location_y"),
                    "end_x": other.get("end_x"), "end_y": other.get("end_y"),
                })
        after = event_scores.get(key, [0, 0])
        is_goal = str(event.get("event_type")).lower() == "goal"
        before = [after[0] - (1 if is_goal and str(event.get("team")) in ("Northbridge Lions", "home") else 0),
                  after[1] - (1 if is_goal and str(event.get("team")) not in ("Northbridge Lions", "home") else 0)]
        clips[key] = {
            "event_id": key, "status": "ready", "seed": seed, "period": event.get("period"),
            "clock": event.get("clock"), "event_type": event.get("event_type"), "team": event.get("team"),
            "player": event.get("player_name"), "fps": FRAME_RATE / STRIDE, "pre_s": 10, "post_s": 10,
            "score_before": before, "score_after": after,
            "roster": [roster[key][i] for i in ids], "frames": frames, "events": window_events,
        }
    return clips


class ClipStore:
    """Clips on disk plus an on-demand recorder for moments that are not stored yet."""

    def __init__(self, path: Optional[str] = None):
        self.path = os.path.abspath(path or DEFAULT_CLIPS_FILE)
        self._lock = threading.Lock()
        self._clips: Dict[str, Dict[str, Any]] = {}
        self._seed: Optional[int] = None
        self._building: set = set()
        self._worker: Optional[threading.Thread] = None
        self._load()

    def _load(self) -> None:
        try:
            with open(self.path, "r", encoding="utf-8") as handle:
                data = json.load(handle)
            self._seed = data.get("seed")
            self._clips = dict(data.get("clips", {}))
        except (OSError, ValueError):
            self._clips, self._seed = {}, None

    def get(self, event_id: str, seed: int) -> Optional[Dict[str, Any]]:
        with self._lock:
            clip = self._clips.get(event_id)
            return clip if clip is not None and clip.get("seed") == seed else None

    def is_building(self, event_id: str) -> bool:
        with self._lock:
            return event_id in self._building

    def save(self, seed: int) -> None:
        with self._lock:
            payload = {"seed": seed, "clips": self._clips}
        os.makedirs(os.path.dirname(self.path), exist_ok=True)
        tmp = f"{self.path}.{os.getpid()}.tmp"
        with open(tmp, "w", encoding="utf-8") as handle:
            json.dump(payload, handle, separators=(",", ":"))
        os.replace(tmp, self.path)

    def put_many(self, clips: Dict[str, Dict[str, Any]]) -> None:
        with self._lock:
            self._clips.update(clips)

    def request(self, seed: int, events: List[Dict[str, Any]], event_id: str) -> str:
        """Starts recording a missing clip in the background; returns 'ready', 'preparing' or 'unknown'."""
        if self.get(event_id, seed) is not None:
            return "ready"
        event = next((e for e in events if str(e.get("event_id")) == event_id), None)
        if event is None:
            return "unknown"
        with self._lock:
            if event_id in self._building:
                return "preparing"
            self._building.add(event_id)
            if self._worker is not None and self._worker.is_alive():
                return "preparing"
            self._worker = threading.Thread(target=self._run, args=(seed, list(events)), daemon=True)
            self._worker.start()
        return "preparing"

    def _run(self, seed: int, events: List[Dict[str, Any]]) -> None:
        try:
            while True:
                with self._lock:
                    pending = [e for e in events if str(e.get("event_id")) in self._building]
                if not pending:
                    return
                wanted = select_clip_events(events)
                wanted_ids = {str(e.get("event_id")) for e in wanted}
                wanted += [e for e in pending if str(e.get("event_id")) not in wanted_ids]
                self.put_many(record_clips(seed, events, wanted))
                with self._lock:
                    self._building -= {str(e.get("event_id")) for e in wanted}
        except Exception as exc:  # recording is best effort; the UI falls back to the freeze-frame
            logger.warning(f"Clip recording failed: {exc}")
            with self._lock:
                self._building.clear()
