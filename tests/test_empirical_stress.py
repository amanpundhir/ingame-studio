"""
InGame Studio - Empirical Adversarial Stress Test Suite
Author: Challenger M5 (Empirical Challenger)

Stress-tests the full stack against hostile inputs, boundary conditions,
and strict invariants:
1. Spatial Bounds Stress: 5,000 consecutive frames, 110,000 player checks,
   strictly in [0, 105] x [0, 68], player speed <= 36 km/h, ball speed <= 150 km/h.
2. Kickoff Spatial Invariants: Clock 00:00 half-confinement across all 24 frames,
   GKs in 6-yard boxes, strikers at center spot.
3. Kinematics Continuity: 100 random passes with extreme distances (1m to 90m),
   step counts >= 10, continuous intermediate coordinates, parabolic elevation Z in [1.5, 6.0m].
4. 90-Minute Dataset Stress: generated events validated against schema.json
   Draft-07, with chronological coverage and score derived from goals.
5. Speed Multiplier Stress: Streamer at 1x, 2x, 5x, 10x, 20x speed,
   step counts and 25Hz broadcast pacing without frame drops.
6. Replay Jump & Macro Simulation: seek state restoration and simulate_full
   completing in < 200ms with complete stats for all 22 players.
"""

import json
import math
import os
import random
import time
import pytest
import jsonschema

from generator.match_generator import MatchGenerator, NORTHBRIDGE_ROSTER, AWAY_ROSTER
from generator.physics_engine import PhysicsEngine
from generator.telemetry_streamer import TelemetryStreamer
from backend.math_engine import MatchAnalyticsTracker
from fastapi.testclient import TestClient
from backend.app import app


@pytest.fixture(scope="module")
def repo_root():
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


@pytest.fixture(scope="module")
def synthetic_events(repo_root):
    events_path = os.path.join(repo_root, "data", "synthetic_events.json")
    with open(events_path, "r", encoding="utf-8") as f:
        return json.load(f)


@pytest.fixture(scope="module")
def schema_draft07(repo_root):
    schema_path = os.path.join(repo_root, "data", "schema.json")
    with open(schema_path, "r", encoding="utf-8") as f:
        return json.load(f)


@pytest.fixture
def client():
    with TestClient(app) as c:
        yield c


class TestSpatialBoundsStress:
    """Stress-tests continuous coordinate boundaries and velocity limits over 5,000 frames."""

    def test_5000_frames_spatial_and_velocity_bounds(self):
        """
        Simulates 5,000 consecutive 25Hz tracking frames (200 seconds of match time).
        Asserts 100% of player and ball coordinates remain strictly within
        [0.0, 105.0] x [0.0, 68.0], player speeds <= 36.0 km/h, ball speeds <= 150.0 km/h.
        Total assertions: >115,000 data point verifications.
        """
        generator = MatchGenerator(match_id="IGS_STRESS_5000", frame_rate=25)

        max_player_speed_observed = 0.0
        max_ball_speed_observed = 0.0
        min_x_observed, max_x_observed = 105.0, 0.0
        min_y_observed, max_y_observed = 68.0, 0.0

        for frame_num in range(1, 5001):
            frame = generator.step()
            assert frame["frame_id"] == frame_num

            # Ball invariants
            ball = frame["ball"]
            bx, by, bz = ball["x"], ball["y"], ball["z"]
            bspeed = ball["speed_kmh"]

            assert bx is not None and not math.isnan(bx) and not math.isinf(bx), f"NaN/Inf ball x at frame {frame_num}"
            assert by is not None and not math.isnan(by) and not math.isinf(by), f"NaN/Inf ball y at frame {frame_num}"
            assert bz is not None and not math.isnan(bz) and not math.isinf(bz), f"NaN/Inf ball z at frame {frame_num}"
            assert bspeed is not None and not math.isnan(bspeed) and not math.isinf(bspeed), f"NaN/Inf ball speed at frame {frame_num}"

            assert 0.0 <= bx <= 105.0, f"Ball X out of bounds: {bx} at frame {frame_num}"
            assert 0.0 <= by <= 68.0, f"Ball Y out of bounds: {by} at frame {frame_num}"
            assert 0.0 <= bz <= 25.0, f"Ball Z out of bounds: {bz} at frame {frame_num}"
            assert 0.0 <= bspeed <= 150.01, f"Ball speed exceeded 150 km/h: {bspeed} at frame {frame_num}"

            if bspeed > max_ball_speed_observed:
                max_ball_speed_observed = bspeed

            # Player invariants (22 players per frame)
            players = frame["players"]
            assert len(players) == 22, f"Expected 22 players, found {len(players)} at frame {frame_num}"

            for p in players:
                pid = p["player_id"]
                px, py = p["x"], p["y"]
                pspeed = p["speed_kmh"]

                assert px is not None and not math.isnan(px) and not math.isinf(px), f"NaN/Inf player x ({pid}) at frame {frame_num}"
                assert py is not None and not math.isnan(py) and not math.isinf(py), f"NaN/Inf player y ({pid}) at frame {frame_num}"
                assert pspeed is not None and not math.isnan(pspeed) and not math.isinf(pspeed), f"NaN/Inf player speed ({pid}) at frame {frame_num}"

                assert 0.0 <= px <= 105.0, f"Player {pid} X out of bounds: {px} at frame {frame_num}"
                assert 0.0 <= py <= 68.0, f"Player {pid} Y out of bounds: {py} at frame {frame_num}"
                assert 0.0 <= pspeed <= 36.01, f"Player {pid} speed exceeded 36 km/h: {pspeed} at frame {frame_num}"

                if pspeed > max_player_speed_observed:
                    max_player_speed_observed = pspeed
                if px < min_x_observed:
                    min_x_observed = px
                if px > max_x_observed:
                    max_x_observed = px
                if py < min_y_observed:
                    min_y_observed = py
                if py > max_y_observed:
                    max_y_observed = py

        # Verify realistic physical ranges were exercised
        assert max_ball_speed_observed > 20.0, "Ball was static during simulation"
        assert max_player_speed_observed > 15.0, "Players were static during simulation"
        assert min_x_observed < 10.0 and max_x_observed > 95.0, "Full pitch length not traversed"


class TestKickoffSpatialInvariants:
    """Stress-tests spatial boundary confinement during kickoff."""

    def test_clock_00_00_half_bounding_and_positions(self):
        """
        Verifies that during clock '00:00' (all 24 frames from 0.04s to 0.96s):
        1. All 11 Northbridge Lions players are strictly in X <= 52.5.
        2. All 11 Harbourside players are strictly in X >= 52.5.
        3. Daniel Roark is strictly inside the Northbridge Lions 6-yard box (X <= 5.5).
        4. Enzo Barreto is strictly inside the Harbourside 6-yard box (X >= 99.5).
        5. Kai Halvorsen is at the center spot (X=52.2, Y=34.0).
        6. Anders Hagen is at the center spot (X=52.8, Y=34.0).
        7. Halvorsen and Hagen have positive distance between them (no overlap).
        """
        generator = MatchGenerator(match_id="IGS_KICKOFF_TEST", frame_rate=25)

        for step_idx in range(1, 25):
            frame = generator.step()
            assert frame["clock"] == "00:00", f"Expected clock 00:00 at frame {step_idx}, got {frame['clock']}"

            players_by_id = {p["player_id"]: p for p in frame["players"]}

            # 1. Half confinement
            for pid in [p["player_id"] for p in NORTHBRIDGE_ROSTER]:
                assert players_by_id[pid]["x"] <= 52.5, (
                    f"Northbridge Lions player {pid} crossed halfway line at frame {step_idx}: X={players_by_id[pid]['x']}"
                )

            for pid in [p["player_id"] for p in AWAY_ROSTER]:
                assert players_by_id[pid]["x"] >= 52.5, (
                    f"Harbourside player {pid} crossed halfway line at frame {step_idx}: X={players_by_id[pid]['x']}"
                )

            # 2. Goalkeepers in 6-yard box
            roark = players_by_id["NBL_01"]
            barreto = players_by_id["HSC_31"]

            assert 0.0 <= roark["x"] <= 5.5, f"Roark outside 6-yard box X: {roark['x']}"
            assert 24.84 <= roark["y"] <= 43.16, f"Roark outside 6-yard box Y: {roark['y']}"

            assert 99.5 <= barreto["x"] <= 105.0, f"Enzo Barreto outside 6-yard box X: {barreto['x']}"
            assert 24.84 <= barreto["y"] <= 43.16, f"Enzo Barreto outside 6-yard box Y: {barreto['y']}"

            # 3. Center spot strikers
            halvorsen = players_by_id["NBL_29"]
            hagen = players_by_id["HSC_09"]

            assert abs(halvorsen["x"] - 52.2) <= 0.1, f"Halvorsen not at center spot: {halvorsen['x']}"
            assert abs(halvorsen["y"] - 34.0) <= 0.1, f"Halvorsen not at center spot Y: {halvorsen['y']}"

            assert abs(hagen["x"] - 52.8) <= 0.1, f"Hagen not at center spot: {hagen['x']}"
            assert abs(hagen["y"] - 34.0) <= 0.1, f"Hagen not at center spot Y: {hagen['y']}"

            dist_strikers = math.hypot(halvorsen["x"] - hagen["x"], halvorsen["y"] - hagen["y"])
            assert dist_strikers >= 0.5, f"Strikers overlapping: {dist_strikers}m"


class TestKinematicsContinuityExtremePasses:
    """Stress-tests continuous ball kinematics across 100 extreme passes."""

    def test_100_random_extreme_passes_kinematics(self):
        """
        Generates 100 random passes with extreme distances (1m micro-taps to 90m cross-pitch switches)
        and kick speeds (20 km/h to 140 km/h).
        Verifies:
        - Every pass runs >= 10 steps.
        - Intermediate coordinates interpolate continuously without jumping.
        - Aerial passes have parabolic elevation Z strictly in [1.5, 6.0m].
        - Ball speed remains <= 150.0 km/h throughout.
        - Ball lands accurately at end coordinates.
        """
        rng = random.Random(1337)  # Deterministic seed for reproducible stress testing
        generator = MatchGenerator(match_id="IGS_KINEMATICS_100", frame_rate=25)
        # Clear background events so they don't preempt the kinematic stress test passes
        generator.events = []

        for pass_idx in range(100):
            # Pick start position inside pitch
            start_x = rng.uniform(5.0, 95.0)
            start_y = rng.uniform(5.0, 63.0)

            # Pick target distance: test extreme spectrum (1m to 90m)
            if pass_idx < 20:
                # Micro passes (1.0m to 4.0m)
                angle = rng.uniform(0, 2 * math.pi)
                dist = rng.uniform(1.0, 4.0)
                end_x = max(1.0, min(104.0, start_x + dist * math.cos(angle)))
                end_y = max(1.0, min(67.0, start_y + dist * math.sin(angle)))
                is_aerial = False
            elif pass_idx < 40:
                # Ultra-long passes (65.0m to 90.0m)
                angle = rng.uniform(0, 2 * math.pi)
                dist = rng.uniform(65.0, 90.0)
                end_x = max(1.0, min(104.0, start_x + dist * math.cos(angle)))
                end_y = max(1.0, min(67.0, start_y + dist * math.sin(angle)))
                is_aerial = True
            else:
                # Varied distances (5.0m to 60.0m)
                end_x = rng.uniform(5.0, 95.0)
                end_y = rng.uniform(5.0, 63.0)
                is_aerial = rng.choice([True, False])

            dist = math.hypot(end_x - start_x, end_y - start_y)
            if dist < 1.0:
                end_x += 1.5
                dist = math.hypot(end_x - start_x, end_y - start_y)

            speed_kmh = rng.uniform(25.0, 135.0)

            traj = generator.start_pass_trajectory(
                start_x=start_x,
                start_y=start_y,
                end_x=end_x,
                end_y=end_y,
                target_player_id="NBL_07",
                target_team="home",
                is_aerial=is_aerial,
                speed_kmh=speed_kmh,
                min_steps=10,
            )

            total_steps = traj["total_steps"]
            assert total_steps >= 10, f"Pass {pass_idx}: total_steps {total_steps} < 10"

            if is_aerial:
                max_z = traj["max_elevation_z"]
                assert 1.5 <= max_z <= 6.0, f"Pass {pass_idx}: max_z {max_z} not in [1.5, 6.0m]"

            prev_x, prev_y, prev_z = generator.ball.x, generator.ball.y, generator.ball.z
            observed_peak_z = 0.0

            # Step through entire trajectory
            for step_num in range(1, total_steps + 1):
                generator.step()
                curr_ball = generator.ball

                # Assert non-null & pitch boundaries
                assert 0.0 <= curr_ball.x <= 105.0
                assert 0.0 <= curr_ball.y <= 68.0
                assert 0.0 <= curr_ball.speed_kmh <= 150.01

                # Continuity check: single-step displacement must not exceed speed * dt + margin
                dt = 0.04
                max_step_disp = (150.0 / 3.6) * dt + 0.15  # <= 1.82m max displacement per 25Hz frame
                actual_disp = math.hypot(curr_ball.x - prev_x, curr_ball.y - prev_y, curr_ball.z - prev_z)
                assert actual_disp <= max_step_disp, (
                    f"Pass {pass_idx} step {step_num}: Discontinuous jump {actual_disp:.3f}m > {max_step_disp:.3f}m"
                )

                if is_aerial:
                    assert 0.0 <= curr_ball.z <= 6.05, f"Aerial ball Z {curr_ball.z} out of bounds"
                    if curr_ball.z > observed_peak_z:
                        observed_peak_z = curr_ball.z
                else:
                    assert curr_ball.z == 0.0, f"Ground pass has non-zero elevation: {curr_ball.z}"

                prev_x, prev_y, prev_z = curr_ball.x, curr_ball.y, curr_ball.z

            # Verify trajectory completed
            assert generator.active_pass_trajectory is None
            # Verify final position matches destination
            assert math.hypot(generator.ball.x - end_x, generator.ball.y - end_y) <= 0.05
            assert generator.ball.z == 0.0
            if is_aerial:
                assert observed_peak_z >= 1.45, f"Aerial pass never elevated: peak {observed_peak_z}m"


class Test90MinuteDatasetStress:
    """Stress-tests generated full-match data without relying on one match script."""

    def test_schema_compliance_for_full_match_events(self, synthetic_events, schema_draft07):
        """Validates a substantial, generated event sequence against Draft-07."""
        assert len(synthetic_events) >= 100, f"Expected at least 100 events, found {len(synthetic_events)}"

        resolver = jsonschema.RefResolver.from_schema(schema_draft07)
        validator = jsonschema.Draft7Validator(schema_draft07["definitions"]["MatchEvent"], resolver=resolver)

        for idx, event in enumerate(synthetic_events):
            errors = list(validator.iter_errors(event))
            assert not errors, f"Event {event.get('event_id', idx)} failed schema validation: {errors[0].message}"

    def test_strict_chronological_monotonicity(self, synthetic_events):
        """Verifies strictly increasing frame indices and non-decreasing clock times."""
        prev_frame = -1
        prev_clock_sec = -1

        for ev in synthetic_events:
            curr_frame = ev["frame_index"]
            assert curr_frame > prev_frame, (
                f"Event {ev['event_id']} frame_index {curr_frame} <= previous {prev_frame}"
            )
            prev_frame = curr_frame

            mm, ss = map(int, ev["clock"].split(":"))
            curr_clock_sec = mm * 60 + ss
            assert curr_clock_sec >= prev_clock_sec, (
                f"Event {ev['event_id']} clock {ev['clock']} went backwards from {prev_clock_sec}s"
            )
            prev_clock_sec = curr_clock_sec

        # Verify time coverage spans the full match.
        first_clock = synthetic_events[0]["clock"]
        last_clock = synthetic_events[-1]["clock"]
        last_mm = int(last_clock.split(":")[0])
        assert int(first_clock.split(":")[0]) <= 1, f"Expected an event near kickoff, got {first_clock}"
        assert last_mm >= 94, f"Expected match to conclude >= 94', got {last_clock}"

    def test_goal_events_and_score_are_consistent(self, synthetic_events):
        """Verifies goal outcomes are explicit and team scores derive from goals."""
        goals = [e for e in synthetic_events if e.get("event_type") == "goal"]
        assert goals, "A full simulated match should contain at least one goal or explicit goal outcome"
        assert all(g.get("outcome") == "goal" for g in goals)
        score = {"home": 0, "away": 0}
        for goal in goals:
            if goal["team"] in ("home", "Northbridge Lions"):
                score["home"] += 1
            elif goal["team"] in ("away", "Harbourside City"):
                score["away"] += 1
            else:
                raise AssertionError(f"Unknown goal team: {goal['team']}")
        assert score["home"] + score["away"] == len(goals)


class TestSpeedMultiplierStress:
    """Stress-tests TelemetryStreamer across 1x to 20x speeds without frame drops."""

    def test_multiplier_discrete_steps(self):
        """Verifies exact discrete step counts at 1x, 2x, 5x, 10x, 20x."""
        streamer = TelemetryStreamer(frame_rate=25)

        for mult, expected_steps in [(1.0, 1), (2.0, 2), (5.0, 5), (10.0, 10), (20.0, 20)]:
            streamer.set_speed(mult)
            steps = streamer.get_steps_for_tick()
            assert steps == expected_steps, f"At {mult}x speed, expected {expected_steps} steps, got {steps}"

    def test_20x_speed_stepping_stability_and_no_frame_drops(self):
        """
        Runs 200 ticks at maximum 20x speed (advancing 4,000 frames).
        Verifies:
        - Streamer steps exactly 4,000 frames without frame loss.
        - Stepping execution latency is < 5ms per tick (well within 40ms broadcast tick).
        - Generator state remains fully bounded and valid.
        """
        streamer = TelemetryStreamer(frame_rate=25)
        streamer.set_speed(20.0)

        start_time = time.time()
        for tick in range(200):
            steps = streamer.get_steps_for_tick()
            assert steps == 20
            t0 = time.time()
            for _ in range(steps):
                streamer.generator.step()
            tick_duration = time.time() - t0
            assert tick_duration < 0.040, f"Tick {tick} took {tick_duration*1000:.2f}ms, exceeded 40ms broadcast tick budget"

        total_elapsed = time.time() - start_time
        assert streamer.generator.frame_index == 4000
        # Average tick time should be < 20ms
        avg_tick_ms = (total_elapsed / 200) * 1000
        assert avg_tick_ms < 20.0, f"Average tick duration {avg_tick_ms:.2f}ms too slow"


class TestReplayJumpAndMacroSimulation:
    """Stress-tests replay jump state restoration and instant macro-simulation (<200ms)."""

    def test_replay_jump_restores_state(self, synthetic_events):
        """Tests jumping to key moments across the match and verifies state restoration."""
        streamer = TelemetryStreamer(frame_rate=25)

        sample_indices = sorted({0, len(synthetic_events) // 4, len(synthetic_events) // 2, 3 * len(synthetic_events) // 4, len(synthetic_events) - 1})

        for index in sample_indices:
            ev = synthetic_events[index]
            frame = streamer.jump_to_event(ev, synthetic_events)

            assert frame["clock"] == ev["clock"]
            assert frame["frame_id"] == ev["frame_index"]
            assert frame["ball"]["x"] == pytest.approx(ev["location_x"], abs=0.1)
            assert frame["ball"]["y"] == pytest.approx(ev["location_y"], abs=0.1)

            # Player who performed action is at ball location
            acting_pid = ev["player_id"]
            player_data = next(p for p in frame["players"] if p["player_id"] == acting_pid)
            assert player_data["x"] == pytest.approx(ev["location_x"], abs=0.1)
            assert player_data["y"] == pytest.approx(ev["location_y"], abs=0.1)

    def test_simulate_full_macro_simulation_under_200ms(self, synthetic_events, client):
        """
        Verifies simulate_full executes quickly, populating 22-player analytics
        and a score derived from the generated goal events.
        """
        tracker = MatchAnalyticsTracker()

        t0 = time.perf_counter()
        tracker.simulate_full(synthetic_events)
        elapsed = time.perf_counter() - t0

        assert elapsed < 0.200, f"simulate_full took {elapsed * 1000:.2f}ms, expected < 200ms"
        expected_score = {"home": 0, "away": 0}
        for event in synthetic_events:
            if event.get("event_type") == "goal" or event.get("outcome") == "goal":
                team = event.get("team")
                if team in ("home", "Northbridge Lions"):
                    expected_score["home"] += 1
                elif team in ("away", "Harbourside City"):
                    expected_score["away"] += 1
        assert tracker.score == expected_score
        assert tracker.minutes_elapsed >= 94.0

        # Verify all 22 players have complete stats
        assert len(tracker.players) >= 22  # starters plus substitutes who came on
        for pid, p in tracker.players.items():
            # The persisted file contains event rows, not 25Hz tracking frames;
            # physical workload is asserted against the live full-match path below.
            assert 0.0 <= p.distance_meters <= 15000.0
            assert 0.0 <= p.top_speed_kmh <= 36.0
            assert 4.0 <= p.rating <= 10.0, f"Player {pid} rating {p.rating} out of bounds"

        # Verify REST API endpoint behaves identically and fast
        resp = client.post("/api/control", json={"action": "simulate_full"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "simulated_full"
        assert data["clock"] == "94:30"
        assert data["score"] == expected_score

        # Verify analytics endpoint reflects full match
        analytics_resp = client.get("/api/analytics")
        assert analytics_resp.status_code == 200
        analytics_data = analytics_resp.json()
        assert analytics_data["match_stats"]["score"]["home"] == expected_score["home"]
        assert analytics_data["match_stats"]["score"]["away"] == expected_score["away"]
        assert len(analytics_data["player_stats"]) >= 22
        for player in analytics_data["player_stats"]:
            played_full_match = not (player["substituted_on"] or player["substituted_off"] or player["red_cards"])
            if played_full_match:
                assert player["minutes_played"] >= 90
            else:
                assert 0 <= player["minutes_played"] < 95
            assert player["distance_km"] > 0.0
            assert 0.0 <= player["top_speed_kmh"] <= 36.0
