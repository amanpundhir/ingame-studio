"""
InGame Studio - 25Hz Physics & Kinematics Engine
Simulates 22 players and 1 ball with realistic kinematics,
pitch boundary enforcement (105m x 68m), 3D ball trajectory, gravity, bounce restitution,
and zero-division guards.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple, Any


@dataclass
class Vector2D:
    x: float
    y: float

    def distance_to(self, other: Vector2D) -> float:
        return math.hypot(self.x - other.x, self.y - other.y)

    def magnitude(self) -> float:
        return math.hypot(self.x, self.y)

    def normalized(self) -> Vector2D:
        mag = self.magnitude()
        if mag <= 1e-7:
            return Vector2D(0.0, 0.0)
        return Vector2D(self.x / mag, self.y / mag)


@dataclass
class Vector3D:
    x: float
    y: float
    z: float

    def distance_to(self, other: Vector3D) -> float:
        return math.sqrt((self.x - other.x) ** 2 + (self.y - other.y) ** 2 + (self.z - other.z) ** 2)

    def magnitude(self) -> float:
        return math.sqrt(self.x ** 2 + self.y ** 2 + self.z ** 2)


@dataclass
class BallState:
    x: float = 52.5
    y: float = 34.0
    z: float = 0.0
    vx: float = 0.0
    vy: float = 0.0
    vz: float = 0.0
    speed_kmh: float = 0.0
    possession_team: Optional[str] = None
    possessed_by_player_id: Optional[str] = None
    status: str = "in_play"  # in_play, dead_ball, out_of_bounds, goal

    def to_dict(self) -> Dict[str, Any]:
        return {
            "x": round(float(self.x), 2),
            "y": round(float(self.y), 2),
            "z": round(float(max(0.0, min(25.0, self.z))), 2),
            "vx": round(float(self.vx), 3),
            "vy": round(float(self.vy), 3),
            "vz": round(float(self.vz), 3),
            "speed_kmh": round(float(max(0.0, min(150.0, self.speed_kmh))), 2),
            "possession_team": self.possession_team,
            "possessed_by_player_id": self.possessed_by_player_id,
            "status": self.status,
        }


@dataclass
class PlayerState:
    player_id: str
    team: str  # "home" | "away"
    jersey_number: int
    name: str
    role: str  # "GK", "DF", "MF", "FW"
    x: float
    y: float
    vx: float = 0.0
    vy: float = 0.0
    speed_kmh: float = 0.0
    is_visible: bool = True

    def to_dict(self) -> Dict[str, Any]:
        return {
            "player_id": self.player_id,
            "team": self.team,
            "jersey_number": int(self.jersey_number),
            "name": self.name,
            "role": self.role,
            "x": round(float(max(0.0, min(105.0, self.x))), 2),
            "y": round(float(max(0.0, min(68.0, self.y))), 2),
            "vx": round(float(self.vx), 3),
            "vy": round(float(self.vy), 3),
            "speed_kmh": round(float(max(0.0, min(36.0, self.speed_kmh))), 2),
            "is_visible": bool(self.is_visible),
        }


class PhysicsEngine:
    """
    Simulates physical dynamics of 22 players and 1 ball on a 105m x 68m pitch.
    Enforces strict 25Hz temporal resolution (dt = 0.04s), realistic kinematic bounds,
    gravitational acceleration, ground bounce restitution, and friction.
    """

    PITCH_LENGTH: float = 105.0
    PITCH_WIDTH: float = 68.0
    FRAME_RATE_HZ: float = 25.0
    DEFAULT_DT: float = 1.0 / 25.0  # 0.04s

    # Ball physical constants
    GRAVITY: float = 9.81  # m/s^2
    RESTITUTION: float = 0.65  # ground bounce coefficient
    GROUND_FRICTION: float = 0.985  # velocity decay factor per frame on ground
    AIR_DRAG: float = 0.998  # velocity decay factor in air
    MAX_BALL_SPEED_KMH: float = 150.0  # Acceptance criteria max 150 km/h (41.67 m/s)
    MAX_BALL_SPEED_MPS: float = 150.0 / 3.6  # 41.667 m/s

    # Player physical constants
    MAX_PLAYER_SPEED_KMH: float = 36.0  # 10.0 m/s
    MAX_PLAYER_SPEED_MPS: float = 36.0 / 3.6  # 10.0 m/s
    MAX_PLAYER_ACCEL_MPS2: float = 5.0  # m/s^2 acceleration limit
    MAX_PLAYER_DECEL_MPS2: float = -6.0  # m/s^2 deceleration limit

    @staticmethod
    def calculate_speed(dx_m: float, dy_m: float, dt_sec: float) -> float:
        """
        Calculates instantaneous speed in km/h with zero-division guard.
        If dt_sec <= 0, returns 0.0 km/h.
        """
        if dt_sec <= 0.0:
            return 0.0
        distance_m = math.hypot(dx_m, dy_m)
        speed_mps = distance_m / dt_sec
        speed_kmh = speed_mps * 3.6
        return round(float(speed_kmh), 2)

    @staticmethod
    def calculate_speed_3d(dx_m: float, dy_m: float, dz_m: float, dt_sec: float) -> float:
        """
        Calculates 3D instantaneous speed in km/h with zero-division guard.
        """
        if dt_sec <= 0.0:
            return 0.0
        distance_m = math.sqrt(dx_m * dx_m + dy_m * dy_m + dz_m * dz_m)
        speed_mps = distance_m / dt_sec
        speed_kmh = min(150.0, speed_mps * 3.6)
        return round(float(speed_kmh), 2)

    def clamp_pitch_bounds(self, x: float, y: float) -> Tuple[float, float]:
        """
        Clamps coordinate strictly within 105m x 68m pitch boundaries.
        """
        clamped_x = max(0.0, min(self.PITCH_LENGTH, float(x)))
        clamped_y = max(0.0, min(self.PITCH_WIDTH, float(y)))
        return round(clamped_x, 2), round(clamped_y, 2)

    @staticmethod
    def compute_ballistic_elevation(u: float, h_peak: float) -> float:
        """
        Computes 3D parabolic elevation Z(u) = 4 * h_peak * u * (1 - u).
        u: normalized trajectory progress in [0.0, 1.0]
        h_peak: peak flight altitude in meters [1.5, 6.0]
        """
        if u <= 0.0 or u >= 1.0 or h_peak <= 0.0:
            return 0.0
        return float(max(0.0, 4.0 * h_peak * u * (1.0 - u)))

    def step_ball(self, ball: BallState, dt: float = 0.04) -> BallState:
        """
        Advances ball state by time step dt:
        - Position integration (x, y, z)
        - Gravitational acceleration (g = 9.81 m/s^2)
        - Ground impact restitution (e = 0.65)
        - Ground friction damping (0.985)
        - Speed cap enforcement (0.0 <= speed <= 150.0 km/h)
        - Pitch boundary enforcement
        """
        if dt <= 0.0:
            dt = self.DEFAULT_DT

        # Current velocities in m/s
        vx = ball.vx
        vy = ball.vy
        vz = ball.vz

        # Air drag damping
        vx *= self.AIR_DRAG
        vy *= self.AIR_DRAG

        # Gravity acting on vertical velocity
        vz -= self.GRAVITY * dt

        # Position updates
        new_x = ball.x + vx * dt
        new_y = ball.y + vy * dt
        new_z = ball.z + vz * dt

        # Ground collision check
        if new_z <= 0.0:
            new_z = 0.0
            if abs(vz) > 0.2:
                vz = -self.RESTITUTION * vz  # Bounce with restitution
            else:
                vz = 0.0  # Stop micro-jitter when settled
            # Apply ground friction to horizontal velocity
            vx *= self.GROUND_FRICTION
            vy *= self.GROUND_FRICTION

        # Pitch boundary checks
        status = ball.status
        if new_x < 0.0 or new_x > self.PITCH_LENGTH or new_y < 0.0 or new_y > self.PITCH_WIDTH:
            # Check if within goal mouth (x <= 0 or x >= 105, 30.34 <= y <= 37.66, z <= 2.44)
            is_goal_y = 30.34 <= new_y <= 37.66
            is_goal_z = new_z <= 2.44
            if (new_x < 0.0 or new_x > self.PITCH_LENGTH) and is_goal_y and is_goal_z:
                status = "goal"
            else:
                status = "out_of_bounds"

            # Clamp coordinates to pitch boundary
            new_x = max(0.0, min(self.PITCH_LENGTH, new_x))
            new_y = max(0.0, min(self.PITCH_WIDTH, new_y))
            # Reverse and damp velocity upon hitting pitch perimeter
            vx = -0.3 * vx
            vy = -0.3 * vy
        elif status in ["out_of_bounds", "dead_ball"] and 0.0 <= new_x <= self.PITCH_LENGTH and 0.0 <= new_y <= self.PITCH_WIDTH:
            status = "in_play"

        # Calculate instantaneous speed in km/h
        speed_mps = math.sqrt(vx * vx + vy * vy + vz * vz)
        speed_kmh = speed_mps * 3.6

        # Strictly enforce maximum ball speed cap 150.0 km/h
        if speed_kmh > self.MAX_BALL_SPEED_KMH:
            scale = self.MAX_BALL_SPEED_MPS / max(1e-6, speed_mps)
            vx *= scale
            vy *= scale
            vz *= scale
            speed_kmh = self.MAX_BALL_SPEED_KMH

        # Update and return state
        ball.x = round(new_x, 2)
        ball.y = round(new_y, 2)
        ball.z = round(max(0.0, min(25.0, new_z)), 2)
        ball.vx = round(vx, 3)
        ball.vy = round(vy, 3)
        ball.vz = round(vz, 3)
        ball.speed_kmh = round(speed_kmh, 2)
        ball.status = status

        return ball

    def step_player(
        self,
        player: PlayerState,
        target_x: float,
        target_y: float,
        dt: float = 0.04,
        max_speed_kmh: float = 36.0,
    ) -> PlayerState:
        """
        Advances player position toward target_x, target_y respecting:
        - Max sprint speed cap (<= 36.0 km/h = 10.0 m/s)
        - Acceleration / deceleration envelopes (<= 5 m/s^2, >= -6 m/s^2)
        - Pitch boundary clamping [0.0, 105.0], [0.0, 68.0]
        - Non-null values guaranteed
        """
        if dt <= 0.0:
            dt = self.DEFAULT_DT

        target_x, target_y = self.clamp_pitch_bounds(target_x, target_y)

        dx = target_x - player.x
        dy = target_y - player.y
        dist = math.hypot(dx, dy)

        if dist < 0.02:
            # Player has reached target anchor
            player.vx = 0.0
            player.vy = 0.0
            player.speed_kmh = 0.0
            return player

        # Direction vector
        dir_x = dx / dist
        dir_y = dy / dist

        # Desired speed capped to player max sprint (36 km/h)
        speed_cap_mps = min(self.MAX_PLAYER_SPEED_MPS, max_speed_kmh / 3.6)
        # Slow down as target approaches
        # Players jog when the target is near and sprint only when it is far, instead of
        # running flat out whenever they are more than a metre away.
        desired_speed_mps = min(speed_cap_mps, 0.45 * dist)

        # Target velocity
        target_vx = dir_x * desired_speed_mps
        target_vy = dir_y * desired_speed_mps

        # Current velocity
        current_vx = player.vx
        current_vy = player.vy

        # Velocity delta
        dvx = target_vx - current_vx
        dvy = target_vy - current_vy
        dv_mag = math.hypot(dvx, dvy)
        max_dv = self.MAX_PLAYER_ACCEL_MPS2 * dt

        if dv_mag > max_dv:
            current_vx += (dvx / dv_mag) * max_dv
            current_vy += (dvy / dv_mag) * max_dv
        else:
            current_vx = target_vx
            current_vy = target_vy

        # Check sprint speed limit
        actual_speed_mps = math.hypot(current_vx, current_vy)
        if actual_speed_mps > self.MAX_PLAYER_SPEED_MPS:
            scale = self.MAX_PLAYER_SPEED_MPS / actual_speed_mps
            current_vx *= scale
            current_vy *= scale
            actual_speed_mps = self.MAX_PLAYER_SPEED_MPS

        # Maximum displacement per frame cap (0.40m at 25Hz / 36 km/h)
        max_displacement = actual_speed_mps * dt
        step_dx = current_vx * dt
        step_dy = current_vy * dt
        step_dist = math.hypot(step_dx, step_dy)
        if step_dist > max_displacement and step_dist > 0.0:
            scale = max_displacement / step_dist
            step_dx *= scale
            step_dy *= scale
            step_dist = max_displacement

        # Arrival: if remaining distance to target is less than step displacement, step cleanly onto target
        if dist <= step_dist:
            new_x = target_x
            new_y = target_y
            current_vx = 0.0
            current_vy = 0.0
            speed_kmh = 0.0
        else:
            # New coordinates clamped to pitch bounds
            new_x = max(0.0, min(self.PITCH_LENGTH, player.x + step_dx))
            new_y = max(0.0, min(self.PITCH_WIDTH, player.y + step_dy))
            speed_kmh = round(actual_speed_mps * 3.6, 2)
            speed_kmh = min(self.MAX_PLAYER_SPEED_KMH, max(0.0, speed_kmh))

        player.x = round(new_x, 2)
        player.y = round(new_y, 2)
        player.vx = round(current_vx, 3)
        player.vy = round(current_vy, 3)
        player.speed_kmh = speed_kmh

        return player

    def kick_ball(
        self,
        ball: BallState,
        target_x: float,
        target_y: float,
        target_z: float = 0.0,
        speed_kmh: float = 70.0,
        possession_team: Optional[str] = None,
        possessed_by_player_id: Optional[str] = None,
    ) -> BallState:
        """
        Applies a kick impulse to the ball directed toward (target_x, target_y, target_z).
        Speed is bounded to [0.0, 150.0] km/h.
        """
        clamped_speed_kmh = max(0.0, min(self.MAX_BALL_SPEED_KMH, float(speed_kmh)))
        speed_mps = clamped_speed_kmh / 3.6

        dx = target_x - ball.x
        dy = target_y - ball.y
        dz = target_z - ball.z
        dist_3d = math.sqrt(dx * dx + dy * dy + dz * dz)

        if dist_3d <= 1e-4:
            ball.vx = 0.0
            ball.vy = 0.0
            ball.vz = 0.0
            ball.speed_kmh = 0.0
        else:
            ball.vx = round((dx / dist_3d) * speed_mps, 3)
            ball.vy = round((dy / dist_3d) * speed_mps, 3)
            ball.vz = round((dz / dist_3d) * speed_mps, 3)
            ball.speed_kmh = round(clamped_speed_kmh, 2)

        ball.possession_team = possession_team
        ball.possessed_by_player_id = possessed_by_player_id
        ball.status = "in_play"

        return ball
