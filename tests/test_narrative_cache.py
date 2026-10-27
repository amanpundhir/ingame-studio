"""Tests for the narrative cache, single-flight generation, story grounding and derived moments."""

import json
import os
import threading
import time

import pytest

from backend.agents.models import FactPack
from backend.agents.orchestrator import MatchIntelligenceOrchestrator
from backend.agents.verifier_agent import VerifierAgent
from backend.moments import build_highlights, build_tactical_moments
from backend.narrative_cache import NarrativeCache, NarrativeService
from backend.story import analyse_moment, generate_story, numbers_are_grounded

EVENTS_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "synthetic_events.json")


class FakeAdapter:
    """Stands in for AzureFoundryAdapter; counts calls and can fail on demand."""

    deployment = "fake-deployment"

    def __init__(self, text=None, delay=0.0):
        self.text = text
        self.delay = delay
        self.calls = 0

    def is_cloud_connected(self):
        return True

    def generate_text_for_facts(self, facts, critique=None):
        self.calls += 1
        time.sleep(self.delay)
        return self.text

    def complete(self, system, user, max_tokens=200):
        self.calls += 1
        time.sleep(self.delay)
        return self.text


@pytest.fixture
def facts():
    return FactPack(
        event_id="EVT_1", match_minute="12:34", event_type="pass", passer_name="Declan Rowe",
        receiver_name="Kofi Sarpong", team_name="Northbridge Lions", opponent_name="Harbourside City",
        pass_distance_m=24.5, pass_difficulty=68.5, ball_speed_kmh=42.0, chaos_index=40.0, xt_gained=0.12,
    )


GOOD_TEXT = "Declan Rowe finds Kofi Sarpong over 24.5m at 42.0 km/h with a 68.5% difficulty rating."


def make_service(tmp_path, adapter):
    return NarrativeService(adapter, NarrativeCache(str(tmp_path / "cache.json")))


def test_cache_persists_across_restarts(tmp_path):
    path = str(tmp_path / "cache.json")
    cache = NarrativeCache(path)
    cache.put("k", "hello", "model")
    cache.flush()
    assert NarrativeCache(path).get("k") == "hello"


def test_key_changes_with_facts_and_deployment(tmp_path, facts):
    service = make_service(tmp_path, FakeAdapter())
    other = facts.model_copy(update={"pass_distance_m": 30.0})
    assert service.key_for(facts) != service.key_for(other)
    changed_model = make_service(tmp_path, FakeAdapter())
    changed_model.adapter.deployment = "another-model"
    assert service.key_for(facts) != changed_model.key_for(facts)


def test_simultaneous_requests_make_one_model_call(tmp_path, facts):
    adapter = FakeAdapter(text=GOOD_TEXT, delay=0.3)
    service = make_service(tmp_path, adapter)
    results = []
    threads = [threading.Thread(target=lambda: results.append(service.generate_live(facts))) for _ in range(8)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    assert adapter.calls == 1
    assert results == [GOOD_TEXT] * 8


def test_failed_generation_is_not_cached(tmp_path, facts):
    service = make_service(tmp_path, FakeAdapter(text=None))
    assert service.generate_live(facts) is None
    assert service.lookup(facts) is None


def test_orchestrator_caches_only_verified_text_and_then_serves_it(tmp_path, facts):
    adapter = FakeAdapter(text=GOOD_TEXT)
    service = make_service(tmp_path, adapter)
    orchestrator = MatchIntelligenceOrchestrator(narrative_service=service)

    first = orchestrator.process_fact_pack(facts, allow_live=True)
    assert first.narrative_source == "azure_foundry_live"
    assert adapter.calls == 1

    second = orchestrator.process_fact_pack(facts, allow_live=False)
    assert second.narrative_source == "azure_foundry_cache"
    assert adapter.calls == 1  # served from cache, no new model call


def test_ungrounded_model_text_is_rejected_and_not_cached(tmp_path, facts):
    adapter = FakeAdapter(text="Declan Rowe scored a stunning goal for Northbridge Lions.")
    service = make_service(tmp_path, adapter)
    orchestrator = MatchIntelligenceOrchestrator(narrative_service=service)
    insight = orchestrator.process_fact_pack(facts, allow_live=True)
    assert insight.verification_status in {"VERIFIED", "FALLBACK_APPLIED"}
    assert insight.narrative_source in {"fallback_template", "local_template"}
    assert service.lookup(facts) is None


def test_live_stream_never_waits_for_the_model(tmp_path, facts):
    adapter = FakeAdapter(text=GOOD_TEXT, delay=0.5)
    service = make_service(tmp_path, adapter)
    orchestrator = MatchIntelligenceOrchestrator(narrative_service=service)
    started = time.time()
    insight = orchestrator.process_fact_pack(facts, allow_live=False)
    assert time.time() - started < 0.4
    assert insight.narrative_source == "local_template"


def test_number_grounding_check():
    facts = "Score 1-2. Expected goals 1.07, 1.51. Possession 46.0 vs 54.0."
    assert numbers_are_grounded("Northbridge Lions had 46% of the ball and 1.07 xG.", facts)
    assert not numbers_are_grounded("Northbridge Lions had 80% of the ball.", facts)
    assert numbers_are_grounded("٤٦ في المئة", "Possession 46.0")  # Arabic-Indic digits are normalised


def test_story_falls_back_to_template_when_model_is_unavailable(tmp_path):
    service = make_service(tmp_path, FakeAdapter(text=None))
    recap = {
        "final_score": {"home": 1, "away": 2, "home_team": "Northbridge Lions", "away_team": "Harbourside City"},
        "xg_balance": {"home_xg": 1.0, "away_xg": 2.0, "home_shots": 5, "away_shots": 9},
        "team_totals": {}, "turning_points": [], "man_of_the_match": {}, "tactical_entropy": {},
        "localized_summaries": {"es": "Final: Northbridge Lions 1-2 Harbourside City."}, "match_story": "Full-time report.",
    }
    result = generate_story(recap, "casual", "es", "Northbridge Lions", service)
    assert result["source"] == "local_template"
    assert result["text"].startswith("Final")


@pytest.fixture(scope="module")
def events():
    with open(EVENTS_PATH, "r", encoding="utf-8") as handle:
        return json.load(handle)


def test_highlights_come_from_real_events_with_the_players_on_the_pitch(events):
    highlights = build_highlights(events)
    assert highlights
    event_ids = {e["event_id"] for e in events}
    for highlight in highlights:
        assert highlight["event_id"] in event_ids
        assert 19 <= len(highlight["players"]) <= 22  # fewer than 22 only after a sending-off
    goals = [e for e in events if e["event_type"] == "goal"]
    assert {h["event_id"] for h in highlights if h["type"] == "goal"} == {g["event_id"] for g in goals}


def test_tactical_moments_have_computed_geometry(events):
    moments = build_tactical_moments(events)
    assert 1 <= len(moments) <= 6
    for moment in moments:
        assert 19 <= len(moment["frame"]["players"]) <= 22
        assert 0 < moment["defensive_line_depth_m"] <= 105
        assert moment["compactness_m2"] >= 0
        assert moment["passing_lanes"]


def test_moment_analysis_uses_model_text_when_grounded(tmp_path, events):
    moment = build_tactical_moments(events)[0]
    event = next(e for e in events if e["event_id"] == moment["event_id"])
    sheet_text = (
        f"The defensive line sat {moment['defensive_line_depth_m']} m from goal with the offside line at "
        f"x = {moment['offside_line_x']} m."
    )
    service = make_service(tmp_path, FakeAdapter(text=sheet_text))
    result = analyse_moment(moment, event, service, "en")
    assert result["breakdown"]["source"] == "azure_foundry"
    assert result["analysis"] == sheet_text
    assert set(result["breakdown"]["persona_notes"]) == {"tactical", "casual", "club", "fantasy"}
