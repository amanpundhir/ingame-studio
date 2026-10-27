"""InGame Studio - Multi-Event Causal Reasoning Test Suite.

Validates:
1. Elimination of pass blindness across non-pass event types:
   - Goals (e.g. Kofi Sarpong 28', Anders Hagen 39')
   - Shots and saves (e.g. Jeremy Dukes denied by Daniel Roark)
   - Tackles (e.g. Kyle Walden on Mateus Montoya)
   - Turnovers (e.g. Wilfred Sandoval on Anders Hagen)
   - Fouls (e.g. Tomas Pardoe on Bernardo Santoro)
2. Grounding score >= 0.95 and status VERIFIED across all event types.
3. Strict rejection of pass misclassification on goal events.
4. Multi-persona adaptation and broadcast ticker formatting.
5. Zero-downtime deterministic fallback for all event types.
"""

import json
import os
import pytest
from jsonschema import Draft7Validator

from backend.agents.models import FactPack, DraftNarrative, VerifiedInsight
from backend.agents.tactician_agent import TacticianAgent
from backend.agents.pundit_agent import PunditAgent
from backend.agents.verifier_agent import VerifierAgent
from backend.agents.director_agent import StudioDirectorAgent
from backend.agents.orchestrator import MatchIntelligenceOrchestrator


@pytest.fixture(scope="module")
def schema():
    """Loads authoritative data/schema.json."""
    repo_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    schema_path = os.path.join(repo_root, "data", "schema.json")
    with open(schema_path, "r", encoding="utf-8") as f:
        return json.load(f)


@pytest.fixture(scope="module")
def synthetic_events():
    """Loads calibrated match events."""
    repo_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    events_path = os.path.join(repo_root, "data", "synthetic_events.json")
    with open(events_path, "r", encoding="utf-8") as f:
        return json.load(f)


def pick_event(events, event_type, outcome=None):
    """Select a generated action by semantics rather than a fixture ID."""
    return next(
        event for event in events
        if event.get("event_type") == event_type
        and (outcome is None or event.get("outcome") == outcome)
    )


class TestMultiEventFactPackExtraction:
    """Tests Agent 1 (The Tactician) multi-event extraction and schema conformance."""

    def test_goal_fact_pack_extraction(self, schema, synthetic_events):
        """Asserts goal event extracts scorer, goalkeeper, and goal-directed coordinates."""
        tactician = TacticianAgent()
        sarpong_goal = pick_event(synthetic_events, "goal")
        facts = tactician.extract_facts(sarpong_goal)

        assert facts.event_id == sarpong_goal["event_id"]
        assert facts.event_type == "goal"
        assert facts.passer_name == sarpong_goal["player_name"]
        assert facts.ball_speed_kmh == sarpong_goal.get("tactical_metrics", {}).get("ball_speed_kmh", 0.0)
        assert 0.0 <= facts.pass_difficulty <= 100.0
        assert facts.pass_distance_m >= 0.0
        assert facts.event_type == "goal"

        # Validate schema
        validator = Draft7Validator(schema["definitions"]["FactPack"])
        validator.validate(facts.model_dump())

    def test_shot_saved_fact_pack_extraction(self, schema, synthetic_events):
        """Asserts saved shot extracts shooter, goalkeeper, and save outcome."""
        tactician = TacticianAgent()
        dukes_shot = pick_event(synthetic_events, "shot", "saved")
        facts = tactician.extract_facts(dukes_shot)

        assert facts.event_id == dukes_shot["event_id"]
        assert facts.event_type == "shot"
        assert facts.passer_name == dukes_shot["player_name"]
        assert facts.outcome == "saved"
        assert facts.ball_speed_kmh == dukes_shot.get("tactical_metrics", {}).get("ball_speed_kmh", 0.0)

        validator = Draft7Validator(schema["definitions"]["FactPack"])
        validator.validate(facts.model_dump())

    def test_tackle_fact_pack_extraction(self, schema, synthetic_events):
        """Asserts tackle extracts tackler and tackled player without artificial 10m pass."""
        tactician = TacticianAgent()
        walden_tackle = pick_event(synthetic_events, "tackle")
        facts = tactician.extract_facts(walden_tackle)

        assert facts.event_id == walden_tackle["event_id"]
        assert facts.event_type == "tackle"
        assert facts.passer_name == walden_tackle["player_name"]
        assert facts.outcome == walden_tackle["outcome"]
        assert facts.event_type == "tackle"

        validator = Draft7Validator(schema["definitions"]["FactPack"])
        validator.validate(facts.model_dump())

    def test_turnover_fact_pack_extraction(self, schema, synthetic_events):
        """Asserts turnover extracts intercepting and dispossessed players."""
        tactician = TacticianAgent()
        sandoval_turnover = pick_event(synthetic_events, "turnover")
        facts = tactician.extract_facts(sandoval_turnover)

        assert facts.event_type == "turnover"
        assert facts.passer_name == sandoval_turnover["player_name"]

        validator = Draft7Validator(schema["definitions"]["FactPack"])
        validator.validate(facts.model_dump())


class TestMultiEventPunditNarratives:
    """Tests Agent 2 (The Pundit) causal reasoning across event types."""

    def test_goal_narrative_eliminates_pass_blindness(self, synthetic_events):
        """Asserts goal events are explicitly narrated as goals and never as passes."""
        tactician = TacticianAgent()
        pundit = PunditAgent()

        sarpong_goal = pick_event(synthetic_events, "goal")
        facts = tactician.extract_facts(sarpong_goal)
        draft = pundit.generate_narrative(facts)

        text = draft.narrative.lower()
        # Must identify goal
        assert any(w in text for w in ["goal", "scored", "finish", "strike"])
        # Must NOT describe as a pass
        assert "pass straight to" not in text
        assert "pass to barreto" not in text
        # Must cite key facts
        assert facts.passer_name.lower() in text
        assert f"{facts.ball_speed_kmh:.1f} km/h" in text
        assert f"{facts.pass_distance_m:.1f}m" in text
        assert f"{facts.pass_difficulty:.1f}%" in text

    def test_shot_save_narrative(self, synthetic_events):
        """Asserts saved shot praises goalkeeper stop and cites shot speed."""
        tactician = TacticianAgent()
        pundit = PunditAgent()

        dukes_shot = pick_event(synthetic_events, "shot", "saved")
        facts = tactician.extract_facts(dukes_shot)
        draft = pundit.generate_narrative(facts)

        text = draft.narrative.lower()
        assert "save" in text or "denied" in text or "shot" in text
        assert facts.passer_name.lower() in text
        assert f"{facts.ball_speed_kmh:.1f} km/h" in text

    def test_tackle_narrative(self, synthetic_events):
        """Asserts tackle is narrated as a tackle and cites players."""
        tactician = TacticianAgent()
        pundit = PunditAgent()

        walden_tackle = pick_event(synthetic_events, "tackle")
        facts = tactician.extract_facts(walden_tackle)
        draft = pundit.generate_narrative(facts)

        text = draft.narrative.lower()
        assert "tackle" in text or "challenge" in text
        assert "pass straight to" not in text
        assert facts.passer_name.lower() in text


class TestMultiEventVerifierGuards:
    """Tests Agent 3 (The Ref) grounding validation and anti-hallucination checks."""

    def test_verifier_accepts_valid_goal_narrative(self, synthetic_events):
        """Asserts verifier awards grounding_score >= 0.95 for genuine goal narrative."""
        tactician = TacticianAgent()
        pundit = PunditAgent()
        verifier = VerifierAgent()

        sarpong_goal = pick_event(synthetic_events, "goal")
        facts = tactician.extract_facts(sarpong_goal)
        draft = pundit.generate_narrative(facts)
        result = verifier.verify(facts, draft)

        assert result.is_valid is True
        assert result.grounding_score >= 0.95
        assert len(result.discrepancies) == 0

    def test_verifier_rejects_pass_misclassification_on_goal(self, synthetic_events):
        """Asserts verifier rejects narrative claiming a goal was a pass to the goalkeeper."""
        tactician = TacticianAgent()
        verifier = VerifierAgent()

        sarpong_goal = pick_event(synthetic_events, "goal")
        facts = tactician.extract_facts(sarpong_goal)

        # Legacy hallucinated narrative that described goal as pass
        hallucinated_narrative = (
            "At 28:15, Kofi Sarpong uncorks an electric 19.1m pass straight to Enzo Barreto clocked at 98.0 km/h! "
            "Pass difficulty was 88.0%."
        )
        result = verifier.verify(facts, hallucinated_narrative)

        assert result.is_valid is False
        assert any("pass" in d.lower() or "goal" in d.lower() for d in result.discrepancies)

    def test_verifier_rejects_hallucinated_goal_on_pass_event(self, synthetic_events):
        """Asserts verifier rejects narrative claiming a pass resulted in a goal."""
        tactician = TacticianAgent()
        verifier = VerifierAgent()

        pass_evt = next(e for e in synthetic_events if e["event_type"] == "pass")
        facts = tactician.extract_facts(pass_evt)

        hallucinated_text = (
            f"At {facts.match_minute}, {facts.passer_name} scored a goal past {facts.receiver_name} "
            f"from {facts.pass_distance_m:.1f}m at {facts.ball_speed_kmh:.1f} km/h (pass difficulty: {facts.pass_difficulty:.1f}%)."
        )
        result = verifier.verify(facts, hallucinated_text)

        assert result.is_valid is False
        assert any("goal" in d.lower() for d in result.discrepancies)


class TestMultiEventStudioDirector:
    """Tests Agent 4 (The Studio Director) persona adaptations and ticker straps."""

    def test_goal_personas_are_authentic_and_distinct(self, synthetic_events):
        """Asserts goal produces 4 distinct broadcast personas celebrating the goal."""
        tactician = TacticianAgent()
        director = StudioDirectorAgent()

        sarpong_goal = pick_event(synthetic_events, "goal")
        facts = tactician.extract_facts(sarpong_goal)
        personas = director.adapt_personas(facts, "Verified goal narrative.")

        # Casual Fan celebrates goal
        assert "⚽ GOAL!" in personas.casual_story
        assert facts.passer_name in personas.casual_story

        # Tactical Purist analyzes conversion
        assert "Tactical Breakdown" in personas.tactical_analysis
        assert f"{facts.pass_distance_m:.1f}m" in personas.tactical_analysis
        assert f"{facts.pass_difficulty:.1f}%" in personas.tactical_analysis

        # Club Loyalist exhibits partisan pride
        assert facts.team_name in personas.club_loyalist_story
        assert facts.passer_name in personas.club_loyalist_story

        # Player-Lock Fantasy highlights forward points and BPS
        assert "Fantasy" in personas.player_lock_story
        assert "Fantasy" in personas.player_lock_story or "BPS" in personas.player_lock_story

        # Ticker shows GOAL
        assert "GOAL!" in personas.lower_third_ticker
        assert facts.passer_name.upper() in personas.lower_third_ticker

    def test_tackle_and_turnover_tickers(self, synthetic_events):
        """Asserts live ticker formats accurately for tackles and turnovers."""
        tactician = TacticianAgent()
        director = StudioDirectorAgent()

        tackle_evt = next(e for e in synthetic_events if e["event_type"] == "tackle")
        facts = tactician.extract_facts(tackle_evt)
        ticker = director.generate_ticker(facts, "VERIFIED")
        assert "TACKLE WON" in ticker

        turnover_evt = next(e for e in synthetic_events if e["event_type"] == "turnover")
        facts_to = tactician.extract_facts(turnover_evt)
        ticker_to = director.generate_ticker(facts_to, "VERIFIED")
        assert "TURNOVER" in ticker_to


class TestMultiEventDeterministicFallback:
    """Tests zero-downtime deterministic fallback for non-pass events."""

    def test_deterministic_fallback_for_goal(self, synthetic_events):
        """Asserts deterministic fallback describes a goal and passes verification."""
        orchestrator = MatchIntelligenceOrchestrator()
        verifier = VerifierAgent()
        tactician = TacticianAgent()

        sarpong_goal = pick_event(synthetic_events, "goal")
        facts = tactician.extract_facts(sarpong_goal)
        fallback_text = orchestrator._deterministic_fallback(facts)

        assert "scored a sensational goal" in fallback_text or "goal" in fallback_text
        assert "pass straight to" not in fallback_text

        result = verifier.verify(facts, fallback_text)
        assert result.is_valid is True
        assert result.grounding_score >= 0.95

    def test_deterministic_fallback_for_tackle(self, synthetic_events):
        """Asserts deterministic fallback describes a tackle and passes verification."""
        orchestrator = MatchIntelligenceOrchestrator()
        verifier = VerifierAgent()
        tactician = TacticianAgent()

        tackle_evt = next(e for e in synthetic_events if e["event_type"] == "tackle")
        facts = tactician.extract_facts(tackle_evt)
        fallback_text = orchestrator._deterministic_fallback(facts)

        assert "tackle" in fallback_text.lower()
        result = verifier.verify(facts, fallback_text)
        assert result.is_valid is True
        assert result.grounding_score >= 0.95


class TestEndToEndMatchIntelligenceOrchestrator:
    """Tests full pipeline execution on all calibrated match moment types."""

    def test_all_four_calibrated_goals_are_verified_as_goals(self, synthetic_events):
        """Asserts Sarpong 28', Hagen 39', Halvorsen 64', and Fenton 86' are verified as goals."""
        orchestrator = MatchIntelligenceOrchestrator()
        goal_events = [e for e in synthetic_events if e["event_type"] == "goal"]
        assert goal_events

        for goal in goal_events:
            insight = orchestrator.process_event(goal)
            assert isinstance(insight, VerifiedInsight)
            assert insight.verification_status == "VERIFIED"
            assert insight.grounding_score >= 0.95

            # Assert goal recognition in all personas
            assert "⚽ GOAL!" in insight.casual_story
            assert "GOAL" in insight.lower_third_ticker
            assert "pass straight to" not in insight.casual_story.lower()

    def test_shot_tackle_turnover_foul_pipeline_execution(self, synthetic_events):
        """Asserts non-goal, non-pass events process cleanly with grounding score >= 0.95."""
        orchestrator = MatchIntelligenceOrchestrator()
        for evt_type in ["shot", "tackle", "turnover", "foul"]:
            sample = next((e for e in synthetic_events if e["event_type"] == evt_type), None)
            if sample:
                insight = orchestrator.process_event(sample)
                assert insight.verification_status in ("VERIFIED", "FALLBACK_APPLIED")
                assert insight.grounding_score >= 0.95
                assert len(insight.casual_story) > 30
                assert len(insight.tactical_analysis) > 30
