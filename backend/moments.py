"""InGame Studio - Event-derived key moments (highlights and tactical freeze-frames).

Everything here is computed from the match events that actually happened: which
moments are chosen, where the 22 players stand, how deep the defensive line is,
where the pressing zones are, and which passing lanes were open. Nothing is a
fixed list, so a different seed or an ingested event feed produces different
moments.
"""

import math
import threading
from typing import Any, Dict, List, Optional, Tuple

from backend.math_engine import TacticalMathEngine
from backend.pitch import own_goal_x as own_goal_line_x, to_attack_frame
from generator.telemetry_streamer import TelemetryStreamer

HOME_NAME = "Northbridge Lions"
AWAY_NAME = "Harbourside City"

_scratch: Optional[TelemetryStreamer] = None
_scratch_lock = threading.Lock()


def side_of(team: Any) -> str:
    return "home" if str(team or "").strip().lower() in {"home", "northbridge lions"} else "away"


def team_name(side: str) -> str:
    return HOME_NAME if side == "home" else AWAY_NAME


def _clock_seconds(clock: str) -> int:
    try:
        minutes, seconds = str(clock).split(":", 1)
        return int(minutes) * 60 + int(seconds)
    except (ValueError, AttributeError):
        return 0


def freeze_frame(event: Dict[str, Any], all_events: Optional[List[Dict[str, Any]]] = None) -> Dict[str, Any]:
    """Reconstructs the players' positions at the instant of an event.

    ``all_events`` lets substitutions and red cards before that moment be applied.
    """
    global _scratch
    with _scratch_lock:
        if _scratch is None:
            _scratch = TelemetryStreamer(match_id=str(event.get("match_id") or "IGS_2026_NBL_HSC"))
        return _scratch.jump_to_event(dict(event), all_events)


def _hull(points: List[Tuple[float, float]]) -> List[Dict[str, float]]:
    pts = sorted(set(points))
    if len(pts) <= 2:
        return [{"x": round(x, 1), "y": round(y, 1)} for x, y in pts]

    def cross(o, a, b):
        return (a[0] - o[0]) * (b[1] - o[1]) - (a[1] - o[1]) * (b[0] - o[0])

    lower: List[Tuple[float, float]] = []
    for p in pts:
        while len(lower) >= 2 and cross(lower[-2], lower[-1], p) <= 0:
            lower.pop()
        lower.append(p)
    upper: List[Tuple[float, float]] = []
    for p in reversed(pts):
        while len(upper) >= 2 and cross(upper[-2], upper[-1], p) <= 0:
            upper.pop()
        upper.append(p)
    return [{"x": round(x, 1), "y": round(y, 1)} for x, y in lower[:-1] + upper[:-1]]


def geometry_from_frame(frame: Dict[str, Any], event: Dict[str, Any]) -> Dict[str, Any]:
    """Defensive line depth, offside line, block shape, press zones and passing lanes."""
    attack_side = side_of(event.get("team"))
    if str(event.get("event_type")).lower() == "card":
        attack_side = "away" if attack_side == "home" else "home"  # the carded side is the one defending
    defend_side = "away" if attack_side == "home" else "home"
    players = frame.get("players", [])
    defenders = [p for p in players if p.get("team") == defend_side]
    outfield = [p for p in defenders if p.get("role") != "GK"]
    own_goal_x = own_goal_line_x(defend_side, frame.get("period", event.get("period", 1)))

    def depth(p: Dict[str, Any]) -> float:
        return abs(float(p["x"]) - own_goal_x)

    by_depth = sorted(defenders, key=depth)
    line = sorted(outfield, key=depth)[:4]
    line_depth = round(sum(depth(p) for p in line) / len(line), 1) if line else 0.0
    offside_x = round(float(by_depth[1]["x"]), 1) if len(by_depth) > 1 else own_goal_x

    polygon = _hull([(float(p["x"]), float(p["y"])) for p in outfield])
    area = 0.0
    for i, point in enumerate(polygon):
        nxt = polygon[(i + 1) % len(polygon)]
        area += point["x"] * nxt["y"] - nxt["x"] * point["y"]
    compactness = round(abs(area) / 2.0, 0) if len(polygon) >= 3 else 0.0
    line_ys = sorted(float(p["y"]) for p in line)
    line_gap = round(max((b - a for a, b in zip(line_ys, line_ys[1:])), default=0.0), 1)

    ball = frame.get("ball", {})
    bx, by = float(ball.get("x", event.get("location_x", 52.5))), float(ball.get("y", event.get("location_y", 34.0)))
    pressers = [p for p in defenders if math.hypot(float(p["x"]) - bx, float(p["y"]) - by) <= 18.0]
    zones: List[Dict[str, Any]] = []
    if pressers:
        cx = sum(float(p["x"]) for p in pressers) / len(pressers)
        cy = sum(float(p["y"]) for p in pressers) / len(pressers)
        radius = max(8.0, max(math.hypot(float(p["x"]) - cx, float(p["y"]) - cy) for p in pressers) + 3.0)
        zones.append({
            "x": round(cx, 1), "y": round(cy, 1), "radius": round(radius, 1),
            "intensity": round(min(1.0, len(pressers) / 5.0), 2), "team": team_name(defend_side),
            "players_involved": len(pressers),
        })

    lanes = _passing_lanes(frame, event, attack_side, defenders)
    return {
        "defensive_line_depth_m": line_depth,
        "offside_line_x": offside_x,
        "low_block_polygon": polygon,
        "compactness_m2": compactness,
        "line_gap_m": line_gap,
        "pressing_zones": zones,
        "passing_lanes": lanes,
        "defending_team": team_name(defend_side),
        "pressing_players": len(pressers),
    }


def _passing_lanes(frame: Dict[str, Any], event: Dict[str, Any], attack_side: str, defenders: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    players = {p["player_id"]: p for p in frame.get("players", []) if p.get("player_id")}
    origin = players.get(event.get("player_id"))
    if not origin:
        return []
    ox, oy = float(origin["x"]), float(origin["y"])
    mates = [p for p in players.values() if p.get("team") == attack_side and p["player_id"] != origin["player_id"] and p.get("role") != "GK"]
    mates.sort(key=lambda p: math.hypot(float(p["x"]) - ox, float(p["y"]) - oy))
    chosen = [m for m in mates if m["player_id"] != event.get("secondary_player_id")][:3]
    target = players.get(event.get("secondary_player_id"))
    lanes = []
    for candidate, active in ([(target, True)] if target and target.get("team") == attack_side else []) + [(m, False) for m in chosen]:
        tx, ty = float(candidate["x"]), float(candidate["y"])
        distance = math.hypot(tx - ox, ty - oy)
        corridor = TacticalMathEngine.calculate_defenders_in_corridor(ox, oy, tx, ty, defenders, 4.0)
        cone = TacticalMathEngine.calculate_defenders_in_cone(ox, oy, tx, ty, defenders, 20.0, distance + 5.0)
        risk = TacticalMathEngine.calculate_pass_difficulty(distance, cone, corridor, 0.0)
        lanes.append({
            "from_player_id": origin["player_id"], "to_player_id": candidate["player_id"],
            "startX": round(ox, 1), "startY": round(oy, 1), "endX": round(tx, 1), "endY": round(ty, 1),
            "risk": round(float(risk), 1), "active": active,
        })
    return lanes


def _running_scores(events: List[Dict[str, Any]]) -> Dict[str, str]:
    scores = {"home": 0, "away": 0}
    after: Dict[str, str] = {}
    for ev in events:
        if str(ev.get("event_type")).lower() == "goal" or str(ev.get("outcome")).lower() == "goal":
            scores[side_of(ev.get("team"))] += 1
        after[str(ev.get("event_id"))] = f"{scores['home']} - {scores['away']}"
    return after


def _impact(ev: Dict[str, Any]) -> float:
    metrics = ev.get("tactical_metrics") or {}
    return float(metrics.get("xt_gained", 0.0) or 0.0) + 0.002 * float(metrics.get("pass_difficulty", 0.0) or 0.0)


def select_highlight_events(events: List[Dict[str, Any]], limit: int = 8) -> List[Dict[str, Any]]:
    """Every goal and sending-off, then the best saves, chances and recoveries, in match order."""
    goals = [e for e in events if str(e.get("event_type")).lower() == "goal"]
    reds = [e for e in events if str(e.get("event_type")).lower() == "card" and str(e.get("outcome")).lower() == "red"]
    shots = [e for e in events if str(e.get("event_type")).lower() == "shot"]
    recoveries = [e for e in events if str(e.get("event_type")).lower() in {"turnover", "tackle"}]
    must_keep = goals + reds
    optional = sorted(shots, key=_impact, reverse=True)[:6] + sorted(recoveries, key=_impact, reverse=True)[:12]
    # One highlight per kind of moment (same type, player and outcome), so the reel is varied.
    seen, unique_optional = set(), []
    for ev in sorted(optional, key=_impact, reverse=True):
        signature = (ev.get("event_type"), ev.get("player_id"), ev.get("secondary_player_id"), ev.get("outcome"))
        if signature in seen:
            continue
        seen.add(signature)
        unique_optional.append(ev)
    chosen = must_keep + unique_optional[: max(0, limit - len(must_keep))]
    return sorted(chosen, key=lambda e: (e.get("period", 1), e.get("frame_index", 0)))


def _highlight_text(ev: Dict[str, Any], score: str) -> Tuple[str, str, str]:
    kind = str(ev.get("event_type")).lower()
    outcome = str(ev.get("outcome") or "").lower()
    name = ev.get("player_name") or "Unnamed player"
    other = ev.get("secondary_player_name") or "the opponent"
    if kind == "goal":
        return "goal", f"GOAL! {name} ({score.replace(' ', '')})", f"{name} beats {other}"
    if kind == "shot" and outcome == "saved":
        return "chance", f"{other} saves from {name}", f"{name}'s shot is stopped by {other}"
    if kind == "shot":
        return "chance", f"{name} shoots {outcome.replace('_', ' ') or 'wide'}", f"{name} goes close against {other}"
    if kind == "card":
        return "card", f"RED CARD! {name} is sent off", f"{name} sees red for a foul on {other}"
    if kind == "tackle":
        return "tackle", f"{name} tackles {other}", f"{name} wins the ball from {other}"
    return "turnover", f"{name} wins possession", f"{name} intercepts {other}"


def build_highlights(events: List[Dict[str, Any]], narrative_lookup=None) -> List[Dict[str, Any]]:
    """Highlight moments with the real 22-player positions at each event."""
    ordered = sorted(events, key=lambda e: (e.get("period", 1), e.get("frame_index", 0)))
    scores = _running_scores(ordered)
    highlights: List[Dict[str, Any]] = []
    for ev in select_highlight_events(ordered):
        frame = freeze_frame(ev, ordered)
        score = scores.get(str(ev.get("event_id")), "0 - 0")
        kind, title, subtitle = _highlight_text(ev, score)
        metrics = ev.get("tactical_metrics") or {}
        description = (narrative_lookup(ev) if narrative_lookup else None) or ev.get("context") or subtitle
        minute = str(ev.get("clock", "00:00")).split(":")[0]
        end_x = ev.get("end_x") if ev.get("end_x") is not None else ev.get("location_x", 52.5)
        end_y = ev.get("end_y") if ev.get("end_y") is not None else ev.get("location_y", 34.0)
        highlights.append({
            "id": str(ev.get("event_id")),
            "event_id": ev.get("event_id"),
            "second": _clock_seconds(ev.get("clock", "00:00")),
            "clock": ev.get("clock"),
            "minute": f"{int(minute)}'",
            "title": title,
            "subtitle": subtitle,
            "type": kind,
            "team": ev.get("team"),
            "score": score,
            "description": description,
            "speed_kmh": metrics.get("ball_speed_kmh"),
            "xt_gained": metrics.get("xt_gained"),
            "shooterId": ev.get("player_id") if kind in {"goal", "chance"} else None,
            "ballPos": {
                "x": float(frame.get("ball", {}).get("x", ev.get("location_x", 52.5))),
                "y": float(frame.get("ball", {}).get("y", ev.get("location_y", 34.0))),
                "z": 0.0,
            },
            "vector": {
                "startX": float(ev.get("location_x", 52.5)), "startY": float(ev.get("location_y", 34.0)),
                "endX": float(end_x), "endY": float(end_y),
            },
            "players": [
                {
                    "id": p["player_id"], "name": str(p.get("name", "")).split(" ")[-1], "num": p.get("jersey_number"),
                    "role": p.get("role"), "team": p.get("team"), "x": p["x"], "y": p["y"],
                }
                for p in frame.get("players", [])
            ],
        })
    return highlights


KEY_MOMENT_LABELS = {
    "goal": "Goal",
    "card": "Red Card",
    "shot": "Big Chance Saved",
    "tackle": "Key Tackle",
    "turnover": "Ball Won",
}


def select_tactical_events(events: List[Dict[str, Any]], limit: int = 6) -> List[Tuple[str, str, Dict[str, Any]]]:
    """The key moments of the match: exactly the turning points listed in the match recap.

    Every goal and sending-off comes first, then the highest-impact saves and recoveries.
    Returns (slug, label, event) in match order.
    """
    from backend.match_recap import _turning_points

    ordered = sorted(events, key=lambda e: (e.get("period", 1), e.get("frame_index", 0)))
    by_id = {str(e.get("event_id")): e for e in ordered}
    picked: List[Tuple[str, str, Dict[str, Any]]] = []
    for point in _turning_points(ordered, {"home": HOME_NAME, "away": AWAY_NAME}, limit=limit):
        ev = by_id.get(str(point.get("event_id")))
        if ev is None:
            continue
        kind = str(ev.get("event_type")).lower()
        slug = "goal" if kind == "goal" else kind
        picked.append((slug, KEY_MOMENT_LABELS.get(slug, "Key Moment"), ev))
    return picked


def build_tactical_moments(events: List[Dict[str, Any]], explain=None) -> List[Dict[str, Any]]:
    """Turning points with freeze-frames, geometry and an explanation of each."""
    moments: List[Dict[str, Any]] = []
    scores = _running_scores(sorted(events, key=lambda e: (e.get("period", 1), e.get("frame_index", 0))))
    for slug, label, ev in select_tactical_events(events):
        frame = freeze_frame(ev, events)
        geo = geometry_from_frame(frame, ev)
        attack = team_name(side_of(ev.get("team")))
        who = ev.get("player_name") or "A player"
        moment = {
            "id": f"{slug}_{ev.get('event_id')}",
            "event_id": ev.get("event_id"),
            "name": f"{label}: {who} ({attack})",
            "turning_point": label,
            "event_type": ev.get("event_type"),
            "period": ev.get("period"),
            "score_after": scores.get(str(ev.get("event_id")), "0 - 0"),
            "clock": ev.get("clock"),
            "timestamp": frame.get("timestamp"),
            "description": ev.get("context") or f"{who} for {attack}.",
            "frame": frame,
            **geo,
        }
        if explain:
            result = explain(moment, ev)
            moment["ai_analysis"] = result["analysis"]
            moment["breakdown"] = result["breakdown"]
        else:
            moment["ai_analysis"] = moment["description"]
        moments.append(moment)
    return moments
