"""Second-half side swap, substitutions, cards and the token budget."""

import json
import os
import time

import pytest

from backend.agents.models import FactPack
from backend.agents.tactician_agent import TacticianAgent
from backend.agents.verifier_agent import VerifierAgent
from backend.agents.foundry_adapter import TokenBudget
from backend.math_engine import MatchAnalyticsTracker
from backend.pitch import attacking_goal_x, own_goal_x, to_attack_frame
from generator.match_generator import NORTHBRIDGE_BENCH, NORTHBRIDGE_ROSTER, BENCH_BY_ID, AWAY_BENCH, AWAY_ROSTER, MatchGenerator

EVENTS_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "synthetic_events.json")
HALF_TIME_FRAME = 2700 * 25
STARTER_IDS = {p["player_id"] for p in NORTHBRIDGE_ROSTER + AWAY_ROSTER}


@pytest.fixture(scope="module")
def events():
    with open(EVENTS_PATH, "r", encoding="utf-8") as handle:
        return json.load(handle)


def _cross_half_time(seed=2036):
    generator = MatchGenerator(seed=seed)
    generator.frame_index = HALF_TIME_FRAME - 4
    frames = [generator.step() for _ in range(40)]
    return generator, frames


def test_pitch_helpers_follow_the_period():
    assert attacking_goal_x("home", 1) == 105.0 and attacking_goal_x("Northbridge Lions", 2) == 0.0
    assert attacking_goal_x("away", 1) == 0.0 and attacking_goal_x("Harbourside City", 2) == 105.0
    assert own_goal_x("home", 2) == 105.0
    assert to_attack_frame(20.0, "home", 1) == 20.0
    assert to_attack_frame(20.0, "home", 2) == 85.0


def test_teams_change_ends_at_half_time():
    generator, frames = _cross_half_time()
    before = next(f for f in frames if f["period"] == 1)
    after = frames[-1]
    assert after["period"] == 2

    def keeper_x(frame, team):
        return next(p["x"] for p in frame["players"] if p["team"] == team and p["role"] == "GK")

    assert keeper_x(before, "home") < 10 < 95 < keeper_x(before, "away")
    assert keeper_x(after, "home") > 95 and keeper_x(after, "away") < 10
    # City kick off the second half from the centre spot.
    kickoff = next(f for f in frames if f["period"] == 2)
    assert kickoff["ball"]["possession_team"] == "away"
    assert abs(kickoff["ball"]["x"] - 52.5) < 1.0


def test_players_restart_at_mirrored_kickoff_positions():
    generator, frames = _cross_half_time()
    second = next(f for f in frames if f["period"] == 2)
    for base in NORTHBRIDGE_ROSTER + AWAY_ROSTER:
        player = next(p for p in second["players"] if p["player_id"] == base["player_id"])
        assert abs(player["x"] - (105.0 - base["base_x"])) < 0.5
        assert abs(player["y"] - (68.0 - base["base_y"])) < 0.5


def test_dataset_goals_are_scored_at_the_correct_end(events):
    goals = [e for e in events if e["event_type"] == "goal"]
    assert goals
    for goal in goals:
        home = goal["team"] == "Northbridge Lions"
        expected = attacking_goal_x("home" if home else "away", goal["period"])
        assert goal["end_x"] == expected, f"{goal['clock']} {goal['team']}"
    assert {g["period"] for g in goals} == {1, 2} or len(goals) >= 2


def test_dataset_has_substitutions_with_valid_players(events):
    subs = [e for e in events if e["event_type"] == "substitution"]
    assert 4 <= len(subs) <= 10
    on_off_seen = set()
    for sub in subs:
        assert sub["player_id"] in BENCH_BY_ID
        assert sub["secondary_player_id"] in STARTER_IDS
        assert sub["player_id"][:3] == sub["secondary_player_id"][:3]
        assert sub["period"] == 2
        assert sub["secondary_player_id"] not in on_off_seen
        on_off_seen.add(sub["secondary_player_id"])
    teams = {s["team"] for s in subs}
    assert teams == {"Northbridge Lions", "Harbourside City"}


def test_dataset_has_cards_with_consistent_types(events):
    cards = [e for e in events if e["event_type"] == "card"]
    assert cards
    for card in cards:
        assert card["sub_type"] in {"yellow_card", "second_yellow", "red_card"}
        assert card["outcome"] == ("yellow" if card["sub_type"] == "yellow_card" else "red")
    # Every card follows a foul by the same player.
    fouls = {(e["player_id"]) for e in events if e["event_type"] == "foul"}
    assert {c["player_id"] for c in cards} <= fouls


def test_substituted_and_sent_off_players_do_not_appear_afterwards(events):
    gone = {}
    for event in events:
        if event["event_type"] == "substitution":
            gone[event["secondary_player_id"]] = event["frame_index"]
        elif event["event_type"] == "card" and event["outcome"] == "red":
            gone[event["player_id"]] = event["frame_index"]
    for event in events:
        for key in ("player_id",):
            left_at = gone.get(event[key])
            if left_at is not None and event["event_type"] not in {"substitution", "card"}:
                assert event["frame_index"] <= left_at, f"{event[key]} acted after leaving at {event['event_id']}"


def test_substitution_swaps_the_player_and_keeps_the_slot():
    generator = MatchGenerator(seed=7)
    incoming = generator._apply_substitution("NBL_29", BENCH_BY_ID["NBL_09"])
    assert incoming is not None and "NBL_29" not in generator.players and "NBL_09" in generator.players
    assert len(generator.players) == 22
    assert generator.slot_of["NBL_09"] == "NBL_29"
    targets = generator.compute_tactical_player_targets(60.0, 30.0, "home")
    assert "NBL_09" in targets and "NBL_29" not in targets


def test_sync_squads_rebuilds_the_pitch_from_events(events):
    generator = MatchGenerator(seed=2036)
    generator.sync_squads(events, 10 ** 9)
    subs = [e for e in events if e["event_type"] == "substitution"]
    reds = [e for e in events if e["event_type"] == "card" and e["outcome"] == "red"]
    assert len(generator.players) == 22 - len(reds)
    for sub in subs:
        assert sub["player_id"] in generator.players or sub["player_id"] in generator.sent_off
        assert sub["secondary_player_id"] not in generator.players
    generator.sync_squads(events, 0)
    assert set(generator.players) == STARTER_IDS


def test_red_card_removes_the_player_and_is_counted():
    generator = MatchGenerator(seed=11)
    generator.frame_index = 4000
    generator._queued_events.append({
        "type": "card", "kind": "red_card", "player_id": "HSC_16", "fouled_id": "NBL_41", "due_frame": 0,
    })
    generator.step()
    generator.step()
    card = next(e for e in generator.events if e["event_type"] == "card")
    assert card["player_id"] == "HSC_16" and card["outcome"] == "red"
    assert "HSC_16" not in generator.players and len(generator.players) == 21

    tracker = MatchAnalyticsTracker()
    tracker.record_event(card)
    stats = tracker.get_match_stats()
    assert stats["cards"]["away"]["red"] == 1 and stats["cards"]["home"]["red"] == 0
    assert tracker.players["HSC_16"].red_cards == 1


def test_second_yellow_counts_as_yellow_and_red():
    tracker = MatchAnalyticsTracker()
    tracker.record_event({
        "event_id": "C1", "event_type": "card", "sub_type": "second_yellow", "outcome": "red", "team": "Northbridge Lions",
        "player_id": "NBL_05", "period": 1, "clock": "30:00", "location_x": 40.0, "location_y": 20.0,
    })
    stats = tracker.get_match_stats()
    assert stats["cards"]["home"] == {"yellow": 1, "red": 1}


def test_substitute_joins_the_tracker_and_minutes_start_when_he_comes_on():
    tracker = MatchAnalyticsTracker()
    tracker.record_event({
        "event_id": "S1", "event_type": "substitution", "sub_type": "tactical_change", "outcome": "completed",
        "team": "Harbourside City", "player_id": "HSC_26", "secondary_player_id": "HSC_11", "period": 2,
        "clock": "63:00", "location_x": 70.0, "location_y": 0.0,
    })
    assert tracker.players["HSC_26"].substituted_on and tracker.players["HSC_11"].substituted_off
    assert tracker.get_match_stats()["substitutions"] == {"home": 0, "away": 1}

    def frame(clock, ids):
        return {
            "clock": clock, "period": 2, "ball": {"x": 50.0, "y": 34.0, "possession_team": "away"},
            "players": [{"player_id": i, "x": 50.0, "y": 34.0, "speed_kmh": 5.0} for i in ids],
        }

    tracker.add_telemetry_frame(frame("62:00", ["HSC_11"]))
    tracker.add_telemetry_frame(frame("70:00", ["HSC_26"]))
    tracker.add_telemetry_frame(frame("80:00", ["HSC_26"]))
    assert tracker.players["HSC_26"].minutes_played == 10
    assert tracker.players["HSC_11"].minutes_played < 5


def test_territory_is_measured_in_each_teams_attacking_direction():
    tracker = MatchAnalyticsTracker()
    # Second half: Northbridge Lions attack towards x = 0, so x = 10 is deep in the opponents' half for them.
    tracker.record_event({
        "event_id": "P1", "event_type": "pass", "outcome": "complete", "team": "Northbridge Lions", "player_id": "NBL_08",
        "period": 2, "clock": "60:00", "location_x": 15.0, "location_y": 30.0, "end_x": 10.0, "end_y": 30.0,
    })
    assert tracker.half_actions["home"] == 1 and tracker.final_third_actions["home"] == 1
    tracker.record_event({
        "event_id": "P2", "event_type": "pass", "outcome": "complete", "team": "Northbridge Lions", "player_id": "NBL_08",
        "period": 1, "clock": "10:00", "location_x": 15.0, "location_y": 30.0, "end_x": 20.0, "end_y": 30.0,
    })
    assert tracker.half_actions["home"] == 1  # the same x is in Northbridge Lions' own half in the first half


def _facts(event_type, sub_type, passer="Savio Neves", receiver="Jeremy Dukes"):
    return FactPack(
        event_id="E", match_minute="63:39", event_type=event_type, passer_name=passer, receiver_name=receiver,
        team_name="Harbourside City", opponent_name="Northbridge Lions", pass_distance_m=0.0, pass_difficulty=12.0,
        ball_speed_kmh=0.0, chaos_index=18.0, xt_gained=0.0, sub_type=sub_type,
    )


def test_verifier_accepts_substitution_text_without_pass_numbers():
    verifier = VerifierAgent()
    facts = _facts("substitution", "tactical_change")
    good = "In minute 63:39, Savio Neves replaces Jeremy Dukes for Harbourside City, adding fresh legs."
    assert verifier.verify(facts, good).is_valid
    assert not verifier.verify(facts, "Savio Neves comes on and is shown a yellow card.").is_valid
    assert not verifier.verify(facts, "Savio Neves replaces Jose Mourinho.").is_valid


def test_verifier_checks_the_card_type():
    verifier = VerifierAgent()
    yellow = _facts("card", "yellow_card", "Rodrigo Vale", "Kai Halvorsen")
    assert verifier.verify(yellow, "Rodrigo Vale is shown a yellow card for a foul on Kai Halvorsen.").is_valid
    assert not verifier.verify(yellow, "Rodrigo Vale is sent off after a foul on Kai Halvorsen.").is_valid
    red = _facts("card", "red_card", "Rodrigo Vale", "Kai Halvorsen")
    assert verifier.verify(red, "Rodrigo Vale is shown a straight red card for a foul on Kai Halvorsen and is sent off.").is_valid
    assert not verifier.verify(red, "Rodrigo Vale is warned about a foul on Kai Halvorsen.").is_valid


def test_dataset_events_produce_valid_local_narratives(events):
    from backend.agents.orchestrator import MatchIntelligenceOrchestrator

    orchestrator = MatchIntelligenceOrchestrator()
    tactician = TacticianAgent()
    for event in [e for e in events if e["event_type"] in {"substitution", "card"}][:6]:
        facts = tactician.extract_facts(event)
        assert facts.passer_name == event["player_name"]
        insight = orchestrator.process_event(event)
        assert insight.verification_status == "VERIFIED", (event["event_type"], insight.casual_story)
        assert set(insight.translations) == {"en", "es"}


def test_token_budget_limits_the_rolling_minute():
    budget = TokenBudget(1_000)
    first = budget.acquire(600, max_wait=0.0)
    assert first is not None
    assert budget.acquire(600, max_wait=0.2) is None  # no room until the minute has passed
    budget.settle(first, 100)
    assert budget.used_last_minute() == 100
    assert budget.acquire(600, max_wait=0.0) is not None


def test_token_budget_never_blocks_forever_when_idle():
    budget = TokenBudget(1_000)
    started = time.time()
    assert budget.acquire(5_000, max_wait=1.0) is not None  # larger than the quota, but nothing else is running
    assert time.time() - started < 0.5


# ---- Full time and the player radar -------------------------------------------------

def test_match_stops_at_full_time_and_play_restarts_it():
    import backend.app as app_module
    from fastapi.testclient import TestClient

    with TestClient(app_module.app) as client:
        client.post("/api/control", json={"action": "pause"})
        client.post("/api/control", json={"action": "simulate_full"})
        assert app_module._match_is_over()
        frame_at_end = app_module.streamer.generator.frame_index
        assert frame_at_end == 5670 * 25

        response = client.post("/api/control", json={"action": "play"})
        assert response.json()["restarted"] is True
        assert app_module.streamer.generator.frame_index < 100  # a fresh kick-off, not minute 95
        assert not app_module._match_is_over()
        assert client.get("/api/analytics").json()["match_stats"]["score"] == {"home": 0, "away": 0}
        client.post("/api/control", json={"action": "pause"})


def test_no_event_or_cache_entry_exists_after_full_time(events):
    assert max(e["frame_index"] for e in events) <= 5670 * 25
    assert all(e["clock"] <= "94:30" for e in events)


def test_radar_axes_differ_between_players():
    from backend.math_engine import RADAR_AXES, compute_radar_profiles

    with open(os.path.join(os.path.dirname(__file__), "..", "data", "synthetic_match_snapshot.json"), "r", encoding="utf-8") as handle:
        stats = json.load(handle)["player_stats"]
    profiles = compute_radar_profiles(stats)
    assert len(profiles) == len(stats)
    for axis_index, axis in enumerate(RADAR_AXES):
        values = {round(profile[axis_index]["value"]) for profile in profiles.values()}
        # Only a few players shoot in a match, so shooting has fewer distinct levels than the other axes.
        assert len(values) >= (3 if axis == "shooting" else 8), f"{axis} barely varies across players: {sorted(values)}"
    shapes = {tuple(round(a["value"]) for a in profile) for profile in profiles.values()}
    assert len(shapes) == len(profiles)
    by_name = {s["name"]: profiles[s["player_id"]] for s in stats}
    hagen = {a["key"]: a["value"] for a in by_name["Anders Hagen"]}
    roark = {a["key"]: a["value"] for a in by_name["Daniel Roark"]}
    assert hagen["shooting"] > 80 > roark["shooting"]
