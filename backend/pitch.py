"""Pitch orientation helpers.

Teams change ends at half-time. In the first half the home side (Northbridge Lions) attacks
towards x = 105; in the second half it attacks towards x = 0 and the away side
attacks towards x = 105. Anything that depends on "forward" must therefore know the
period. These helpers answer that in one place.
"""

from typing import Any

PITCH_LENGTH = 105.0
PITCH_WIDTH = 68.0


def side_of(team: Any) -> str:
    """'home' or 'away' from a side id or a team name."""
    return "home" if str(team or "").strip().lower() in {"home", "northbridge lions"} else "away"


def attacks_right(team: Any, period: Any) -> bool:
    home_right = int(period or 1) != 2
    return home_right if side_of(team) == "home" else not home_right


def attacking_goal_x(team: Any, period: Any) -> float:
    return PITCH_LENGTH if attacks_right(team, period) else 0.0


def own_goal_x(team: Any, period: Any) -> float:
    return 0.0 if attacks_right(team, period) else PITCH_LENGTH


def to_attack_frame(x: float, team: Any, period: Any) -> float:
    """x measured as if the team were attacking towards x = 105 (0 = own goal line)."""
    return float(x) if attacks_right(team, period) else PITCH_LENGTH - float(x)


def to_attack_frame_y(y: float, team: Any, period: Any) -> float:
    """y flipped together with x so a team's left and right flanks stay consistent."""
    return float(y) if attacks_right(team, period) else PITCH_WIDTH - float(y)
