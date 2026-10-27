"""Comprehensive Test Suite for InGame Studio Multi-Agent Reasoning & Verification.

Tests:
1. TacticianAgent FactPack extraction, physical metrics, and schema validity.
2. PunditAgent causal "Why It Matters" narrative generation and critique responsiveness.
3. VerifierAgent grounding evaluation:
   - Genuine accurate narratives pass with 100% grounding.
   - Altered numerical claims (>1% relative error) are strictly rejected.
   - Minor variations within 1% relative error are accepted.
   - Missing player names are rejected.
   - Hallucinated match events (e.g. goal or red card on a pass) are rejected.
4. MatchIntelligenceOrchestrator bounded retry loop (up to 2 retries).
5. Deterministic fallback activation upon retry exhaustion producing 100% compliant broadcast output.
6. Schema conformance of VerifiedInsight against data/schema.json.
"""

import json
import os
import pytest
from jsonschema import Draft7Validator, validate

from backend.agents.models import FactPack, DraftNarrative, VerificationResult, VerifiedInsight
from backend.agents.tactician_agent import TacticianAgent
from backend.agents.pundit_agent import PunditAgent
from backend.agents.verifier_agent import VerifierAgent
from backend.agents.director_agent import StudioDirectorAgent
from backend.agents.orchestrator import MatchIntelligenceOrchestrator


@pytest.fixture(scope="module")
def schema():
    """Loads the authoritative JSONSchema draft-07 specification."""
    current_dir = os.path.dirname(os.path.abspath(__file__))
    repo_root = os.path.dirname(current_dir)
    schema_path = os.path.join(repo_root, "data", "schema.json")
    with open(schema_path, "r", encoding="utf-8") as f:
        schema_data = json.load(f)
    Draft7Validator.check_schema(schema_data)
    return schema_data


@pytest.fixture
def sample_pass_event():
    """Sample realistic pass event between Declan Rowe and Kofi Sarpong."""
    return {
        "event_id": "EVT_1009",
        "match_id": "IGS_2026_NBL_HSC",
        "match_minute": "42:18",
        "clock": "42:18",
        "period": 1,
        "event_type": "pass",
        "team": "Northbridge Lions",
        "opponent": "Harbourside City",
        "player_id": "NBL_41",
        "player_name": "Declan Rowe",
        "secondary_player_id": "NBL_07",
        "secondary_player_name": "Kofi Sarpong",
        "start_x": 48.5,
        "start_y": 28.0,
        "end_x": 77.0,
        "end_y": 28.0,
        "duration_sec": 1.425,
        "tactical_metrics": {
            "pass_difficulty": 80.0,
            "ball_speed_kmh": 72.0,
            "chaos_index": 68.0,
            "xt_gained": 0.18,
            "defenders_in_corridor": 2,
            "defenders_in_cone": 1,
        },
        "context": "Northbridge Lions build-up breaking Harbourside City mid-block",
    }


class TestFactPackExtraction:
    """Tests Agent 1 (The Tactician) extraction logic and schema validity."""

    def test_extract_facts_validates_schema(self, schema, sample_pass_event):
        """Asserts extracted FactPack validates strictly against data/schema.json."""
        tactician = TacticianAgent()
        fact_pack = tactician.extract_facts(sample_pass_event)

        fact_dict = fact_pack.model_dump()
        fact_subschema = schema["definitions"]["FactPack"]
        validate(instance=fact_dict, schema=fact_subschema)

        assert fact_pack.event_id == "EVT_1009"
        assert fact_pack.passer_name == "Declan Rowe"
        assert fact_pack.receiver_name == "Kofi Sarpong"
        assert fact_pack.pass_distance_m == 28.5
        assert fact_pack.pass_difficulty == 80.0
        assert fact_pack.ball_speed_kmh == 72.0
        assert fact_pack.chaos_index == 68.0
        assert fact_pack.xt_gained == 0.18
        assert fact_pack.defenders_in_corridor == 2

    def test_extract_facts_bounds_enforcement(self):
        """Asserts extracted metrics stay strictly within physical and mathematical boundaries."""
        tactician = TacticianAgent()
        extreme_event = {
            "event_id": "EVT_EXTREME",
            "match_minute": "89:00",
            "period": 2,
            "player_name": "Goalkeeper",
            "receiver_name": "Striker",
            "start_x": -10.0,  # Below pitch bound
            "start_y": 75.0,   # Above pitch bound
            "end_x": 120.0,    # Above pitch bound
            "end_y": -5.0,     # Below pitch bound
            "duration_sec": 0.5,
        }
        fact_pack = tactician.extract_facts(extreme_event)
        assert 0.0 <= fact_pack.start_x <= 105.0
        assert 0.0 <= fact_pack.start_y <= 68.0
        assert 0.0 <= fact_pack.end_x <= 105.0
        assert 0.0 <= fact_pack.end_y <= 68.0
        assert 0.0 <= fact_pack.pass_difficulty <= 100.0
        assert 0.0 <= fact_pack.chaos_index <= 100.0
        assert 0.0 <= fact_pack.ball_speed_kmh <= 150.0
        assert -1.0 <= fact_pack.xt_gained <= 1.0


class TestPunditAgent:
    """Tests Agent 2 (The Pundit) causal reasoning and critique repairs."""

    def test_pundit_cites_exact_entities_and_metrics(self, sample_pass_event):
        """Asserts draft narrative explicitly cites passer, receiver, and metrics."""
        tactician = TacticianAgent()
        facts = tactician.extract_facts(sample_pass_event)

        pundit = PunditAgent()
        draft = pundit.generate_narrative(facts)

        text = draft.narrative
        assert "Declan Rowe" in text
        assert "Kofi Sarpong" in text
        assert "28.5m" in text
        assert "80.0%" in text
        assert "72.0 km/h" in text
        assert draft.event_id == "EVT_1009"

    def test_pundit_addresses_critique_on_revision(self, sample_pass_event):
        """Asserts Pundit includes explicit corrections when critique is passed."""
        tactician = TacticianAgent()
        facts = tactician.extract_facts(sample_pass_event)

        pundit = PunditAgent()
        critique = "REJECTED: Missing or incorrect passer name: 'Declan Rowe'"
        revised = pundit.generate_narrative(facts, critique=critique, attempt=1)

        assert revised.generation_attempt == 1
        assert revised.critique_addressed == critique
        assert "Declan Rowe" in revised.narrative


class TestVerifierAgent:
    """Tests Agent 3 (The Ref) grounding, numerical tolerance, and hallucination checks."""

    def test_verifier_approves_genuine_accurate_narrative(self, sample_pass_event):
        """Asserts genuine narrative matching FactPack passes with 100% grounding."""
        tactician = TacticianAgent()
        facts = tactician.extract_facts(sample_pass_event)

        pundit = PunditAgent()
        draft = pundit.generate_narrative(facts)

        verifier = VerifierAgent(tolerance_pct=0.01)
        res = verifier.verify(facts, draft)

        assert res.is_valid is True
        assert res.grounding_score == 1.0
        assert len(res.discrepancies) == 0
        assert "VERIFIED" in res.critique

    def test_verifier_rejects_altered_pass_difficulty(self, sample_pass_event):
        """Asserts PDR altered beyond 1% relative error is strictly rejected."""
        tactician = TacticianAgent()
        facts = tactician.extract_facts(sample_pass_event)  # PDR is 80.0%

        verifier = VerifierAgent(tolerance_pct=0.01)

        # Alter difficulty to 85.0% (> 1% relative error)
        altered_text = (
            "In minute 42:18, Declan Rowe played a 28.5m pass to Kofi Sarpong at 72.0 km/h "
            "with a 85.0% pass difficulty rating."
        )
        res = verifier.verify(facts, altered_text)

        assert res.is_valid is False
        assert any("pass difficulty" in d.lower() for d in res.discrepancies)
        assert res.grounding_score < 1.0

    def test_verifier_rejects_altered_ball_speed(self, sample_pass_event):
        """Asserts ball speed altered beyond 1% relative error is strictly rejected."""
        tactician = TacticianAgent()
        facts = tactician.extract_facts(sample_pass_event)  # Speed is 72.0 km/h

        verifier = VerifierAgent(tolerance_pct=0.01)

        # Alter speed to 85.0 km/h (actual 72.0 km/h -> relative error ~18%)
        altered_text = (
            "At 42:18, Declan Rowe fired a 28.5m pass to Kofi Sarpong at 85.0 km/h "
            "navigating an 80.0% pass difficulty rating."
        )
        res = verifier.verify(facts, altered_text)

        assert res.is_valid is False
        assert any("ball speed" in d.lower() for d in res.discrepancies)

    def test_verifier_rejects_altered_pass_distance(self, sample_pass_event):
        """Asserts pass distance altered beyond 1% relative error is strictly rejected."""
        tactician = TacticianAgent()
        facts = tactician.extract_facts(sample_pass_event)  # Distance is 28.5m

        verifier = VerifierAgent(tolerance_pct=0.01)

        altered_text = (
            "At 42:18, Declan Rowe executed an expansive 38.0m pass to Kofi Sarpong "
            "travelling at 72.0 km/h with 80.0% difficulty."
        )
        res = verifier.verify(facts, altered_text)

        assert res.is_valid is False
        assert any("pass distance" in d.lower() for d in res.discrepancies)

    def test_verifier_accepts_tolerable_numerical_variation(self, sample_pass_event):
        """Asserts numerical citation within 1% relative error is accepted."""
        tactician = TacticianAgent()
        facts = tactician.extract_facts(sample_pass_event)  # Speed 72.0 km/h, dist 28.5m, PDR 80.0%

        verifier = VerifierAgent(tolerance_pct=0.01)

        # 72.3 km/h has relative error |72.3-72.0|/72.0 = 0.00416 <= 0.01 (0.41% error)
        # 28.6m has relative error |28.6-28.5|/28.5 = 0.0035 <= 0.01 (0.35% error)
        # 80.4% has relative error |80.4-80.0|/80.0 = 0.0050 <= 0.01 (0.50% error)
        tolerable_text = (
            "In minute 42:18, Declan Rowe executed a 28.6m pass to Kofi Sarpong clocked at 72.3 km/h "
            "with a 80.4% difficulty rating."
        )
        res = verifier.verify(facts, tolerable_text)
        assert res.is_valid is True

    def test_verifier_rejects_missing_player_names(self, sample_pass_event):
        """Asserts omission of passer or receiver name fails verification."""
        tactician = TacticianAgent()
        facts = tactician.extract_facts(sample_pass_event)

        verifier = VerifierAgent()

        # Omit receiver Kofi Sarpong
        missing_receiver_text = (
            "At 42:18, Declan Rowe executed a 28.5m pass to his teammate travelling at 72.0 km/h "
            "with an 80.0% pass difficulty rating."
        )
        res = verifier.verify(facts, missing_receiver_text)
        assert res.is_valid is False
        assert any("receiver name" in d.lower() for d in res.discrepancies)

    def test_verifier_rejects_hallucinated_outcomes(self, sample_pass_event):
        """Asserts claiming ungrounded events (e.g. goal or red card on a pass) is rejected."""
        tactician = TacticianAgent()
        facts = tactician.extract_facts(sample_pass_event)  # event_type is "pass"

        verifier = VerifierAgent()

        hallucinated_goal_text = (
            "At 42:18, Declan Rowe passed 28.5m to Kofi Sarpong at 72.0 km/h with 80.0% difficulty, "
            "and Northbridge Lions scored a goal from this brilliant move!"
        )
        res = verifier.verify(facts, hallucinated_goal_text)
        assert res.is_valid is False
        assert any("hallucinated event" in d.lower() for d in res.discrepancies)


class MockFlakyPundit:
    """Mock Pundit that fails on initial attempt and fixes on retry."""

    def __init__(self, fail_attempts: int = 1):
        self.fail_attempts = fail_attempts
        self.call_count = 0

    def generate_narrative(self, facts: FactPack, critique=None, attempt: int = 0):
        self.call_count += 1
        if attempt < self.fail_attempts:
            # Emit corrupted speed
            return DraftNarrative(
                event_id=facts.event_id,
                narrative=(
                    f"At {facts.match_minute}, {facts.passer_name} linked with {facts.receiver_name} "
                    f"over {facts.pass_distance_m:.1f}m at 145.0 km/h with {facts.pass_difficulty:.1f}% difficulty."
                ),
                generation_attempt=attempt,
            )
        # Correct generation
        return DraftNarrative(
            event_id=facts.event_id,
            narrative=(
                f"At {facts.match_minute}, {facts.passer_name} linked with {facts.receiver_name} "
                f"over {facts.pass_distance_m:.1f}m at {facts.ball_speed_kmh:.1f} km/h with {facts.pass_difficulty:.1f}% difficulty."
            ),
            generation_attempt=attempt,
        )


class MockAlwaysFailingPundit:
    """Mock Pundit that always hallucinates to trigger deterministic fallback."""

    def __init__(self):
        self.call_count = 0

    def generate_narrative(self, facts: FactPack, critique=None, attempt: int = 0):
        self.call_count += 1
        return DraftNarrative(
            event_id=facts.event_id,
            narrative=f"At {facts.match_minute}, {facts.passer_name} passed to {facts.receiver_name} and scored a goal!",
            generation_attempt=attempt,
        )


class TestOrchestratorWorkflow:
    """Tests MatchIntelligenceOrchestrator coordination, retry state machine, and fallback."""

    def test_orchestrator_standard_path_zero_retries(self, sample_pass_event):
        """Asserts standard event processes smoothly with 0 retries and VERIFIED status."""
        orchestrator = MatchIntelligenceOrchestrator()
        insight = orchestrator.process_event(sample_pass_event)

        assert insight.event_id == "EVT_1009"
        assert insight.verification_status == "VERIFIED"
        assert insight.retries_attempted == 0
        assert insight.grounding_score == 1.0
        assert "DECLAN ROWE" in insight.lower_third_ticker
        assert "KOFI SARPONG" in insight.lower_third_ticker

    def test_orchestrator_retry_recovery_success(self, sample_pass_event):
        """Asserts orchestrator retries when initial attempt is rejected and recovers."""
        flaky_pundit = MockFlakyPundit(fail_attempts=1)
        orchestrator = MatchIntelligenceOrchestrator(pundit=flaky_pundit)

        insight = orchestrator.process_event(sample_pass_event)

        assert insight.verification_status == "VERIFIED"
        assert insight.retries_attempted == 1
        assert flaky_pundit.call_count == 2
        assert insight.grounding_score == 1.0

    def test_orchestrator_deterministic_fallback_when_retries_exhausted(self, sample_pass_event):
        """Asserts deterministic fallback triggers when max retries (2) are exhausted."""
        failing_pundit = MockAlwaysFailingPundit()
        orchestrator = MatchIntelligenceOrchestrator(pundit=failing_pundit, max_retries=2)

        insight = orchestrator.process_event(sample_pass_event)

        # 1 initial + 2 retries = 3 attempts total
        assert failing_pundit.call_count == 3
        assert insight.verification_status == "FALLBACK_APPLIED"
        assert insight.retries_attempted == 2
        assert insight.grounding_score == 1.0  # Fallback template is 100% grounded
        assert "STATUS: FALLBACK_APPLIED" in insight.lower_third_ticker
        assert "Declan Rowe" in insight.casual_story
        assert "Kofi Sarpong" in insight.casual_story

    def test_verified_insight_conforms_to_schema(self, schema, sample_pass_event):
        """Asserts output VerifiedInsight passes full JSONSchema validation."""
        orchestrator = MatchIntelligenceOrchestrator()
        insight = orchestrator.process_event(sample_pass_event)

        insight_dict = insight.model_dump()
        insight_subschema = schema["definitions"]["VerifiedInsight"]
        validate(instance=insight_dict, schema=insight_subschema)
