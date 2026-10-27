"""Uploads the narrative cache (data/narrative_cache.json) to Azure Cosmos DB.

Run once after pre-generation so every instance of the app starts with the same answers:

    python scripts/sync_cache_to_cosmos.py

Needs COSMOS_ENDPOINT and COSMOS_KEY in the environment or in .env. Answers already in
Cosmos DB are left alone, so the script can be run again safely.
"""

import os
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, ROOT)

import backend.config  # noqa: E402,F401  (loads .env)
import backend.agents  # noqa: E402,F401  (import order: avoids a circular import)
from backend.cosmos_store import CosmosStore  # noqa: E402
from backend.narrative_cache import NarrativeCache  # noqa: E402


def main() -> int:
    store = CosmosStore()
    if not store.configured:
        print("COSMOS_ENDPOINT and COSMOS_KEY are not set (or INGAME_COSMOS=off).")
        return 1
    cache = NarrativeCache(cosmos=CosmosStore(endpoint="", key=""))  # local file only
    local = cache.stats()["entries"]
    remote_before = len(store.load_all())
    print(f"{local} answers in the local cache; {remote_before} already in Cosmos DB")
    written = 0
    remote_keys = set(store.load_all())
    for key, entry in list(cache._entries.items()):
        if key in remote_keys:
            continue
        if store.upsert(key, entry):
            written += 1
            if written % 200 == 0:
                print(f"  uploaded {written}")
    print(f"Uploaded {written} answers; Cosmos DB now holds {len(store.load_all())}")
    if store.last_error:
        print(f"Last error: {store.last_error}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
