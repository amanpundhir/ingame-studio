"""Tactical Math & Spatial Metrics Engine for InGame Studio.

Calculates real-time, explainable tactical metrics from tracking telemetry:
- Pass Difficulty Rating (PDR in [0.0, 100.0])
- Chaos vs. Control Rhythm Index (CCI in [0.0, 100.0])
- Instantaneous Speed & Shot Velocity in km/h (in [0.0, 150.0])
- Spatial Geometry: Passing corridor density and intercept angle cone
- Expected Threat (xT) 12x8 grid transition deltas
- RollingTacticalWindow for entropy and line dynamics tracking
"""

from collections import deque
import math
from backend.pitch import to_attack_frame, to_attack_frame_y, side_of as _side_of
from typing import Any, Dict, List, Optional, Set, Tuple, Union


# Standard 12x8 Expected Threat (xT) Grid for 105m x 68m pitch
# 12 columns along X (length 0..105m, step = 8.75m)
# 8 rows along Y (width 0..68m, step = 8.50m)
XT_GRID: List[List[float]] = [
    # col 0 (own goal / 0.00m - 8.75m)
    [0.001, 0.001, 0.002, 0.002, 0.002, 0.002, 0.001, 0.001],
    # col 1 (8.75m - 17.50m)
    [0.002, 0.002, 0.003, 0.003, 0.003, 0.003, 0.002, 0.002],
    # col 2 (17.50m - 26.25m)
    [0.003, 0.003, 0.004, 0.005, 0.005, 0.004, 0.003, 0.003],
    # col 3 (26.25m - 35.00m)
    [0.004, 0.005, 0.006, 0.007, 0.007, 0.006, 0.005, 0.004],
    # col 4 (35.00m - 43.75m)
    [0.006, 0.007, 0.009, 0.011, 0.011, 0.009, 0.007, 0.006],
    # col 5 (43.75m - 52.50m)
    [0.008, 0.010, 0.013, 0.016, 0.016, 0.013, 0.010, 0.008],
    # col 6 (52.50m - 61.25m / midfield)
    [0.011, 0.014, 0.019, 0.024, 0.024, 0.019, 0.014, 0.011],
    # col 7 (61.25m - 70.00m)
    [0.015, 0.020, 0.028, 0.036, 0.036, 0.028, 0.020, 0.015],
    # col 8 (70.00m - 78.75m / final third)
    [0.022, 0.031, 0.046, 0.062, 0.062, 0.046, 0.031, 0.022],
    # col 9 (78.75m - 87.50m / penalty zone edge)
    [0.032, 0.048, 0.082, 0.125, 0.125, 0.082, 0.048, 0.032],
    # col 10 (87.50m - 96.25m / box)
    [0.045, 0.075, 0.155, 0.245, 0.245, 0.155, 0.075, 0.045],
    # col 11 (96.25m - 105.00m / 6-yd box & goalmouth)
    [0.060, 0.110, 0.220, 0.350, 0.350, 0.220, 0.110, 0.060],
]


def _extract_coords(p: Any) -> Optional[Tuple[float, float]]:
    """Safely extracts (x, y) coordinates from a player dict, object, or tuple."""
    if p is None:
        return None
    if isinstance(p, dict):
        x = p.get("x", p.get("location_x"))
        y = p.get("y", p.get("location_y"))
        if x is not None and y is not None:
            try:
                xf, yf = float(x), float(y)
                if not (math.isnan(xf) or math.isnan(yf) or math.isinf(xf) or math.isinf(yf)):
                    return xf, yf
            except (ValueError, TypeError):
                return None
    elif hasattr(p, "x") and hasattr(p, "y"):
        try:
            xf, yf = float(p.x), float(p.y)
            if not (math.isnan(xf) or math.isnan(yf) or math.isinf(xf) or math.isinf(yf)):
                return xf, yf
        except (ValueError, TypeError):
            return None
    elif isinstance(p, (list, tuple)) and len(p) >= 2:
        try:
            xf, yf = float(p[0]), float(p[1])
            if not (math.isnan(xf) or math.isnan(yf) or math.isinf(xf) or math.isinf(yf)):
                return xf, yf
        except (ValueError, TypeError):
            return None
    return None


class TacticalMathEngine:
    """Core mathematical engine for tactical and physical metrics."""

    @staticmethod
    def calculate_pass_difficulty(
        distance_m: float,
        defenders_in_cone: int,
        defenders_radius_4m: int,
        ball_speed_kmh: float,
    ) -> float:
        """Calculates Pass Difficulty Rating (PDR) bounded strictly in [0.0, 100.0].

        Formula:
            PDR = 100 * (1 - exp(-max(0.0, 0.04*d + 0.35*rho + 0.25*theta - 0.015*v)))

        Args:
            distance_m: Euclidean pass length in meters.
            defenders_in_cone: Count of defenders inside the angular intercept cone (+-20 deg).
            defenders_radius_4m: Count of defenders within 4m of the passing corridor.
            ball_speed_kmh: Ball travel velocity in km/h.

        Returns:
            Pass Difficulty Rating float in [0.0, 100.0] rounded to 1 decimal place.
        """
        # Guard against NaN/inf inputs
        if any(
            math.isnan(v) or math.isinf(v)
            for v in (distance_m, float(defenders_in_cone), float(defenders_radius_4m), ball_speed_kmh)
        ):
            return 0.0

        d_pass = max(0.0, float(distance_m))
        rho_def = max(0.0, float(defenders_radius_4m))
        theta_cone = max(0.0, float(defenders_in_cone))
        v_ball = max(0.0, float(ball_speed_kmh))

        exponent = (
            0.04 * d_pass +
            0.35 * rho_def +
            0.25 * theta_cone -
            0.015 * v_ball
        )

        clamped_exp = max(0.0, exponent)
        try:
            pdr = 100.0 * (1.0 - math.exp(-clamped_exp))
        except OverflowError:
            pdr = 100.0

        return round(min(100.0, max(0.0, pdr)), 1)

    @staticmethod
    def calculate_chaos_index(
        recent_turnovers_count: int,
        ball_speed_variance: float,
        defensive_line_displacement_m: float,
    ) -> float:
        """Calculates Chaos vs. Control Rhythm Index (CCI) bounded in [0.0, 100.0].

        Formula:
            CCI = 0.40 * (T * 12.0) + 0.35 * min(50.0, sigma^2) + 0.25 * min(40.0, DeltaX * 2.5)

        Tactical Zones:
            - High Control: CCI < 35.0 (structured possession)
            - Balanced Contest: 35.0 <= CCI <= 65.0 (contested midfield)
            - Chaos / High Transition: CCI > 65.0 (counter-attacks & turnovers)

        Args:
            recent_turnovers_count: Number of possession turnovers in rolling window.
            ball_speed_variance: Variance of instantaneous ball speeds (sigma^2).
            defensive_line_displacement_m: Longitudinal movement range of defensive line (DeltaX).

        Returns:
            Chaos Index float in [0.0, 100.0] rounded to 1 decimal place.
        """
        # Guard against NaN/inf
        if any(
            math.isnan(v) or math.isinf(v)
            for v in (float(recent_turnovers_count), float(ball_speed_variance), float(defensive_line_displacement_m))
        ):
            return 0.0

        t = max(0.0, float(recent_turnovers_count))
        sigma_sq = max(0.0, float(ball_speed_variance))
        delta_x = max(0.0, float(defensive_line_displacement_m))

        turnover_term = 0.40 * (t * 12.0)
        variance_term = 0.35 * min(50.0, sigma_sq)
        displacement_term = 0.25 * min(40.0, delta_x * 2.5)

        raw = turnover_term + variance_term + displacement_term
        return round(min(100.0, max(0.0, raw)), 1)

    @staticmethod
    def calculate_speed(dx_m: float, dy_m: float, dt_sec: float) -> float:
        """Calculates instantaneous velocity in km/h with zero-division safeguard.

        Guards against dt_sec <= 0 returning 0.0. Clamps result to [0.0, 150.0] km/h.

        Args:
            dx_m: Longitudinal delta in meters.
            dy_m: Lateral delta in meters.
            dt_sec: Time elapsed in seconds.

        Returns:
            Speed in km/h rounded to 1 decimal place.
        """
        if (
            dt_sec <= 0.0 or
            math.isnan(dt_sec) or math.isinf(dt_sec) or
            math.isnan(dx_m) or math.isinf(dx_m) or
            math.isnan(dy_m) or math.isinf(dy_m)
        ):
            return 0.0

        distance_m = math.hypot(dx_m, dy_m)
        speed_mps = distance_m / dt_sec
        speed_kmh = speed_mps * 3.6
        return round(min(150.0, max(0.0, speed_kmh)), 1)

    @staticmethod
    def calculate_defenders_in_corridor(
        passer_x: float,
        passer_y: float,
        receiver_x: float,
        receiver_y: float,
        defenders: List[Any],
        corridor_radius: float = 4.0,
    ) -> int:
        """Counts defenders positioned within corridor_radius meters of the passing segment.

        Uses vector projection onto the pass segment PR. Handles degenerate cases (L < 1e-4) safely.

        Args:
            passer_x: Passer X coordinate.
            passer_y: Passer Y coordinate.
            receiver_x: Receiver X coordinate.
            receiver_y: Receiver Y coordinate.
            defenders: List of defenders (dicts, objects, or (x, y) tuples).
            corridor_radius: Lateral threshold radius in meters (default 4.0m).

        Returns:
            Integer count of defenders within the passing corridor.
        """
        if not defenders:
            return 0

        # Guard against NaN/inf coordinates
        if any(math.isnan(v) or math.isinf(v) for v in (passer_x, passer_y, receiver_x, receiver_y)):
            return 0

        dx = receiver_x - passer_x
        dy = receiver_y - passer_y
        l_sq = dx * dx + dy * dy

        # Degenerate case: pass length < 1e-4 meters
        if l_sq < 1e-8:
            count = 0
            for d in defenders:
                coords = _extract_coords(d)
                if coords is None:
                    continue
                dist = math.hypot(coords[0] - passer_x, coords[1] - passer_y)
                if dist <= corridor_radius:
                    count += 1
            return count

        count = 0
        for d in defenders:
            coords = _extract_coords(d)
            if coords is None:
                continue
            xd, yd = coords
            wx = xd - passer_x
            wy = yd - passer_y

            # Scalar projection onto segment
            t = (wx * dx + wy * dy) / l_sq
            t_clamped = max(0.0, min(1.0, t))

            proj_x = passer_x + t_clamped * dx
            proj_y = passer_y + t_clamped * dy

            dist = math.hypot(xd - proj_x, yd - proj_y)
            if dist <= corridor_radius:
                count += 1

        return count

    @staticmethod
    def calculate_defenders_in_cone(
        passer_x: float,
        passer_y: float,
        receiver_x: float,
        receiver_y: float,
        defenders: List[Any],
        max_angle_deg: float = 20.0,
        max_distance_m: Optional[float] = None,
    ) -> int:
        """Counts defenders positioned inside an angular interception cone along the pass.

        Args:
            passer_x: Passer X coordinate.
            passer_y: Passer Y coordinate.
            receiver_x: Receiver X coordinate.
            receiver_y: Receiver Y coordinate.
            defenders: List of defenders (dicts, objects, or (x, y) tuples).
            max_angle_deg: Half-angle aperture threshold in degrees (default 20.0 deg).
            max_distance_m: Optional upper distance cutoff from passer in meters.

        Returns:
            Integer count of defenders within the interception cone.
        """
        if not defenders:
            return 0

        if any(math.isnan(v) or math.isinf(v) for v in (passer_x, passer_y, receiver_x, receiver_y)):
            return 0

        dx = receiver_x - passer_x
        dy = receiver_y - passer_y
        pass_len = math.hypot(dx, dy)

        if pass_len < 1e-4:
            return 0

        count = 0
        for d in defenders:
            coords = _extract_coords(d)
            if coords is None:
                continue
            xd, yd = coords
            ux = xd - passer_x
            uy = yd - passer_y
            d_def = math.hypot(ux, uy)

            if d_def < 1e-4:
                # Defender directly on passer
                count += 1
                continue

            if max_distance_m is not None and d_def > max_distance_m:
                continue

            dot = dx * ux + dy * uy
            # Cosine clamp to [-1.0, 1.0] to prevent math domain error in acos
            cos_theta = max(-1.0, min(1.0, dot / (pass_len * d_def)))
            theta_deg = math.degrees(math.acos(cos_theta))

            if theta_deg <= max_angle_deg:
                count += 1

        return count

    @staticmethod
    def calculate_expected_threat(
        start_x: float,
        start_y: float,
        end_x: float,
        end_y: float,
        pitch_length: float = 105.0,
        pitch_width: float = 68.0,
    ) -> float:
        """Calculates Expected Threat delta (xT gained) between start and end coordinates.

        Uses a calibrated 12x8 spatial grid dividing the pitch into:
        - 12 zones longitudinally (col 0: defensive goal -> col 11: attacking goal)
        - 8 zones laterally (row 0: left flank -> row 3-4: central channel -> row 7: right flank)

        Result is bounded strictly in [-1.0, 1.0].

        Args:
            start_x: Initial ball X coordinate (0.0 to 105.0).
            start_y: Initial ball Y coordinate (0.0 to 68.0).
            end_x: Destination ball X coordinate (0.0 to 105.0).
            end_y: Destination ball Y coordinate (0.0 to 68.0).
            pitch_length: Pitch length in meters (default 105.0).
            pitch_width: Pitch width in meters (default 68.0).

        Returns:
            Delta xT float bounded in [-1.0, 1.0] rounded to 3 decimal places.
        """
        # Guard against non-finite values
        if any(math.isnan(v) or math.isinf(v) for v in (start_x, start_y, end_x, end_y)):
            return 0.0

        cols = len(XT_GRID)  # 12
        rows = len(XT_GRID[0])  # 8

        def get_grid_cell(x: float, y: float) -> Tuple[int, int]:
            cx = min(pitch_length, max(0.0, x))
            cy = min(pitch_width, max(0.0, y))
            col_idx = min(cols - 1, max(0, int(cx / (pitch_length / cols))))
            row_idx = min(rows - 1, max(0, int(cy / (pitch_width / rows))))
            return col_idx, row_idx

        start_col, start_row = get_grid_cell(start_x, start_y)
        end_col, end_row = get_grid_cell(end_x, end_y)

        start_xt = XT_GRID[start_col][start_row]
        end_xt = XT_GRID[end_col][end_row]

        delta_xt = end_xt - start_xt
        clamped_delta = max(-1.0, min(1.0, delta_xt))
        return round(clamped_delta, 3)


class RollingTacticalWindow:
    """Maintains a rolling temporal window of tracking metrics to compute match entropy (CCI).

    Tracks:
    - Instantaneous ball velocities (for variance calculation)
    - Turnovers (frequency count)
    - Defensive line positions (displacement range over time)
    """

    def __init__(self, window_size_seconds: float = 180.0, fps: float = 25.0):
        """Initializes rolling window buffer.

        Args:
            window_size_seconds: Rolling window duration in seconds (default 180s = 3 minutes).
            fps: Telemetry frame rate (default 25.0 Hz).
        """
        self.window_size_seconds = float(window_size_seconds)
        self.fps = float(fps)
        self.max_frames = max(10, int(self.window_size_seconds * self.fps))

        self.ball_speeds: deque = deque(maxlen=self.max_frames)
        self.turnover_timestamps: deque = deque()
        self.defensive_line_positions: deque = deque(maxlen=self.max_frames)
        self.current_time_sec: float = 0.0

    def reset(self) -> None:
        """Clears all internal rolling buffers."""
        self.ball_speeds.clear()
        self.turnover_timestamps.clear()
        self.defensive_line_positions.clear()
        self.current_time_sec = 0.0

    def add_metric(
        self,
        ball_speed_kmh: float,
        defensive_line_x: Optional[float] = None,
        is_turnover: bool = False,
        timestamp_sec: Optional[float] = None,
    ) -> None:
        """Records a single telemetry frame observation.

        Args:
            ball_speed_kmh: Instantaneous ball speed in km/h.
            defensive_line_x: Optional average X position of defensive line in meters.
            is_turnover: True if a turnover event occurred at this moment.
            timestamp_sec: Optional match timestamp in elapsed seconds.
        """
        if timestamp_sec is not None and not math.isnan(timestamp_sec) and not math.isinf(timestamp_sec):
            self.current_time_sec = float(timestamp_sec)
        else:
            self.current_time_sec += 1.0 / self.fps

        if not (math.isnan(ball_speed_kmh) or math.isinf(ball_speed_kmh)):
            self.ball_speeds.append(float(ball_speed_kmh))

        if defensive_line_x is not None:
            if not (math.isnan(defensive_line_x) or math.isinf(defensive_line_x)):
                self.defensive_line_positions.append(float(defensive_line_x))

        if is_turnover:
            self.turnover_timestamps.append(self.current_time_sec)

        self._prune_turnovers()

    def record_turnover(self, timestamp_sec: Optional[float] = None) -> None:
        """Records a turnover event."""
        t = timestamp_sec if timestamp_sec is not None else self.current_time_sec
        self.turnover_timestamps.append(float(t))
        self._prune_turnovers()

    def _prune_turnovers(self) -> None:
        """Prunes turnovers that fall outside the rolling window duration."""
        cutoff = self.current_time_sec - self.window_size_seconds
        while self.turnover_timestamps and self.turnover_timestamps[0] < cutoff:
            self.turnover_timestamps.popleft()

    def add_telemetry_frame(self, frame: Dict[str, Any]) -> None:
        """Ingests a TelemetryFrame dict conforming to TelemetryFrame JSON schema."""
        if not isinstance(frame, dict):
            return

        ball = frame.get("ball") or {}
        speed = ball.get("speed_kmh", 0.0)
        if speed is None or math.isnan(float(speed)) or math.isinf(float(speed)):
            speed = 0.0
        else:
            speed = float(speed)

        # Extract defensive line position from players
        players = frame.get("players") or []
        defensive_x = None
        if players and isinstance(players, list):
            # Look for outfield defenders or away/home defensive cluster
            possession_team = ball.get("possession_team") if isinstance(ball, dict) else None
            defending_players = [
                p for p in players
                if isinstance(p, dict) and possession_team and p.get("team") != possession_team and p.get("role") in ("DF", "GK")
            ]
            if not defending_players:
                defending_players = [
                    p for p in players
                    if isinstance(p, dict) and p.get("role") in ("DF",)
                ]

            if defending_players:
                xs = [
                    float(p["x"]) for p in defending_players
                    if isinstance(p, dict) and p.get("x") is not None and not math.isnan(float(p["x"])) and not math.isinf(float(p["x"]))
                ]
                if xs:
                    defensive_x = sum(xs) / len(xs)

        active_evt = frame.get("active_event_id")
        is_turnover = False
        if active_evt and "turnover" in str(active_evt).lower():
            is_turnover = True

        self.add_metric(
            ball_speed_kmh=speed,
            defensive_line_x=defensive_x,
            is_turnover=is_turnover,
        )

    def get_ball_speed_variance(self) -> float:
        """Computes sample variance of ball speeds in the rolling window."""
        n = len(self.ball_speeds)
        if n < 2:
            return 0.0
        mean = sum(self.ball_speeds) / n
        var = sum((s - mean) ** 2 for s in self.ball_speeds) / n
        return round(float(var), 2)

    def get_turnovers_count(self) -> int:
        """Returns the count of turnovers within the current rolling window."""
        self._prune_turnovers()
        return len(self.turnover_timestamps)

    def get_defensive_line_displacement(self) -> float:
        """Computes the displacement range (max - min) of defensive line positions in window."""
        if len(self.defensive_line_positions) < 2:
            return 0.0
        disp = max(self.defensive_line_positions) - min(self.defensive_line_positions)
        return round(float(disp), 2)

    def get_chaos_index(self) -> float:
        """Calculates current Chaos vs. Control Rhythm Index from window metrics."""
        return TacticalMathEngine.calculate_chaos_index(
            recent_turnovers_count=self.get_turnovers_count(),
            ball_speed_variance=self.get_ball_speed_variance(),
            defensive_line_displacement_m=self.get_defensive_line_displacement(),
        )


RADAR_AXES = ("pace", "shooting", "passing", "defending", "threat", "workrate")
_RADAR_LABELS = {
    "pace": "Pace", "shooting": "Shooting", "passing": "Passing",
    "defending": "Defending", "threat": "Threat", "workrate": "Work Rate",
}


def _radar_inputs(p: Dict[str, Any]) -> Dict[str, float]:
    """The raw quantity behind each radar axis, per 90 minutes where it is a count."""
    minutes = max(30.0, float(p.get("minutes_played") or 0.0))
    per90 = 90.0 / minutes
    passes = p.get("passes") or {}
    completed = float(passes.get("completed") or 0.0)
    accuracy = float(passes.get("accuracy_pct") or 0.0) / 100.0
    return {
        # Many players touch the 36 km/h limit, so time spent sprinting separates them.
        "pace": float(p.get("top_speed_kmh") or 0.0) + 0.04 * float(p.get("sprint_seconds") or 0.0) * per90,
        "shooting": (float(p.get("xg") or 0.0) + 0.6 * float(p.get("goals") or 0.0)
                     + 0.15 * float(p.get("shots_on_target") or 0.0) + 0.04 * float(p.get("shots") or 0.0)) * per90,
        "passing": completed * accuracy * per90,
        "defending": (float(p.get("defensive_interventions") or 0.0) + 0.5 * float(p.get("tackles_won") or 0.0)) * per90,
        "threat": (float(p.get("xt_created") or 0.0) + 0.15 * float(p.get("key_passes") or 0.0)
                   + 0.3 * float(p.get("assists") or 0.0)) * per90,
        "workrate": float(p.get("distance_km") or 0.0) * per90,
    }


def compute_radar_profiles(players: List[Dict[str, Any]]) -> Dict[str, List[Dict[str, Any]]]:
    """6-axis radar for every player, each axis ranked against all the players in the match.

    A radar value is the player's percentile on that axis (0-100) among everyone who has
    played, so a striker, a full-back and a goalkeeper no longer end up with the same
    shape: the axes show who is actually best at pace, shooting, passing, defending,
    creating threat and running. Counts are scaled per 90 minutes.
    """
    inputs = {str(p.get("player_id")): _radar_inputs(p) for p in players}
    pool = list(inputs.values())
    result: Dict[str, List[Dict[str, Any]]] = {}
    for p in players:
        pid = str(p.get("player_id"))
        mine = inputs[pid]
        passes = p.get("passes") or {}
        display = {
            "pace": f"{float(p.get('top_speed_kmh') or 0.0):.1f} km/h · {float(p.get('sprint_seconds') or 0.0):.0f}s sprinting",
            "shooting": f"{int(p.get('goals') or 0)}G · {float(p.get('xg') or 0.0):.2f} xG",
            "passing": f"{int(passes.get('completed') or 0)} passes · {float(passes.get('accuracy_pct') or 0.0):.0f}%",
            "defending": f"{int(p.get('defensive_interventions') or 0)} interventions",
            "threat": f"+{float(p.get('xt_created') or 0.0):.2f} xT · {int(p.get('key_passes') or 0)} key",
            "workrate": f"{float(p.get('distance_km') or 0.0):.1f} km",
        }
        axes = []
        for axis in RADAR_AXES:
            values = [other[axis] for other in pool]
            below = sum(1 for v in values if v < mine[axis] - 1e-9)
            equal = sum(1 for v in values if abs(v - mine[axis]) <= 1e-9)
            # Doing nothing on an axis (no shots, no tackles) ranks at the bottom, not in the middle.
            percentile = 0.0 if mine[axis] <= 1e-9 else 100.0 * (below + 0.5 * equal) / max(1, len(values))
            axes.append({
                "key": axis, "axis": _RADAR_LABELS[axis], "label": _RADAR_LABELS[axis],
                "value": round(max(5.0, min(99.0, percentile)), 1), "fullMark": 100,
                "displayValue": display[axis], "formattedValue": f"{percentile:.0f}",
                "raw": round(mine[axis], 3),
            })
        result[pid] = axes
    return result


class PlayerAnalytics:
    """Tracks continuous, cumulative performance statistics for a single player."""

    def __init__(
        self,
        player_id: str,
        name: str,
        team: str,
        jersey_number: int,
        role: str,
    ):
        self.player_id = player_id
        self.name = name
        self.team = team  # "home" or "away"
        self.jersey_number = jersey_number
        self.role = role  # "GK", "DF", "MF", "FW"
        self.minutes_played: int = 0
        self.distance_meters: float = 0.0
        self.last_x: Optional[float] = None
        self.last_y: Optional[float] = None
        self.top_speed_kmh: float = 0.0
        self.sprint_frames: int = 0  # tracked frames spent above 30 km/h (25 per second)
        self.passes_total: int = 0
        self.passes_completed: int = 0
        self.pdr_values: List[float] = []
        self.xt_created: float = 0.0
        self.xg: float = 0.0
        self.shots: int = 0
        self.shots_on_target: int = 0
        self.goals: int = 0
        self.assists: int = 0
        self.key_passes: int = 0
        self.defensive_interventions: int = 0
        self.tackles_total: int = 0
        self.tackles_won: int = 0
        self.interceptions: int = 0
        self.saves: int = 0
        self.fouls_committed: int = 0
        self.yellow_cards: int = 0
        self.red_cards: int = 0
        self.substituted_on: bool = False
        self.substituted_off: bool = False
        self.entered_minute: Optional[int] = None
        self.goals_conceded: int = 0
        self.rating: float = 6.0
        self.is_motm: bool = False
        self.bps: int = 0
        self.fantasy_bonus_points: int = 0
        self.xa: float = 0.0
        self.heatmap: List[List[int]] = [[0 for _ in range(8)] for _ in range(12)]

    def update_tracking(self, x: float, y: float, speed_kmh: float, period: int = 1) -> None:
        """Updates instantaneous spatial position and physical metrics with teleportation guard."""
        if self.last_x is not None and self.last_y is not None:
            dist = math.hypot(x - self.last_x, y - self.last_y)
            # Guard against teleportation (jumps > 1.5m)
            if dist <= 1.5:
                self.distance_meters += dist
        self.last_x = x
        self.last_y = y

        # Heatmaps are drawn as if the team always attacked towards x = 105.
        col = min(11, max(0, int(to_attack_frame(x, self.team, period) / (105.0 / 12.0))))
        row = min(7, max(0, int(to_attack_frame_y(y, self.team, period) / (68.0 / 8.0))))
        self.heatmap[col][row] += 1

        speed_capped = max(0.0, min(36.0, float(speed_kmh)))
        if speed_capped >= 30.0:
            self.sprint_frames += 1
        if speed_capped > self.top_speed_kmh:
            self.top_speed_kmh = speed_capped

    def to_dict(self) -> Dict[str, Any]:
        """Serializes player performance record conforming to project schema."""
        acc = round((self.passes_completed / max(1, self.passes_total)) * 100.0, 1) if self.passes_total > 0 else 0.0
        avg_pdr = round(sum(self.pdr_values) / len(self.pdr_values), 1) if self.pdr_values else 0.0
        tackle_pct = round((self.tackles_won / max(1, self.tackles_total)) * 100.0, 1) if self.tackles_total > 0 else 0.0
        calculated_xa = round(max(0.0, self.key_passes * 0.14 + max(0.0, self.xt_created) * 0.25 + self.assists * 0.2), 2)
        final_xa = max(self.xa, calculated_xa)
        return {
            "player_id": self.player_id,
            "name": self.name,
            "team": self.team,
            "jersey_number": self.jersey_number,
            "role": self.role,
            "minutes_played": int(self.minutes_played),
            "yellow_cards": self.yellow_cards,
            "red_cards": self.red_cards,
            "fouls_committed": self.fouls_committed,
            "substituted_on": self.substituted_on,
            "substituted_off": self.substituted_off,
            "distance_km": round(self.distance_meters / 1000.0, 2),
            "top_speed_kmh": round(self.top_speed_kmh, 1),
            "sprint_seconds": round(self.sprint_frames / 25.0, 1),
            "passes": {
                "total": self.passes_total,
                "completed": self.passes_completed,
                "accuracy_pct": acc,
                "avg_pdr": avg_pdr,
            },
            "xt_created": round(self.xt_created, 3),
            "xg": round(self.xg, 2),
            "xa": round(final_xa, 2),
            "shots": self.shots,
            "shots_on_target": self.shots_on_target,
            "goals": self.goals,
            "assists": self.assists,
            "key_passes": self.key_passes,
            "defensive_interventions": self.defensive_interventions,
            "tackles_total": self.tackles_total,
            "tackles_won": self.tackles_won,
            "tackle_won_pct": tackle_pct,
            "interceptions": self.interceptions,
            "rating": round(self.rating, 1),
            "is_motm": self.is_motm,
            "bps": int(self.bps),
            "fantasy_bonus_points": int(self.fantasy_bonus_points),
            "heatmap": [list(row) for row in self.heatmap],
        }


class MatchAnalyticsTracker:
    """
    Maintains real-time, explainable analytics across all 22 authentic players
    and aggregates team-level match statistics, player ratings, and Fantasy BPS podiums.
    """

    def __init__(self):
        from generator.match_generator import NORTHBRIDGE_ROSTER, AWAY_ROSTER
        self.home_roster = NORTHBRIDGE_ROSTER
        self.away_roster = AWAY_ROSTER
        self.players: Dict[str, PlayerAnalytics] = {}
        self.rolling_window = RollingTacticalWindow(window_size_seconds=60.0)
        self.processed_event_ids: Set[str] = set()
        self.possession_frames = {"home": 0, "away": 0}
        self.xg = {"home": 0.0, "away": 0.0}
        self.shots = {
            "home": {"total": 0, "on_target": 0, "blocked": 0, "off_target": 0},
            "away": {"total": 0, "on_target": 0, "blocked": 0, "off_target": 0},
        }
        self.passes = {
            "home": {"total": 0, "completed": 0},
            "away": {"total": 0, "completed": 0},
        }
        self.tackles = {
            "home": {"total": 0, "won": 0},
            "away": {"total": 0, "won": 0},
        }
        self.interceptions = {"home": 0, "away": 0}
        self.fouls = {"home": 0, "away": 0}
        self.cards = {
            "home": {"yellow": 0, "red": 0},
            "away": {"yellow": 0, "red": 0},
        }
        self.corners = {"home": 0, "away": 0}
        self.substitutions = {"home": 0, "away": 0}
        self.score = {"home": 0, "away": 0}
        self.final_third_actions = {"home": 0, "away": 0}
        self.half_actions = {"home": 0, "away": 0}
        self.minutes_elapsed: float = 0.0
        # Milestone and physical threshold tracking
        self.milestones: List[Dict[str, Any]] = []
        self._milestones_seen: Set[str] = set()
        self.alerts: List[Dict[str, Any]] = []
        self.pending_alerts: List[Dict[str, Any]] = []
        self._sprint_cooldowns: Dict[str, float] = {}  # player_id -> last alert match time in seconds
        self._distance_marks_notified: Set[Tuple[str, int]] = set()  # (player_id, meter_mark)
        self._alert_counter: int = 0
        self._last_ball_speed_alert_sec: float = -100.0
        self._cached_match_stats: Optional[Dict[str, Any]] = None
        self._cached_player_stats: Optional[List[Dict[str, Any]]] = None
        self._init_players()

    def _init_players(self) -> None:
        """Initializes all 22 players from official squad sheets."""
        self.players.clear()
        for p in self.home_roster:
            self.players[p["player_id"]] = PlayerAnalytics(
                player_id=p["player_id"],
                name=p["name"],
                team="home",
                jersey_number=p["jersey_number"],
                role=p["role"],
            )
        for p in self.away_roster:
            self.players[p["player_id"]] = PlayerAnalytics(
                player_id=p["player_id"],
                name=p["name"],
                team="away",
                jersey_number=p["jersey_number"],
                role=p["role"],
            )

    def reset(self) -> None:
        """Resets all tracker state to kickoff (00:00)."""
        self._init_players()
        self.rolling_window = RollingTacticalWindow(window_size_seconds=60.0)
        self.processed_event_ids.clear()
        self.possession_frames = {"home": 0, "away": 0}
        self.xg = {"home": 0.0, "away": 0.0}
        self.shots = {
            "home": {"total": 0, "on_target": 0, "blocked": 0, "off_target": 0},
            "away": {"total": 0, "on_target": 0, "blocked": 0, "off_target": 0},
        }
        self.passes = {
            "home": {"total": 0, "completed": 0},
            "away": {"total": 0, "completed": 0},
        }
        self.tackles = {
            "home": {"total": 0, "won": 0},
            "away": {"total": 0, "won": 0},
        }
        self.interceptions = {"home": 0, "away": 0}
        self.fouls = {"home": 0, "away": 0}
        self.cards = {
            "home": {"yellow": 0, "red": 0},
            "away": {"yellow": 0, "red": 0},
        }
        self.corners = {"home": 0, "away": 0}
        self.substitutions = {"home": 0, "away": 0}
        self.score = {"home": 0, "away": 0}
        self.final_third_actions = {"home": 0, "away": 0}
        self.half_actions = {"home": 0, "away": 0}
        self.minutes_elapsed = 0.0
        self.milestones.clear()
        self._milestones_seen.clear()
        self.alerts.clear()
        self.pending_alerts.clear()
        self._sprint_cooldowns.clear()
        self._distance_marks_notified.clear()
        self._alert_counter = 0
        self._last_ball_speed_alert_sec = -100.0
        self._cached_match_stats = None
        self._cached_player_stats = None

    def _ensure_player(self, pid: Optional[str]) -> Optional["PlayerAnalytics"]:
        """Substitutes are added to the tracker the first time they appear."""
        if not pid:
            return None
        if pid in self.players:
            return self.players[pid]
        from generator.match_generator import BENCH_BY_ID
        entry = BENCH_BY_ID.get(pid)
        if entry is None:
            return None
        team = "home" if pid.startswith("NBL") else "away"
        self.players[pid] = PlayerAnalytics(
            player_id=pid, name=entry["name"], team=team,
            jersey_number=entry["jersey_number"], role=entry["role"],
        )
        return self.players[pid]

    def seek_to_event(self, event_data: Dict[str, Any]) -> None:
        """Resets teleportation anchors for all players and syncs time to seeked event."""
        for p in self.players.values():
            p.last_x = None
            p.last_y = None
        clock = event_data.get("clock", "00:00")
        if ":" in clock:
            try:
                m, s = map(int, clock.split(":"))
                self.minutes_elapsed = m + s / 60.0
            except ValueError:
                pass

    def add_telemetry_frame(self, frame: Dict[str, Any]) -> None:
        """Ingests a live telemetry frame to accumulate distance, speed, possession, and detect alerts."""
        self._cached_match_stats = None
        self._cached_player_stats = None
        self.rolling_window.add_telemetry_frame(frame)

        clock = frame.get("clock", "00:00")
        match_time_sec = 0.0
        if ":" in clock:
            try:
                m, s = map(int, clock.split(":"))
                self.minutes_elapsed = m + s / 60.0
                match_time_sec = m * 60.0 + s
                curr_min = int(self.minutes_elapsed)
                for p_dict in frame.get("players", []):
                    on_pitch = self._ensure_player(p_dict.get("player_id"))
                    if on_pitch is None:
                        continue
                    if on_pitch.entered_minute is None:
                        on_pitch.entered_minute = curr_min
                    on_pitch.minutes_played = max(on_pitch.minutes_played, curr_min - on_pitch.entered_minute)
            except ValueError:
                pass
        else:
            match_time_sec = self.minutes_elapsed * 60.0

        ball = frame.get("ball", {})
        poss_team = ball.get("possession_team")
        ball_x = ball.get("x")
        period = int(frame.get("period", 1) or 1)
        if poss_team in ("home", "Northbridge Lions", "away", "Harbourside City"):
            side = _side_of(poss_team)
            self.possession_frames[side] += 1
            if ball_x is not None:
                try:
                    # Measured in the team's attacking direction (teams swap ends at half-time).
                    bx = to_attack_frame(float(ball_x), side, period)
                    if bx >= 70.0:
                        self.final_third_actions[side] += 1
                    if bx > 52.5:
                        self.half_actions[side] += 1
                except (ValueError, TypeError):
                    pass

        # Check instantaneous ball speed threshold (> 100 km/h)
        ball_spd = float(ball.get("speed_kmh", 0.0) or 0.0)
        if ball_spd > 100.0 and (match_time_sec - self._last_ball_speed_alert_sec) >= 5.0:
            self._last_ball_speed_alert_sec = match_time_sec
            self._alert_counter += 1
            ball_alert = {
                "alert_id": f"ALT_SHOT_{self._alert_counter}",
                "alert_type": "shot_velocity",
                "player_id": ball.get("possession_player_id"),
                "player_name": "Striker",
                "team": str(poss_team or "home"),
                "metric_name": "ball_speed_kmh",
                "metric_value": round(ball_spd, 1),
                "threshold": 100.0,
                "unit": "km/h",
                "clock": clock,
                "message": f"🚀 ROCKET SHOT: High-velocity strike clocked at {ball_spd:.1f} km/h! (>100.0 km/h threshold)",
            }
            self.alerts.append(ball_alert)
            self.pending_alerts.append(ball_alert)

        for p_dict in frame.get("players", []):
            pid = p_dict.get("player_id")
            self._ensure_player(pid)
            if pid in self.players:
                x = p_dict.get("x")
                y = p_dict.get("y")
                spd = float(p_dict.get("speed_kmh", 0.0) or 0.0)
                if x is not None and y is not None:
                    self.players[pid].update_tracking(float(x), float(y), spd, period)

                p_obj = self.players[pid]

                # Sprint speed threshold alert (> 32 km/h with 15s cooldown per player)
                if spd > 32.0:
                    last_alert = self._sprint_cooldowns.get(pid, -100.0)
                    if (match_time_sec - last_alert) >= 15.0:
                        self._sprint_cooldowns[pid] = match_time_sec
                        self._alert_counter += 1
                        sprint_alert = {
                            "alert_id": f"ALT_SPRINT_{self._alert_counter}_{pid}",
                            "alert_type": "sprint_speed",
                            "player_id": pid,
                            "player_name": p_obj.name,
                            "team": p_obj.team,
                            "metric_name": "sprint_speed_kmh",
                            "metric_value": round(spd, 1),
                            "threshold": 32.0,
                            "unit": "km/h",
                            "clock": clock,
                            "message": f"⚡ SPRINT ALERT: {p_obj.name} bursts to {spd:.1f} km/h! (>32.0 km/h threshold)",
                        }
                        self.alerts.append(sprint_alert)
                        self.pending_alerts.append(sprint_alert)

                # Distance marks (5000m = 5km, 10000m = 10km)
                for mark in (5000, 10000):
                    if p_obj.distance_meters >= mark and (pid, mark) not in self._distance_marks_notified:
                        self._distance_marks_notified.add((pid, mark))
                        self._alert_counter += 1
                        km_val = mark // 1000
                        dist_alert = {
                            "alert_id": f"ALT_DIST_{self._alert_counter}_{pid}_{km_val}K",
                            "alert_type": "distance_mark",
                            "player_id": pid,
                            "player_name": p_obj.name,
                            "team": p_obj.team,
                            "metric_name": "distance_meters",
                            "metric_value": round(p_obj.distance_meters, 1),
                            "threshold": float(mark),
                            "unit": "meters",
                            "clock": clock,
                            "message": f"🏃 DISTANCE MILESTONE: {p_obj.name} reaches {km_val}.0 km mark!",
                        }
                        self.alerts.append(dist_alert)
                        self.pending_alerts.append(dist_alert)

    def record_event(self, ev: Dict[str, Any]) -> Optional[str]:
        """Processes a match event, updates player and match counters, and evaluates milestones."""
        ev_id = ev.get("event_id")
        if ev_id and ev_id in self.processed_event_ids:
            return None
        self._cached_match_stats = None
        self._cached_player_stats = None
        if ev_id:
            self.processed_event_ids.add(ev_id)

        team_str = str(ev.get("team", ""))
        side = "home" if team_str in ("Northbridge Lions", "home") else "away"
        opp_side = "away" if side == "home" else "home"
        pid = ev.get("player_id")
        sec_pid = ev.get("secondary_player_id")
        ev_type = str(ev.get("event_type", ""))
        sub_type = str(ev.get("sub_type", ""))
        outcome = str(ev.get("outcome", ""))

        loc_x = float(ev.get("location_x", 52.5))
        loc_y = float(ev.get("location_y", 34.0))
        end_x = float(ev.get("end_x", loc_x)) if ev.get("end_x") is not None else loc_x
        end_y = float(ev.get("end_y", loc_y)) if ev.get("end_y") is not None else loc_y

        tactical_metrics = ev.get("tactical_metrics", {})
        pdr = tactical_metrics.get("pass_difficulty")
        xt_gained = tactical_metrics.get("xt_gained")
        if xt_gained is None:
            xt_gained = TacticalMathEngine.calculate_expected_threat(loc_x, loc_y, end_x, end_y)
        else:
            xt_gained = float(xt_gained)

        p = self.players.get(pid) or self._ensure_player(pid)

        # Everything below is measured in the acting team's attacking direction, because
        # the teams change ends at half-time.
        period = int(ev.get("period", 1) or 1)
        att_x = to_attack_frame(loc_x, side, period)
        att_y = to_attack_frame_y(loc_y, side, period)
        att_end_x = to_attack_frame(end_x, side, period)

        # Track final-third and attacking half actions for field tilt and territory
        if att_x >= 70.0 or att_end_x >= 70.0:
            self.final_third_actions[side] += 1
        if att_x > 52.5 or att_end_x > 52.5:
            self.half_actions[side] += 1

        if p:
            p_col = min(11, max(0, int(att_x / (105.0 / 12.0))))
            p_row = min(7, max(0, int(att_y / (68.0 / 8.0))))
            p.heatmap[p_col][p_row] += 2

        # Check shot velocity alert (> 100 km/h)
        if ev_type in ("shot", "goal") or outcome == "goal":
            shot_spd = float(tactical_metrics.get("ball_speed_kmh", ev.get("ball_speed_kmh", 0.0)) or 0.0)
            if shot_spd > 100.0:
                self._alert_counter += 1
                shot_alert = {
                    "alert_id": f"ALT_SHOT_{self._alert_counter}_{ev_id or 'EVT'}",
                    "alert_type": "shot_velocity",
                    "player_id": pid,
                    "player_name": p.name if p else ev.get("player_name", "Striker"),
                    "team": team_str or ("Northbridge Lions" if side == "home" else "Harbourside City"),
                    "metric_name": "ball_speed_kmh",
                    "metric_value": round(shot_spd, 1),
                    "threshold": 100.0,
                    "unit": "km/h",
                    "clock": ev.get("clock", "00:00"),
                    "message": f"🚀 ROCKET SHOT: {p.name if p else ev.get('player_name', 'Striker')} uncorks a {shot_spd:.1f} km/h strike! (>100.0 km/h threshold)",
                }
                self.alerts.append(shot_alert)
                self.pending_alerts.append(shot_alert)

        if ev_type == "pass":
            self.passes[side]["total"] += 1
            if p:
                p.passes_total += 1
                if pdr is not None:
                    p.pdr_values.append(float(pdr))
                if xt_gained > 0:
                    p.xt_created += xt_gained

            if outcome in ("complete", "goal", "assist"):
                self.passes[side]["completed"] += 1
                if p:
                    p.passes_completed += 1
                if outcome == "assist" or sub_type in ("key_pass", "through_ball") or "chance" in sub_type:
                    if p:
                        p.key_passes += 1
                if outcome == "assist":
                    if p:
                        p.assists += 1

        elif ev_type in ("shot", "goal") or outcome == "goal":
            self.shots[side]["total"] += 1
            dist_to_goal = math.hypot(105.0 - att_x, 34.0 - att_y)
            shot_xg = min(0.95, max(0.05, 1.0 / (1.0 + 0.08 * (dist_to_goal ** 2))))
            if p:
                p.shots += 1

            is_goal = (ev_type == "goal" or outcome == "goal")
            if is_goal:
                shot_xg = max(0.35, shot_xg)
                self.shots[side]["on_target"] += 1
                self.score[side] += 1
                if p:
                    p.shots_on_target += 1
                    p.goals += 1
                if sec_pid and sec_pid in self.players:
                    self.players[sec_pid].assists += 1
                for opp_p in self.players.values():
                    if opp_p.team == opp_side and opp_p.role in ("GK", "DF"):
                        opp_p.goals_conceded += 1
            elif outcome == "saved" or sub_type == "goalkeeper_save":
                self.shots[side]["on_target"] += 1
                if p:
                    p.shots_on_target += 1
                opp_gk = next(
                    (gid for gid, gp in self.players.items() if gp.team == opp_side and gp.role == "GK"), None
                )
                if opp_gk in self.players:
                    self.players[opp_gk].saves += 1
                    self.players[opp_gk].defensive_interventions += 1
            elif outcome == "blocked":
                self.shots[side]["blocked"] += 1
            else:
                self.shots[side]["off_target"] += 1

            self.xg[side] = round(self.xg[side] + shot_xg, 2)
            if p:
                p.xg = round(p.xg + shot_xg, 2)

        elif ev_type == "tackle":
            self.tackles[side]["total"] += 1
            if p:
                p.tackles_total += 1
                p.defensive_interventions += 1
            if outcome == "won":
                self.tackles[side]["won"] += 1
                if p:
                    p.tackles_won += 1

        elif ev_type in ("interception", "turnover"):
            if ev_type == "interception" or outcome == "won":
                self.interceptions[side] += 1
                if p:
                    p.interceptions += 1
                    p.defensive_interventions += 1

        elif ev_type == "foul":
            self.fouls[side] += 1
            if p:
                p.fouls_committed += 1

        elif ev_type == "card":
            if sub_type == "second_yellow":
                # A second booking counts as a yellow and the red that follows it.
                self.cards[side]["yellow"] += 1
                self.cards[side]["red"] += 1
                if p:
                    p.yellow_cards += 1
                    p.red_cards += 1
            elif "yellow" in sub_type or "yellow" in outcome:
                self.cards[side]["yellow"] += 1
                if p:
                    p.yellow_cards += 1
            elif "red" in sub_type or "red" in outcome:
                self.cards[side]["red"] += 1
                if p:
                    p.red_cards += 1

        elif ev_type == "substitution":
            self.substitutions[side] += 1
            if p:
                p.substituted_on = True
            off_player = self.players.get(sec_pid) if sec_pid else None
            if off_player:
                off_player.substituted_off = True

        elif ev_type == "corner" or "corner" in sub_type:
            self.corners[side] += 1

        # Evaluate notable milestone crossings
        milestone_triggered: Optional[str] = None

        # 1. Goal milestones
        if (ev_type == "goal" or outcome == "goal"):
            total_goals = self.score["home"] + self.score["away"]
            if total_goals == 1 and "match_opening_goal" not in self._milestones_seen:
                self._milestones_seen.add("match_opening_goal")
                milestone_triggered = f"Opening Match Goal ({p.name if p else 'Goal'})"
            elif self.score["home"] == self.score["away"] and self.score["home"] > 0:
                eq_key = f"equalizer_{self.score['home']}_{self.score['away']}"
                if eq_key not in self._milestones_seen:
                    self._milestones_seen.add(eq_key)
                    milestone_triggered = f"Equalizing Goal ({self.score['home']}-{self.score['away']})"
            else:
                goal_key = f"goal_{side}_{self.score[side]}"
                if goal_key not in self._milestones_seen:
                    self._milestones_seen.add(goal_key)
                    milestone_triggered = f"{team_str or side.capitalize()} Goal #{self.score[side]}"

        # 2. Team completed passes
        if not milestone_triggered:
            completed_passes = self.passes[side]["completed"]
            for mark in (25, 50, 100, 150, 200, 250, 300, 400, 500):
                pass_key = f"{side}_pass_{mark}"
                if completed_passes >= mark and pass_key not in self._milestones_seen:
                    self._milestones_seen.add(pass_key)
                    milestone_triggered = f"{team_str or side.capitalize()} {mark}th completed pass"
                    break

        # 3. Player completed passes
        if not milestone_triggered and p:
            for mark in (10, 25, 50, 75):
                player_pass_key = f"{pid}_pass_{mark}"
                if p.passes_completed >= mark and player_pass_key not in self._milestones_seen:
                    self._milestones_seen.add(player_pass_key)
                    milestone_triggered = f"{p.name} {mark}th completed pass"
                    break

        # 4. Team defensive interventions / tackles won
        if not milestone_triggered:
            tack_won = self.tackles[side]["won"]
            for mark in (5, 10, 15, 20):
                tack_key = f"{side}_tackles_{mark}"
                if tack_won >= mark and tack_key not in self._milestones_seen:
                    self._milestones_seen.add(tack_key)
                    milestone_triggered = f"{team_str or side.capitalize()} {mark}th tackle won"
                    break

        # 5. Player defensive interventions
        if not milestone_triggered and p:
            for mark in (3, 5, 10):
                int_key = f"{pid}_def_int_{mark}"
                if p.defensive_interventions >= mark and int_key not in self._milestones_seen:
                    self._milestones_seen.add(int_key)
                    milestone_triggered = f"{p.name} {mark}th defensive intervention"
                    break

        # 6. Team shots on target
        if not milestone_triggered:
            sot = self.shots[side]["on_target"]
            for mark in (3, 5, 10):
                sot_key = f"{side}_sot_{mark}"
                if sot >= mark and sot_key not in self._milestones_seen:
                    self._milestones_seen.add(sot_key)
                    milestone_triggered = f"{team_str or side.capitalize()} {mark}th shot on target"
                    break

        # 7. Player shots on target
        if not milestone_triggered and p:
            for mark in (2, 3, 5):
                psot_key = f"{pid}_sot_{mark}"
                if p.shots_on_target >= mark and psot_key not in self._milestones_seen:
                    self._milestones_seen.add(psot_key)
                    milestone_triggered = f"{p.name} {mark}th shot on target"
                    break

        if milestone_triggered:
            self.milestones.append({
                "milestone": milestone_triggered,
                "clock": ev.get("clock", "00:00"),
                "event_id": ev_id,
                "team": team_str or side.capitalize(),
                "player_id": pid,
                "player_name": p.name if p else None,
            })

        return milestone_triggered

    def _compute_ratings_and_bps(self) -> None:
        """Calculates 0-10 player ratings, assigns single MOTM badge, and computes Fantasy BPS podium."""
        for p in self.players.values():
            rating = 6.0
            if p.passes_total > 0:
                acc = p.passes_completed / p.passes_total
                rating += 0.5 * (acc - 0.75) + min(0.4, p.passes_completed * 0.01)
            rating += 1.2 * p.goals
            rating += 0.8 * p.assists
            rating += 0.2 * p.shots_on_target
            rating += 1.5 * min(0.8, p.xt_created)
            rating += min(1.2, 0.15 * (p.tackles_won + p.interceptions))
            rating += 0.4 * p.saves
            penalties = 0.5 * p.yellow_cards + 1.5 * p.red_cards
            if p.role in ("GK", "DF"):
                penalties += 0.3 * p.goals_conceded
            rating -= penalties
            p.rating = round(max(4.0, min(10.0, rating)), 1)

        # MOTM: only assign the award when the tracker contains actual player contributions.
        active_players = [
            p for p in self.players.values()
            if p.minutes_played > 0 or p.distance_meters > 0 or p.passes_total > 0
            or p.shots > 0 or p.goals > 0 or p.assists > 0
            or p.defensive_interventions > 0
        ]
        for p in self.players.values():
            p.is_motm = False
        best_player = max(
            active_players,
            key=lambda p: (p.rating, p.bps, p.goals, p.assists, p.xt_created),
            default=None,
        )
        if best_player:
            best_player.is_motm = True

        # Fantasy BPS
        for p in self.players.values():
            bps = 0
            if p.minutes_played >= 60:
                bps += 12
            elif p.minutes_played > 0:
                bps += 6

            if p.role == "FW":
                bps += 24 * p.goals
            elif p.role == "MF":
                bps += 18 * p.goals
            else:
                bps += 12 * p.goals

            bps += 9 * p.assists
            if p.role in ("GK", "DF") and p.goals_conceded == 0 and p.minutes_played >= 60:
                bps += 12

            if p.passes_total >= 10:
                acc = (p.passes_completed / p.passes_total) * 100.0
                if acc >= 85.0:
                    bps += 6
                elif acc >= 70.0:
                    bps += 3

            bps += 3 * p.key_passes
            bps += 2 * p.shots_on_target
            bps += 2 * p.tackles_won
            bps += 1 * p.interceptions
            bps += 2 * p.saves
            bps -= 3 * p.yellow_cards
            bps -= 9 * p.red_cards
            if p.role in ("GK", "DF"):
                bps -= 4 * p.goals_conceded
            p.bps = max(0, int(round(bps)))
            p.fantasy_bonus_points = 0

        # Podium: Rank 1 -> 3 pts, Rank 2 -> 2 pts, Rank 3 -> 1 pt, rest -> 0
        sorted_players = sorted(
            active_players,
            key=lambda x: (x.bps, x.rating, x.goals, x.assists, x.xt_created),
            reverse=True,
        )
        if len(sorted_players) >= 3:
            sorted_players[0].fantasy_bonus_points = 3
            sorted_players[1].fantasy_bonus_points = 2
            sorted_players[2].fantasy_bonus_points = 1

    def simulate_full(self, events: List[Dict[str, Any]]) -> None:
        """Aggregates a completed synthetic match strictly from its supplied events.

        Physical distance, peak speed, and minutes require tracking frames and therefore
        remain unset when this fast event-only path is used.
        """
        self.reset()
        ordered_events = sorted(events, key=lambda event: (event.get("period", 1), event.get("frame_index", 0)))
        for event in ordered_events:
            self.record_event(event)

        if ordered_events:
            last_clock = str(ordered_events[-1].get("clock", "00:00"))
            try:
                minute, second = (int(part) for part in last_clock.split(":", 1))
                self.minutes_elapsed = minute + second / 60.0
            except (TypeError, ValueError):
                self.minutes_elapsed = 0.0
        self._compute_ratings_and_bps()

    def _compute_field_tilt(self) -> Dict[str, float]:
        """Calculates Field Tilt % based on final third passes/touches."""
        home_ft = self.final_third_actions["home"]
        away_ft = self.final_third_actions["away"]
        total_ft = home_ft + away_ft
        if total_ft > 0:
            home_tilt = round((home_ft / total_ft) * 100.0, 1)
            away_tilt = round(100.0 - home_tilt, 1)
            return {"home": home_tilt, "away": away_tilt}
        return {"home": 50.0, "away": 50.0}

    def _compute_territory(self) -> Dict[str, float]:
        """Calculates Territory % based on actions in opponent's half."""
        home_half = self.half_actions["home"]
        away_half = self.half_actions["away"]
        total_half = home_half + away_half
        if total_half > 0:
            home_terr = round((home_half / total_half) * 100.0, 1)
            away_terr = round(100.0 - home_terr, 1)
            return {"home": home_terr, "away": away_terr}
        return {"home": 50.0, "away": 50.0}

    def get_match_stats(self) -> Dict[str, Any]:
        """Returns aggregated match statistics conforming to GET /api/analytics schema."""
        if self._cached_match_stats is not None:
            stats = dict(self._cached_match_stats)
            if "field_tilt" not in stats:
                stats["field_tilt"] = self._compute_field_tilt()
            if "territory" not in stats:
                stats["territory"] = self._compute_territory()
            return stats
        total_poss = self.possession_frames["home"] + self.possession_frames["away"]
        if total_poss > 0:
            home_pos = round((self.possession_frames["home"] / total_poss) * 100.0, 1)
            away_pos = round(100.0 - home_pos, 1)
        else:
            home_pos, away_pos = 0.0, 0.0

        home_pass_tot = max(1, self.passes["home"]["total"])
        away_pass_tot = max(1, self.passes["away"]["total"])
        home_pass_acc = round((self.passes["home"]["completed"] / home_pass_tot) * 100.0, 1)
        away_pass_acc = round((self.passes["away"]["completed"] / away_pass_tot) * 100.0, 1)

        home_tack_tot = max(1, self.tackles["home"]["total"])
        away_tack_tot = max(1, self.tackles["away"]["total"])
        home_tack_acc = round((self.tackles["home"]["won"] / home_tack_tot) * 100.0, 1)
        away_tack_acc = round((self.tackles["away"]["won"] / away_tack_tot) * 100.0, 1)

        chaos = self.rolling_window.get_chaos_index()

        return {
            "possession_pct": {"home": home_pos, "away": away_pos},
            "xg": {"home": round(self.xg["home"], 2), "away": round(self.xg["away"], 2)},
            "field_tilt": self._compute_field_tilt(),
            "territory": self._compute_territory(),
            "shots": {
                "home": {
                    "total": self.shots["home"]["total"],
                    "on_target": self.shots["home"]["on_target"],
                    "blocked": self.shots["home"]["blocked"],
                    "off_target": self.shots["home"]["off_target"],
                },
                "away": {
                    "total": self.shots["away"]["total"],
                    "on_target": self.shots["away"]["on_target"],
                    "blocked": self.shots["away"]["blocked"],
                    "off_target": self.shots["away"]["off_target"],
                },
            },
            "passes": {
                "home": {
                    "total": self.passes["home"]["total"],
                    "completed": self.passes["home"]["completed"],
                    "accuracy_pct": home_pass_acc,
                },
                "away": {
                    "total": self.passes["away"]["total"],
                    "completed": self.passes["away"]["completed"],
                    "accuracy_pct": away_pass_acc,
                },
            },
            "tackles": {
                "home": {
                    "total": self.tackles["home"]["total"],
                    "won": self.tackles["home"]["won"],
                    "won_pct": home_tack_acc,
                },
                "away": {
                    "total": self.tackles["away"]["total"],
                    "won": self.tackles["away"]["won"],
                    "won_pct": away_tack_acc,
                },
            },
            "interceptions": {"home": self.interceptions["home"], "away": self.interceptions["away"]},
            "fouls": {"home": self.fouls["home"], "away": self.fouls["away"]},
            "cards": {
                "home": {"yellow": self.cards["home"]["yellow"], "red": self.cards["home"]["red"]},
                "away": {"yellow": self.cards["away"]["yellow"], "red": self.cards["away"]["red"]},
            },
            "corners": {"home": self.corners["home"], "away": self.corners["away"]},
            "substitutions": {"home": self.substitutions["home"], "away": self.substitutions["away"]},
            "chaos_index": round(min(100.0, max(0.0, chaos)), 1),
            "score": {"home": self.score["home"], "away": self.score["away"]},
        }

    def load_snapshot(
        self,
        events: List[Dict[str, Any]],
        match_stats: Dict[str, Any],
        player_stats: List[Dict[str, Any]],
    ) -> None:
        """Load simulator-derived full-match event and tracking analytics."""
        self.simulate_full(events)
        self._cached_match_stats = dict(match_stats)
        self._cached_player_stats = list(player_stats)

    def get_all_player_stats(self) -> List[Dict[str, Any]]:
        """Statistics for every player who has played, each with a radar ranked against the others."""
        stats = self._player_stats_without_radar()
        radars = compute_radar_profiles(stats)
        for entry in stats:
            entry["radar"] = radars.get(str(entry.get("player_id")), [])
        return stats

    def _player_stats_without_radar(self) -> List[Dict[str, Any]]:
        if self._cached_player_stats is not None:
            enriched = []
            for p_dict in self._cached_player_stats:
                d = dict(p_dict)
                pid = d.get("player_id")
                p_obj = self.players.get(pid)
                if p_obj:
                    if "tackles_total" not in d:
                        d["tackles_total"] = p_obj.tackles_total
                    if "tackle_won_pct" not in d:
                        tt = d.get("tackles_total", p_obj.tackles_total)
                        tw = d.get("tackles_won", p_obj.tackles_won)
                        d["tackle_won_pct"] = round((tw / max(1, tt)) * 100.0, 1) if tt > 0 else 0.0
                    if "xa" not in d:
                        d["xa"] = round(max(p_obj.xa, d.get("key_passes", 0) * 0.14 + max(0.0, d.get("xt_created", 0.0)) * 0.25 + d.get("assists", 0) * 0.2), 2)
                    if "heatmap" not in d:
                        d["heatmap"] = [list(r) for r in p_obj.heatmap]
                enriched.append(d)
            return enriched
        self._compute_ratings_and_bps()
        return [p.to_dict() for p in self.players.values()]

    def get_player_stats(self, player_id: str) -> Optional[Dict[str, Any]]:
        """Returns individual stats for a single player by ID."""
        all_stats = self.get_all_player_stats()
        return next((player for player in all_stats if player.get("player_id") == player_id), None)

    def get_milestones(self) -> List[Dict[str, Any]]:
        """Returns chronological list of all detected match and player milestones."""
        return list(self.milestones)

    def get_latest_milestone(self) -> Optional[str]:
        """Returns the most recent milestone string if any."""
        if self.milestones:
            return self.milestones[-1].get("milestone")
        return None

    def pop_pending_alerts(self) -> List[Dict[str, Any]]:
        """Returns and clears pending physical threshold alerts for broadcast."""
        alerts = list(self.pending_alerts)
        self.pending_alerts.clear()
        return alerts

    def get_all_alerts(self) -> List[Dict[str, Any]]:
        """Returns all detected physical threshold alerts."""
        return list(self.alerts)








