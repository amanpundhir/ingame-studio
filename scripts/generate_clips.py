"""Records the replay clips (10 s before and after each key moment) for the default match.

Usage (from the repository root):
    python scripts/generate_clips.py

Writes data/match_clips.json. Run it again whenever the seed or the simulator changes.
"""

import argparse
import json
import os
import sys
import time

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, ROOT)

from backend.clips import ClipStore, record_clips, select_clip_events  # noqa: E402
from scripts.generate_90min_dataset import DEFAULT_SEED, MATCH_ID  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--seed", type=int, default=DEFAULT_SEED)
    parser.add_argument("--events", default=os.path.join(ROOT, "data", "synthetic_events.json"))
    args = parser.parse_args()

    with open(args.events, "r", encoding="utf-8") as handle:
        events = json.load(handle)
    wanted = select_clip_events(events)
    print(f"Recording {len(wanted)} clips (the whole match is simulated once)...")
    started = time.time()
    clips = record_clips(args.seed, events, wanted, MATCH_ID)
    store = ClipStore()
    store._clips = {}
    store.put_many(clips)
    store.save(args.seed)
    size = os.path.getsize(store.path) / 1_000_000
    print(f"Saved {len(clips)} clips ({size:.1f} MB) to {store.path} in {time.time() - started:.0f}s")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
