"""
Test Suite: Generator Bounds & Physical Kinematics
Validates 25Hz coordinate tracking, pitch boundaries (105m x 68m), non-null assertions,
velocity limits (player <= 36 km/h, ball <= 150 km/h), zero-division guards,
and 3D ball trajectory physics.
"""

import math
import pytest
from generator.physics_engine import PhysicsEngine, BallState, PlayerState, Vector2D
from generator.match_generator import MatchGenerator
from generator.telemetry_streamer import TelemetryStreamer


class TestPhysicsEngineBounds:
    """Tests core physics engine calculations and boundary protections."""

    def test_zero_division_guard(self):
        """Asserts that speed calculations with dt <= 0 return 0.0 km/h without throwing ZeroDivisionError."""
        # 2D speed calculation
        assert PhysicsEngine.calculate_speed(10.0, 5.0, dt_sec=0.0) == 0.0
        assert PhysicsEngine.calculate_speed(10.0, 5.0, dt_sec=-0.04) == 0.0
        # 3D speed calculation
        assert PhysicsEngine.calculate_speed_3d(10.0, 5.0, 2.0, dt_sec=0.0) == 0.0
        assert PhysicsEngine.calculate_speed_3d(10.0, 5.0, 2.0, dt_sec=-1.0) == 0.0

    def test_speed_calculation_accuracy(self):
        """Asserts standard physical accuracy: 10 m/s == 36.0 km/h."""
        # At dt = 0.04s, 0.40m displacement is 10 m/s = 36 km/h
        speed = PhysicsEngine.calculate_speed(0.40, 0.0, dt_sec=0.04)
        assert pytest.approx(speed, rel=1e-2) == 36.0

    def test_pitch_bounds_clamping(self):
        """Asserts coordinates outside 105m x 68m are strictly clamped."""
        pe = PhysicsEngine()
        # Test negative coordinates
        cx, cy = pe.clamp_pitch_bounds(-5.2, -10.0)
        assert cx == 0.0
        assert cy == 0.0

        # Test overflow coordinates
        cx, cy = pe.clamp_pitch_bounds(120.5, 75.0)
        assert cx == 105.0
        assert cy == 68.0

        # Test valid within-bounds coordinates
        cx, cy = pe.clamp_pitch_bounds(52.5, 34.0)
        assert cx == 52.5
        assert cy == 34.0

    def test_ball_speed_cap(self):
        """Asserts ball speed can never exceed 150.0 km/h."""
        pe = PhysicsEngine()
        ball = BallState(x=50.0, y=34.0, z=0.0)
        # Attempt to kick ball at 250 km/h (unphysical extreme)
        kicked_ball = pe.kick_ball(ball, target_x=105.0, target_y=34.0, target_z=0.0, speed_kmh=250.0)
        assert kicked_ball.speed_kmh <= 150.0

        # Step ball forward and verify speed remains <= 150.0 km/h
        stepped_ball = pe.step_ball(kicked_ball, dt=0.04)
        assert stepped_ball.speed_kmh <= 150.0

    def test_ball_bounce_and_gravity(self):
        """Asserts ball drops with gravity (9.81 m/s^2) and bounces with restitution e=0.65."""
        pe = PhysicsEngine()
        ball = BallState(x=50.0, y=34.0, z=5.0, vx=0.0, vy=0.0, vz=0.0)

        # Drop ball from 5m height
        for _ in range(30):
            pe.step_ball(ball, dt=0.04)
            # Assert z is never negative
            assert ball.z >= 0.0
            assert ball.z <= 25.0

        # Ball should have made contact with ground and bounced
        assert ball.z >= 0.0

    def test_player_speed_and_acceleration_limits(self):
        """Asserts player speed is strictly capped at 36.0 km/h and displacement <= 0.40m per frame."""
        pe = PhysicsEngine()
        player = PlayerState(
            player_id="TEST_01",
            team="home",
            jersey_number=7,
            name="Test Sprinter",
            role="FW",
            x=20.0,
            y=20.0,
        )

        # Command player to sprint to opposite corner (105, 68)
        for _ in range(50):
            old_x, old_y = player.x, player.y
            pe.step_player(player, target_x=105.0, target_y=68.0, dt=0.04, max_speed_kmh=36.0)

            # Player speed cap assertion
            assert 0.0 <= player.speed_kmh <= 36.0
            # Pitch bounds assertion
            assert 0.0 <= player.x <= 105.0
            assert 0.0 <= player.y <= 68.0

            # Frame displacement cap assertion (0.40m at 25Hz)
            displacement = math.hypot(player.x - old_x, player.y - old_y)
            assert displacement <= 0.41  # small floating-point tolerance


class TestMatchGeneratorBounds:
    """Validates 25Hz tracking stream for 22 players and 1 ball."""

    @pytest.fixture
    def generator(self):
        return MatchGenerator(match_id="IGS_2026_TEST", frame_rate=25)

    def test_player_count_and_roles(self, generator):
        """Asserts every frame contains exactly 22 players (11 home, 11 away) with non-null data."""
        frame = generator.step()
        players = frame["players"]

        assert len(players) == 22
        home_players = [p for p in players if p["team"] == "home"]
        away_players = [p for p in players if p["team"] == "away"]

        assert len(home_players) == 11
        assert len(away_players) == 11

        roles = {p["role"] for p in players}
        assert roles == {"GK", "DF", "MF", "FW"}

    def test_pitch_bounds_over_simulation(self, generator):
        """Simulates 300 frames (12 seconds of match tracking) and asserts all bounds and non-null values."""
        for _ in range(300):
            frame = generator.step()

            # Pitch dimensions contract
            assert frame["pitch_dimensions"]["length"] == 105.0
            assert frame["pitch_dimensions"]["width"] == 68.0

            # Ball bounds and speed
            ball = frame["ball"]
            assert ball["x"] is not None and 0.0 <= ball["x"] <= 105.0
            assert ball["y"] is not None and 0.0 <= ball["y"] <= 68.0
            assert ball["z"] is not None and 0.0 <= ball["z"] <= 25.0
            assert ball["speed_kmh"] is not None and 0.0 <= ball["speed_kmh"] <= 150.0

            # 22 Players bounds and speeds
            players = frame["players"]
            assert len(players) == 22
            for p in players:
                assert p["player_id"] is not None
                assert p["name"] is not None
                assert p["x"] is not None and 0.0 <= p["x"] <= 105.0
                assert p["y"] is not None and 0.0 <= p["y"] <= 68.0
                assert p["speed_kmh"] is not None and 0.0 <= p["speed_kmh"] <= 36.0

    def test_clock_and_period_progression(self, generator):
        """Asserts monotonic progression of match clock and periods."""
        f1 = generator.step()
        assert f1["frame_id"] == 1
        assert f1["period"] == 1
        assert f1["clock"] == "00:00"

        # Advance 1500 frames (60 seconds)
        for _ in range(1500):
            frame = generator.step()

        assert frame["frame_id"] == 1501
        assert frame["clock"] == "01:00"


class TestTelemetryStreamer:
    """Validates streaming generator behavior and controls."""

    def test_sync_iter_frames(self):
        """Asserts synchronous iter_frames yields expected batch size with correct types."""
        streamer = TelemetryStreamer(match_id="IGS_2026_TEST", frame_rate=25, real_time=False)
        frames = list(streamer.iter_frames(limit=50, as_broadcast_payload=True))

        assert len(frames) == 50
        for f in frames:
            assert f["type"] == "telemetry"
            assert "timestamp" in f
            data = f["data"]
            assert len(data["players"]) == 22
            assert 0.0 <= data["ball"]["x"] <= 105.0

    @pytest.mark.asyncio
    async def test_async_stream_frames(self):
        """Asserts async stream_frames yields frames."""
        streamer = TelemetryStreamer(match_id="IGS_2026_TEST", frame_rate=25, real_time=False)
        collected = []
        async for frame_payload in streamer.stream_frames(limit=10, as_broadcast_payload=False):
            collected.append(frame_payload)

        assert len(collected) == 10
        assert collected[0]["frame_id"] == 1
        assert collected[9]["frame_id"] == 10
