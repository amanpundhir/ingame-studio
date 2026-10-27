"""
InGame Studio - Continuous Ball Kinematics & 3D Ballistic Trajectory Test Suite
Validates Requirement R3:
- Every pass interpolates across >= 10 discrete simulation frames
- No single-frame coordinate snapping / teleportation
- Collinear monotonic intermediate (x, y) coordinates
- 3D parabolic elevation Z(u) = 4 * h_peak * u * (1 - u) with h_peak in [1.5, 6.0m]
- Ground passes maintain Z(u) = 0.0
- Instantaneous ball speed strictly capped to [0.0, 150.0] km/h
- In-flight possession lifecycle (unassigned during travel, assigned upon arrival)
"""

import json
import math
import os
import pytest
from generator.match_generator import MatchGenerator
from generator.physics_engine import PhysicsEngine, BallState


class TestPassStepCount:
    """Verifies every pass runs across at least 10 discrete simulation steps."""

    @pytest.mark.parametrize("start,end,speed", [
        ((50.0, 34.0), (53.0, 34.0), 40.0),    # Short 3.0m pass
        ((20.0, 20.0), (38.0, 35.0), 65.0),    # Medium 23.4m pass
        ((15.0, 10.0), (70.0, 55.0), 95.0),    # Long 71.0m pass
        ((50.0, 34.0), (50.5, 34.0), 120.0),   # Ultra short 0.5m pass
        ((10.0, 10.0), (100.0, 60.0), 140.0),  # Diagonal 102.9m pass
    ])
    def test_every_pass_has_at_least_10_steps(self, start, end, speed):
        """Asserts start_pass_trajectory allocates total_steps >= 10 regardless of distance or speed."""
        gen = MatchGenerator(match_id="IGS_TEST_PASS_STEPS")
        traj = gen.start_pass_trajectory(
            start_x=start[0],
            start_y=start[1],
            end_x=end[0],
            end_y=end[1],
            target_player_id="NBL_07",
            target_team="Northbridge Lions",
            is_aerial=False,
            speed_kmh=speed,
        )
        assert traj["total_steps"] >= 10
        assert traj["current_step"] == 0

    def test_event_triggered_passes_have_at_least_10_steps(self):
        """Loads all pass events from synthetic_events.json and verifies each receives >= 10 steps."""
        repo_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        events_path = os.path.join(repo_root, "data", "synthetic_events.json")
        with open(events_path, "r", encoding="utf-8") as f:
            events = json.load(f)

        pass_events = [e for e in events if e.get("event_type") in ["pass", "shot"] and e.get("end_x") is not None]
        assert len(pass_events) >= 30

        gen = MatchGenerator(match_id="IGS_TEST_EVENT_STEPS")
        for ev in pass_events:
            gen._apply_event_trigger(ev)
            traj = gen.active_pass_trajectory
            assert traj is not None, f"Event {ev['event_id']} did not activate pass trajectory"
            assert traj["total_steps"] >= 10, (
                f"Event {ev['event_id']} total_steps={traj['total_steps']} < 10"
            )


class TestCoordinateContinuity:
    """Verifies smooth coordinate interpolation without single-frame teleportation."""

    def test_no_single_frame_coordinate_snapping(self):
        """Stepping through a 35m pass verifies displacement per frame is smoothly bounded."""
        gen = MatchGenerator(match_id="IGS_TEST_CONTINUITY")
        start_x, start_y = 20.0, 30.0
        end_x, end_y = 55.0, 30.0
        total_dist = 35.0

        gen.start_pass_trajectory(
            start_x=start_x,
            start_y=start_y,
            end_x=end_x,
            end_y=end_y,
            target_player_id="NBL_07",
            target_team="Northbridge Lions",
            speed_kmh=65.0,
        )

        traj = gen.active_pass_trajectory
        total_steps = traj["total_steps"]
        assert total_steps >= 10

        prev_x, prev_y = start_x, start_y
        for step_idx in range(1, total_steps + 1):
            frame = gen.step()
            ball = frame["ball"]
            curr_x = ball["x"]
            curr_y = ball["y"]

            step_dist = math.hypot(curr_x - prev_x, curr_y - prev_y)
            # Maximum step displacement should not exceed (total_dist / total_steps) + 0.1m tolerance
            max_expected_step = (total_dist / total_steps) + 0.1
            assert step_dist <= max_expected_step, (
                f"Frame {step_idx}: step_dist={step_dist:.3f} exceeded max_expected={max_expected_step:.3f}"
            )
            prev_x, prev_y = curr_x, curr_y

        # On the final step, ball must arrive exactly at landing target
        assert abs(prev_x - end_x) < 0.05
        assert abs(prev_y - end_y) < 0.05

    def test_intermediate_coordinates_collinear_with_pass_vector(self):
        """Verifies intermediate ball coordinates lie on the direct line between start and end."""
        gen = MatchGenerator(match_id="IGS_TEST_COLLINEAR")
        start_x, start_y = 15.0, 20.0
        end_x, end_y = 65.0, 55.0

        gen.start_pass_trajectory(
            start_x=start_x,
            start_y=start_y,
            end_x=end_x,
            end_y=end_y,
            target_player_id="HSC_09",
            target_team="Harbourside City",
            speed_kmh=70.0,
        )

        total_steps = gen.active_pass_trajectory["total_steps"]
        dx_total = end_x - start_x
        dy_total = end_y - start_y
        total_len = math.hypot(dx_total, dy_total)

        for _ in range(total_steps):
            frame = gen.step()
            ball = frame["ball"]
            bx, by = ball["x"], ball["y"]

            # Perpendicular distance from (bx, by) to line segment (start -> end)
            # |(end_y - start_y)*bx - (end_x - start_x)*by + end_x*start_y - end_y*start_x| / total_len
            numerator = abs(dy_total * bx - dx_total * by + end_x * start_y - end_y * start_x)
            dist_to_line = numerator / total_len
            assert dist_to_line < 0.05, f"Ball ({bx}, {by}) deviated from pass line by {dist_to_line:.4f}m"


class Test3DBallisticElevation:
    """Verifies 3D ballistic elevation parabola Z(u) = 4 * h_peak * u * (1 - u)."""

    def test_ground_pass_zero_elevation(self):
        """Ground pass must maintain Z = 0.0 across all simulation frames."""
        gen = MatchGenerator(match_id="IGS_TEST_GROUND_ELEVATION")
        gen.start_pass_trajectory(
            start_x=25.0,
            start_y=30.0,
            end_x=55.0,
            end_y=30.0,
            is_aerial=False,
            h_peak=0.0,
        )

        steps = gen.active_pass_trajectory["total_steps"]
        for _ in range(steps):
            frame = gen.step()
            assert frame["ball"]["z"] == 0.0, f"Ground pass had non-zero elevation: {frame['ball']['z']}"

    def test_aerial_pass_parabolic_arc(self):
        """Verifies aerial pass elevation strictly matches the ballistic formula."""
        h_peak = 3.5
        for u_val in [0.0, 0.1, 0.25, 0.5, 0.75, 0.9, 1.0]:
            expected_z = 0.0 if u_val in (0.0, 1.0) else 4.0 * h_peak * u_val * (1.0 - u_val)
            calculated_z = PhysicsEngine.compute_ballistic_elevation(u_val, h_peak)
            assert abs(calculated_z - expected_z) < 1e-4

    def test_aerial_apex_height_and_bounds(self):
        """Simulates an aerial cross and checks apex elevation around midpoint step."""
        gen = MatchGenerator(match_id="IGS_TEST_AERIAL_APEX")
        h_peak = 4.2
        gen.start_pass_trajectory(
            start_x=30.0,
            start_y=60.0,
            end_x=85.0,
            end_y=34.0,
            is_aerial=True,
            h_peak=h_peak,
            speed_kmh=60.0,
        )

        steps = gen.active_pass_trajectory["total_steps"]
        midpoint_step = steps // 2
        max_observed_z = 0.0

        for step_idx in range(1, steps + 1):
            frame = gen.step()
            z = frame["ball"]["z"]
            if z > max_observed_z:
                max_observed_z = z

            if step_idx == midpoint_step:
                # Midpoint frame should be very close to h_peak
                assert abs(z - h_peak) < 0.25, f"Midpoint z={z} not near h_peak={h_peak}"

        # Apex should be in [1.5, 6.0m]
        assert 1.5 <= max_observed_z <= 6.0
        # Final frame must land back on ground
        assert frame["ball"]["z"] == 0.0

    def test_launch_and_landing_elevation_is_zero(self):
        """Verifies start and end of trajectory have elevation 0.0."""
        gen = MatchGenerator(match_id="IGS_TEST_LAUNCH_LANDING")
        gen.start_pass_trajectory(
            start_x=20.0,
            start_y=20.0,
            end_x=70.0,
            end_y=50.0,
            is_aerial=True,
            h_peak=4.0,
        )
        assert gen.ball.z == 0.0

        total_steps = gen.active_pass_trajectory["total_steps"]
        for _ in range(total_steps):
            frame = gen.step()

        assert frame["ball"]["z"] == 0.0


class TestBallSpeedLimits:
    """Verifies ball speed complies with physical limits [0.0, 150.0] km/h."""

    def test_speed_never_exceeds_150_kmh(self):
        """Runs fast pass across pitch and checks instantaneous speed across every frame."""
        gen = MatchGenerator(match_id="IGS_TEST_SPEED_CAP")
        gen.start_pass_trajectory(
            start_x=10.0,
            start_y=10.0,
            end_x=95.0,
            end_y=58.0,
            is_aerial=True,
            h_peak=5.5,
            speed_kmh=140.0,
        )

        steps = gen.active_pass_trajectory["total_steps"]
        for _ in range(steps):
            frame = gen.step()
            speed = frame["ball"]["speed_kmh"]
            assert 0.0 <= speed <= 150.0, f"Speed {speed} km/h exceeded physical cap 150.0 km/h"

    def test_speed_non_negative(self):
        """Verifies speed is always >= 0.0 across simulation steps."""
        gen = MatchGenerator(match_id="IGS_TEST_SPEED_NON_NEGATIVE")
        gen.start_pass_trajectory(
            start_x=40.0,
            start_y=30.0,
            end_x=50.0,
            end_y=35.0,
            speed_kmh=45.0,
        )

        steps = gen.active_pass_trajectory["total_steps"]
        for _ in range(steps):
            frame = gen.step()
            assert frame["ball"]["speed_kmh"] >= 0.0


class TestPossessionStateLifecycle:
    """Verifies ball possession lifecycle during flight and upon reception."""

    def test_possession_transfers_on_final_step(self):
        """During flight (steps 1 to N-1), possessed_by_player_id is None; at step N, it is assigned."""
        gen = MatchGenerator(match_id="IGS_TEST_POSSESSION_LIFECYCLE")
        target_player = "NBL_07"
        target_team = "Northbridge Lions"

        gen.start_pass_trajectory(
            start_x=30.0,
            start_y=30.0,
            end_x=60.0,
            end_y=30.0,
            target_player_id=target_player,
            target_team=target_team,
            speed_kmh=60.0,
        )

        steps = gen.active_pass_trajectory["total_steps"]
        for step_idx in range(1, steps):
            frame = gen.step()
            assert frame["ball"]["possessed_by_player_id"] is None, (
                f"Step {step_idx}: ball in flight should not be possessed"
            )
            assert frame["ball"]["possession_team"] == target_team

        # Final step
        final_frame = gen.step()
        assert final_frame["ball"]["possessed_by_player_id"] == target_player
        assert final_frame["ball"]["possession_team"] == target_team
        assert gen.active_pass_trajectory is None
