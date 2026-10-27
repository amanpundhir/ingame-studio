"""Automated post-match studio recap derived from the supplied synthetic match data."""

import json
import os
from typing import Any, Dict, List, Optional
from backend.math_engine import MatchAnalyticsTracker


def _side(team: Any) -> str:
    value = str(team or "").strip().lower()
    return "home" if value in {"home", "northbridge lions"} else "away"


def _team_labels(events: List[Dict[str, Any]]) -> Dict[str, str]:
    labels = {"home": "Home", "away": "Away"}
    for event in events:
        team = str(event.get("team") or "").strip()
        if team and team.lower() not in {"home", "away"}:
            labels[_side(team)] = team
    return labels


def _minute(event: Dict[str, Any]) -> str:
    clock = str(event.get("clock") or "00:00")
    if ":" in clock:
        return f"{clock.split(':', 1)[0]}'"
    return clock


def _turning_points(events: List[Dict[str, Any]], team_labels: Dict[str, str], limit: int = 6) -> List[Dict[str, Any]]:
    points: List[Dict[str, Any]] = []
    scores = {"home": 0, "away": 0}
    goals = [e for e in events if e.get("event_type") == "goal" or str(e.get("outcome", "")).lower() == "goal"]
    reds = [e for e in events if e.get("event_type") == "card" and str(e.get("outcome", "")).lower() == "red"]
    other_moments = [
        e for e in events
        if e not in goals and (
            (e.get("event_type") == "shot" and str(e.get("outcome", "")).lower() in {"saved", "blocked"})
            or (e.get("event_type") in {"turnover", "tackle"} and str(e.get("outcome", "")).lower() == "won")
        )
    ]
    # Include every goal, then fill the editorial list with a few high-impact
    # defensive or chance moments. Rank from event facts, not fixed names/IDs.
    def impact(event: Dict[str, Any]) -> tuple[float, int]:
        kind = event.get("event_type")
        outcome = str(event.get("outcome", "")).lower()
        category_weight = 3.0 if kind == "shot" and outcome == "saved" else 2.0 if kind == "turnover" else 1.0
        metrics = event.get("tactical_metrics") or {}
        return category_weight + float(metrics.get("xt_gained", 0.0) or 0.0), -int(event.get("frame_index", 0))

    selected = goals + reds + sorted(other_moments, key=impact, reverse=True)[:max(0, limit - len(goals) - len(reds))]
    key_events = sorted(selected, key=lambda event: (event.get("period", 1), event.get("frame_index", 0)))
    for event in key_events:
        side = _side(event.get("team"))
        event_type = str(event.get("event_type") or "moment")
        is_goal = event_type == "goal" or str(event.get("outcome", "")).lower() == "goal"
        if is_goal:
            scores[side] += 1
        name = str(event.get("player_name") or "An unnamed player")
        team = team_labels[side]
        detail = str(event.get("context") or event.get("sub_type") or event_type.replace("_", " ").capitalize())
        points.append({
            "minute": _minute(event),
            "title": f"{name} {'scores' if is_goal else 'is sent off' if event_type == 'card' else event_type.replace('_', ' ')}",
            "event_id": event.get("event_id", ""),
            "type": "goal" if is_goal else event_type,
            "player": name,
            "team": team,
            "score_after": f"{scores['home']}-{scores['away']}",
            "impact": f"Score after event: {scores['home']}-{scores['away']}" if is_goal else detail,
            "description": f"{name} ({team}) {('scores' if is_goal else 'is sent off' if event_type == 'card' else 'is involved in')} at {_minute(event)}. {detail}.",
        })
    return points


def _phase_summaries(events: List[Dict[str, Any]], team_labels: Dict[str, str]) -> List[Dict[str, Any]]:
    phases = [(0, 25, "Opening phase"), (26, 45, "First-half finish"), (46, 70, "Middle phase"), (71, 120, "Closing phase")]
    output = []
    for start, end, name in phases:
        phase_events = []
        for event in events:
            try:
                minute = int(str(event.get("clock", "0:00")).split(":", 1)[0])
            except ValueError:
                continue
            if start <= minute <= end:
                phase_events.append(event)
        if not phase_events:
            continue
        cci_values = []
        for event in phase_events:
            metrics = event.get("tactical_metrics") or event.get("metrics") or {}
            value = metrics.get("chaos_index", metrics.get("cci"))
            if value is not None:
                try:
                    cci_values.append(float(value))
                except (TypeError, ValueError):
                    pass
        avg_cci = round(sum(cci_values) / len(cci_values), 1) if cci_values else 0.0
        character = "High Control" if avg_cci < 35 else "High Transition Chaos" if avg_cci > 65 else "Balanced Contest"
        team_counts: Dict[str, int] = {"home": 0, "away": 0}
        for event in phase_events:
            team_counts[_side(event.get("team"))] += 1
        dominant_side = max(team_counts, key=team_counts.get)
        dominant = team_labels[dominant_side] if team_counts[dominant_side] else "Balanced Contest"
        output.append({
            "phase": f"{name} ({start}'-{end}')",
            "avg_cci": avg_cci,
            "character": character,
            "dominant_team": dominant,
            "description": f"{len(phase_events)} recorded events; {dominant} generated the most events in this phase." + (" CCI is unavailable for this phase." if not cci_values else ""),
        })
    return output


def _localized_summaries(home: str, away: str, score_home: int, score_away: int, motm: str) -> Dict[str, str]:
    score = f"{score_home}-{score_away}"
    return {
        "en": f"Full-time: {home} {score} {away}. Player of the match: {motm}.",
        "es": f"Final: {home} {score} {away}. Jugador del partido: {motm}.",
    }


def generate_match_recap(
    analytics_tracker: Optional[MatchAnalyticsTracker] = None,
    events: Optional[List[Dict[str, Any]]] = None,
    match_id: str = "IGS_2026_NBL_HSC",
    clock: Optional[str] = None,
) -> Dict[str, Any]:
    """Build a structured recap from actual events and accumulated tracker values."""
    if events is None:
        events_path = os.path.join(os.path.dirname(__file__), "..", "data", "synthetic_events.json")
        try:
            with open(events_path, "r", encoding="utf-8") as source:
                events = json.load(source)
        except (OSError, json.JSONDecodeError):
            events = []
    events = sorted(
        list(events or []),
        key=lambda event: (event.get("period", 1), event.get("frame_index", 0)),
    )

    if analytics_tracker is None or not getattr(analytics_tracker, "processed_event_ids", set()):
        analytics_tracker = MatchAnalyticsTracker()
        if events:
            analytics_tracker.simulate_full(events)
    elif events:
        # Include externally supplied events not already represented in the tracker.
        for event in events:
            analytics_tracker.record_event(event)

    stats = analytics_tracker.get_match_stats()
    players = analytics_tracker.get_all_player_stats()
    labels = _team_labels(events)
    if labels["home"] == "Home" and match_id == "IGS_2026_NBL_HSC":
        labels["home"] = "Northbridge Lions"
    if labels["away"] == "Away" and match_id == "IGS_2026_NBL_HSC":
        labels["away"] = "Harbourside City"
    home_name, away_name = labels["home"], labels["away"]
    score_home = int(stats.get("score", {}).get("home", 0))
    score_away = int(stats.get("score", {}).get("away", 0))
    winner = home_name if score_home > score_away else away_name if score_away > score_home else "draw"

    active_players = [p for p in players if any((p.get("goals"), p.get("assists"), p.get("shots"), p.get("passes", {}).get("total"), p.get("defensive_interventions"), p.get("minutes_played"), p.get("distance_km", 0) > 0))]
    motm_player = next((p for p in active_players if p.get("is_motm")), None)
    if motm_player is None and active_players:
        motm_player = max(active_players, key=lambda p: (p.get("rating", 0), p.get("bps", 0)))
    motm_name = str(motm_player.get("name")) if motm_player else "Not available"
    motm = {
        "player_id": motm_player.get("player_id", "") if motm_player else "",
        "name": motm_name,
        "team": home_name if motm_player and motm_player.get("team") == "home" else away_name if motm_player else "",
        "role": motm_player.get("role", "") if motm_player else "",
        "rating": motm_player.get("rating", 0) if motm_player else 0,
        "bps": motm_player.get("bps", 0) if motm_player else 0,
        "goals": motm_player.get("goals", 0) if motm_player else 0,
        "assists": motm_player.get("assists", 0) if motm_player else 0,
        "shots_on_target": motm_player.get("shots_on_target", 0) if motm_player else 0,
        "key_passes": motm_player.get("key_passes", 0) if motm_player else 0,
        "xt_created": motm_player.get("xt_created", 0) if motm_player else 0,
        "top_speed_kmh": motm_player.get("top_speed_kmh", 0) if motm_player else 0,
        "distance_km": motm_player.get("distance_km", 0) if motm_player else 0,
        "fantasy_bonus_points": motm_player.get("fantasy_bonus_points", 0) if motm_player else 0,
        "summary": f"{motm_name} led the available player ratings." if motm_player else "Player of the match is unavailable because no player performance data was recorded.",
    }

    xg = stats.get("xg", {})
    shots = stats.get("shots", {})
    passes = stats.get("passes", {})
    tackles = stats.get("tackles", {})
    home_xg, away_xg = float(xg.get("home", 0)), float(xg.get("away", 0))
    goals = _turning_points(events, labels)
    phase_summaries = _phase_summaries(events, labels)
    cci_values = [phase["avg_cci"] for phase in phase_summaries if phase.get("avg_cci") is not None]
    average_cci = round(sum(cci_values) / len(cci_values), 1) if cci_values else 0.0
    rhythm_label = "High Control" if average_cci < 35 else "High Transition Chaos" if average_cci > 65 else "Balanced Contest"
    event_names = ", ".join(f"{g['player']} ({g['minute']})" for g in goals if g["type"] == "goal")
    result_text = f"{home_name} and {away_name} finished {score_home}-{score_away}."
    if event_names:
        result_text += f" Recorded goals: {event_names}."
    elif not goals:
        result_text += " No decisive turning-point events were recorded."
    story = f"Full-time report: {result_text} Expected goals were {home_xg:.2f} to {away_xg:.2f}."

    event_clocks = [str(e.get("clock")) for e in events if ":" in str(e.get("clock", ""))]
    recap_clock = clock or (event_clocks[-1] if event_clocks else "00:00")

    highlights_sequence: List[Dict[str, Any]] = []
    events_by_id = {e.get("event_id"): e for e in events if e.get("event_id")}
    for idx, tp in enumerate(goals):
        eid = tp.get("event_id")
        orig_ev = events_by_id.get(eid)
        frame_idx = int(orig_ev.get("frame_index", 0)) if orig_ev else idx * 600
        start_frame = max(0, frame_idx - 75)
        end_frame = frame_idx + 75
        duration_sec = round((end_frame - start_frame) / 25.0, 1)
        highlights_sequence.append({
            "id": eid or f"hl_{idx+1}",
            "minute": tp.get("minute", "00'"),
            "title": tp.get("title", f"Key Moment #{idx+1}"),
            "start_frame": start_frame,
            "end_frame": end_frame,
            "duration_seconds": duration_sec,
            "event_type": tp.get("type", "highlight"),
        })

    return {
        "match_id": match_id,
        "fixture": f"{home_name} vs {away_name}",
        "status": "FT",
        "clock": recap_clock,
        "final_score": {"home": score_home, "away": score_away, "home_team": home_name, "away_team": away_name},
        "winner": winner,
        "headline": f"{home_name} {score_home}-{score_away} {away_name}",
        "match_story": story,
        "xg_balance": {
            "home_xg": home_xg, "away_xg": away_xg,
            "xg_delta": round(abs(home_xg - away_xg), 2),
            "dominance": f"{home_name} generated more expected goals" if home_xg > away_xg else f"{away_name} generated more expected goals" if away_xg > home_xg else "Expected goals were level",
            "home_shots": shots.get("home", {}).get("total", 0),
            "away_shots": shots.get("away", {}).get("total", 0),
            "home_goals": score_home, "away_goals": score_away,
            "shot_count": {"home": shots.get("home", {}).get("total", 0), "away": shots.get("away", {}).get("total", 0)},
            "shots_on_target": {"home": shots.get("home", {}).get("on_target", 0), "away": shots.get("away", {}).get("on_target", 0)},
            "analysis": f"{home_name} produced {shots.get('home', {}).get('total', 0)} shots and {home_xg:.2f} xG; {away_name} produced {shots.get('away', {}).get('total', 0)} shots and {away_xg:.2f} xG.",
        },
        "turning_points": goals,
        "highlights_sequence": highlights_sequence,
        "man_of_the_match": motm,
        "tactical_entropy": {
            "average_cci": average_cci,
            "rhythm_label": rhythm_label,
            "summary": " ".join(phase["description"] for phase in phase_summaries) or "No phase-level event data is available.",
        },
        "tactical_entropy_shifts": phase_summaries,
        "team_totals": {
            "possession_pct": stats.get("possession_pct", {"home": 0.0, "away": 0.0}),
            "shots": {"home": shots.get("home", {}).get("total", 0), "away": shots.get("away", {}).get("total", 0)},
            "shots_on_target": {"home": shots.get("home", {}).get("on_target", 0), "away": shots.get("away", {}).get("on_target", 0)},
            "passes": {"home": passes.get("home", {}).get("total", 0), "away": passes.get("away", {}).get("total", 0)},
            "pass_accuracy_pct": {"home": passes.get("home", {}).get("accuracy_pct", 0.0), "away": passes.get("away", {}).get("accuracy_pct", 0.0)},
            "tackles_won_pct": {"home": tackles.get("home", {}).get("won_pct", 0.0), "away": tackles.get("away", {}).get("won_pct", 0.0)},
            "corners": stats.get("corners", {"home": 0, "away": 0}),
            "fouls": stats.get("fouls", {"home": 0, "away": 0}),
            "yellow_cards": {"home": stats.get("cards", {}).get("home", {}).get("yellow", 0), "away": stats.get("cards", {}).get("away", {}).get("yellow", 0)},
            "red_cards": {"home": stats.get("cards", {}).get("home", {}).get("red", 0), "away": stats.get("cards", {}).get("away", {}).get("red", 0)},
            "substitutions": stats.get("substitutions", {"home": 0, "away": 0}),
        },
        "localized_summaries": _localized_summaries(home_name, away_name, score_home, score_away, motm_name),
        "translations": {lang: {"headline": summary, "match_story": summary} for lang, summary in _localized_summaries(home_name, away_name, score_home, score_away, motm_name).items()},
    }
