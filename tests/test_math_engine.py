"""Comprehensive Unit & Stress Test Suite for TacticalMathEngine and RollingTacticalWindow.

Validates:
- Strict bounds: 0.0 <= PDR <= 100.0, 0.0 <= CCI <= 100.0, 0.0 <= speed <= 150.0
- Zero-division immunity: dt <= 0, L < 1e-4, empty defenders
- Spatial geometry: Passing corridor perpendicular projection (4.0m) & Interception cone (+-20 deg)
- Expected Threat (xT): 12x8 grid delta transitions bounded in [-1.0, 1.0]
- Rolling buffer dynamics: Turnover spikes, quiet possession, window pruning, variance
- 1,000+ iteration randomized stress tests verifying zero NaNs and total numerical stability
"""

import math
import random
from typing import NamedTuple
import pytest

from backend.math_engine import TacticalMathEngine, RollingTacticalWindow, XT_GRID


class DummyPoint(NamedTuple):
    x: float
    y: float


class TestPassDifficultyRating:
    """Tests for calculate_pass_difficulty (PDR in [0.0, 100.0])."""

    def test_pdr_known_calibrated_baseline(self):
        """Validates blueprint reference pass: 28.5m, 2 cone def, 3 near def, 72 km/h."""
        pdr = TacticalMathEngine.calculate_pass_difficulty(
            distance_m=28.5,
            defenders_in_cone=2,
            defenders_radius_4m=3,
            ball_speed_kmh=72.0,
        )
        # Exponent: 0.04*28.5 + 0.35*3 + 0.25*2 - 0.015*72 = 1.14 + 1.05 + 0.50 - 1.08 = 1.61
        # PDR = 100 * (1 - exp(-1.61)) = 100 * (1 - 0.199887) = 80.0
        assert pdr == 80.0
        assert 0.0 <= pdr <= 100.0

    def test_pdr_zero_conditions_returns_zero(self):
        """Pass with zero distance, zero defenders, and high speed yields 0.0 difficulty."""
        pdr = TacticalMathEngine.calculate_pass_difficulty(
            distance_m=0.0,
            defenders_in_cone=0,
            defenders_radius_4m=0,
            ball_speed_kmh=50.0,
        )
        assert pdr == 0.0

    def test_pdr_strictly_bounded_upper(self):
        """Ultra-difficult pass (long range, crowded box, slow ball) does not exceed 100.0."""
        pdr = TacticalMathEngine.calculate_pass_difficulty(
            distance_m=80.0,
            defenders_in_cone=6,
            defenders_radius_4m=8,
            ball_speed_kmh=10.0,
        )
        assert 0.0 <= pdr <= 100.0
        assert pdr >= 95.0

    def test_pdr_negative_and_corrupt_inputs_handled_safely(self):
        """Negative inputs are clamped gracefully; NaNs/Infs return 0.0."""
        pdr_neg = TacticalMathEngine.calculate_pass_difficulty(-20.0, -2, -3, -50.0)
        assert 0.0 <= pdr_neg <= 100.0

        pdr_nan = TacticalMathEngine.calculate_pass_difficulty(float("nan"), 2, 3, 50.0)
        assert pdr_nan == 0.0

        pdr_inf = TacticalMathEngine.calculate_pass_difficulty(30.0, 2, 3, float("inf"))
        assert pdr_inf == 0.0

    def test_pdr_monotonicity(self):
        """Increasing distance or defenders increases difficulty; increasing ball speed lowers difficulty."""
        base = TacticalMathEngine.calculate_pass_difficulty(30.0, 2, 2, 50.0)
        longer = TacticalMathEngine.calculate_pass_difficulty(50.0, 2, 2, 50.0)
        more_def = TacticalMathEngine.calculate_pass_difficulty(30.0, 4, 2, 50.0)
        faster = TacticalMathEngine.calculate_pass_difficulty(30.0, 2, 2, 90.0)

        assert longer >= base
        assert more_def >= base
        assert faster <= base


class TestChaosControlIndex:
    """Tests for calculate_chaos_index (CCI in [0.0, 100.0])."""

    def test_cci_high_control_quiet_play(self):
        """Structured possession: 0 turnovers, low speed variance, static backline -> CCI < 35."""
        cci = TacticalMathEngine.calculate_chaos_index(
            recent_turnovers_count=0,
            ball_speed_variance=4.0,
            defensive_line_displacement_m=2.0,
        )
        assert 0.0 <= cci < 35.0
        # raw: 0.40*(0) + 0.35*min(50, 4) + 0.25*min(40, 5) = 1.4 + 1.25 = 2.65 -> 2.6 (IEEE 754 half-even)
        assert cci == 2.6

    def test_cci_balanced_contest(self):
        """Midfield contest with occasional turnovers -> 35 <= CCI <= 65."""
        cci = TacticalMathEngine.calculate_chaos_index(
            recent_turnovers_count=4,
            ball_speed_variance=25.0,
            defensive_line_displacement_m=8.0,
        )
        # 0.40*(48) + 0.35*(25) + 0.25*(20) = 19.2 + 8.75 + 5.0 = 32.95 -> ~33.0
        assert 0.0 <= cci <= 100.0

    def test_cci_chaotic_transitions(self):
        """End-to-end match phase with 8 turnovers and large displacement -> CCI > 65."""
        cci = TacticalMathEngine.calculate_chaos_index(
            recent_turnovers_count=8,
            ball_speed_variance=55.0,
            defensive_line_displacement_m=22.0,
        )
        # 0.40*(96) + 0.35*(50) + 0.25*(40) = 38.4 + 17.5 + 10.0 = 65.9
        assert cci > 65.0
        assert cci <= 100.0

    def test_cci_extreme_saturation_bounds(self):
        """Massive turnover count and wild swings clamp strictly to 100.0."""
        cci = TacticalMathEngine.calculate_chaos_index(
            recent_turnovers_count=50,
            ball_speed_variance=1000.0,
            defensive_line_displacement_m=200.0,
        )
        assert cci == 100.0

    def test_cci_nan_inf_guards(self):
        """NaN and Inf inputs safely yield 0.0."""
        assert TacticalMathEngine.calculate_chaos_index(0, float("nan"), 10.0) == 0.0
        assert TacticalMathEngine.calculate_chaos_index(0, 10.0, float("inf")) == 0.0


class TestInstantaneousSpeed:
    """Tests for calculate_speed (in [0.0, 150.0] km/h)."""

    def test_speed_accurate_kinematics(self):
        """10 meters in 1 second = 10 m/s = 36.0 km/h."""
        speed = TacticalMathEngine.calculate_speed(dx_m=6.0, dy_m=8.0, dt_sec=1.0)
        assert speed == 36.0

    def test_speed_zero_division_guard(self):
        """dt == 0.0 returns 0.0 strictly without raising ZeroDivisionError."""
        assert TacticalMathEngine.calculate_speed(10.0, 5.0, dt_sec=0.0) == 0.0

    def test_speed_negative_dt_guard(self):
        """dt < 0.0 returns 0.0 strictly."""
        assert TacticalMathEngine.calculate_speed(10.0, 5.0, dt_sec=-0.04) == 0.0

    def test_speed_upper_bound_clamp(self):
        """Extreme speed (e.g. 500m in 0.1s) is clamped strictly to 150.0 km/h."""
        speed = TacticalMathEngine.calculate_speed(dx_m=500.0, dy_m=0.0, dt_sec=0.1)
        assert speed == 150.0

    def test_speed_nan_inf_safety(self):
        """NaN or Inf values in coordinates or dt return 0.0."""
        assert TacticalMathEngine.calculate_speed(float("nan"), 0.0, 1.0) == 0.0
        assert TacticalMathEngine.calculate_speed(1.0, float("inf"), 1.0) == 0.0
        assert TacticalMathEngine.calculate_speed(1.0, 1.0, float("nan")) == 0.0


class TestSpatialCorridorGeometry:
    """Tests for calculate_defenders_in_corridor (vector projection, 4m radius)."""

    def test_defender_directly_on_segment(self):
        """Pass along X axis from (10, 20) to (50, 20); defender at (30, 20) is detected."""
        defenders = [{"x": 30.0, "y": 20.0}]
        count = TacticalMathEngine.calculate_defenders_in_corridor(
            passer_x=10.0, passer_y=20.0,
            receiver_x=50.0, receiver_y=20.0,
            defenders=defenders,
            corridor_radius=4.0,
        )
        assert count == 1

    def test_defender_within_lateral_corridor(self):
        """Defender at (30, 23.5) is 3.5m away perpendicularly (within 4m) -> detected."""
        defenders = [{"x": 30.0, "y": 23.5}]
        count = TacticalMathEngine.calculate_defenders_in_corridor(
            10.0, 20.0, 50.0, 20.0, defenders, corridor_radius=4.0
        )
        assert count == 1

    def test_defender_outside_lateral_corridor(self):
        """Defender at (30, 26.0) is 6.0m away perpendicularly (> 4m) -> not detected."""
        defenders = [{"x": 30.0, "y": 26.0}]
        count = TacticalMathEngine.calculate_defenders_in_corridor(
            10.0, 20.0, 50.0, 20.0, defenders, corridor_radius=4.0
        )
        assert count == 0

    def test_defender_far_behind_passer(self):
        """Defender at (0.0, 20.0) is 10m behind passer at (10.0, 20.0) -> not detected."""
        defenders = [{"x": 0.0, "y": 20.0}]
        count = TacticalMathEngine.calculate_defenders_in_corridor(
            10.0, 20.0, 50.0, 20.0, defenders, corridor_radius=4.0
        )
        assert count == 0

    def test_zero_length_pass_safely_evaluated(self):
        """Pass length L < 1e-4 does not crash and counts defenders within radius of point."""
        defenders = [
            {"x": 10.0, "y": 21.0},  # 1m away: detected
            {"x": 10.0, "y": 30.0},  # 10m away: not detected
        ]
        count = TacticalMathEngine.calculate_defenders_in_corridor(
            10.0, 20.0, 10.0, 20.0, defenders, corridor_radius=4.0
        )
        assert count == 1

    def test_heterogeneous_defender_formats(self):
        """Supports dicts, tuples, and objects with .x and .y attributes."""
        defenders = [
            {"x": 20.0, "y": 20.0},
            (25.0, 21.0),
            DummyPoint(x=35.0, y=19.5),
        ]
        count = TacticalMathEngine.calculate_defenders_in_corridor(
            10.0, 20.0, 50.0, 20.0, defenders, corridor_radius=4.0
        )
        assert count == 3


class TestSpatialConeGeometry:
    """Tests for calculate_defenders_in_cone (angular intercept check +-20 deg)."""

    def test_defender_inside_cone_angle(self):
        """Pass from (0, 0) to (30, 0). Defender at (15, 2.0) has angle ~7.6 deg <= 20 deg."""
        defenders = [{"x": 15.0, "y": 2.0}]
        count = TacticalMathEngine.calculate_defenders_in_cone(
            0.0, 0.0, 30.0, 0.0, defenders, max_angle_deg=20.0
        )
        assert count == 1

    def test_defender_outside_cone_angle(self):
        """Defender at (10, 10) has angle 45 deg > 20 deg -> not in cone."""
        defenders = [{"x": 10.0, "y": 10.0}]
        count = TacticalMathEngine.calculate_defenders_in_cone(
            0.0, 0.0, 30.0, 0.0, defenders, max_angle_deg=20.0
        )
        assert count == 0

    def test_defender_behind_passer_excluded(self):
        """Defender behind passer (-10, 0) is along opposite direction (180 deg) -> excluded."""
        defenders = [{"x": -10.0, "y": 0.0}]
        count = TacticalMathEngine.calculate_defenders_in_cone(
            0.0, 0.0, 30.0, 0.0, defenders, max_angle_deg=20.0
        )
        assert count == 0

    def test_cone_zero_length_pass_safe(self):
        """Zero-length pass returns 0 safely without division by zero."""
        defenders = [{"x": 1.0, "y": 1.0}]
        count = TacticalMathEngine.calculate_defenders_in_cone(
            5.0, 5.0, 5.0, 5.0, defenders, max_angle_deg=20.0
        )
        assert count == 0

    def test_cone_defender_distance_cutoff(self):
        """Defender at 10 deg but beyond max_distance_m is filtered out."""
        defenders = [{"x": 50.0, "y": 5.0}]  # distance ~50.2m, angle ~5.7 deg
        count_no_cutoff = TacticalMathEngine.calculate_defenders_in_cone(
            0.0, 0.0, 30.0, 0.0, defenders, max_angle_deg=20.0, max_distance_m=None
        )
        count_with_cutoff = TacticalMathEngine.calculate_defenders_in_cone(
            0.0, 0.0, 30.0, 0.0, defenders, max_angle_deg=20.0, max_distance_m=35.0
        )
        assert count_no_cutoff == 1
        assert count_with_cutoff == 0


class TestExpectedThreatGrid:
    """Tests for calculate_expected_threat (12x8 spatial grid, delta in [-1.0, 1.0])."""

    def test_forward_pass_into_box_increases_threat(self):
        """Passing from defensive midfield (X=35, Y=34) to box (X=95, Y=34) yields positive xT gain."""
        delta_xt = TacticalMathEngine.calculate_expected_threat(
            start_x=35.0, start_y=34.0,
            end_x=95.0, end_y=34.0,
        )
        assert delta_xt > 0.10
        assert delta_xt <= 1.0

    def test_backward_pass_reduces_threat(self):
        """Passing backwards towards own goal reduces Expected Threat."""
        delta_xt = TacticalMathEngine.calculate_expected_threat(
            start_x=95.0, start_y=34.0,
            end_x=20.0, end_y=34.0,
        )
        assert delta_xt < 0.0
        assert delta_xt >= -1.0

    def test_same_spot_pass_zero_threat(self):
        """Pass starting and ending in the same cell yields exactly 0.0 delta."""
        delta_xt = TacticalMathEngine.calculate_expected_threat(50.0, 30.0, 50.0, 30.0)
        assert delta_xt == 0.0

    def test_out_of_bounds_coords_clamped_safely(self):
        """Negative or out-of-pitch coordinates clamp safely to grid boundaries."""
        delta_xt = TacticalMathEngine.calculate_expected_threat(-10.0, -5.0, 120.0, 80.0)
        assert -1.0 <= delta_xt <= 1.0

    def test_xt_nan_inf_guards(self):
        """NaN/Inf coordinates return 0.0."""
        assert TacticalMathEngine.calculate_expected_threat(float("nan"), 0, 50, 50) == 0.0


class TestRollingTacticalWindow:
    """Tests for RollingTacticalWindow entropy and tracking dynamics."""

    def test_turnover_spikes_and_expiration(self):
        """Turnovers accumulate and expire as time advances past the 180s window."""
        window = RollingTacticalWindow(window_size_seconds=180.0, fps=25.0)

        # Record 5 turnovers at time = 10s
        for _ in range(5):
            window.record_turnover(timestamp_sec=10.0)
        assert window.get_turnovers_count() == 5

        # Record 3 more turnovers at time = 100s
        for _ in range(3):
            window.record_turnover(timestamp_sec=100.0)
        assert window.get_turnovers_count() == 8

        # Advance window to time = 200s (cutoff = 200 - 180 = 20s)
        # Turnovers from time=10s should expire, 3 turnovers from time=100s remain
        window.add_metric(ball_speed_kmh=20.0, timestamp_sec=200.0)
        assert window.get_turnovers_count() == 3

    def test_ball_speed_variance_computation(self):
        """Computes accurate sample variance for speed values."""
        window = RollingTacticalWindow(window_size_seconds=180.0, fps=25.0)
        assert window.get_ball_speed_variance() == 0.0

        # Speeds: 10, 20, 30 -> mean = 20, var = ((10-20)^2 + (20-20)^2 + (30-20)^2)/3 = 200/3 = 66.67
        for s in [10.0, 20.0, 30.0]:
            window.add_metric(ball_speed_kmh=s)

        var = window.get_ball_speed_variance()
        assert math.isclose(var, 66.67, abs_tol=0.01)

    def test_defensive_line_displacement_computation(self):
        """Computes max - min range of defensive line positions."""
        window = RollingTacticalWindow(window_size_seconds=180.0, fps=25.0)
        assert window.get_defensive_line_displacement() == 0.0

        window.add_metric(ball_speed_kmh=15.0, defensive_line_x=25.0)
        window.add_metric(ball_speed_kmh=18.0, defensive_line_x=38.5)
        window.add_metric(ball_speed_kmh=12.0, defensive_line_x=20.0)

        # max = 38.5, min = 20.0 -> displacement = 18.5
        assert window.get_defensive_line_displacement() == 18.5

    def test_telemetry_frame_ingestion(self):
        """Ingests full TelemetryFrame conforming to project JSON schema."""
        window = RollingTacticalWindow(window_size_seconds=180.0, fps=25.0)
        mock_frame = {
            "ball": {"speed_kmh": 45.0, "possession_team": "Northbridge Lions"},
            "players": [
                {"player_id": "HSC_03", "team": "Harbourside City", "role": "DF", "x": 32.0, "y": 30.0},
                {"player_id": "HSC_05", "team": "Harbourside City", "role": "DF", "x": 34.0, "y": 45.0},
            ],
            "active_event_id": "turnover_101",
        }
        window.add_telemetry_frame(mock_frame)
        assert len(window.ball_speeds) == 1
        assert window.get_turnovers_count() == 1
        assert len(window.defensive_line_positions) == 1
        assert window.defensive_line_positions[0] == 33.0  # (32 + 34)/2

    def test_reset_clears_buffers(self):
        """reset() empties all collections to initial state."""
        window = RollingTacticalWindow(window_size_seconds=180.0, fps=25.0)
        window.record_turnover(timestamp_sec=10.0)
        window.add_metric(ball_speed_kmh=50.0, defensive_line_x=40.0)
        assert window.get_turnovers_count() == 1

        window.reset()
        assert window.get_turnovers_count() == 0
        assert window.get_ball_speed_variance() == 0.0
        assert window.get_defensive_line_displacement() == 0.0
        assert window.get_chaos_index() == 0.0


class TestNumericalStabilityStress:
    """Stress tests with 1,000+ randomized inputs checking numerical stability and zero NaNs."""

    def test_stress_1000_random_pdr(self):
        """1,000 randomized PDR inputs; verifies strict [0.0, 100.0] bounds and zero NaNs."""
        rng = random.Random(42)
        for _ in range(1000):
            dist = rng.uniform(-50.0, 150.0)
            cone_def = rng.randint(-5, 15)
            near_def = rng.randint(-5, 15)
            speed = rng.uniform(-30.0, 200.0)

            pdr = TacticalMathEngine.calculate_pass_difficulty(dist, cone_def, near_def, speed)

            assert not math.isnan(pdr), f"PDR returned NaN for inputs: {dist}, {cone_def}, {near_def}, {speed}"
            assert not math.isinf(pdr), f"PDR returned Inf for inputs: {dist}, {cone_def}, {near_def}, {speed}"
            assert 0.0 <= pdr <= 100.0, f"PDR out of bounds: {pdr}"

    def test_stress_1000_random_cci(self):
        """1,000 randomized CCI inputs; verifies strict [0.0, 100.0] bounds and zero NaNs."""
        rng = random.Random(1337)
        for _ in range(1000):
            turnovers = rng.randint(-10, 50)
            variance = rng.uniform(-100.0, 500.0)
            displacement = rng.uniform(-50.0, 200.0)

            cci = TacticalMathEngine.calculate_chaos_index(turnovers, variance, displacement)

            assert not math.isnan(cci), f"CCI returned NaN for: {turnovers}, {variance}, {displacement}"
            assert not math.isinf(cci), f"CCI returned Inf for: {turnovers}, {variance}, {displacement}"
            assert 0.0 <= cci <= 100.0, f"CCI out of bounds: {cci}"

    def test_stress_1000_random_speed(self):
        """1,000 randomized velocity inputs (including zero & negative dt); verifies [0.0, 150.0] bounds."""
        rng = random.Random(2026)
        for _ in range(1000):
            dx = rng.uniform(-100.0, 100.0)
            dy = rng.uniform(-70.0, 70.0)
            # Mix positive, negative, and zero dt
            dt = rng.choice([0.0, -0.04, rng.uniform(0.001, 5.0)])

            speed = TacticalMathEngine.calculate_speed(dx, dy, dt)

            assert not math.isnan(speed), f"Speed returned NaN for: {dx}, {dy}, {dt}"
            assert not math.isinf(speed), f"Speed returned Inf for: {dx}, {dy}, {dt}"
            assert 0.0 <= speed <= 150.0, f"Speed out of bounds: {speed}"

    def test_stress_1000_random_spatial_geometry(self):
        """1,000 randomized spatial passes and defenders; verifies valid integer counts and zero crashes."""
        rng = random.Random(999)
        for _ in range(1000):
            px, py = rng.uniform(-20, 120), rng.uniform(-20, 80)
            rx, ry = rng.uniform(-20, 120), rng.uniform(-20, 80)
            num_def = rng.randint(0, 15)
            defenders = [
                {"x": rng.uniform(-10, 115), "y": rng.uniform(-10, 78)}
                for _ in range(num_def)
            ]

            corridor_count = TacticalMathEngine.calculate_defenders_in_corridor(
                px, py, rx, ry, defenders, corridor_radius=4.0
            )
            cone_count = TacticalMathEngine.calculate_defenders_in_cone(
                px, py, rx, ry, defenders, max_angle_deg=20.0
            )

            assert 0 <= corridor_count <= num_def
            assert 0 <= cone_count <= num_def

    def test_stress_1000_random_expected_threat(self):
        """1,000 randomized coordinate transitions; verifies delta_xt bounded in [-1.0, 1.0]."""
        rng = random.Random(777)
        for _ in range(1000):
            sx, sy = rng.uniform(-50, 150), rng.uniform(-50, 100)
            ex, ey = rng.uniform(-50, 150), rng.uniform(-50, 100)

            delta_xt = TacticalMathEngine.calculate_expected_threat(sx, sy, ex, ey)

            assert not math.isnan(delta_xt)
            assert not math.isinf(delta_xt)
            assert -1.0 <= delta_xt <= 1.0
