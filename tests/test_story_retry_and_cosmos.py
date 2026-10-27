"""Match stories use the same verify-and-retry idea as event narratives, and the narrative
cache writes through to Azure Cosmos DB (tested against a fake container, no network)."""

import os
import tempfile

from backend import story
from backend.cosmos_store import CosmosStore
from backend.narrative_cache import NarrativeCache

FACTS = "Fixture: Northbridge Lions 3-1 Harbourside City\nPossession %: 52.4 vs 47.6"


class FakeAdapter:
    deployment = "test-deployment"

    def __init__(self, answers):
        self.answers = list(answers)
        self.prompts = []

    def complete(self, system, user, max_tokens=0):
        self.prompts.append(user)
        return self.answers.pop(0) if self.answers else None


class FakeService:
    enabled = True

    def __init__(self, adapter, cache):
        self.adapter, self.cache = adapter, cache
        self.live_calls = 0
        self.live_failures = 0


def _service(answers):
    cache = NarrativeCache(path=os.path.join(tempfile.mkdtemp(), "cache.json"), cosmos=CosmosStore(endpoint="", key=""))
    return FakeService(FakeAdapter(answers), cache)


def test_story_with_an_invented_number_is_retried_with_a_critique():
    service = _service(["Northbridge won 3-1 with 88.8 percent of the ball.", "Northbridge won 3-1 with 52.4 percent of the ball."])
    result = story._complete_cached(service, "k1", "system", FACTS, FACTS, 100)

    assert result["source"] == "azure_foundry_live"
    assert "52.4" in result["text"]
    assert len(service.adapter.prompts) == 2
    assert "REVIEWER CRITIQUE" in service.adapter.prompts[1] and "88.8" in service.adapter.prompts[1]
    assert service.cache.get("k1") == result["text"]
    assert service.live_failures == 0


def test_story_that_never_passes_is_not_cached():
    service = _service(["99.9 percent possession."] * 5)
    assert story._complete_cached(service, "k2", "system", FACTS, FACTS, 100) is None
    assert len(service.adapter.prompts) == story.MAX_STORY_RETRIES + 1
    assert service.cache.peek("k2") is False
    assert service.live_failures == 1


def test_model_error_is_not_retried():
    service = _service([])  # the adapter returns None
    assert story._complete_cached(service, "k3", "system", FACTS, FACTS, 100) is None
    assert len(service.adapter.prompts) == 1


class FakeContainer:
    def __init__(self):
        self.items = {}
        self.fail = False

    def upsert_item(self, item):
        if self.fail:
            raise RuntimeError("cosmos is down")
        self.items[item["id"]] = item

    def query_items(self, query, enable_cross_partition_query=False):
        if self.fail:
            raise RuntimeError("cosmos is down")
        return list(self.items.values())

    def delete_item(self, key, partition_key=None):
        self.items.pop(key)


def _cosmos(container):
    store = CosmosStore(endpoint="https://example.invalid", key="not-a-real-key")
    store._container = container
    return store


def test_cache_writes_through_to_cosmos_and_a_new_instance_loads_it(monkeypatch):
    monkeypatch.delenv("INGAME_COSMOS", raising=False)
    container = FakeContainer()
    first = NarrativeCache(path=os.path.join(tempfile.mkdtemp(), "a.json"), cosmos=_cosmos(container))
    first.put("key-1", "A verified narrative.", "azure-foundry-test")
    first.cosmos._pool.shutdown(wait=True)  # let the background write finish

    assert container.items["key-1"]["text"] == "A verified narrative."

    second = NarrativeCache(path=os.path.join(tempfile.mkdtemp(), "b.json"), cosmos=_cosmos(container))
    assert second.get("key-1") == "A verified narrative."
    assert second.stats()["store"] == "cosmos+file"


def test_cosmos_failure_never_breaks_the_cache(monkeypatch):
    monkeypatch.delenv("INGAME_COSMOS", raising=False)
    container = FakeContainer()
    container.fail = True
    cache = NarrativeCache(path=os.path.join(tempfile.mkdtemp(), "c.json"), cosmos=_cosmos(container))
    cache.put("key-2", "Still cached locally.", "azure-foundry-test")
    cache.cosmos._pool.shutdown(wait=True)

    assert cache.get("key-2") == "Still cached locally."
    assert cache.cosmos.write_errors == 1


def test_cosmos_is_off_without_credentials_or_when_switched_off(monkeypatch):
    assert CosmosStore(endpoint="", key="").configured is False
    monkeypatch.setenv("INGAME_COSMOS", "off")
    assert CosmosStore(endpoint="https://x.invalid", key="k").configured is False
