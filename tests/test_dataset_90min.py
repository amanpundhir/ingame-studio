"""Contract tests for the checked-in full-match synthetic event dataset.

The dataset is generated from the same seeded simulation as tracking. Tests
intentionally validate structural and football-event coverage rather than a
fixed scoreline or hand-authored sequence.
"""

import json
import os
from collections import Counter

import jsonschema
import pytest

from generator.match_generator import NORTHBRIDGE_BENCH, NORTHBRIDGE_ROSTER, AWAY_BENCH, AWAY_ROSTER


@pytest.fixture(scope="module")
def dataset_context():
    repo_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    with open(os.path.join(repo_root, "data", "schema.json"), encoding="utf-8") as f:
        schema = json.load(f)
    with open(os.path.join(repo_root, "data", "synthetic_events.json"), encoding="utf-8") as f:
        events = json.load(f)
    validator = jsonschema.Draft7Validator(schema["definitions"]["MatchEvent"])
    roster = {p["player_id"]: p for p in NORTHBRIDGE_ROSTER + AWAY_ROSTER + NORTHBRIDGE_BENCH + AWAY_BENCH}
    return {"events": events, "validator": validator, "roster": roster}


def _clock_seconds(clock):
    minute, second = map(int, clock.split(":")[:2])
    return minute * 60 + second


def test_full_match_dataset_is_synthetic_and_schema_valid(dataset_context):
    events = dataset_context["events"]
    assert isinstance(events, list)
    assert len(events) >= 100
    for index, event in enumerate(events):
        errors = list(dataset_context["validator"].iter_errors(event))
        assert not errors, f"Event {event.get('event_id', index)}: {errors[0].message if errors else ''}"
        assert event.get("data_provenance") == "synthetic_simulation"


def test_match_events_cover_full_duration_in_order(dataset_context):
    events = dataset_context["events"]
    assert events
    times = [_clock_seconds(e["clock"]) for e in events]
    assert times == sorted(times)
    assert times[0] <= 60
    assert times[-1] >= 90 * 60
    assert events[0]["period"] == 1
    assert events[-1]["period"] == 2
    assert all(e["period"] == (1 if _clock_seconds(e["clock"]) < 45 * 60 else 2) for e in events)


def test_event_types_cover_hackathon_data_requirements(dataset_context):
    event_types = {event["event_type"] for event in dataset_context["events"]}
    # Possession changes may be represented by explicit turnovers or event
    # outcomes on tackles/passes; the required event categories remain clear.
    assert {"pass", "shot", "tackle", "turnover", "pressure"} <= event_types


def test_event_frame_clock_and_player_references_are_consistent(dataset_context):
    events = dataset_context["events"]
    roster = dataset_context["roster"]
    event_ids = [event["event_id"] for event in events]
    frame_ids = [event["frame_index"] for event in events]
    assert len(event_ids) == len(set(event_ids))
    assert frame_ids == sorted(frame_ids)

    for event in events:
        # Event clocks are displayed at whole-second precision while frame
        # indices retain 25Hz resolution.
        assert abs(event["frame_index"] - _clock_seconds(event["clock"]) * 25) < 25
        player = roster[event["player_id"]]
        assert event["player_name"] == player["name"]
        secondary_id = event.get("secondary_player_id")
        if secondary_id is not None:
            assert secondary_id in roster
            assert event.get("secondary_player_name") == roster[secondary_id]["name"]
        if event["event_type"] in {"pass", "shot", "goal"}:
            assert event.get("end_x") is not None and event.get("end_y") is not None
        assert event.get("data_provenance") == "synthetic_simulation"


def test_both_sides_are_represented(dataset_context):
    events = dataset_context["events"]
    teams = Counter(event["team"] for event in events)
    assert len(teams) == 2
    assert all(count > 0 for count in teams.values())


def test_match_metadata_declares_synthetic_source_and_match_bounds():
    repo_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    metadata_path = os.path.join(repo_root, "data", "synthetic_match_metadata.json")
    with open(metadata_path, encoding="utf-8") as source:
        metadata = json.load(source)

    assert metadata["data_provenance"] == "synthetic_simulation"
    assert metadata["pitch_dimensions_m"] == {"length": 105.0, "width": 68.0}
    assert metadata["duration_seconds"] >= 90 * 60
    assert metadata["duration_clock"] == "94:30"
    assert len(metadata["periods"]) == 2
    assert metadata["simulation_seed"] is not None
    assert len(metadata["teams"]) == 2


def test_full_match_snapshot_is_derived_from_same_seeded_simulation(dataset_context):
    repo_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    snapshot_path = os.path.join(repo_root, "data", "synthetic_match_snapshot.json")
    with open(snapshot_path, encoding="utf-8") as source:
        snapshot = json.load(source)

    assert snapshot["data_provenance"] == "synthetic_simulation"
    assert snapshot["match_id"] == dataset_context["events"][0]["match_id"]
    assert snapshot["simulation_seed"] == 2036
    assert snapshot["final_frame"]["frame_id"] == 141750
    assert snapshot["final_frame"]["clock"] == "94:30"
    reds = sum(1 for e in dataset_context["events"] if e["event_type"] == "card" and e["outcome"] == "red")
    assert len(snapshot["final_frame"]["players"]) == 22 - reds
    assert len(snapshot["player_stats"]) >= 22
    assert snapshot["match_stats"]["score"]["home"] == sum(
        event["event_type"] == "goal" and event["team"] == "Northbridge Lions"
        for event in dataset_context["events"]
    )
