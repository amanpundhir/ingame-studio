"""Key moments, replay clips (10 s before and after) and the highlight reel's data."""

import json
import os

import pytest
from fastapi.testclient import TestClient

from backend.clips import ClipStore, select_clip_events
from backend.match_recap import _turning_points
from backend.moments import build_highlights, build_tactical_moments, select_tactical_events

DATA = os.path.join(os.path.dirname(__file__), "..", "data")


@pytest.fixture(scope="module")
def events():
    with open(os.path.join(DATA, "synthetic_events.json"), "r", encoding="utf-8") as handle:
        return json.load(handle)


@pytest.fixture(scope="module")
def store():
    return ClipStore()


def test_tactical_moments_are_the_recap_turning_points(events):
    ordered = sorted(events, key=lambda e: (e.get("period", 1), e.get("frame_index", 0)))
    turning = {p["event_id"] for p in _turning_points(ordered, {"home": "Northbridge Lions", "away": "Harbourside City"}, limit=6)}
    picked = {ev["event_id"] for _slug, _label, ev in select_tactical_events(events)}
    assert picked == turning
    goals = {e["event_id"] for e in events if e["event_type"] == "goal"}
    reds = {e["event_id"] for e in events if e["event_type"] == "card" and e["outcome"] == "red"}
    assert (goals | reds) <= picked


def test_red_card_moment_analyses_the_carded_team_defending(events):
    moments = build_tactical_moments(events)
    red = next(m for m in moments if m["event_type"] == "card")
    event = next(e for e in events if e["event_id"] == red["event_id"])
    assert red["defending_team"] == event["team"]
    assert len(red["frame"]["players"]) == 22  # the player is still on the pitch at the moment of the card


def test_every_key_moment_and_highlight_has_a_stored_clip(events, store):
    seed = 2036
    for _slug, _label, ev in select_tactical_events(events):
        assert store.get(ev["event_id"], seed) is not None, ev["event_id"]
    for highlight in build_highlights(events):
        assert store.get(highlight["event_id"], seed) is not None, highlight["event_id"]


def test_clip_covers_ten_seconds_each_side_and_matches_the_event(events, store):
    goal = next(e for e in events if e["event_type"] == "goal")
    clip = store.get(goal["event_id"], 2036)
    times = [f["t"] for f in clip["frames"]]
    assert times[0] == pytest.approx(-10.0, abs=0.1) and times[-1] == pytest.approx(10.0, abs=0.1)
    assert clip["fps"] == 12.5 and len(times) >= 240
    assert all(len(f["p"]) == len(clip["roster"]) for f in clip["frames"])
    at_event = min(clip["frames"], key=lambda f: abs(f["t"]))
    ball_x, ball_y, _ = at_event["ball"]
    assert abs(ball_x - goal["location_x"]) < 3.0 and abs(ball_y - goal["location_y"]) < 3.0
    assert any(e["id"] == goal["event_id"] and e["t"] == 0.0 for e in clip["events"])
    assert clip["score_after"][0] + clip["score_after"][1] == clip["score_before"][0] + clip["score_before"][1] + 1


def test_second_half_clip_has_teams_on_the_swapped_ends(events, store):
    second_half_goal = next(e for e in events if e["event_type"] == "goal" and e["period"] == 2)
    clip = store.get(second_half_goal["event_id"], 2036)
    frame = min(clip["frames"], key=lambda f: abs(f["t"]))
    keepers = {r["team"]: frame["p"][i] for i, r in enumerate(clip["roster"]) if r["role"] == "GK"}
    home_attacks_left = second_half_goal["team"] == "Northbridge Lions"
    assert home_attacks_left and second_half_goal["end_x"] == 0.0
    assert keepers["away"][0] < 25  # City keeper is in the left-hand goal area, being attacked


def test_clip_endpoint_serves_stored_clips_and_rejects_unknown_events(events):
    from backend.app import app

    client = TestClient(app)
    goal = next(e for e in events if e["event_type"] == "goal")
    response = client.get(f"/api/clips/{goal['event_id']}")
    assert response.status_code == 200
    body = response.json()
    assert body["event_id"] == goal["event_id"] and body["frames"] and body["roster"]
    assert client.get("/api/clips/NOT_AN_EVENT").status_code in (202, 404)


def test_clip_event_selection_includes_goals_cards_and_shots(events):
    ids = {str(e["event_id"]) for e in select_clip_events(events)}
    for e in events:
        if e["event_type"] in ("goal", "shot") or (e["event_type"] == "card" and e["outcome"] == "red"):
            assert str(e["event_id"]) in ids
