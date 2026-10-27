"""Removes cached model answers that do not belong to the current match.

The cache can collect stray answers: for example from an earlier seed or prompt
version, or from a live run that went past full time. This script works out which
cache keys the current match needs (every event narrative, the match stories and the
tactical moment analyses, in both languages) and deletes all the others.

Usage (from the repository root):
    python scripts/prune_cache.py            # report what would be removed
    python scripts/prune_cache.py --apply    # remove it
"""

import argparse
import json
import os
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, ROOT)

import backend.config  # noqa: E402,F401  (loads .env)
from backend.agents.foundry_adapter import AzureFoundryAdapter  # noqa: E402
from backend.narrative_cache import NarrativeCache, NarrativeService  # noqa: E402
from scripts.pregenerate_narratives import build_fact_packs, warm_stories_and_moments  # noqa: E402


class RecordingCache(NarrativeCache):
    """Remembers every key that is looked up; never needs the model."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.requested = set()

    def get(self, key):
        self.requested.add(key)
        return super().get(key)

    def peek(self, key):
        self.requested.add(key)
        return super().peek(key)


class OfflineAdapter(AzureFoundryAdapter):
    """Reports as connected (so the cache is consulted) but never calls the model."""

    def is_cloud_connected(self):
        return True

    def complete(self, system_prompt, user_content, max_tokens=220):
        return None

    def generate_text_for_facts(self, facts, critique=None):
        return None


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--apply", action="store_true", help="Delete the stray entries")
    parser.add_argument("--events", default=os.path.join(ROOT, "data", "synthetic_events.json"))
    args = parser.parse_args()

    adapter = OfflineAdapter(endpoint="https://offline.invalid", api_key="offline-not-used")
    adapter.deployment = os.environ.get("AZURE_OPENAI_DEPLOYMENT") or adapter.deployment
    cache = RecordingCache()
    before = cache.stats()["entries"]
    service = NarrativeService(adapter, cache)

    for facts in build_fact_packs(args.events, 0):
        cache.peek(service.key_for(facts))
    warm_stories_and_moments(service, args.events)

    keep = cache.requested & set(cache._entries)
    stray = set(cache._entries) - keep
    print(f"{before} cached answers; {len(keep)} belong to the current match; {len(stray)} do not")
    if args.apply and stray:
        for key in stray:
            cache._entries.pop(key, None)
        cache._dirty = True
        # Write the pruned set exactly: do not merge back what is on disk.
        os.makedirs(os.path.dirname(cache.path), exist_ok=True)
        tmp = f"{cache.path}.prune.tmp"
        with open(tmp, "w", encoding="utf-8") as handle:
            json.dump({"version": 1, "entries": cache._entries}, handle, ensure_ascii=False)
        os.replace(tmp, cache.path)
        print(f"Removed {len(stray)}; {len(cache._entries)} entries remain")
        if cache.cosmos.configured:
            removed = sum(1 for key in stray if cache.cosmos.delete(key))
            print(f"Removed {removed} of {len(stray)} from Cosmos DB as well")
    elif stray:
        print("Run again with --apply to remove them")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
