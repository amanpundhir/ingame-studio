"""
InGame Studio - Asynchronous Telemetry Streamer
Provides async and synchronous generators yielding 25Hz tracking frames and BroadcastPayloads
with replay, pause, play, seek, and real-time pacing capabilities.
"""

from __future__ import annotations

import asyncio
import time
from typing import AsyncIterator, Callable, Dict, Iterator, Optional, Any

from .match_generator import MatchGenerator


class TelemetryStreamer:
    """
    Broadcast streaming engine for match telemetry.
    Streams 25Hz TelemetryFrame packets and BroadcastPayload wrappers with
    precision pacing and playback controls.
    """

    def __init__(
        self,
        match_id: str = "IGS_2026_NBL_HSC",
        frame_rate: int = 25,
        real_time: bool = True,
        events_file: Optional[str] = None,
        seed: int = 2036,
    ):
        self.match_id = match_id
        self.frame_rate = frame_rate
        self.frame_interval = 1.0 / frame_rate  # 0.04s for 25Hz
        self.real_time = real_time
        self.events_file = events_file
        self.seed = int(seed)

        self.generator = MatchGenerator(
            match_id=self.match_id,
            frame_rate=self.frame_rate,
            events_file=self.events_file,
            seed=self.seed,
        )

        self.is_paused = False
        self.is_running = True
        self.speed_multiplier: float = 1.0
        self._accumulator: float = 0.0

    def set_speed(self, multiplier: float) -> float:
        """Sets and validates playback speed multiplier in [0.25, 20.0]."""
        clamped = max(0.25, min(20.0, float(multiplier)))
        self.speed_multiplier = clamped
        return self.speed_multiplier

    def get_steps_for_tick(self) -> int:
        """Calculates discrete steps to advance for current 40ms broadcast tick."""
        self._accumulator += self.speed_multiplier
        steps = int(self._accumulator)
        self._accumulator -= steps
        return max(1, steps) if self.speed_multiplier >= 1.0 else steps

    def pause(self) -> None:
        """Pauses the stream."""
        self.is_paused = True

    def resume(self) -> None:
        """Resumes the stream."""
        self.is_paused = False

    def reset(self) -> None:
        """Resets the match generator back to frame 0."""
        self.generator = MatchGenerator(
            match_id=self.match_id,
            frame_rate=self.frame_rate,
            events_file=self.events_file,
            seed=self.seed,
        )
        self._accumulator = 0.0

    def seek_to_frame(self, frame_index: int) -> None:
        """Fast-forwards simulation to a specified frame index."""
        current_frame = self.generator.frame_index
        if frame_index < current_frame:
            self.reset()
            current_frame = 0
        diff = frame_index - current_frame
        for _ in range(diff):
            self.generator.step()

    def jump_to_event(
        self,
        event_data: Dict[str, Any],
        all_events: Optional[list[Dict[str, Any]]] = None,
    ) -> Dict[str, Any]:
        """
        Seeks simulator directly to an event's timestamp, restores physical state
        (ball position, passer, receiver, other players), triggers the event kinematics,
        and returns the synchronized frame.

        ``all_events`` lets the squads be rebuilt for that moment (substitutions and
        red cards that happened before it).
        """
        target_frame = int(event_data.get("frame_index", 0))
        clock_str = event_data.get("clock", "00:00")
        if target_frame <= 0 and ":" in clock_str:
            parts = clock_str.split(":")
            target_frame = (int(parts[0]) * 60 + int(parts[1])) * self.frame_rate

        self.generator.frame_index = target_frame
        self.generator.elapsed_sec = float(target_frame) / float(self.frame_rate)
        self.generator.period = event_data.get("period", 2 if self.generator.elapsed_sec >= 2700.0 else 1)
        self.generator._second_half_started = self.generator.period == 2
        squad_frame = target_frame - 1 if event_data.get("event_type") in ("card", "substitution") else target_frame
        self.generator.sync_squads(all_events if all_events is not None else self.generator.events, squad_frame)

        # Events carry real pitch coordinates; the simulation works with the home side
        # always attacking +x, so rotate second-half events back into that frame.
        event_data = dict(event_data)
        if self.generator.period == 2:
            for x_key, y_key in (("location_x", "location_y"), ("end_x", "end_y")):
                if event_data.get(x_key) is not None and event_data.get(y_key) is not None:
                    event_data[x_key], event_data[y_key] = self.generator._out_xy(
                        float(event_data[x_key]), float(event_data[y_key])
                    )

        # Restore ball state
        loc_x = float(event_data.get("location_x", 52.5))
        loc_y = float(event_data.get("location_y", 34.0))
        self.generator.ball.x = round(loc_x, 2)
        self.generator.ball.y = round(loc_y, 2)
        self.generator.ball.z = 0.0
        self.generator.ball.vx = 0.0
        self.generator.ball.vy = 0.0
        self.generator.ball.vz = 0.0
        self.generator.ball.speed_kmh = 0.0
        self.generator.ball.possession_team = event_data.get("team")
        self.generator.ball.possessed_by_player_id = event_data.get("player_id")
        self.generator.ball.status = "in_play"

        # Compute master tactical positions for all 22 players using MTPS
        team = event_data.get("team", "home")
        is_kickoff = (clock_str == "00:00")
        targets = self.generator.compute_tactical_player_targets(
            loc_x, loc_y, team, active_event=event_data, is_kickoff=is_kickoff
        )

        pid = event_data.get("player_id")
        sec_pid = event_data.get("secondary_player_id")

        for other_id, player in self.generator.players.items():
            tx, ty = targets.get(other_id, (player.x, player.y))
            player.x = round(tx, 2)
            player.y = round(ty, 2)
            player.vx = 0.0
            player.vy = 0.0
            player.speed_kmh = 10.0 if other_id in [pid, sec_pid] else 4.0

        # Position primary player at ball coordinates
        if pid and pid in self.generator.players:
            self.generator.players[pid].x = round(loc_x, 2)
            self.generator.players[pid].y = round(loc_y, 2)

        # Trigger event physical action
        ev_id = event_data.get("event_id")
        if ev_id:
            self.generator.triggered_event_ids.add(ev_id)
        self.generator._apply_event_trigger(event_data)
        self.generator.active_event_id = ev_id

        ball_state, player_states = self.generator.export_state()
        return {
            "frame_id": self.generator.frame_index,
            "match_id": self.generator.match_id,
            "timestamp": self.generator.get_timestamp_string(),
            "period": self.generator.period,
            "clock": self.generator.get_clock_string(),
            "pitch_dimensions": {"length": 105.0, "width": 68.0},
            "ball": ball_state,
            "players": player_states,
            "active_event_id": self.generator.active_event_id,
        }

    def simulate_full_match(
        self,
        on_frame: Optional[Callable[[Dict[str, Any]], None]] = None,
        snapshot: Optional[Dict[str, Any]] = None,
        events: Optional[list[Dict[str, Any]]] = None,
    ) -> Dict[str, Any]:
        """
        Advances the simulation frame by frame to 94:30 full-time.
        If provided, calls on_frame for every generated frame so analytics can
        accumulate physical tracking metrics instead of seeing only the final
        state. Pauses streaming and returns the final frame.
        """
        self.pause()
        if snapshot is not None:
            frame = self.generator.restore_snapshot(snapshot, events)
            if on_frame is not None:
                on_frame(frame)
            return frame

        target_frame = int(round(5670.0 * self.frame_rate))
        frame: Optional[Dict[str, Any]] = None
        while self.generator.frame_index < target_frame:
            frame = self.generator.step()
            if on_frame is not None and self.generator.frame_index < target_frame:
                on_frame(frame)

        # Correct accumulated floating point drift at the exact full-time frame.
        self.generator.elapsed_sec = target_frame / float(self.frame_rate)

        if frame is None:
            fallback_ball, fallback_players = self.generator.export_state()
            frame = {
                "frame_id": self.generator.frame_index,
                "match_id": self.generator.match_id,
                "data_provenance": self.generator.data_provenance,
                "synthetic_data_notice": getattr(
                    self.generator,
                    "synthetic_data_notice",
                    "Synthetic demonstration data; fictional simulation, not a real match feed.",
                ),
                "timestamp": self.generator.get_timestamp_string(),
                "period": self.generator.period,
                "clock": self.generator.get_clock_string(),
                "pitch_dimensions": {"length": 105.0, "width": 68.0},
                "ball": fallback_ball,
                "players": fallback_players,
                "active_event_id": self.generator.active_event_id,
            }

        self.generator.period = 2
        self.generator.ball.status = "stopped"
        frame["period"] = self.generator.period
        frame["clock"] = self.generator.get_clock_string()
        frame["timestamp"] = self.generator.get_timestamp_string()
        frame["ball"], frame["players"] = self.generator.export_state()
        frame["active_event_id"] = None
        if on_frame is not None:
            on_frame(frame)
        return frame

    async def stream_frames(
        self,
        limit: Optional[int] = None,
        as_broadcast_payload: bool = True,
    ) -> AsyncIterator[Dict[str, Any]]:
        """
        Asynchronous generator yielding frames at 25Hz.
        Wraps in BroadcastPayload format if as_broadcast_payload is True.
        """
        yielded_count = 0
        while self.is_running:
            if limit is not None and yielded_count >= limit:
                break

            if self.is_paused:
                await asyncio.sleep(0.05)
                continue

            t_start = time.perf_counter()
            steps = self.get_steps_for_tick() if self.real_time else 1
            frame = None
            for _ in range(steps):
                frame = self.generator.step()

            if as_broadcast_payload:
                payload = {
                    "type": "telemetry",
                    "timestamp": frame["timestamp"],
                    "data": frame,
                }
                yield payload
            else:
                yield frame

            yielded_count += 1

            if self.real_time:
                elapsed = time.perf_counter() - t_start
                sleep_time = max(0.0, self.frame_interval - elapsed)
                if sleep_time > 0:
                    await asyncio.sleep(sleep_time)

    def iter_frames(
        self,
        limit: Optional[int] = None,
        as_broadcast_payload: bool = False,
    ) -> Iterator[Dict[str, Any]]:
        """
        Synchronous generator yielding frames immediately (useful for testing and batch processing).
        """
        yielded_count = 0
        while True:
            if limit is not None and yielded_count >= limit:
                break
            frame = self.generator.step()
            if as_broadcast_payload:
                yield {
                    "type": "telemetry",
                    "timestamp": frame["timestamp"],
                    "data": frame,
                }
            else:
                yield frame
            yielded_count += 1
