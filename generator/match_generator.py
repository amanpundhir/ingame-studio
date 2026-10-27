"""
InGame Studio - Synthetic Match & Telemetry Generator
Generates fictional 25Hz tracking telemetry for 22 players and 1 ball on a
standard 105m x 68m pitch. The seeded fixture is synthetic and does not represent
a real match or tracking feed, even where familiar club or player labels are used.
Generates and coordinates passes, shots, tackles, turnovers, and pressure events.
"""

from __future__ import annotations

import json
import math
import os
import random
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Optional, Any, Tuple, Set

from .physics_engine import PhysicsEngine, BallState, PlayerState, Vector2D

SYNTHETIC_DATA_NOTICE = (
    "Synthetic demonstration data. This fictional scenario does not represent "
    "a real match or real tracking feed."
)


# Calibrated Rosters (Northbridge Lions vs Harbourside City)
NORTHBRIDGE_ROSTER = [
    {"player_id": "NBL_01", "name": "Daniel Roark", "jersey_number": 1, "role": "GK", "base_x": 4.0, "base_y": 34.0},
    {"player_id": "NBL_04", "name": "Ben Whitlock", "jersey_number": 4, "role": "DF", "base_x": 18.0, "base_y": 56.0},
    {"player_id": "NBL_02", "name": "Wilfred Sandoval", "jersey_number": 2, "role": "DF", "base_x": 15.0, "base_y": 42.0},
    {"player_id": "NBL_06", "name": "Gabriel Marchetti", "jersey_number": 6, "role": "DF", "base_x": 15.0, "base_y": 26.0},
    {"player_id": "NBL_12", "name": "Joris Tamblyn", "jersey_number": 12, "role": "DF", "base_x": 18.0, "base_y": 12.0},
    {"player_id": "NBL_05", "name": "Tomas Pardoe", "jersey_number": 5, "role": "MF", "base_x": 28.0, "base_y": 26.0},
    {"player_id": "NBL_41", "name": "Declan Rowe", "jersey_number": 41, "role": "MF", "base_x": 32.0, "base_y": 40.0},
    {"player_id": "NBL_08", "name": "Martin Olsvik", "jersey_number": 8, "role": "MF", "base_x": 38.0, "base_y": 30.0},
    {"player_id": "NBL_07", "name": "Kofi Sarpong", "jersey_number": 7, "role": "FW", "base_x": 46.0, "base_y": 56.0},
    {"player_id": "NBL_29", "name": "Kai Halvorsen", "jersey_number": 29, "role": "FW", "base_x": 52.2, "base_y": 34.0},
    {"player_id": "NBL_11", "name": "Mateus Montoya", "jersey_number": 11, "role": "FW", "base_x": 46.0, "base_y": 12.0},
]

AWAY_ROSTER = [
    {"player_id": "HSC_31", "name": "Enzo Barreto", "jersey_number": 31, "role": "GK", "base_x": 101.0, "base_y": 34.0},
    {"player_id": "HSC_02", "name": "Kyle Walden", "jersey_number": 2, "role": "DF", "base_x": 87.0, "base_y": 12.0},
    {"player_id": "HSC_25", "name": "Manuel Adeyemi", "jersey_number": 25, "role": "DF", "base_x": 90.0, "base_y": 26.0},
    {"player_id": "HSC_03", "name": "Ruben Duarte", "jersey_number": 3, "role": "DF", "base_x": 90.0, "base_y": 42.0},
    {"player_id": "HSC_24", "name": "Josip Grbic", "jersey_number": 24, "role": "DF", "base_x": 87.0, "base_y": 56.0},
    {"player_id": "HSC_16", "name": "Rodrigo Vale", "jersey_number": 16, "role": "MF", "base_x": 77.0, "base_y": 34.0},
    {"player_id": "HSC_17", "name": "Karel Devos", "jersey_number": 17, "role": "MF", "base_x": 67.0, "base_y": 42.0},
    {"player_id": "HSC_20", "name": "Bernardo Santoro", "jersey_number": 20, "role": "MF", "base_x": 67.0, "base_y": 26.0},
    {"player_id": "HSC_47", "name": "Phil Fenton", "jersey_number": 47, "role": "FW", "base_x": 59.0, "base_y": 12.0},
    {"player_id": "HSC_09", "name": "Anders Hagen", "jersey_number": 9, "role": "FW", "base_x": 52.8, "base_y": 34.0},
    {"player_id": "HSC_11", "name": "Jeremy Dukes", "jersey_number": 11, "role": "FW", "base_x": 59.0, "base_y": 56.0},
]


# Substitutes. They are not on the pitch at kick-off; the simulator brings them on
# in place of the listed starter (their "slot"), so they take over that starter's
# tactical role. Goalkeepers are never substituted.
NORTHBRIDGE_BENCH = [
    {"player_id": "NBL_09", "name": "Jonas Jessup", "jersey_number": 9, "role": "FW"},
    {"player_id": "NBL_19", "name": "Lars Tordal", "jersey_number": 19, "role": "FW"},
    {"player_id": "NBL_23", "name": "Mikel Maddox", "jersey_number": 23, "role": "MF"},
    {"player_id": "NBL_33", "name": "Rico Calloway", "jersey_number": 33, "role": "DF"},
]

AWAY_BENCH = [
    {"player_id": "HSC_19", "name": "Julian Alcott", "jersey_number": 19, "role": "FW"},
    {"player_id": "HSC_26", "name": "Savio Neves", "jersey_number": 26, "role": "FW"},
    {"player_id": "HSC_08", "name": "Mateo Kovar", "jersey_number": 8, "role": "MF"},
    {"player_id": "HSC_06", "name": "Nathan Ames", "jersey_number": 6, "role": "DF"},
]

BENCH_BY_ID: Dict[str, Dict[str, Any]] = {p["player_id"]: p for p in NORTHBRIDGE_BENCH + AWAY_BENCH}

# (team, starter slot being replaced, substitute, planned minute). A few minutes of
# jitter are added per seed so the timing differs between simulations.
SUBSTITUTION_PLAN = [
    ("home", "NBL_29", "NBL_09", 58), ("home", "NBL_11", "NBL_19", 64),
    ("home", "NBL_05", "NBL_23", 72), ("home", "NBL_12", "NBL_33", 80),
    ("away", "HSC_11", "HSC_26", 60), ("away", "HSC_09", "HSC_19", 66),
    ("away", "HSC_17", "HSC_08", 74), ("away", "HSC_24", "HSC_06", 82),
]

PITCH_LENGTH = 105.0
PITCH_WIDTH = 68.0
HALF_TIME_SEC = 2700.0
SECOND_HALF_KICKOFF_FRAMES = 375


class MatchGenerator:
    """
    Simulates high-fidelity 25Hz football match tracking telemetry.
    Maintains full tactical state for 22 players and 1 ball, executing passes,
    tackles, shots, turnovers, and pressure events.
    """

    def __init__(
        self,
        match_id: str = "IGS_2026_NBL_HSC",
        frame_rate: int = 25,
        start_clock_sec: float = 0.0,
        events_file: Optional[str] = None,
        seed: int = 0,
    ):
        self.match_id = match_id
        self.seed = int(seed)
        self._rng = random.Random(self.seed)
        self.data_provenance = "synthetic_simulation"
        self.frame_rate = frame_rate
        self.dt = 1.0 / frame_rate
        self.start_clock_sec = float(start_clock_sec)
        self.physics = PhysicsEngine()

        self.frame_index = 0
        self.elapsed_sec = self.start_clock_sec
        self.period = 1
        self.base_time = datetime(2026, 4, 18, 16, 30, 0, tzinfo=timezone.utc)

        # Initialize ball at center spot
        self.ball = BallState(
            x=52.5,
            y=34.0,
            z=0.0,
            vx=0.0,
            vy=0.0,
            vz=0.0,
            speed_kmh=0.0,
            possession_team="home",
            possessed_by_player_id="NBL_29",
            status="in_play",
        )

        # Squads: 22 starters, replaced over time by substitutions and red cards.
        self.players: Dict[str, PlayerState] = {}
        self.player_anchors: Dict[str, Tuple[float, float]] = {}
        self.slot_of: Dict[str, str] = {}
        self.sent_off: Set[str] = set()
        self.subbed_off: Set[str] = set()
        self.yellow_counts: Dict[str, int] = {}
        self._reset_squads()

        # Discipline and substitutions use their own random stream so adding them
        # does not disturb how open play is sampled.
        self._aux_rng = random.Random(self.seed * 7919 + 13)
        self._queued_events: List[Dict[str, Any]] = []
        self._sub_plan = self._build_sub_plan()
        self._last_stoppage_frame = -10_000
        self._second_half_started = False
        self._kickoff_end_frame = SECOND_HALF_KICKOFF_FRAMES

        # Events queue
        self.events: List[Dict[str, Any]] = []
        self._replay_events = events_file is not None
        self._event_sequence = 0
        self.active_event_id: Optional[str] = None
        self.triggered_event_ids: Set[str] = set()
        self.active_pass_trajectory: Optional[Dict[str, Any]] = None
        self.possession_frames: int = 0
        self._next_action_after = 90
        self._load_events(events_file)

    # ------------------------------------------------------------------
    # Squads, sides and output orientation
    # ------------------------------------------------------------------

    def _reset_squads(self) -> None:
        """Puts the 22 starters back on the pitch at their kick-off anchors."""
        self.players = {}
        self.player_anchors = {}
        self.slot_of = {}
        self.sent_off = set()
        self.subbed_off = set()
        self.yellow_counts = {}
        for roster, team in ((NORTHBRIDGE_ROSTER, "home"), (AWAY_ROSTER, "away")):
            for p in roster:
                pid = p["player_id"]
                self.players[pid] = PlayerState(
                    player_id=pid,
                    team=team,
                    jersey_number=p["jersey_number"],
                    name=p["name"],
                    role=p["role"],
                    x=p["base_x"],
                    y=p["base_y"],
                    vx=0.0,
                    vy=0.0,
                    speed_kmh=0.0,
                    is_visible=True,
                )
                self.player_anchors[pid] = (p["base_x"], p["base_y"])
                self.slot_of[pid] = pid

    def _build_sub_plan(self) -> List[Dict[str, Any]]:
        plan = []
        jitter = random.Random(self.seed * 104729 + 7)
        for team, off_slot, on_id, minute in SUBSTITUTION_PLAN:
            due = (minute + jitter.uniform(-3.0, 3.0)) * 60.0
            plan.append({"team": team, "off_slot": off_slot, "on_id": on_id, "due_sec": due})
        plan.sort(key=lambda item: item["due_sec"])
        return plan

    def _slot_player_id(self, slot: str) -> Optional[str]:
        """Player currently occupying a starter's slot (the starter or his replacement)."""
        for pid, owner in self.slot_of.items():
            if owner == slot and pid in self.players:
                return pid
        prefix = slot.split("_")[0]
        for pid, player in self.players.items():
            if pid.startswith(prefix) and player.role != "GK":
                return pid
        return None

    def attacks_right(self, team: str) -> bool:
        """True when the team attacks towards x = 105 in the current period.

        The simulation is carried out with the home side always attacking +x. From the
        second half the teams have changed ends, so everything that leaves the
        generator (frames, events) is rotated 180 degrees about the centre spot.
        """
        home_right = self.period != 2
        return home_right if team in ("home", "Northbridge Lions") else not home_right

    def _out_xy(self, x: float, y: float) -> Tuple[float, float]:
        if self.period == 2:
            return PITCH_LENGTH - x, PITCH_WIDTH - y
        return x, y

    def _mirror_state(self, data: Dict[str, Any]) -> Dict[str, Any]:
        out = dict(data)
        for key, extent in (("x", PITCH_LENGTH), ("y", PITCH_WIDTH)):
            if out.get(key) is not None:
                out[key] = round(extent - float(out[key]), 2)
        for key in ("vx", "vy"):
            if out.get(key) is not None:
                out[key] = round(-float(out[key]), 3)
        return out

    def export_state(self) -> Tuple[Dict[str, Any], List[Dict[str, Any]]]:
        """Ball and player dictionaries in pitch coordinates for the current period."""
        ball = self.ball.to_dict()
        players = [p.to_dict() for p in self.players.values()]
        if self.period == 2:
            ball = self._mirror_state(ball)
            players = [self._mirror_state(p) for p in players]
        return ball, players

    def _start_second_half(self) -> None:
        """Half-time: teams change ends and the away side kicks off."""
        self._second_half_started = True
        self.active_pass_trajectory = None
        for pid, player in self.players.items():
            player.x, player.y = self.player_anchors[pid]
            player.vx = player.vy = 0.0
            player.speed_kmh = 0.0
        kicker = self._slot_player_id("HSC_09")
        self.ball.x, self.ball.y, self.ball.z = 52.5, 34.0, 0.0
        self.ball.vx = self.ball.vy = self.ball.vz = 0.0
        self.ball.speed_kmh = 0.0
        self.ball.possession_team = "away"
        self.ball.possessed_by_player_id = kicker
        self.ball.status = "in_play"
        self.possession_frames = 0
        self._next_action_after = self._rng.randint(75, 110)
        self._kickoff_end_frame = self.frame_index + SECOND_HALF_KICKOFF_FRAMES

    def _in_kickoff_phase(self) -> bool:
        return self.get_clock_string() == "00:00" or self.frame_index < self._kickoff_end_frame

    def _apply_substitution(self, off_id: str, on_entry: Dict[str, Any]) -> Optional[PlayerState]:
        """Swaps a player on the pitch for a substitute; the substitute inherits the slot."""
        off = self.players.get(off_id)
        if off is None:
            return None
        incoming = PlayerState(
            player_id=on_entry["player_id"], team=off.team, jersey_number=on_entry["jersey_number"],
            name=on_entry["name"], role=on_entry["role"], x=off.x, y=off.y, vx=0.0, vy=0.0,
            speed_kmh=0.0, is_visible=True,
        )
        ordered = list(self.players.items())
        self.players = {}
        for key, value in ordered:
            if key == off_id:
                self.players[incoming.player_id] = incoming
            else:
                self.players[key] = value
        self.slot_of[incoming.player_id] = self.slot_of.get(off_id, off_id)
        self.player_anchors[incoming.player_id] = self.player_anchors[off_id]
        self.subbed_off.add(off_id)
        return incoming

    def _send_off(self, player_id: str) -> None:
        self.players.pop(player_id, None)
        self.sent_off.add(player_id)

    def sync_squads(self, events: List[Dict[str, Any]], up_to_frame: int) -> None:
        """Rebuilds who is on the pitch at a frame from the recorded substitutions and red cards."""
        self._reset_squads()
        for event in sorted(events, key=lambda e: int(e.get("frame_index", 0))):
            if int(event.get("frame_index", 0)) > up_to_frame:
                break
            kind = event.get("event_type")
            if kind == "substitution":
                on_entry = BENCH_BY_ID.get(str(event.get("player_id")))
                if on_entry and self._apply_substitution(str(event.get("secondary_player_id")), on_entry):
                    self._sub_plan = [s for s in self._sub_plan if s["on_id"] != on_entry["player_id"]]
            elif kind == "card":
                pid = str(event.get("player_id"))
                sub_type = str(event.get("sub_type", ""))
                if "yellow" in sub_type:
                    self.yellow_counts[pid] = self.yellow_counts.get(pid, 0) + 1
                if "red" in sub_type or sub_type == "second_yellow":
                    self._send_off(pid)

    def _load_events(self, events_file: Optional[str] = None) -> None:
        """
        Loads an explicitly requested legacy event replay. The default match is
        generated from simulated play; it must not silently load a hand-authored
        fixture as its source of truth.
        """
        if events_file and os.path.exists(events_file):
            try:
                with open(events_file, "r", encoding="utf-8") as f:
                    self.events = json.load(f)
                for event in self.events:
                    if isinstance(event, dict):
                        event.setdefault("data_provenance", self.data_provenance)
            except Exception:
                self.events = []
        else:
            self.events = []

    def start_pass_trajectory(
        self,
        start_x: float,
        start_y: float,
        end_x: float,
        end_y: float,
        target_player_id: Optional[str] = None,
        target_team: Optional[str] = None,
        is_aerial: bool = False,
        h_peak: float = 0.0,
        speed_kmh: float = 65.0,
        min_steps: int = 10,
        event_id: Optional[str] = None,
        is_goal: bool = False,
    ) -> Dict[str, Any]:
        """
        Initializes a continuous multi-step pass trajectory with >= 10 steps.
        Enforces physical bounds, smooth 2D interpolation, and 3D parabolic elevation.
        """
        dx = float(end_x) - float(start_x)
        dy = float(end_y) - float(start_y)
        dist = math.hypot(dx, dy)

        speed = max(20.0, min(140.0, float(speed_kmh)))
        nominal_steps = int(round((90.0 * dist) / speed))
        speed_cap_steps = int(math.ceil((90.0 * dist) / 145.0))
        total_steps = max(int(min_steps), 10, nominal_steps, speed_cap_steps)

        if is_aerial and h_peak <= 0.0:
            h_peak = min(6.0, max(1.5, 0.06 * dist + 1.2))

        # Position ball at start of trajectory
        self.ball.x = round(float(start_x), 2)
        self.ball.y = round(float(start_y), 2)
        self.ball.z = 0.0
        self.ball.possession_team = target_team
        self.ball.possessed_by_player_id = None
        self.ball.status = "in_play"

        self.active_pass_trajectory = {
            "start_x": float(start_x),
            "start_y": float(start_y),
            "end_x": float(end_x),
            "end_y": float(end_y),
            "total_steps": int(total_steps),
            "current_step": 0,
            "is_aerial": bool(is_aerial),
            "max_elevation_z": float(h_peak if is_aerial else 0.0),
            "speed_kmh": float(speed),
            "target_player_id": target_player_id,
            "target_team": target_team,
            "event_id": event_id,
            "is_goal": bool(is_goal),
        }
        return self.active_pass_trajectory

    def get_clock_string(self) -> str:
        """
        Formats current elapsed match time as MM:SS string.
        """
        total_seconds = int(self.elapsed_sec)
        minutes = total_seconds // 60
        seconds = total_seconds % 60
        return f"{minutes:02d}:{seconds:02d}"

    def get_timestamp_string(self) -> str:
        """
        Returns ISO-8601 formatted timestamp string.
        """
        current_time = self.base_time + timedelta(seconds=self.elapsed_sec)
        return current_time.isoformat()

    def step(self) -> Dict[str, Any]:
        """
        Advances the simulation by 1 frame (dt = 0.04s) and returns a TelemetryFrame dict.
        """
        self.frame_index += 1
        # Derive time from the integer frame counter to avoid cumulative float
        # drift over a full match (e.g. 1,000 frames must be exactly 40 seconds).
        self.elapsed_sec = self.start_clock_sec + self.frame_index / float(self.frame_rate)

        # Check match period (second half starts after 45 minutes)
        if self.elapsed_sec >= HALF_TIME_SEC:
            self.period = 2
        else:
            self.period = 1
        if self.period == 2 and not self._second_half_started and not self._replay_events:
            self._start_second_half()

        # Replay mode is retained only for explicitly supplied legacy fixtures.
        # In generated mode an event is emitted by the action that creates it.
        clock_str = self.get_clock_string()
        self.active_event_id = None
        if self._replay_events:
            for ev in self.events:
                ev_frame = ev.get("frame_index", -999)
                if ev.get("clock") == clock_str or abs(ev_frame - self.frame_index) < 25:
                    self.active_event_id = ev.get("event_id")
                    ev_id = ev.get("event_id")
                    if ev_id not in self.triggered_event_ids and abs(ev_frame - self.frame_index) <= 2:
                        self.triggered_event_ids.add(ev_id)
                        self._apply_event_trigger(ev)
                    break

        # On the opening kickoff frame (frame 1), players start exactly at calibrated base positions
        if self.frame_index == 1:
            for pid, player in self.players.items():
                base_x, base_y = self.player_anchors[pid]
                player.x = base_x
                player.y = base_y
                player.vx = 0.0
                player.vy = 0.0
                player.speed_kmh = 0.0

        # A goal ends the prior trajectory. Restart from the centre with the
        # conceding side in possession so the match continues naturally.
        if self.ball.status == "goal" and self.active_pass_trajectory is None:
            conceding_team = "away" if self.ball.possession_team == "home" else "home"
            restart_id = self._slot_player_id("HSC_09" if conceding_team == "away" else "NBL_29")
            self.ball.x, self.ball.y, self.ball.z = 52.5, 34.0, 0.0
            self.ball.vx = self.ball.vy = self.ball.vz = 0.0
            self.ball.speed_kmh = 0.0
            self.ball.possession_team = conceding_team
            self.ball.possessed_by_player_id = restart_id
            self.ball.status = "in_play"
            self.possession_frames = 0
            self._next_action_after = self._rng.randint(75, 110)

        # Advance active pass trajectory or step standard ball physics
        if self.active_pass_trajectory is not None:
            traj = self.active_pass_trajectory
            traj["current_step"] += 1
            k = traj["current_step"]
            N = traj["total_steps"]
            u = min(1.0, k / max(1, N))
            u_prev = (k - 1) / max(1, N)

            # Linear horizontal interpolation
            new_x = traj["start_x"] + u * (traj["end_x"] - traj["start_x"])
            new_y = traj["start_y"] + u * (traj["end_y"] - traj["start_y"])
            prev_x = traj["start_x"] + u_prev * (traj["end_x"] - traj["start_x"])
            prev_y = traj["start_y"] + u_prev * (traj["end_y"] - traj["start_y"])

            # Parabolic 3D ballistic elevation
            if traj["is_aerial"]:
                new_z = PhysicsEngine.compute_ballistic_elevation(u, traj["max_elevation_z"])
                prev_z = PhysicsEngine.compute_ballistic_elevation(u_prev, traj["max_elevation_z"])
            else:
                new_z = 0.0
                prev_z = 0.0

            dt = self.dt
            vx = (new_x - prev_x) / dt
            vy = (new_y - prev_y) / dt
            vz = (new_z - prev_z) / dt
            speed_mps = math.sqrt(vx * vx + vy * vy + vz * vz)
            speed_kmh = min(150.0, max(0.0, speed_mps * 3.6))

            self.ball.x = round(new_x, 2)
            self.ball.y = round(new_y, 2)
            self.ball.z = round(new_z, 2)
            self.ball.vx = round(vx, 3)
            self.ball.vy = round(vy, 3)
            self.ball.vz = round(vz, 3)
            self.ball.speed_kmh = round(speed_kmh, 2)

            if k < N:
                # In flight: possession unassigned / transferring
                self.ball.possessed_by_player_id = None
                self.ball.possession_team = traj["target_team"]
                self.ball.status = "in_play"
            else:
                # Trajectory completed at step N
                self.ball.x = round(traj["end_x"], 2)
                self.ball.y = round(traj["end_y"], 2)
                self.ball.z = 0.0
                self.ball.vx = 0.0
                self.ball.vy = 0.0
                self.ball.vz = 0.0
                self.ball.speed_kmh = 0.0
                self.ball.possessed_by_player_id = traj["target_player_id"]
                self.ball.possession_team = traj["target_team"]
                self.ball.status = "goal" if traj.get("is_goal") else "in_play"
                if traj.get("is_goal"):
                    # The ball is in the net at this frame; the next step will
                    # restart play for the other side.
                    self.ball.possession_team = traj.get("target_team")
                    self.ball.possessed_by_player_id = None
                elif not self._replay_events and traj.get("target_player_id") and traj.get("target_team"):
                    source_event = next(
                        (event for event in reversed(self.events) if event.get("event_id") == traj.get("event_id")),
                        None,
                    )
                    receiver = self.players.get(traj["target_player_id"])
                    if (
                        receiver
                        and source_event
                        and source_event.get("team") != self._team_label(receiver.team)
                    ):
                        self._record_simulated_event(
                            "turnover", receiver, "won",
                            secondary=self.players.get(source_event.get("player_id")),
                            sub_type="intercepted_pass",
                            context=f"{receiver.name} intercepts a pass and wins possession.",
                            defenders_nearby=1,
                        )
                self.active_pass_trajectory = None
                self.possession_frames = 0
        elif self.frame_index > 1:
            possessor = self.players.get(self.ball.possessed_by_player_id) if self.ball.possessed_by_player_id else None
            if possessor:
                self.possession_frames += 1
                # Ball is carried with possessor
                lead_dir = 1.0 if possessor.team == "home" else -1.0
                self.ball.x = round(float(possessor.x + 0.35 * lead_dir), 2)
                self.ball.y = round(float(possessor.y), 2)
                self.ball.z = 0.0
                self.ball.vx = possessor.vx
                self.ball.vy = possessor.vy
                self.ball.speed_kmh = possessor.speed_kmh
                self.ball.status = "in_play"

                is_kickoff_phase = self._in_kickoff_phase()
                if self.possession_frames >= self._next_action_after and not is_kickoff_phase and not self._replay_events:
                    self._simulate_possession_action(possessor)
            else:
                self.physics.step_ball(self.ball, self.dt)

        # Dynamic tactical positioning (Master Tactical Positioning System)
        if self.frame_index > 1:
            ball_x = self.ball.x
            ball_y = self.ball.y
            is_kickoff_phase = self._in_kickoff_phase()

            # Look ahead for upcoming event to initiate seamless anticipation runs
            upcoming_ev = None
            if self._replay_events:
                for ev in self.events:
                    ev_frame = ev.get("frame_index", -999)
                    if ev_frame > self.frame_index:
                        upcoming_ev = ev
                        break

            curr_event = None
            if self.active_event_id:
                curr_event = next((e for e in self.events if e.get("event_id") == self.active_event_id), None)

            # Compute master tactical positions for all 22 players
            tactical_targets = self.compute_tactical_player_targets(
                ball_x, ball_y, self.ball.possession_team or "home",
                active_event=curr_event,
                is_kickoff=is_kickoff_phase
            )

            # Update all 22 players
            frames_to_upcoming = (upcoming_ev.get("frame_index", -999) - self.frame_index) if upcoming_ev else 9999
            up_pid = upcoming_ev.get("player_id") if upcoming_ev else None
            up_sec_pid = upcoming_ev.get("secondary_player_id") if upcoming_ev else None
            up_loc_x = upcoming_ev.get("location_x") if upcoming_ev else None
            up_loc_y = upcoming_ev.get("location_y") if upcoming_ev else None

            for pid, player in self.players.items():
                if is_kickoff_phase:
                    target_x, target_y = self.player_anchors[pid]
                elif self.active_pass_trajectory is not None and player.player_id == self.active_pass_trajectory.get("target_player_id"):
                    # Target receiver runs toward pass landing coordinates
                    target_x = self.active_pass_trajectory["end_x"]
                    target_y = self.active_pass_trajectory["end_y"]
                elif player.player_id == self.ball.possessed_by_player_id and up_loc_x is not None and up_loc_y is not None:
                    # Current ball carrier smoothly progresses towards upcoming event location
                    target_x = up_loc_x
                    target_y = up_loc_y
                elif frames_to_upcoming <= 175 and up_loc_x is not None and up_loc_y is not None and pid == up_pid:
                    # Upcoming primary actor smoothly runs towards action location
                    target_x = up_loc_x
                    target_y = up_loc_y
                elif frames_to_upcoming <= 175 and pid == up_sec_pid and upcoming_ev:
                    # Upcoming secondary player smoothly positions for the action
                    if upcoming_ev.get("end_x") is not None and upcoming_ev.get("end_y") is not None and upcoming_ev.get("event_type") in ["pass", "shot"]:
                        target_x = upcoming_ev["end_x"]
                        target_y = upcoming_ev["end_y"]
                    elif up_loc_x is not None and up_loc_y is not None:
                        opp_dir = 1.0 if player.team == "home" else -1.0
                        target_x = up_loc_x + 1.2 * opp_dir
                        target_y = up_loc_y
                    else:
                        target_x, target_y = tactical_targets.get(pid, (player.x, player.y))
                else:
                    target_x, target_y = tactical_targets.get(pid, (player.x, player.y))

                # Strict pitch half confinement during kickoff phase
                if is_kickoff_phase:
                    if player.team == "home":
                        target_x = min(52.5, target_x)
                    else:
                        target_x = max(52.5, target_x)
                    if player.role == "GK":
                        if player.team == "home":
                            target_x = max(1.0, min(5.2, target_x))
                            target_y = max(25.0, min(43.0, target_y))
                        else:
                            target_x = max(99.8, min(104.0, target_x))
                            target_y = max(25.0, min(43.0, target_y))

                # Clamp targets to pitch bounds
                target_x, target_y = self.physics.clamp_pitch_bounds(target_x, target_y)

                # Step player physics with sprint limits (max 36 km/h)
                self.physics.step_player(player, target_x, target_y, dt=self.dt, max_speed_kmh=36.0)

                # Strict clamp player positions to halves during kickoff phase
                if is_kickoff_phase:
                    if player.team == "home" and player.x > 52.5:
                        player.x = 52.5
                    elif player.team == "away" and player.x < 52.5:
                        player.x = 52.5
                    if player.role == "GK":
                        if player.team == "home":
                            player.x = min(5.5, max(0.0, player.x))
                            player.y = min(43.16, max(24.84, player.y))
                        else:
                            player.x = max(99.5, min(105.0, player.x))
                            player.y = min(43.16, max(24.84, player.y))

        # Cards and substitutions are emitted in a step of their own, so each frame
        # carries at most one event.
        if not self._replay_events and self.active_event_id is None:
            self._emit_discipline_or_substitution()

        # Assemble and validate frame payload
        ball_state, player_states = self.export_state()
        frame_payload = {
            "frame_id": self.frame_index,
            "match_id": self.match_id,
            "data_provenance": self.data_provenance,
            "synthetic_data_notice": SYNTHETIC_DATA_NOTICE,
            "timestamp": self.get_timestamp_string(),
            "period": self.period,
            "clock": self.get_clock_string(),
            "pitch_dimensions": {
                "length": 105.0,
                "width": 68.0,
            },
            "ball": ball_state,
            "players": player_states,
            "active_event_id": self.active_event_id,
        }

        return frame_payload

    @staticmethod
    def _team_label(team: str) -> str:
        return "Northbridge Lions" if team == "home" else "Harbourside City"

    def _record_simulated_event(
        self,
        event_type: str,
        player: PlayerState,
        outcome: str,
        *,
        secondary: Optional[PlayerState] = None,
        end_x: Optional[float] = None,
        end_y: Optional[float] = None,
        sub_type: str = "",
        context: str = "",
        pass_distance: Optional[float] = None,
        ball_speed: Optional[float] = None,
        xt_gained: float = 0.0,
        defenders_nearby: int = 0,
        at: Optional[Tuple[float, float]] = None,
        frame_offset: int = 0,
    ) -> Dict[str, Any]:
        """Record one action from the current simulated state.

        Positions are given in the simulation's frame (home always attacking +x) and
        written out in real pitch coordinates for the current period.
        """
        self._event_sequence += 1
        event_id = f"SIM_{self.seed}_{self._event_sequence:06d}"
        x, y = (float(at[0]), float(at[1])) if at else (float(self.ball.x), float(self.ball.y))
        if pass_distance is None and end_x is not None and end_y is not None:
            pass_distance = math.hypot(float(end_x) - x, float(end_y) - y)
        out_x, out_y = self._out_xy(x, y)
        if end_x is not None and end_y is not None:
            end_x, end_y = self._out_xy(float(end_x), float(end_y))
        if event_type in ("foul", "goal"):
            self._last_stoppage_frame = self.frame_index
        distance = float(pass_distance or 0.0)
        pdr = max(0.0, min(100.0, 12.0 + distance * 1.25 + defenders_nearby * 8.0))
        event = {
            "event_id": event_id,
            "match_id": self.match_id,
            "event_type": event_type,
            "sub_type": sub_type or event_type,
            "period": self.period,
            "clock": self.get_clock_string(),
            "frame_index": self.frame_index + frame_offset,
            "team": self._team_label(player.team),
            "player_id": player.player_id,
            "player_name": player.name,
            "secondary_player_id": secondary.player_id if secondary else None,
            "secondary_player_name": secondary.name if secondary else None,
            "location_x": round(out_x, 2),
            "location_y": round(out_y, 2),
            "end_x": round(float(end_x), 2) if end_x is not None else None,
            "end_y": round(float(end_y), 2) if end_y is not None else None,
            "outcome": outcome,
            "tactical_metrics": {
                "pass_difficulty": round(pdr, 1),
                "ball_speed_kmh": round(float(ball_speed or 0.0), 1),
                "possession_change": bool(
                    event_type == "turnover" or (event_type == "tackle" and outcome == "won")
                ),
                "chaos_index": round(min(100.0, 18.0 + defenders_nearby * 12.0 + (28.0 if event_type in {"tackle", "turnover", "goal"} else 0.0)), 1),
                "xt_gained": round(float(xt_gained), 4),
                "defenders_in_corridor": int(defenders_nearby),
                "defenders_in_cone": int(defenders_nearby),
            },
            "context": context,
            "data_provenance": self.data_provenance,
        }
        self.events.append(event)
        self.active_event_id = event_id
        return event

    PRESSURE_EVENT_PROBABILITY = 0.12
    YELLOW_CARD_PROBABILITY = 0.24
    STRAIGHT_RED_PROBABILITY = 0.006

    def _maybe_queue_card(self, offender: PlayerState, fouled: PlayerState) -> None:
        """Decides whether a foul is punished; the card follows in the next frame."""
        if offender.role == "GK":
            return
        roll = self._aux_rng.random()
        if self.yellow_counts.get(offender.player_id, 0) >= 1:
            # A player already on a yellow is more careful, and referees are slower to send him off.
            roll = roll if roll < self.STRAIGHT_RED_PROBABILITY else roll / 0.4
        if roll < self.STRAIGHT_RED_PROBABILITY:
            kind = "red_card"
        elif roll < self.STRAIGHT_RED_PROBABILITY + self.YELLOW_CARD_PROBABILITY:
            kind = "second_yellow" if self.yellow_counts.get(offender.player_id, 0) >= 1 else "yellow_card"
        else:
            return
        self._queued_events.append({
            "type": "card", "kind": kind, "player_id": offender.player_id,
            "fouled_id": fouled.player_id, "due_frame": self.frame_index + 1,
        })

    def _emit_discipline_or_substitution(self) -> None:
        """Emits one queued card, or one due substitution at the next stoppage."""
        if self._queued_events and self._queued_events[0]["due_frame"] <= self.frame_index:
            item = self._queued_events.pop(0)
            if item.get("type") == "pressure":
                self._emit_pressure(item)
            else:
                self._emit_card(item)
            return
        if self._queued_events or self._in_kickoff_phase() or self.ball.status == "goal":
            return
        if self.active_pass_trajectory is not None or not self._sub_plan:
            return
        due = self._sub_plan[0]
        if self.elapsed_sec < due["due_sec"]:
            return
        at_stoppage = 2 <= self.frame_index - self._last_stoppage_frame <= 60
        if not at_stoppage and self.elapsed_sec < due["due_sec"] + 300.0:
            return
        self._sub_plan.pop(0)
        off_id = self._slot_player_id(due["off_slot"])
        off = self.players.get(off_id) if off_id else None
        # Skip if the starter has already left or is the one on the ball.
        if off is None or off.player_id == self.ball.possessed_by_player_id or off.role == "GK":
            return
        on_entry = BENCH_BY_ID[due["on_id"]]
        incoming = self._apply_substitution(off.player_id, on_entry)
        if incoming is None:
            return
        touchline_y = 0.0 if off.y < PITCH_WIDTH / 2 else PITCH_WIDTH
        self._record_simulated_event(
            "substitution", incoming, "completed", secondary=off, sub_type="tactical_change",
            context=f"{incoming.name} replaces {off.name} for {self._team_label(off.team)}.",
            at=(off.x, touchline_y),
        )

    def _emit_pressure(self, item: Dict[str, Any]) -> None:
        presser = self.players.get(item["player_id"])
        target = self.players.get(item["target_id"])
        if presser is None or target is None:
            return
        self._record_simulated_event(
            "pressure", presser, "applied", secondary=target, sub_type="press",
            context=f"{presser.name} presses {target.name} at {item['distance']:.1f}m.",
            defenders_nearby=int(item["defenders"]),
        )

    def _emit_card(self, item: Dict[str, Any]) -> None:
        player = self.players.get(item["player_id"])
        if player is None:
            return
        fouled = self.players.get(item["fouled_id"])
        kind = item["kind"]
        label = {"yellow_card": "a yellow card", "second_yellow": "a second yellow card and is sent off",
                 "red_card": "a straight red card and is sent off"}[kind]
        self._record_simulated_event(
            "card", player, "red" if kind != "yellow_card" else "yellow", secondary=fouled,
            sub_type=kind, at=(player.x, player.y),
            context=f"{player.name} is shown {label} for the foul"
                    + (f" on {fouled.name}." if fouled else "."),
        )
        if kind == "yellow_card":
            self.yellow_counts[player.player_id] = self.yellow_counts.get(player.player_id, 0) + 1
        else:
            if kind == "second_yellow":
                self.yellow_counts[player.player_id] = self.yellow_counts.get(player.player_id, 0) + 1
            self._send_off(player.player_id)

    def _simulate_possession_action(self, possessor: PlayerState) -> None:
        """Choose and execute an action from current possession and pitch state."""
        # This is a delay measured from the beginning of each possession, not
        # an absolute counter carried across possessions.
        self._next_action_after = self._rng.randint(75, 110)
        opponents = [p for p in self.players.values() if p.team != possessor.team]
        opponents.sort(key=lambda p: math.hypot(p.x - possessor.x, p.y - possessor.y))
        nearest_defender = opponents[0] if opponents else None
        defender_distance = math.hypot(nearest_defender.x - possessor.x, nearest_defender.y - possessor.y) if nearest_defender else 99.0
        close_defenders = sum(
            1 for p in opponents
            if math.hypot(p.x - possessor.x, p.y - possessor.y) <= 8.0
        )
        attack_progress = possessor.x / 105.0 if possessor.team == "home" else (105.0 - possessor.x) / 105.0
        goal_x = 105.0 if possessor.team == "home" else 0.0
        goal_distance = math.hypot(goal_x - possessor.x, 34.0 - possessor.y)
        teammates = [
            p for p in self.players.values()
            if p.team == possessor.team and p.player_id != possessor.player_id and p.role != "GK"
        ]
        # Prefer a forward or open option, but rotate among similarly viable receivers.
        direction = 1.0 if possessor.team == "home" else -1.0
        teammates.sort(key=lambda p: (
            math.hypot(p.x - possessor.x, p.y - possessor.y) * 0.55
            - max(0.0, (p.x - possessor.x) * direction) * 0.30
            + close_defenders * 0.0
        ))
        if not teammates:
            return
        receiver = self._rng.choice(teammates[: min(4, len(teammates))])
        pass_distance = math.hypot(receiver.x - self.ball.x, receiver.y - self.ball.y)

        # A shot is attempted only in the attacking half, with frequency increasing
        # as the carrier approaches goal. Its result is sampled from location and pressure.
        shot_probability = max(0.0, min(0.16, (attack_progress - 0.52) * 0.30))
        if goal_distance < 27.0 and self._rng.random() < shot_probability:
            on_target = self._rng.random() < max(0.28, min(0.78, 0.62 - close_defenders * 0.07))
            goal_chance = max(0.10, min(0.42, 0.56 - goal_distance * 0.010 - close_defenders * 0.030))
            scored = on_target and self._rng.random() < goal_chance
            keeper_id = "HSC_31" if possessor.team == "home" else "NBL_01"
            keeper = self.players[keeper_id]
            end_y = max(29.5, min(38.5, 34.0 + self._rng.uniform(-4.0, 4.0)))
            if not on_target:
                end_y = max(26.0, min(42.0, end_y + self._rng.choice([-1.0, 1.0]) * self._rng.uniform(3.0, 7.0)))
            speed = self._rng.uniform(65.0, 112.0)
            event_type = "goal" if scored else "shot"
            outcome = "goal" if scored else ("saved" if on_target else "off_target")
            xt = max(0.0, min(0.8, (0.8 - goal_distance / 50.0) * (1.0 - close_defenders * 0.12)))
            self._record_simulated_event(
                event_type, possessor, outcome, secondary=keeper,
                end_x=goal_x, end_y=end_y, sub_type="shot",
                context=f"{possessor.name} shoots from {goal_distance:.1f}m with {close_defenders} nearby defender(s).",
                pass_distance=goal_distance, ball_speed=speed, xt_gained=xt,
                defenders_nearby=close_defenders,
            )
            self.start_pass_trajectory(
                self.ball.x, self.ball.y, goal_x, end_y,
                target_player_id=None if scored else keeper.player_id,
                target_team=possessor.team if scored else keeper.team,
                is_aerial=True, h_peak=1.6, speed_kmh=speed,
                min_steps=12, event_id=self.active_event_id, is_goal=scored,
            )
            self.possession_frames = 0
            self._next_action_after = self._rng.randint(75, 110)
            return

        # Close pressure can result in a genuine turnover. Other pressure moments
        # are recorded without claiming possession changed.
        if nearest_defender and defender_distance <= 4.0 and self._rng.random() < 0.08:
            self._record_simulated_event(
                "foul", nearest_defender, "foul_conceded",
                secondary=possessor, sub_type="tactical_foul",
                context=f"{nearest_defender.name} fouls {possessor.name} while challenging for possession.",
                defenders_nearby=close_defenders,
            )
            self._maybe_queue_card(nearest_defender, possessor)
            self.possession_frames = 0
            self._next_action_after = self._rng.randint(75, 110)
            return
        if nearest_defender and defender_distance <= 5.5 and self._rng.random() < 0.18:
            won = self._rng.random() < 0.58
            # A challenge that does not win the ball is either a failed tackle or sustained
            # pressure. The split uses the auxiliary generator so the match itself is unchanged.
            failed_tackle = (not won) and self._aux_rng.random() < 0.45
            kind = "tackle" if (won or failed_tackle) else "pressure"
            actor = nearest_defender
            self._record_simulated_event(
                kind, actor, "won" if won else ("lost" if failed_tackle else "applied"),
                secondary=possessor,
                sub_type="standing_tackle" if won else ("failed_tackle" if failed_tackle else "press"),
                context=f"{actor.name} closes down {possessor.name} at {defender_distance:.1f}m.",
                defenders_nearby=close_defenders,
            )
            self.possession_frames = 0
            self._next_action_after = self._rng.randint(75, 110)
            if won:
                self.ball.possession_team = actor.team
                self.ball.possessed_by_player_id = actor.player_id
            return

        # Off-ball pressure: a defender closing down the carrier is recorded as a pressure event.
        # It changes nothing in the match, so it uses the auxiliary generator.
        if (
            nearest_defender and defender_distance <= 9.0
            and self._aux_rng.random() < self.PRESSURE_EVENT_PROBABILITY
        ):
            # Emitted on the next frame, like cards, so every frame carries at most one event.
            self._queued_events.append({
                "type": "pressure", "player_id": nearest_defender.player_id,
                "target_id": possessor.player_id, "distance": defender_distance,
                "defenders": close_defenders, "due_frame": self.frame_index + 1,
            })

        pass_speed = self._rng.uniform(38.0, 78.0)
        # Interception chance rises with distance and immediate defensive pressure.
        complete_probability = max(0.48, min(0.96, 0.91 - pass_distance * 0.004 - close_defenders * 0.055))
        completed = self._rng.random() < complete_probability
        receiver_team = possessor.team
        target = receiver
        outcome = "complete" if completed else "incomplete"
        if not completed and nearest_defender:
            target = nearest_defender
            receiver_team = nearest_defender.team
        xt = max(0.0, min(0.25, ((receiver.x - possessor.x) * direction) / 1050.0))
        self._record_simulated_event(
            "pass", possessor, outcome, secondary=target,
            end_x=target.x, end_y=target.y,
            sub_type="aerial_pass" if pass_distance > 28.0 else "ground_pass",
            context=f"{possessor.name} attempts a {pass_distance:.1f}m pass; {close_defenders} defender(s) are within 8m.",
            pass_distance=pass_distance, ball_speed=pass_speed, xt_gained=xt,
            defenders_nearby=close_defenders,
        )
        self.start_pass_trajectory(
            self.ball.x, self.ball.y, target.x, target.y,
            target_player_id=target.player_id, target_team=receiver_team,
            is_aerial=pass_distance > 28.0,
            h_peak=min(5.5, max(1.8, pass_distance * 0.08)) if pass_distance > 28.0 else 0.0,
            speed_kmh=pass_speed, min_steps=12, event_id=self.active_event_id,
        )
        self.possession_frames = 0

    def compute_tactical_player_targets(
        self,
        ball_x: float,
        ball_y: float,
        possession_team: str,
        active_event: Optional[Dict[str, Any]] = None,
        is_kickoff: bool = False,
    ) -> Dict[str, Tuple[float, float]]:
        """
        Master Tactical Positioning System (MTPS):
        Computes realistic positional play coordinates for all 22 players
        based on ball location, attacking progression, phase of play, rest defense,
        and compact low/mid blocks.
        """
        targets: Dict[str, Tuple[float, float]] = {}

        # Normalized progression metrics
        p = max(0.0, min(1.0, float(ball_x) / 105.0))  # Northbridge Lions progression (0.0=own box, 1.0=City box)
        q = max(0.0, min(1.0, (105.0 - float(ball_x)) / 105.0))  # City progression (0.0=own box, 1.0=Northbridge Lions box)
        dy = float(ball_y) - 34.0

        # 1. Northbridge Lions Players (Home)
        if is_kickoff:
            for pid, (bx, by) in self.player_anchors.items():
                if pid.startswith("NBL"):
                    targets[pid] = (bx, by)
        elif possession_team in ["home", "Northbridge Lions"]:
            # Northbridge Lions In Possession (the home manager 3-2-4-1 / 3-2-5 attacking structure)
            # Sweeper Keeper Roark
            targets["NBL_01"] = (max(3.5, min(24.0, 3.5 + 20.0 * p)), 34.0 + 0.10 * dy)
            # Rest Defense CBs (Sandoval & Gabriel)
            cb_x = 14.0 + 44.0 * p
            targets["NBL_02"] = (cb_x + 1.0, 40.0 + 0.18 * dy)
            targets["NBL_06"] = (cb_x - 0.5, 28.0 + 0.18 * dy)
            # Fullbacks (White & Tamblyn)
            targets["NBL_04"] = (max(18.0, min(86.0, 18.0 + 64.0 * p)), 56.0 + 0.12 * dy)
            targets["NBL_12"] = (max(18.0, min(82.0, 18.0 + 60.0 * p)), 14.0 + 0.15 * dy)
            # Midfield Pivot (Pardoe & Rowe)
            targets["NBL_05"] = (max(26.0, min(74.0, 26.0 + 46.0 * p)), 32.0 + 0.20 * dy)
            targets["NBL_41"] = (max(30.0, min(84.0, 30.0 + 52.0 * p)), 38.0 + 0.20 * dy)
            # Playmaker (Olsvik)
            targets["NBL_08"] = (max(36.0, min(92.0, 36.0 + 54.0 * p)), 36.0 + 0.22 * dy)
            # Wingers (Sarpong & Montoya)
            targets["NBL_07"] = (max(44.0, min(98.0, 44.0 + 52.0 * p)), 54.0 + 0.15 * dy)
            targets["NBL_11"] = (max(44.0, min(98.0, 44.0 + 52.0 * p)), 14.0 + 0.15 * dy)
            # Striker (Halvorsen)
            targets["NBL_29"] = (max(50.0, min(100.0, 50.0 + 49.0 * p)), 34.0 + 0.20 * dy)
        else:
            # Northbridge Lions Defending (Compact Block against City attack)
            def_line = 36.0 - 29.5 * q
            # Roark on goal line bisecting angle
            gk_x = max(1.8, min(4.5, 1.8 + 0.04 * max(0.0, float(ball_x) - 10.0)))
            slope = dy / max(1.0, float(ball_x))
            gk_y = max(29.5, min(38.5, 34.0 + slope * gk_x))
            targets["NBL_01"] = (gk_x, gk_y)
            # Back 4
            targets["NBL_04"] = (max(8.0, min(40.0, def_line + 2.0)), 52.0 + 0.20 * dy)
            targets["NBL_02"] = (max(6.5, min(36.0, def_line)), 37.0 + 0.22 * dy)
            targets["NBL_06"] = (max(6.5, min(36.0, def_line)), 31.0 + 0.22 * dy)
            targets["NBL_12"] = (max(8.0, min(40.0, def_line + 2.0)), 16.0 + 0.20 * dy)
            # Midfield Line
            targets["NBL_05"] = (max(14.0, min(48.0, def_line + 8.0)), 32.0 + 0.25 * dy)
            targets["NBL_41"] = (max(14.0, min(48.0, def_line + 9.0)), 38.0 + 0.25 * dy)
            targets["NBL_08"] = (max(20.0, min(56.0, def_line + 15.0)), 36.0 + 0.25 * dy)
            targets["NBL_07"] = (max(22.0, min(65.0, def_line + 14.0)), 50.0 + 0.18 * dy)
            targets["NBL_11"] = (max(22.0, min(65.0, def_line + 14.0)), 18.0 + 0.18 * dy)
            # Lone Striker Outlet
            targets["NBL_29"] = (max(34.0, min(70.0, def_line + 24.0)), 34.0 + 0.20 * dy)

        # 2. Harbourside City Players (Away)
        if is_kickoff:
            for pid, (bx, by) in self.player_anchors.items():
                if pid.startswith("HSC"):
                    targets[pid] = (bx, by)
        elif possession_team in ["away", "Harbourside City"]:
            # Harbourside In Possession (the Harbourside manager 3-2-4-1 attacking structure)
            # Sweeper Keeper Enzo Barreto
            targets["HSC_31"] = (min(101.5, max(81.0, 101.5 - 20.0 * q)), 34.0 + 0.10 * dy)
            # Rest Defense CBs (Duarte & Adeyemi)
            city_cb_x = 91.0 - 44.0 * q
            targets["HSC_03"] = (city_cb_x - 1.0, 40.0 + 0.18 * dy)
            targets["HSC_25"] = (city_cb_x + 0.5, 28.0 + 0.18 * dy)
            # Fullbacks / Inverted (Walden & Grbic)
            targets["HSC_02"] = (min(87.0, max(19.0, 87.0 - 64.0 * q)), 14.0 + 0.15 * dy)
            targets["HSC_24"] = (min(87.0, max(23.0, 87.0 - 60.0 * q)), 56.0 + 0.12 * dy)
            # Pivot (Rodrigo Vale)
            targets["HSC_16"] = (min(79.0, max(31.0, 79.0 - 46.0 * q)), 34.0 + 0.20 * dy)
            # Attacking Midfielders (KDB & Bernardo)
            targets["HSC_17"] = (min(75.0, max(21.0, 75.0 - 52.0 * q)), 42.0 + 0.20 * dy)
            targets["HSC_20"] = (min(75.0, max(21.0, 75.0 - 52.0 * q)), 26.0 + 0.20 * dy)
            # Wingers (Fenton & Dukes)
            targets["HSC_47"] = (min(61.0, max(7.0, 61.0 - 52.0 * q)), 16.0 + 0.18 * dy)
            targets["HSC_11"] = (min(61.0, max(7.0, 61.0 - 52.0 * q)), 54.0 + 0.18 * dy)
            # Striker (Hagen)
            targets["HSC_09"] = (min(55.0, max(5.0, 55.0 - 49.0 * q)), 34.0 + 0.20 * dy)
        else:
            # Harbourside Defending (against Northbridge Lions attack)
            def_line_city = 69.0 + 29.5 * p
            # Enzo Barreto on goal line bisecting angle
            gk_x = min(103.2, max(100.5, 103.2 - 0.04 * max(0.0, 95.0 - float(ball_x))))
            dist_to_goal = max(1.0, 105.0 - float(ball_x))
            slope = dy / dist_to_goal
            gk_y = max(29.5, min(38.5, 34.0 + slope * (105.0 - gk_x)))
            targets["HSC_31"] = (gk_x, gk_y)
            # Back 4
            targets["HSC_02"] = (min(97.0, max(65.0, def_line_city - 2.0)), 16.0 + 0.20 * dy)
            targets["HSC_25"] = (min(98.5, max(69.0, def_line_city)), 31.0 + 0.22 * dy)
            targets["HSC_03"] = (min(98.5, max(69.0, def_line_city)), 37.0 + 0.22 * dy)
            targets["HSC_24"] = (min(97.0, max(65.0, def_line_city - 2.0)), 52.0 + 0.20 * dy)
            # Midfield Line
            targets["HSC_16"] = (min(91.0, max(57.0, def_line_city - 8.0)), 34.0 + 0.25 * dy)
            targets["HSC_20"] = (min(85.0, max(49.0, def_line_city - 14.0)), 28.0 + 0.22 * dy)
            targets["HSC_17"] = (min(85.0, max(49.0, def_line_city - 14.0)), 40.0 + 0.22 * dy)
            targets["HSC_47"] = (min(83.0, max(40.0, def_line_city - 14.0)), 18.0 + 0.18 * dy)
            targets["HSC_11"] = (min(83.0, max(40.0, def_line_city - 14.0)), 50.0 + 0.18 * dy)
            # Striker Outlet
            targets["HSC_09"] = (min(71.0, max(35.0, def_line_city - 24.0)), 34.0 + 0.20 * dy)

        # Substitutes take over the tactical slot of the starter they replaced.
        slotted: Dict[str, Tuple[float, float]] = {}
        for pid in self.players:
            slot = self.slot_of.get(pid, pid)
            if pid in targets:
                slotted[pid] = targets[pid]
            elif slot in targets:
                slotted[pid] = targets[slot]
        targets = slotted

        # 3. Active Event Pinning
        if active_event:
            ev_pid = active_event.get("player_id")
            ev_loc_x = active_event.get("location_x")
            ev_loc_y = active_event.get("location_y")
            ev_sec_pid = active_event.get("secondary_player_id")
            ev_end_x = active_event.get("end_x")
            ev_end_y = active_event.get("end_y")
            ev_t = active_event.get("event_type")

            if ev_pid and ev_loc_x is not None and ev_loc_y is not None and ev_pid in targets:
                targets[ev_pid] = (float(ev_loc_x), float(ev_loc_y))

            if ev_sec_pid and ev_sec_pid in targets:
                if ev_end_x is not None and ev_end_y is not None:
                    targets[ev_sec_pid] = (float(ev_end_x), float(ev_end_y))
                elif ev_loc_x is not None and ev_loc_y is not None:
                    opp_dir = 1.0 if ev_loc_x < 52.5 else -1.0
                    targets[ev_sec_pid] = (float(ev_loc_x) + 1.2 * opp_dir, float(ev_loc_y))

            # Goalmouth defense adjustment for shots/goals
            if ev_t in ["shot", "goal"]:
                if active_event.get("team") in ["Northbridge Lions", "home"]:
                    ed_x = 104.2
                    dy_shot = (ev_loc_y - 34.0) if ev_loc_y is not None else 0.0
                    ed_y = max(30.0, min(38.0, 34.0 + 0.3 * dy_shot))
                    targets["HSC_31"] = (ed_x, ed_y)
                else:
                    ra_x = 0.8
                    dy_shot = (ev_loc_y - 34.0) if ev_loc_y is not None else 0.0
                    ra_y = max(30.0, min(38.0, 34.0 + 0.3 * dy_shot))
                    targets["NBL_01"] = (ra_x, ra_y)

        # Clamp all targets to pitch bounds
        for k, (tx, ty) in targets.items():
            targets[k] = (round(max(0.0, min(105.0, tx)), 2), round(max(0.0, min(68.0, ty)), 2))

        return targets

    def _apply_event_trigger(self, ev: Dict[str, Any]) -> None:
        """
        Executes physical kick, pass, tackle, or shot based on event specifications.
        Uses active_pass_trajectory to guarantee smooth multi-step interpolation (>=10 steps).
        """
        ev_type = ev.get("event_type")
        sub_type = str(ev.get("sub_type", ""))
        loc_x = ev.get("location_x", self.ball.x)
        loc_y = ev.get("location_y", self.ball.y)
        end_x = ev.get("end_x")
        end_y = ev.get("end_y")
        tactical_metrics = ev.get("tactical_metrics", {})
        ball_speed = tactical_metrics.get("ball_speed_kmh", 65.0)
        team = ev.get("team")
        pid = ev.get("player_id")
        sec_player_id = ev.get("secondary_player_id")

        # Position kicker at event location with displacement limiter
        if pid and pid in self.players:
            p_kicker = self.players[pid]
            d_kicker = math.hypot(p_kicker.x - float(loc_x), p_kicker.y - float(loc_y))
            if d_kicker <= 0.40:
                p_kicker.x = round(float(loc_x), 2)
                p_kicker.y = round(float(loc_y), 2)
            else:
                dir_x = (float(loc_x) - p_kicker.x) / d_kicker
                dir_y = (float(loc_y) - p_kicker.y) / d_kicker
                p_kicker.x = round(p_kicker.x + dir_x * 0.38, 2)
                p_kicker.y = round(p_kicker.y + dir_y * 0.38, 2)

        if ev_type in ["pass", "shot", "goal"] and end_x is not None and end_y is not None:
            is_goal = (ev_type == "goal")
            is_aerial = (
                ev_type in ["shot", "goal"]
                or sub_type in [
                    "cross", "long_ball", "aerial_pass", "through_ball_aerial",
                    "lofted_pass", "header", "lob", "curled_shot",
                    "near_post_finish", "long_range_shot"
                ]
                or "aerial" in sub_type
            )
            dx = float(end_x) - float(loc_x)
            dy = float(end_y) - float(loc_y)
            dist = math.hypot(dx, dy)

            h_peak = 0.0
            if is_aerial:
                if sub_type == "cross":
                    h_peak = min(6.0, max(3.2, 0.08 * dist + 1.8))
                elif sub_type == "long_ball":
                    h_peak = min(5.8, max(3.0, 0.07 * dist + 1.5))
                elif ev_type in ["shot", "goal"]:
                    h_peak = min(2.8, max(1.2, 0.04 * dist + 1.0))
                else:
                    h_peak = min(3.5, max(1.8, 0.05 * dist + 1.2))

            speed = float(ball_speed) if ball_speed and ball_speed > 0 else (90.0 if ev_type in ["shot", "goal"] else 65.0)

            self.start_pass_trajectory(
                start_x=float(loc_x),
                start_y=float(loc_y),
                end_x=float(end_x),
                end_y=float(end_y),
                target_player_id=sec_player_id if not is_goal else None,
                target_team=team,
                is_aerial=is_aerial,
                h_peak=h_peak,
                speed_kmh=speed,
                min_steps=10,
                event_id=ev.get("event_id"),
                is_goal=is_goal,
            )
        elif ev_type in ["tackle", "turnover"]:
            self.active_pass_trajectory = None
            self.ball.x = float(loc_x)
            self.ball.y = float(loc_y)
            self.ball.z = 0.0
            self.ball.vx = 0.0
            self.ball.vy = 0.0
            self.ball.vz = 0.0
            self.ball.speed_kmh = 0.0
            self.ball.possession_team = team
            self.ball.possessed_by_player_id = pid
            self.ball.status = "in_play"
            if sec_player_id and sec_player_id in self.players:
                opp_dir = 1.0 if self.players[sec_player_id].team == "home" else -1.0
                t_sec_x = round(max(0.0, min(105.0, float(loc_x) + 1.2 * opp_dir)), 2)
                t_sec_y = round(float(loc_y), 2)
                sec_p = self.players[sec_player_id]
                d_sec = math.hypot(sec_p.x - t_sec_x, sec_p.y - t_sec_y)
                if d_sec <= 0.40:
                    sec_p.x = t_sec_x
                    sec_p.y = t_sec_y
                else:
                    dir_x = (t_sec_x - sec_p.x) / d_sec
                    dir_y = (t_sec_y - sec_p.y) / d_sec
                    sec_p.x = round(sec_p.x + dir_x * 0.38, 2)
                    sec_p.y = round(sec_p.y + dir_y * 0.38, 2)
        elif ev_type == "goal":
            self.active_pass_trajectory = None
            self.ball.x = float(loc_x)
            self.ball.y = float(loc_y)
            self.ball.z = 0.5
            self.ball.vx = 0.0
            self.ball.vy = 0.0
            self.ball.vz = 0.0
            self.ball.speed_kmh = 0.0
            self.ball.possession_team = team
            self.ball.possessed_by_player_id = pid
            self.ball.status = "goal"
        elif ev_type in ["set_piece", "foul", "card", "pressure"]:
            self.active_pass_trajectory = None
            self.ball.x = float(loc_x)
            self.ball.y = float(loc_y)
            self.ball.z = 0.0
            self.ball.vx = 0.0
            self.ball.vy = 0.0
            self.ball.vz = 0.0
            self.ball.speed_kmh = 0.0
            self.ball.possession_team = team
            self.ball.possessed_by_player_id = pid
            self.ball.status = "in_play"
            if sec_player_id and sec_player_id in self.players:
                opp_dir = 1.0 if self.players[sec_player_id].team == "home" else -1.0
                t_sec_x = round(max(0.0, min(105.0, float(loc_x) + 1.2 * opp_dir)), 2)
                t_sec_y = round(float(loc_y), 2)
                sec_p = self.players[sec_player_id]
                d_sec = math.hypot(sec_p.x - t_sec_x, sec_p.y - t_sec_y)
                if d_sec <= 0.40:
                    sec_p.x = t_sec_x
                    sec_p.y = t_sec_y
                else:
                    dir_x = (t_sec_x - sec_p.x) / d_sec
                    dir_y = (t_sec_y - sec_p.y) / d_sec
                    sec_p.x = round(sec_p.x + dir_x * 0.38, 2)
                    sec_p.y = round(sec_p.y + dir_y * 0.38, 2)

    def generate_frames(self, count: int = 100) -> List[Dict[str, Any]]:
        """
        Generates and returns count consecutive TelemetryFrame objects.
        """
        frames: List[Dict[str, Any]] = []
        for _ in range(count):
            frames.append(self.step())
        return frames

    def get_events(self) -> List[Dict[str, Any]]:
        """
        Returns all registered match events.
        """
        return list(self.events)

    def restore_snapshot(
        self,
        final_frame: Dict[str, Any],
        events: Optional[List[Dict[str, Any]]] = None,
    ) -> Dict[str, Any]:
        """Restore a deterministic, simulator-generated full-match snapshot."""
        self.reset()
        self.frame_index = int(final_frame.get("frame_id", 0))
        self.elapsed_sec = self.frame_index / float(self.frame_rate)
        self.period = int(final_frame.get("period", 2))
        self.events = list(events or [])
        self._replay_events = False
        self._event_sequence = len(self.events)
        self.active_event_id = None
        self.active_pass_trajectory = None
        self._second_half_started = self.period == 2
        self.sync_squads(self.events, self.frame_index)

        # The stored frame is in real pitch coordinates; the simulation works in its own frame.
        ball_data = self._mirror_state(final_frame.get("ball") or {}) if self.period == 2 else (final_frame.get("ball") or {})
        for field_name in ("x", "y", "z", "vx", "vy", "vz", "speed_kmh", "possession_team", "possessed_by_player_id", "status"):
            if field_name in ball_data:
                setattr(self.ball, field_name, ball_data[field_name])
        self.ball.status = "stopped"

        for player_data in final_frame.get("players", []):
            player = self.players.get(player_data.get("player_id"))
            if player is None:
                continue
            if self.period == 2:
                player_data = self._mirror_state(player_data)
            for field_name in ("x", "y", "vx", "vy", "speed_kmh", "is_visible"):
                if field_name in player_data:
                    setattr(player, field_name, player_data[field_name])

        frame = dict(final_frame)
        frame["timestamp"] = self.get_timestamp_string()
        frame["clock"] = self.get_clock_string()
        frame["period"] = self.period
        frame["ball"], frame["players"] = self.export_state()
        frame["active_event_id"] = None
        return frame

    def get_kickoff_frame(self) -> Dict[str, Any]:
        """
        Returns a canonical kickoff TelemetryFrame at clock 00:00 with players
        strictly at their calibrated base positions and ball at center spot.
        """
        players_data = []
        for pid, player in self.players.items():
            base_x, base_y = self.player_anchors[pid]
            p_dict = player.to_dict()
            p_dict["x"] = base_x
            p_dict["y"] = base_y
            p_dict["vx"] = 0.0
            p_dict["vy"] = 0.0
            p_dict["speed_kmh"] = 0.0
            players_data.append(p_dict)

        return {
            "frame_id": 0,
            "match_id": self.match_id,
            "data_provenance": self.data_provenance,
            "synthetic_data_notice": SYNTHETIC_DATA_NOTICE,
            "timestamp": self.base_time.isoformat(),
            "period": 1,
            "clock": "00:00",
            "pitch_dimensions": {
                "length": 105.0,
                "width": 68.0,
            },
            "ball": {
                "x": 52.5,
                "y": 34.0,
                "z": 0.0,
                "vx": 0.0,
                "vy": 0.0,
                "vz": 0.0,
                "speed_kmh": 0.0,
                "possession_team": "home",
                "possessed_by_player_id": "NBL_29",
                "status": "in_play",
            },
            "players": players_data,
            "active_event_id": None,
        }

    def reset(self) -> None:
        """
        Resets match generator state back to kickoff (frame 0).
        """
        self.frame_index = 0
        self.elapsed_sec = self.start_clock_sec
        self.period = 1
        self.active_event_id = None
        self.active_pass_trajectory = None
        self.triggered_event_ids.clear()
        if not self._replay_events:
            self.events.clear()
            self._event_sequence = 0
        self._rng = random.Random(self.seed)
        self._aux_rng = random.Random(self.seed * 7919 + 13)
        self._queued_events = []
        self._last_stoppage_frame = -10_000
        self._second_half_started = False
        self._kickoff_end_frame = SECOND_HALF_KICKOFF_FRAMES
        self.possession_frames = 0
        self._next_action_after = 90
        self.ball = BallState(
            x=52.5,
            y=34.0,
            z=0.0,
            vx=0.0,
            vy=0.0,
            vz=0.0,
            speed_kmh=0.0,
            possession_team="home",
            possessed_by_player_id="NBL_29",
            status="in_play",
        )
        self._reset_squads()
        self._sub_plan = self._build_sub_plan()

