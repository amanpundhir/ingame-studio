"""Generate a reproducible full-match event dataset from the match simulator.

Unlike the former hand-authored fixture, this script records events emitted by
the same seeded simulation that produces the 25 Hz tracking frames.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from typing import Any

# Support invocation as `python scripts/generate_90min_dataset.py` from any
# working directory without requiring an editable package installation.
REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

from generator.match_generator import MatchGenerator
from backend.math_engine import MatchAnalyticsTracker


DEFAULT_SEED = 2036
FULL_MATCH_SECONDS = 94 * 60 + 30
DEFAULT_FRAME_RATE = 25
MATCH_ID = "IGS_2026_NBL_HSC"


def build_events(
    seed: int = DEFAULT_SEED,
    duration_seconds: int = FULL_MATCH_SECONDS,
    frame_rate: int = DEFAULT_FRAME_RATE,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Run one full simulation and return its events plus analytics snapshot."""
    generator = MatchGenerator(
        match_id=MATCH_ID,
        frame_rate=frame_rate,
        seed=seed,
    )
    tracker = MatchAnalyticsTracker()
    last_frame: dict[str, Any] | None = None
    frame_count = int(duration_seconds * frame_rate)
    for _ in range(frame_count):
        last_frame = generator.step()
        tracker.add_telemetry_frame(last_frame)
        event_id = last_frame.get("active_event_id")
        if event_id:
            event = next((item for item in reversed(generator.events) if item.get("event_id") == event_id), None)
            if event:
                tracker.record_event(event)

    events = generator.get_events()
    for event in events:
        event.setdefault("data_provenance", "synthetic_simulation")
    final_frame = last_frame or generator.get_kickoff_frame()
    final_frame = dict(final_frame)
    final_frame["period"] = 2
    final_frame["clock"] = f"{duration_seconds // 60:02d}:{duration_seconds % 60:02d}"
    final_frame["ball"] = dict(final_frame.get("ball") or {})
    final_frame["ball"]["status"] = "stopped"
    snapshot = {
        "match_id": MATCH_ID,
        "simulation_seed": int(seed),
        "data_provenance": "synthetic_simulation",
        "final_frame": final_frame,
        "match_stats": tracker.get_match_stats(),
        "player_stats": tracker.get_all_player_stats(),
    }
    return events, snapshot


def build_metadata(seed: int, duration_seconds: int, frame_rate: int) -> dict[str, Any]:
    """Describe provenance and simulation settings for the generated fixture."""
    return {
        "match_id": MATCH_ID,
        "data_provenance": "synthetic_simulation",
        "synthetic_data_notice": (
            "Fictional, rule-based simulation. It is not a real match or tracking feed; "
            "club and player labels are illustrative."
        ),
        "simulation_seed": int(seed),
        "simulation_version": 1,
        "frame_rate_hz": int(frame_rate),
        "duration_seconds": int(duration_seconds),
        "duration_clock": f"{duration_seconds // 60:02d}:{duration_seconds % 60:02d}",
        "pitch_dimensions_m": {"length": 105.0, "width": 68.0},
        "periods": [
            {"period": 1, "start_seconds": 0, "end_seconds": 2700},
            {"period": 2, "start_seconds": 2700, "end_seconds": int(duration_seconds)},
        ],
        "teams": [
            {"team_id": "home", "display_name": "Northbridge Lions", "player_count": 11},
            {"team_id": "away", "display_name": "Harbourside City", "player_count": 11},
        ],
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--seed", type=int, default=DEFAULT_SEED)
    parser.add_argument("--duration-seconds", type=int, default=FULL_MATCH_SECONDS)
    parser.add_argument("--frame-rate", type=int, default=DEFAULT_FRAME_RATE)
    parser.add_argument("--output", default=None)
    parser.add_argument("--metadata-output", default=None)
    args = parser.parse_args()

    output_path = args.output or os.path.join(REPO_ROOT, "data", "synthetic_events.json")
    metadata_path = args.metadata_output or os.path.join(REPO_ROOT, "data", "synthetic_match_metadata.json")
    os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)

    events, snapshot = build_events(args.seed, args.duration_seconds, args.frame_rate)
    with open(output_path, "w", encoding="utf-8") as output_file:
        json.dump(events, output_file, indent=2, ensure_ascii=False)
        output_file.write("\n")

    with open(metadata_path, "w", encoding="utf-8") as metadata_file:
        json.dump(build_metadata(args.seed, args.duration_seconds, args.frame_rate), metadata_file, indent=2)
        metadata_file.write("\n")

    snapshot_path = os.path.join(REPO_ROOT, "data", "synthetic_match_snapshot.json")
    with open(snapshot_path, "w", encoding="utf-8") as snapshot_file:
        json.dump(snapshot, snapshot_file, indent=2, ensure_ascii=False)
        snapshot_file.write("\n")

    print(
        f"Generated {len(events)} simulator-derived events with seed {args.seed} "
        f"over {args.duration_seconds}s at {args.frame_rate}Hz: {output_path}; "
        f"metadata: {metadata_path}; snapshot: {snapshot_path}"
    )


if __name__ == "__main__":
    main()
