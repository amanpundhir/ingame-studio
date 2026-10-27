"""InGame Studio - Agent 1: The Tactician (Stats & State).

Extracts spatial coordinates, evaluates geometric pressure cones and corridors,
computes physical kinematics, PDR, CCI, and Expected Threat (xT), and emits a
validated FactPack Pydantic model conforming to data/schema.json.
"""

import math
from typing import Any, Dict, List, Optional
from backend.agents.models import FactPack
from backend.math_engine import TacticalMathEngine, RollingTacticalWindow
from backend.pitch import attacking_goal_x, to_attack_frame, to_attack_frame_y


class TacticianAgent:
    """Agent 1: The Tactician.

    Extracts spatial coordinates and event attributes, calculates PDR, CCI,
    speed, corridor pressure, and returns a verified FactPack.
    """

    def __init__(self, rolling_window: Optional[RollingTacticalWindow] = None):
        self.rolling_window = rolling_window or RollingTacticalWindow()

    def extract_facts(
        self,
        event: Dict[str, Any],
        telemetry_frame: Optional[Dict[str, Any]] = None,
        defenders: Optional[List[Dict[str, Any]]] = None,
    ) -> FactPack:
        """Extracts and evaluates tactical telemetry into a structured FactPack.

        Args:
            event: Match event dictionary (e.g. from synthetic_events.json).
            telemetry_frame: Optional contemporary TelemetryFrame dict.
            defenders: Optional explicit list of defender coordinates/dicts.

        Returns:
            FactPack: Fully populated, bounded, validated fact model.
        """
        event_id = str(event.get("event_id") or "EVT_0000")
        match_minute = str(event.get("match_minute") or event.get("clock") or "00:00")
        period = int(event.get("period", 1))
        event_type = str(event.get("event_type", "pass")).lower()
        sub_type = str(event.get("sub_type", "")).lower()
        outcome = str(event.get("outcome", "")).lower()
        milestone = event.get("milestone")

        # Player names & teams
        team_name = str(event.get("team") or event.get("team_name") or "Northbridge Lions")
        default_opponent = "Northbridge Lions" if team_name == "Harbourside City" else "Harbourside City"
        opponent_name = str(event.get("opponent") or event.get("opponent_name") or default_opponent)

        passer_name = str(event.get("player_name") or event.get("passer_name") or "Declan Rowe")
        if event.get("secondary_player_name") or event.get("receiver_name") or event.get("target_player"):
            receiver_name = str(
                event.get("secondary_player_name")
                or event.get("receiver_name")
                or event.get("target_player")
            )
        elif event_type in ("goal", "shot"):
            receiver_name = "Enzo Barreto" if team_name == "Northbridge Lions" else "Daniel Roark"
        elif event_type == "tackle":
            receiver_name = "Mateus Montoya" if team_name == "Harbourside City" else "Anders Hagen"
        elif event_type == "turnover":
            receiver_name = "Anders Hagen" if team_name == "Northbridge Lions" else "Kofi Sarpong"
        elif event_type == "foul":
            receiver_name = "Bernardo Santoro" if team_name == "Northbridge Lions" else "Martin Olsvik"
        else:
            receiver_name = "Kofi Sarpong"

        # Extract coordinates supporting start_x/y or location_x/y
        raw_start_x = event.get("start_x") if event.get("start_x") is not None else event.get("location_x", 50.0)
        raw_start_y = event.get("start_y") if event.get("start_y") is not None else event.get("location_y", 34.0)

        if event.get("end_x") is not None:
            raw_end_x = event.get("end_x")
            raw_end_y = event.get("end_y") if event.get("end_y") is not None else float(raw_start_y)
        elif event_type in ("tackle", "turnover", "pressure", "foul", "card"):
            raw_end_x = float(raw_start_x)
            raw_end_y = float(raw_start_y)
        elif event_type in ("shot", "goal"):
            target_goal_x = attacking_goal_x(team_name, period)
            raw_end_x = target_goal_x
            raw_end_y = 34.0
        else:
            raw_end_x = float(raw_start_x) + 10.0
            raw_end_y = float(raw_start_y)

        start_x = max(0.0, min(105.0, float(raw_start_x)))
        start_y = max(0.0, min(68.0, float(raw_start_y)))
        end_x = max(0.0, min(105.0, float(raw_end_x)))
        end_y = max(0.0, min(68.0, float(raw_end_y)))

        # Calculate exact Euclidean distance (clamped to pitch length 105.0m maximum)
        dx = end_x - start_x
        dy = end_y - start_y
        dist = math.hypot(dx, dy)
        pass_distance_m = min(105.0, round(dist, 1))

        # Ingest telemetry frame into rolling tactical window if provided
        if telemetry_frame:
            self.rolling_window.add_telemetry_frame(telemetry_frame)

        # Calculate Ball / Shot Speed
        duration_sec = float(event.get("duration_sec", 1.2))
        speed_override = None
        if "tactical_metrics" in event and isinstance(event["tactical_metrics"], dict):
            speed_override = event["tactical_metrics"].get("ball_speed_kmh")
        elif "metrics" in event and isinstance(event["metrics"], dict):
            speed_override = event["metrics"].get("ball_speed_kmh") or event["metrics"].get("speed_kmh")
        elif "ball_speed_kmh" in event:
            speed_override = event["ball_speed_kmh"]

        if speed_override is not None and not math.isnan(float(speed_override)):
            ball_speed_kmh = round(max(0.0, min(150.0, float(speed_override))), 1)
        else:
            ball_speed_kmh = TacticalMathEngine.calculate_speed(dx_m=dx, dy_m=dy, dt_sec=duration_sec)

        # Defender spatial pressure analysis
        opponents = defenders
        if opponents is None and telemetry_frame:
            players = telemetry_frame.get("players", [])
            own_side = "home" if team_name in ("Northbridge Lions", "home") else "away"
            opponents = [
                p for p in players
                if p.get("team") not in (team_name, own_side) and p.get("role") != "GK"
            ]

        if opponents is not None and len(opponents) > 0:
            defenders_in_corridor = TacticalMathEngine.calculate_defenders_in_corridor(
                passer_x=start_x,
                passer_y=start_y,
                receiver_x=end_x,
                receiver_y=end_y,
                defenders=opponents,
                corridor_radius=4.0,
            )
            defenders_in_cone = TacticalMathEngine.calculate_defenders_in_cone(
                passer_x=start_x,
                passer_y=start_y,
                receiver_x=end_x,
                receiver_y=end_y,
                defenders=opponents,
                max_angle_deg=20.0,
                max_distance_m=dist + 5.0,
            )
        elif "defenders_in_corridor" in event:
            defenders_in_corridor = int(event["defenders_in_corridor"])
            defenders_in_cone = int(event.get("defenders_in_cone", max(0, defenders_in_corridor - 1)))
        else:
            evt_metrics = event.get("tactical_metrics") or event.get("metrics") or {}
            defenders_in_corridor = int(evt_metrics.get("defenders_corridor", evt_metrics.get("defenders_in_corridor", 2)))
            defenders_in_cone = int(evt_metrics.get("defenders_cone", evt_metrics.get("defenders_in_cone", 1)))

        # Calculate Pass Difficulty Rating (PDR)
        pdr_override = None
        if "tactical_metrics" in event and isinstance(event["tactical_metrics"], dict):
            pdr_override = event["tactical_metrics"].get("pass_difficulty")
        elif "metrics" in event and isinstance(event["metrics"], dict):
            pdr_override = event["metrics"].get("pass_difficulty") or event["metrics"].get("pdr")
        elif "pass_difficulty" in event:
            pdr_override = event["pass_difficulty"]

        if pdr_override is not None and not math.isnan(float(pdr_override)):
            pass_difficulty = round(max(0.0, min(100.0, float(pdr_override))), 1)
        else:
            pass_difficulty = TacticalMathEngine.calculate_pass_difficulty(
                distance_m=pass_distance_m,
                defenders_in_cone=defenders_in_cone,
                defenders_radius_4m=defenders_in_corridor,
                ball_speed_kmh=ball_speed_kmh,
            )

        # Calculate Expected Threat (Delta xT)
        xt_override = None
        if "tactical_metrics" in event and isinstance(event["tactical_metrics"], dict):
            xt_override = event["tactical_metrics"].get("xt_gained")
        elif "metrics" in event and isinstance(event["metrics"], dict):
            xt_override = event["metrics"].get("xt_gained")
        elif "xt_gained" in event:
            xt_override = event["xt_gained"]

        if xt_override is not None and not math.isnan(float(xt_override)):
            xt_gained = round(max(-1.0, min(1.0, float(xt_override))), 3)
        else:
            xt_gained = TacticalMathEngine.calculate_expected_threat(
                to_attack_frame(start_x, team_name, period), to_attack_frame_y(start_y, team_name, period),
                to_attack_frame(end_x, team_name, period), to_attack_frame_y(end_y, team_name, period),
            )

        # Calculate Chaos vs. Control Index (CCI)
        cci_override = None
        if "tactical_metrics" in event and isinstance(event["tactical_metrics"], dict):
            cci_override = event["tactical_metrics"].get("chaos_index")
        elif "metrics" in event and isinstance(event["metrics"], dict):
            cci_override = event["metrics"].get("chaos_index")
        elif "chaos_index" in event:
            cci_override = event["chaos_index"]

        if cci_override is not None and not math.isnan(float(cci_override)):
            chaos_index = round(max(0.0, min(100.0, float(cci_override))), 1)
        else:
            chaos_index = self.rolling_window.get_chaos_index()
            # If window is empty, calibrate default around 45.0
            if chaos_index == 0.0 and len(self.rolling_window.ball_speeds) == 0:
                chaos_index = 45.0

        # Formulate descriptive tactical context
        milestone_str = f" [Milestone: {milestone}]" if milestone else ""
        if "context" in event and event["context"]:
            tactical_context = str(event["context"]) + milestone_str
        elif event_type == "goal":
            tactical_context = f"Decisive goal strike by {passer_name} inside the penalty area{milestone_str}"
        elif event_type == "shot":
            if outcome == "saved" or sub_type == "goalkeeper_save":
                tactical_context = f"Goal-bound strike by {passer_name} denied by goalkeeper {receiver_name}{milestone_str}"
            else:
                tactical_context = f"High-threat shot attempt by {passer_name} targeting the goal{milestone_str}"
        elif event_type == "tackle":
            tactical_context = f"High-intensity defensive tackle by {passer_name} against {receiver_name}{milestone_str}"
        elif event_type == "turnover":
            tactical_context = f"Defensive turnover won by {passer_name} stopping {receiver_name}{milestone_str}"
        elif event_type == "foul":
            tactical_context = f"Tactical foul committed by {passer_name} breaking up counter-attack{milestone_str}"
        elif event_type == "pressure":
            tactical_context = (
                str(event.get("context") or f"{passer_name} applies pressure to {receiver_name} during {opponent_name}'s build-up")
                + milestone_str
            )
        elif xt_gained > 0.15:
            tactical_context = f"High-threat penetration piercing defensive lines into the danger zone{milestone_str}"
        elif defenders_in_corridor >= 2:
            tactical_context = f"High-pressure pass breaking the opponent midfield press{milestone_str}"
        elif pass_distance_m > 30.0:
            tactical_context = f"Expansive switch of play stretching opponent lateral coverage{milestone_str}"
        else:
            tactical_context = f"Controlled possession build-up seeking progressive corridors{milestone_str}"

        return FactPack(
            event_id=event_id,
            match_minute=match_minute,
            period=period,
            frame_index=int(event["frame_index"]) if event.get("frame_index") is not None else None,
            event_type=event_type,
            passer_name=passer_name,
            receiver_name=receiver_name,
            team_name=team_name,
            opponent_name=opponent_name,
            start_x=round(start_x, 2),
            start_y=round(start_y, 2),
            end_x=round(end_x, 2),
            end_y=round(end_y, 2),
            pass_distance_m=pass_distance_m,
            pass_difficulty=pass_difficulty,
            ball_speed_kmh=ball_speed_kmh,
            chaos_index=chaos_index,
            xt_gained=xt_gained,
            defenders_in_corridor=defenders_in_corridor,
            defenders_in_cone=defenders_in_cone,
            tactical_context=tactical_context,
            sub_type=sub_type or None,
            outcome=outcome or None,
            milestone=milestone or None,
        )
