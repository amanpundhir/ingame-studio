"""InGame Studio - Multi-Agent Workflow Orchestrator.

Coordinates the 4-agent causal reasoning and verification pipeline:
1. Agent 1 (The Tactician): Extracts and computes telemetry into FactPack.
2. Agent 2 (The Pundit): Produces causal narrative linking action to tactics.
3. Agent 3 (The Ref): Audits draft narrative against FactPack within 1% tolerance.
4. Bounded Recovery Loop: Maximum 2 retries with targeted critique upon rejection.
5. Deterministic Fallback: Guarantees zero broadcast downtime if retries are exhausted.
6. Agent 4 (The Studio Director): Adapts verified insights into 4 viewer personas,
   lower-third ticker, telestrator vectors, and English and Spanish translations.
"""

import logging
import os
from typing import Any, Dict, List, Optional
from backend.agents.models import FactPack, VerifiedInsight, VerificationResult
from backend.agents.pipeline_state import PipelineState
from backend.agents.tactician_agent import TacticianAgent
from backend.agents.pundit_agent import PunditAgent
from backend.agents.verifier_agent import VerifierAgent
from backend.agents.director_agent import StudioDirectorAgent
from backend.agents.foundry_adapter import AzureFoundryAdapter
from backend.narrative_cache import NarrativeService

logger = logging.getLogger(__name__)

_default_service: Optional[NarrativeService] = None


def get_default_narrative_service() -> NarrativeService:
    """Process-wide cache-first Foundry service (disabled when no credentials are set)."""
    global _default_service
    if _default_service is None:
        _default_service = NarrativeService(AzureFoundryAdapter())
    return _default_service


def _agent_framework_available() -> bool:
    try:
        from backend.agents.af_workflow import run_pipeline  # noqa: F401
        return True
    except ImportError:
        return False


def run_pipeline(orchestrator: Any, state: PipelineState) -> VerifiedInsight:
    from backend.agents.af_workflow import run_pipeline as _run
    return _run(orchestrator, state)


class MatchIntelligenceOrchestrator:
    """Orchestrates the 4-agent match intelligence workflow for live broadcasting."""

    def __init__(
        self,
        tactician: Optional[TacticianAgent] = None,
        pundit: Optional[PunditAgent] = None,
        verifier: Optional[VerifierAgent] = None,
        director: Optional[StudioDirectorAgent] = None,
        max_retries: int = 2,
        narrative_service: Optional[NarrativeService] = None,
    ):
        """Initializes the multi-agent orchestrator with agents and retry policy.

        Args:
            tactician: Agent 1 instance (or default TacticianAgent).
            pundit: Agent 2 instance (or default PunditAgent).
            verifier: Agent 3 instance (or default VerifierAgent).
            director: Agent 4 instance (or default StudioDirectorAgent).
            max_retries: Maximum critique-driven retries permitted (default 2, total 3 attempts).
        """
        self.tactician = tactician or TacticianAgent()
        self.narrative_service = narrative_service or get_default_narrative_service()
        self.pundit = pundit or PunditAgent(narrative_service=self.narrative_service)
        self.verifier = verifier or VerifierAgent()
        self.director = director or StudioDirectorAgent()
        self.max_retries = max_retries
        # The agents run as a Microsoft Agent Framework workflow unless it is switched off
        # (INGAME_ORCHESTRATION=plain) or the package is not installed.
        self.use_agent_framework = (
            os.environ.get("INGAME_ORCHESTRATION", "agent_framework").strip().lower() != "plain"
            and _agent_framework_available()
        )

    def process_event(
        self,
        event: Dict[str, Any],
        telemetry_frame: Optional[Dict[str, Any]] = None,
        defenders: Optional[List[Dict[str, Any]]] = None,
        allow_live: bool = False,
    ) -> VerifiedInsight:
        """Processes a match event through the complete 4-agent reasoning pipeline.

        Args:
            event: Match event dictionary (e.g. from synthetic_events.json).
            telemetry_frame: Optional corresponding TelemetryFrame dictionary.
            defenders: Optional explicit defender coordinates.

        Returns:
            VerifiedInsight: 100% schema-compliant verified broadcast artifact.
        """
        state = PipelineState(
            allow_live=allow_live, max_retries=self.max_retries,
            event=event, telemetry_frame=telemetry_frame, defenders=defenders,
        )
        return self._run(state)

    def process_fact_pack(self, fact_pack: FactPack, allow_live: bool = False) -> VerifiedInsight:
        """Runs the Pundit -> Verifier retry loop and Director adaptation on a FactPack."""
        state = PipelineState(allow_live=allow_live, max_retries=self.max_retries, fact_pack=fact_pack)
        return self._run(state)

    def _run(self, state: PipelineState) -> VerifiedInsight:
        """Runs the pipeline on Microsoft Agent Framework, or as a plain loop when that is off."""
        if self.use_agent_framework:
            try:
                return run_pipeline(self, state)
            except Exception as exc:  # noqa: BLE001 - broadcast must never stop on an orchestration error
                logger.warning("Agent Framework workflow failed (%s); using the plain pipeline", exc)
                state = PipelineState(
                    allow_live=state.allow_live, max_retries=self.max_retries, event=state.event,
                    telemetry_frame=state.telemetry_frame, defenders=state.defenders,
                    fact_pack=state.fact_pack,
                )
        return self._run_plain(state)

    def _run_plain(self, state: PipelineState) -> VerifiedInsight:
        """The same four steps as the workflow, as an ordinary loop."""
        self.tactician_step(state)
        while True:
            self.pundit_step(state)
            self.verifier_step(state)
            if state.finished:
                break
        return self.director_step(state)

    # ------------------------------------------------------------------
    # Agent steps. Both the Agent Framework executors and the plain loop call these.
    # ------------------------------------------------------------------
    def tactician_step(self, state: PipelineState) -> None:
        """Agent 1 (The Tactician) extracts verified facts from the raw event."""
        if state.fact_pack is None:
            state.fact_pack = self.tactician.extract_facts(
                event=state.event,
                telemetry_frame=state.telemetry_frame,
                defenders=state.defenders,
            )
        state.trace.append("tactician")

    def pundit_step(self, state: PipelineState) -> None:
        """Agent 2 (The Pundit) writes the narrative; on a retry it receives the critique."""
        try:
            draft = self.pundit.generate_narrative(
                facts=state.fact_pack,
                critique=state.critique,
                attempt=state.attempt,
                allow_live=state.allow_live,
            )
        except TypeError:  # custom pundit without the allow_live argument
            draft = self.pundit.generate_narrative(
                facts=state.fact_pack, critique=state.critique, attempt=state.attempt
            )
        state.draft = draft
        state.trace.append(f"pundit#{state.attempt}")

    def verifier_step(self, state: PipelineState) -> None:
        """Agent 3 (The Ref) audits the draft; sets ``finished`` when it is accepted or retries run out."""
        verification = self.verifier.verify(state.fact_pack, state.draft)
        state.verification = verification
        state.retries_attempted = state.attempt
        if verification.is_valid:
            state.verified_narrative = state.draft.narrative
            state.final_draft = state.draft
            state.finished = True
            state.trace.append("verifier:accepted")
            return
        state.critique = verification.critique
        state.trace.append("verifier:rejected")
        if state.attempt >= state.max_retries:
            state.finished = True  # retries used up: the Director applies the deterministic fallback
        else:
            state.attempt += 1

    def director_step(self, state: PipelineState) -> VerifiedInsight:
        """Agent 4 (The Studio Director) adapts the result into personas and the broadcast payload."""
        fact_pack = state.fact_pack
        if state.verified_narrative is None:
            verified_narrative = self._deterministic_fallback(fact_pack)
            verification_status = "FALLBACK_APPLIED"
            final_grounding_score = self.verifier.verify(fact_pack, verified_narrative).grounding_score
            state.trace.append("fallback")
        else:
            verified_narrative = state.verified_narrative
            verification_status = "VERIFIED"
            final_grounding_score = state.verification.grounding_score if state.verification else 1.0
        state.trace.append("director")

        insight = self.director.create_verified_insight(
            facts=fact_pack,
            verified_narrative=verified_narrative,
            grounding_score=final_grounding_score,
            verification_status=verification_status,
            retries_attempted=state.retries_attempted,
        )
        insight.narrative_source = self._narrative_source(state.final_draft, verification_status)
        insight.agent_trace = list(state.trace)
        final_draft = state.final_draft
        if (
            final_draft is not None
            and not final_draft.from_cache
            and final_draft.model_used.startswith("azure-foundry")
        ):
            self.narrative_service.store_verified(fact_pack, final_draft.narrative)
        return insight

    @staticmethod
    def _narrative_source(draft: Optional[Any], status: str) -> str:
        if status != "VERIFIED" or draft is None:
            return "fallback_template"
        if draft.model_used.startswith("azure-foundry"):
            return "azure_foundry_cache" if draft.from_cache else "azure_foundry_live"
        return "local_template"

    def _deterministic_fallback(self, facts: FactPack) -> str:
        """Zero-latency deterministic template fallback ensuring zero broadcast disruption.

        Guaranteed to cite exact player names and metrics within 1% tolerance,
        conforming 100% to Verifier rules.
        """
        xt_sign = "+" if facts.xt_gained >= 0 else ""
        evt_type = facts.event_type.lower()

        if evt_type == "goal":
            return (
                f"InGame Tactical Feed [{facts.match_minute}]: {facts.passer_name} scored a sensational goal "
                f"for {facts.team_name} against {facts.receiver_name} with a {facts.pass_distance_m:.1f}m strike at "
                f"{facts.ball_speed_kmh:.1f} km/h ({facts.pass_difficulty:.1f}% execution difficulty, "
                f"{xt_sign}{facts.xt_gained:.2f} xT, {facts.tactical_context})."
            )
        elif evt_type == "shot":
            if (facts.outcome and "save" in facts.outcome) or (facts.sub_type and "save" in facts.sub_type):
                return (
                    f"InGame Tactical Feed [{facts.match_minute}]: Goalkeeper {facts.receiver_name} saved a "
                    f"{facts.pass_distance_m:.1f}m shot from {facts.passer_name} traveling at {facts.ball_speed_kmh:.1f} km/h "
                    f"({facts.pass_difficulty:.1f}% shot difficulty, {xt_sign}{facts.xt_gained:.2f} xT, {facts.tactical_context})."
                )
            return (
                f"InGame Tactical Feed [{facts.match_minute}]: {facts.passer_name} registered a {facts.pass_distance_m:.1f}m shot "
                f"towards {facts.receiver_name} clocked at {facts.ball_speed_kmh:.1f} km/h "
                f"({facts.pass_difficulty:.1f}% shot difficulty, {xt_sign}{facts.xt_gained:.2f} xT, {facts.tactical_context})."
            )
        elif evt_type == "tackle":
            return (
                f"InGame Tactical Feed [{facts.match_minute}]: {facts.passer_name} executed a decisive tackle on "
                f"{facts.receiver_name} over {facts.pass_distance_m:.1f}m at {facts.ball_speed_kmh:.1f} km/h "
                f"({facts.pass_difficulty:.1f}% tackle difficulty, {xt_sign}{facts.xt_gained:.2f} xT, {facts.tactical_context})."
            )
        elif evt_type in ("turnover", "interception"):
            return (
                f"InGame Tactical Feed [{facts.match_minute}]: {facts.passer_name} forced a turnover against "
                f"{facts.receiver_name} over {facts.pass_distance_m:.1f}m at {facts.ball_speed_kmh:.1f} km/h "
                f"({facts.pass_difficulty:.1f}% difficulty, {xt_sign}{facts.xt_gained:.2f} xT, {facts.tactical_context})."
            )
        elif evt_type == "foul":
            return (
                f"InGame Tactical Feed [{facts.match_minute}]: {facts.passer_name} committed a tactical foul on "
                f"{facts.receiver_name} over {facts.pass_distance_m:.1f}m at {facts.ball_speed_kmh:.1f} km/h "
                f"({facts.pass_difficulty:.1f}% difficulty, {xt_sign}{facts.xt_gained:.2f} xT, {facts.tactical_context})."
            )

        return (
            f"InGame Tactical Feed [{facts.match_minute}]: {facts.passer_name} completed a "
            f"{facts.pass_distance_m:.1f}m pass to {facts.receiver_name} at {facts.ball_speed_kmh:.1f} km/h. "
            f"Navigating a {facts.pass_difficulty:.1f}% pass difficulty rating and {facts.defenders_in_corridor} "
            f"corridor defenders, the sequence generated {xt_sign}{facts.xt_gained:.2f} xT ({facts.tactical_context})."
        )
