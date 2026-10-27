"""Pre-generates Azure Foundry narratives for every event in the synthetic match.

Each narrative is verified against its FactPack before it is cached, so the live
app serves model-written commentary from the cache with no model call at all.

Usage (from the repository root):
    python scripts/pregenerate_narratives.py             # whole default match
    python scripts/pregenerate_narratives.py --limit 10  # quick trial
"""

import argparse
import json
import os
import sys
import time
from concurrent.futures import ThreadPoolExecutor

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, ROOT)

import backend.config  # noqa: E402,F401  (loads .env)
from backend.agents.foundry_adapter import DEFAULT_TPM_USAGE, AzureFoundryAdapter, get_token_budget  # noqa: E402
from backend.agents.tactician_agent import TacticianAgent  # noqa: E402
from backend.agents.verifier_agent import VerifierAgent  # noqa: E402
from backend.math_engine import MatchAnalyticsTracker  # noqa: E402
from backend.narrative_cache import NarrativeCache, NarrativeService  # noqa: E402


def build_fact_packs(events_path: str, limit: int):
    with open(events_path, "r", encoding="utf-8") as handle:
        events = json.load(handle)
    tracker = MatchAnalyticsTracker()
    tactician = TacticianAgent()
    facts = []
    for event in events[: limit or None]:
        milestone = tracker.record_event(event)
        if milestone:
            event = dict(event, milestone=milestone)
        facts.append(tactician.extract_facts(event))
    return facts


def warm_stories_and_moments(service, events_path: str) -> None:
    """Pre-writes the match stories and tactical breakdowns in English and Spanish."""
    from backend import moments as moments_lib
    from backend import story as story_lib
    from backend.match_recap import generate_match_recap

    with open(events_path, "r", encoding="utf-8") as handle:
        events = json.load(handle)
    snapshot_path = os.path.join(ROOT, "data", "synthetic_match_snapshot.json")
    tracker = MatchAnalyticsTracker()
    with open(snapshot_path, "r", encoding="utf-8") as handle:
        snapshot = json.load(handle)
    tracker.load_snapshot(events=events, match_stats=snapshot.get("match_stats", {}), player_stats=snapshot.get("player_stats", []))
    recap = generate_match_recap(tracker, events=events)
    recap["status"] = "FT"
    recap["clock"] = snapshot.get("final_frame", {}).get("clock", "94:30")

    languages = list(story_lib.LANGUAGE_NAMES)
    jobs = [(persona, lang, club) for lang in languages for persona in ("tactical", "casual", "fantasy") for club in ("Northbridge Lions",)]
    jobs += [("club", lang, club) for lang in languages for club in ("Northbridge Lions", "Harbourside City")]
    for persona, lang, club in jobs:
        result = story_lib.generate_story(recap, persona, lang, club, service)
        print(f"  story {persona:8s} {lang} {club:16s} -> {result['source']}")
    for lang in languages:
        moments = moments_lib.build_tactical_moments(
            events, explain=lambda moment, ev, lang=lang: story_lib.analyse_moment(moment, ev, service, lang)
        )
        print(f"  moments {lang}: {len(moments)} -> {[m['breakdown']['source'] for m in moments]}")
    service.cache.flush()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--events", default=os.path.join(ROOT, "data", "synthetic_events.json"))
    parser.add_argument("--limit", type=int, default=0)
    parser.add_argument("--workers", type=int, default=4)
    parser.add_argument("--tpm", type=int, default=0, help="Quota in tokens per minute (default 150000)")
    parser.add_argument("--skip-stories", action="store_true", help="Only generate per-event narratives")
    args = parser.parse_args()

    adapter = AzureFoundryAdapter()
    if not adapter.is_cloud_connected():
        print("Azure credentials not found. Fill in .env first.")
        return 1
    if args.tpm:
        os.environ["AZURE_OPENAI_TPM_LIMIT"] = str(args.tpm)
    # Bulk job: wait for room in the token budget instead of skipping calls.
    adapter.budget_wait_seconds = 1800.0
    budget = get_token_budget(adapter.deployment)
    print(f"Token budget: {budget.tokens_per_minute:,} tokens per minute "
          f"({int(float(os.environ.get('AZURE_OPENAI_TPM_USAGE', DEFAULT_TPM_USAGE)) * 100)}% of the quota)")
    service = NarrativeService(adapter, NarrativeCache())
    verifier = VerifierAgent()
    if not args.skip_stories and not args.limit:
        # Stories and tactical breakdowns first: the Recap and Tactics tabs depend on them.
        warm_stories_and_moments(service, args.events)
        print(f"Stories and moments ready; cache now has {service.cache.stats()['entries']} entries")
    facts_list = build_fact_packs(args.events, args.limit)
    todo = [f for f in facts_list if not service.cache.peek(service.key_for(f))]
    # The model quota is limited, so write the moments viewers care about first.
    priority = {"goal": 0, "card": 1, "shot": 2, "substitution": 3, "foul": 4, "tackle": 5, "pressure": 6, "turnover": 7}
    todo.sort(key=lambda f: (priority.get(f.event_type, 8), -abs(f.xt_gained)))
    print(f"{len(facts_list)} events, {len(facts_list) - len(todo)} already cached, {len(todo)} to generate")

    stats = {"stored": 0, "rejected": 0, "failed": 0}

    def work(facts):
        critique = None
        for _ in range(3):
            text = service.generate_live(facts, critique)
            if not text:
                stats["failed"] += 1
                return
            result = verifier.verify(facts, text)
            if result.is_valid:
                service.store_verified(facts, text)
                stats["stored"] += 1
                return
            critique = result.critique
        stats["rejected"] += 1  # never cached: the live app uses the local template

    started = time.time()
    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        for index, _ in enumerate(pool.map(work, todo), 1):
            if index % 100 == 0:
                print(f"  {index}/{len(todo)}  {stats}  tokens last minute: {budget.used_last_minute():,}", flush=True)
    service.cache.flush()
    print(f"Done in {time.time() - started:.0f}s: {stats}; cache now has {service.cache.stats()['entries']} entries")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
