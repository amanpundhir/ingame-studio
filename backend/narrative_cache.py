"""InGame Studio - Narrative cache and generation service.

Model answers for a given match moment never change, so each one is generated
once and reused for every viewer:

* ``NarrativeCache`` stores verified model narratives in memory and in a JSON
  file that survives restarts (and can be shipped pre-generated).
* When Azure Cosmos DB credentials are set (``backend/cosmos_store.py``) the cache also
  loads from and writes through to Cosmos DB, the shared store for many instances.
* ``NarrativeService`` fronts the Foundry adapter. It answers from the cache,
  collapses simultaneous misses into a single model call (single flight), and
  never stores a failed or fallback answer.

The cache key covers everything that changes the text: the facts, the model
deployment, and a prompt version. Bumping ``PROMPT_VERSION`` invalidates old
answers.
"""

import hashlib
import json
import logging
import os
import threading
import time
from concurrent.futures import Future, ThreadPoolExecutor
from typing import Any, Dict, Optional

from backend.agents.models import FactPack
from backend.cosmos_store import CosmosStore

logger = logging.getLogger("ingame.cache")

PROMPT_VERSION = "v3"
DEFAULT_CACHE_FILE = os.path.join(os.path.dirname(__file__), "..", "data", "narrative_cache.json")


class NarrativeCache:
    """Thread-safe in-memory cache backed by an atomically written JSON file."""

    def __init__(
        self,
        path: Optional[str] = None,
        autosave_interval: float = 2.0,
        cosmos: Optional[CosmosStore] = None,
    ):
        self.cosmos = cosmos if cosmos is not None else CosmosStore()
        self.path = os.path.abspath(path or os.environ.get("NARRATIVE_CACHE_FILE") or DEFAULT_CACHE_FILE)
        self.autosave_interval = autosave_interval
        self._lock = threading.Lock()
        self._flush_lock = threading.Lock()
        self._entries: Dict[str, Dict[str, Any]] = {}
        self._dirty = False
        self._last_save = 0.0
        self.hits = 0
        self.misses = 0
        self._load()
        self._load_from_cosmos()

    def _load(self) -> None:
        try:
            with open(self.path, "r", encoding="utf-8") as handle:
                data = json.load(handle)
            self._entries = dict(data.get("entries", {}))
        except (OSError, ValueError):
            self._entries = {}

    def _load_from_cosmos(self) -> None:
        """Adds every answer stored in Cosmos DB, so a fresh instance starts warm."""
        remote = self.cosmos.load_all()
        for key, entry in remote.items():
            self._entries.setdefault(key, entry)
        if remote:
            logger.info("Loaded %d narrative answers from Cosmos DB", len(remote))

    def sync_to_cosmos(self) -> int:
        """Uploads every local answer that Cosmos DB does not have yet. Returns how many were written."""
        remote = self.cosmos.load_all()
        written = 0
        for key, entry in list(self._entries.items()):
            if key not in remote and self.cosmos.upsert(key, entry):
                written += 1
        return written

    def get(self, key: str) -> Optional[str]:
        with self._lock:
            entry = self._entries.get(key)
            if entry:
                self.hits += 1
                return entry["text"]
            self.misses += 1
            return None

    def peek(self, key: str) -> bool:
        with self._lock:
            return key in self._entries

    def put(self, key: str, text: str, model: str) -> None:
        with self._lock:
            entry = {"text": text, "model": model, "created": int(time.time())}
            self._entries[key] = entry
            self._dirty = True
            due = time.time() - self._last_save >= self.autosave_interval
        self.cosmos.upsert_async(key, entry)
        if due:
            self.flush()

    def flush(self) -> None:
        with self._flush_lock:  # one writer at a time; avoids clashes on the temp file
            with self._lock:
                if not self._dirty:
                    return
                # Merge entries another process (e.g. the pre-generation script) wrote meanwhile.
                try:
                    with open(self.path, "r", encoding="utf-8") as handle:
                        on_disk = dict(json.load(handle).get("entries", {}))
                except (OSError, ValueError):
                    on_disk = {}
                for key, entry in on_disk.items():
                    self._entries.setdefault(key, entry)
                snapshot = {"version": 1, "prompt_version": PROMPT_VERSION, "entries": dict(self._entries)}
                self._dirty = False
                self._last_save = time.time()
            try:
                os.makedirs(os.path.dirname(self.path), exist_ok=True)
                tmp = f"{self.path}.{os.getpid()}.tmp"
                with open(tmp, "w", encoding="utf-8") as handle:
                    json.dump(snapshot, handle, ensure_ascii=False)
                for attempt in range(5):  # Windows can briefly lock the target file
                    try:
                        os.replace(tmp, self.path)
                        break
                    except PermissionError:
                        time.sleep(0.2 * (attempt + 1))
                else:
                    self._dirty = True
            except OSError as exc:
                self._dirty = True
                logger.warning(f"Could not persist narrative cache: {exc}")

    def stats(self) -> Dict[str, Any]:
        with self._lock:
            total = self.hits + self.misses
            return {
                "entries": len(self._entries),
                "hits": self.hits,
                "misses": self.misses,
                "hit_rate": round(self.hits / total, 3) if total else 0.0,
                "store": "cosmos+file" if self.cosmos.configured else "file",
                "cosmos": self.cosmos.stats(),
            }


class NarrativeService:
    """Cache-first narrative generation with single-flight model calls."""

    def __init__(self, adapter: Any, cache: Optional[NarrativeCache] = None, workers: int = 4):
        self.adapter = adapter
        self.cache = cache or NarrativeCache()
        self._inflight: Dict[str, Future] = {}
        self._inflight_lock = threading.Lock()
        self._pool = ThreadPoolExecutor(max_workers=workers, thread_name_prefix="narrative")
        self.live_calls = 0
        self.live_failures = 0

    @property
    def enabled(self) -> bool:
        return bool(self.adapter and self.adapter.is_cloud_connected())

    def key_for(self, facts: FactPack) -> str:
        parts = [
            PROMPT_VERSION, self.adapter.deployment, facts.event_id, facts.event_type,
            facts.passer_name, facts.receiver_name, facts.team_name, facts.match_minute,
            f"{facts.pass_distance_m:.1f}", f"{facts.ball_speed_kmh:.1f}", f"{facts.pass_difficulty:.1f}",
            f"{facts.xt_gained:.3f}", f"{facts.chaos_index:.1f}", facts.milestone or "",
            facts.outcome or "", facts.sub_type or "",
        ]
        return hashlib.sha256("|".join(parts).encode("utf-8")).hexdigest()[:32]

    def lookup(self, facts: FactPack) -> Optional[str]:
        return self.cache.get(self.key_for(facts)) if self.enabled else None

    def generate_live(self, facts: FactPack, critique: Optional[str] = None) -> Optional[str]:
        """Calls the model once per key even when many callers ask at the same moment."""
        if not self.enabled:
            return None
        key = self.key_for(facts) + (":c" if critique else "")
        with self._inflight_lock:
            future = self._inflight.get(key)
            owner = future is None
            if owner:
                future = Future()
                self._inflight[key] = future
        if not owner:
            try:
                return future.result(timeout=30)
            except Exception:
                return None
        try:
            self.live_calls += 1
            text = self.adapter.generate_text_for_facts(facts, critique)
            if not text:
                self.live_failures += 1
            future.set_result(text)
            return text
        except Exception as exc:  # network or service failure: caller falls back locally
            self.live_failures += 1
            logger.warning(f"Live narrative call failed: {exc}")
            future.set_result(None)
            return None
        finally:
            with self._inflight_lock:
                self._inflight.pop(key, None)

    def store_verified(self, facts: FactPack, text: str) -> None:
        """Stores a narrative only after the Verifier approved it."""
        self.cache.put(self.key_for(facts), text, f"azure-foundry-{self.adapter.deployment}")

    def warm_in_background(self, facts: FactPack, verifier: Any) -> None:
        """Generates and caches a verified narrative without blocking the 25Hz stream."""
        if not self.enabled or self.cache.peek(self.key_for(facts)):
            return

        def _job() -> None:
            text = self.generate_live(facts)
            if text and verifier.verify(facts, text).is_valid:
                self.store_verified(facts, text)

        self._pool.submit(_job)

    def status(self) -> Dict[str, Any]:
        return {
            "mode": "azure_foundry" if self.enabled else "local_fallback",
            "deployment": self.adapter.deployment if self.adapter else None,
            "prompt_version": PROMPT_VERSION,
            "live_calls": self.live_calls,
            "live_failures": self.live_failures,
            "cache": self.cache.stats(),
        }
