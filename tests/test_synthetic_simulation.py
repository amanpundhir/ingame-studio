"""Checks that generated tracking and generated events share one simulation."""

import json

from generator.match_generator import MatchGenerator


def _run_prefix(seed, frame_count=2500):
    generator = MatchGenerator(match_id="SYNTHETIC_TEST", frame_rate=25, seed=seed)
    active_events = {}
    for _ in range(frame_count):
        frame = generator.step()
        if frame.get("active_event_id"):
            active_events[frame["active_event_id"]] = frame
    return generator, active_events


def test_seeded_simulation_is_reproducible():
    first, _ = _run_prefix(seed=1729, frame_count=500)
    second, _ = _run_prefix(seed=1729, frame_count=500)
    assert first.get_events() == second.get_events()
    assert first.frame_index == second.frame_index
    assert first.ball.to_dict() == second.ball.to_dict()
    assert [player.to_dict() for player in first.players.values()] == [
        player.to_dict() for player in second.players.values()
    ]


def test_events_are_emitted_on_their_authoritative_tracking_frames():
    generator, active_frames = _run_prefix(seed=2026)
    events = generator.get_events()
    assert events, "Seeded simulation should produce match events"

    events_by_id = {event["event_id"]: event for event in events}
    assert len(events_by_id) == len(events)
    assert set(events_by_id) <= set(active_frames)

    for event_id, event in events_by_id.items():
        frame = active_frames[event_id]
        assert frame["frame_id"] == event["frame_index"]
        assert frame["clock"] == event["clock"]
        assert event["data_provenance"] == "synthetic_simulation"
        player_ids = {player["player_id"] for player in frame["players"]}
        assert event["player_id"] in player_ids
        if event.get("secondary_player_id"):
            assert event["secondary_player_id"] in player_ids

        # Event location is tied to the ball state observed at that exact frame.
        ball = frame["ball"]
        assert abs(event["location_x"] - ball["x"]) <= 1.0
        assert abs(event["location_y"] - ball["y"]) <= 1.0


def test_generated_event_payloads_are_json_serializable():
    generator, _ = _run_prefix(seed=31415, frame_count=1000)
    json.dumps(generator.get_events(), allow_nan=False)
