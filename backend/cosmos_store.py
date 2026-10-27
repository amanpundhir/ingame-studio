"""InGame Studio - Azure Cosmos DB store for the narrative cache.

The narrative cache keeps answers in memory for speed and in a JSON file that ships with
the app. When ``COSMOS_ENDPOINT`` and ``COSMOS_KEY`` are set, Azure Cosmos DB for NoSQL is
used as the shared, durable store as well:

* on start-up the cache loads every stored answer from Cosmos DB, so a new instance (or a
  restarted container) is warm at once and all instances share the same answers;
* every newly verified answer is written to Cosmos DB in the background; a Cosmos error is
  logged and never slows or breaks the live stream.

One document per cached answer: ``{"id": <cache key>, "text": ..., "model": ..., "created": ...}``,
partitioned by ``/id``. Set ``INGAME_COSMOS=off`` to ignore the credentials (the tests do).
"""

import logging
import os
import threading
from concurrent.futures import ThreadPoolExecutor
from typing import Any, Dict, Optional

logger = logging.getLogger("ingame.cosmos")


class CosmosStore:
    """Thin wrapper over one Cosmos DB container. Every method is safe to call when it is unavailable."""

    def __init__(
        self,
        endpoint: Optional[str] = None,
        key: Optional[str] = None,
        database: Optional[str] = None,
        container: Optional[str] = None,
    ):
        self.endpoint = endpoint if endpoint is not None else os.environ.get("COSMOS_ENDPOINT", "")
        self.key = key if key is not None else os.environ.get("COSMOS_KEY", "")
        self.database_name = database or os.environ.get("COSMOS_DATABASE", "ingame")
        self.container_name = container or os.environ.get("COSMOS_CONTAINER", "narratives")
        self._container: Any = None
        self._lock = threading.Lock()
        self._pool: Optional[ThreadPoolExecutor] = None
        self.writes = 0
        self.write_errors = 0
        self.last_error: Optional[str] = None

    @property
    def configured(self) -> bool:
        if os.environ.get("INGAME_COSMOS", "").strip().lower() == "off":
            return False
        return bool(self.endpoint and self.key)

    def _get_container(self) -> Any:
        if self._container is not None:
            return self._container
        with self._lock:
            if self._container is None:
                from azure.cosmos import CosmosClient  # imported lazily: optional dependency

                client = CosmosClient(self.endpoint, credential=self.key)
                self._container = client.get_database_client(self.database_name).get_container_client(
                    self.container_name
                )
        return self._container

    def load_all(self) -> Dict[str, Dict[str, Any]]:
        """Returns every stored answer as ``{key: entry}``; an empty dict when unavailable."""
        if not self.configured:
            return {}
        try:
            container = self._get_container()
            entries: Dict[str, Dict[str, Any]] = {}
            for item in container.query_items(
                query="SELECT c.id, c.text, c.model, c.created FROM c", enable_cross_partition_query=True
            ):
                entries[item["id"]] = {
                    "text": item["text"], "model": item.get("model", ""), "created": item.get("created", 0),
                }
            return entries
        except Exception as exc:  # noqa: BLE001 - the cache must work without Cosmos DB
            self.last_error = str(exc)[:200]
            logger.warning("Could not read the Cosmos DB narrative store: %s", self.last_error)
            return {}

    def upsert(self, key: str, entry: Dict[str, Any]) -> bool:
        """Writes one answer synchronously. Returns False on failure."""
        if not self.configured:
            return False
        try:
            self._get_container().upsert_item(
                {"id": key, "text": entry["text"], "model": entry.get("model", ""), "created": entry.get("created", 0)}
            )
            self.writes += 1
            return True
        except Exception as exc:  # noqa: BLE001
            self.write_errors += 1
            self.last_error = str(exc)[:200]
            logger.warning("Could not write to the Cosmos DB narrative store: %s", self.last_error)
            return False

    def delete(self, key: str) -> bool:
        """Removes one answer. Returns False on failure (a missing answer counts as removed)."""
        if not self.configured:
            return False
        try:
            self._get_container().delete_item(key, partition_key=key)
            return True
        except Exception as exc:  # noqa: BLE001
            if "NotFound" in type(exc).__name__ or "404" in str(exc)[:80]:
                return True
            self.last_error = str(exc)[:200]
            return False

    def upsert_async(self, key: str, entry: Dict[str, Any]) -> None:
        """Writes one answer in the background so the caller never waits for the network."""
        if not self.configured:
            return
        if self._pool is None:
            self._pool = ThreadPoolExecutor(max_workers=2, thread_name_prefix="cosmos")
        self._pool.submit(self.upsert, key, dict(entry))

    def stats(self) -> Dict[str, Any]:
        return {
            "enabled": self.configured,
            "database": self.database_name if self.configured else None,
            "container": self.container_name if self.configured else None,
            "writes": self.writes,
            "write_errors": self.write_errors,
        }
