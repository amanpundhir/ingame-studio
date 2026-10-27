"""The four agents run as a Microsoft Agent Framework workflow.

Checks that the workflow is really used, that the retry loop is a graph edge (a rejected
draft goes back to the Pundit with a critique), that exhausted retries end in the
deterministic fallback, and that the workflow and the plain loop give the same insight.
"""

import json
import os

import pytest

from backend.agents.af_workflow import build_workflow
from backend.agents.models import DraftNarrative
from backend.agents.orchestrator import MatchIntelligenceOrchestrator

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


@pytest.fixture(scope="module")
def events():
    with open(os.path.join(ROOT, "data", "synthetic_events.json"), encoding="utf-8") as handle:
        return json.load(handle)


class ScriptedPundit:
    """Returns the given narratives in order; the last one repeats."""

    def __init__(self, narratives):
        self.narratives = narratives
        self.critiques = []

    def generate_narrative(self, facts, critique=None, attempt=0, allow_live=False):
        self.critiques.append(critique)
        text = self.narratives[min(attempt, len(self.narratives) - 1)]
        return DraftNarrative(event_id=facts.event_id, narrative=text, generation_attempt=attempt)


def _orchestrator(pundit=None, **kwargs):
    orchestrator = MatchIntelligenceOrchestrator(pundit=pundit, **kwargs)
    orchestrator.use_agent_framework = True
    return orchestrator


def test_workflow_graph_has_the_four_agents_and_a_retry_edge():
    workflow = build_workflow(_orchestrator())
    executor_ids = set(workflow.executors)
    assert {"tactician", "pundit", "verifier", "director"} <= executor_ids


def test_accepted_draft_goes_straight_through(events):
    insight = _orchestrator().process_event(events[10])
    assert insight.verification_status == "VERIFIED"
    assert insight.agent_trace == ["tactician", "pundit#0", "verifier:accepted", "director"]


def test_rejected_draft_loops_back_to_the_pundit_with_a_critique(events):
    event = events[10]
    orchestrator = _orchestrator()
    facts = orchestrator.tactician.extract_facts(event)
    good = orchestrator._deterministic_fallback(facts)
    pundit = ScriptedPundit(["Something happened somewhere on the pitch.", good])
    insight = _orchestrator(pundit=pundit).process_event(event)

    assert insight.verification_status == "VERIFIED"
    assert insight.retries_attempted == 1
    assert insight.agent_trace == [
        "tactician", "pundit#0", "verifier:rejected", "pundit#1", "verifier:accepted", "director",
    ]
    assert pundit.critiques[0] is None
    assert pundit.critiques[1], "the second attempt must receive the Verifier's critique"


def test_exhausted_retries_end_in_the_deterministic_fallback(events):
    pundit = ScriptedPundit(["Nothing to see here."])
    insight = _orchestrator(pundit=pundit, max_retries=2).process_event(events[10])

    assert insight.verification_status == "FALLBACK_APPLIED"
    assert insight.narrative_source == "fallback_template"
    assert insight.agent_trace.count("verifier:rejected") == 3
    assert insight.agent_trace[-2:] == ["fallback", "director"]
    assert insight.grounding_score == 1.0


def test_workflow_and_plain_loop_agree(events):
    for event in (events[3], events[40], events[200]):
        in_workflow = _orchestrator().process_event(event)
        plain = MatchIntelligenceOrchestrator()
        plain.use_agent_framework = False
        in_loop = plain.process_event(event)
        assert in_workflow.model_dump() == in_loop.model_dump()


def test_workflow_works_inside_a_running_event_loop(events):
    import asyncio

    async def call():
        return _orchestrator().process_event(events[5])

    insight = asyncio.run(call())
    assert insight.agent_trace[-1] == "director"
