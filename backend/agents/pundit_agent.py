"""InGame Studio - Agent 2: The Pundit (Causal Reasoner).

Answers "Why does this moment matter?" by linking spatial action to tactical outcomes.
Must cite exact player names and numerical metrics present in the FactPack.
Supports critique-driven revisions during the bounded retry loop.
"""

from typing import Any, Optional
from backend.agents.models import FactPack, DraftNarrative


class PunditAgent:
    """Agent 2: The Pundit.

    Transforms raw statistical FactPacks into causal football narratives.
    Explains space creation, line-breaking efficiency, press resistance,
    and momentum shifts with exact statistical citations.
    """

    def __init__(self, model_name: str = "deterministic-heuristic", narrative_service: Any = None):
        self.model_name = model_name
        self.narrative_service = narrative_service

    def generate_narrative(
        self,
        facts: FactPack,
        critique: Optional[str] = None,
        attempt: int = 0,
        allow_live: bool = False,
    ) -> DraftNarrative:
        """Generates a causal narrative grounded strictly in the FactPack facts.

        Args:
            facts: Validated FactPack emitted by Agent 1.
            critique: Optional rejection critique from Agent 3 to resolve.
            attempt: Current retry iteration index (0 = initial, 1 or 2 = revision).

        Returns:
            DraftNarrative containing the causal story and attribution metadata.
        """
        model_draft = self._model_narrative(facts, critique, attempt, allow_live)
        if model_draft is not None:
            return model_draft

        dist_str = f"{facts.pass_distance_m:.1f}m"
        pdr_str = f"{facts.pass_difficulty:.1f}%"
        speed_str = f"{facts.ball_speed_kmh:.1f} km/h"
        xt_sign = "+" if facts.xt_gained >= 0 else ""
        xt_str = f"{xt_sign}{facts.xt_gained:.2f} xT"

        if facts.event_type.lower() == "goal":
            story = (
                f"In minute {facts.match_minute}, {facts.passer_name} scored a sensational goal for {facts.team_name}, "
                f"beating goalkeeper {facts.receiver_name} with a {dist_str} strike clocked at {speed_str}! "
                f"Overcoming an exacting {pdr_str} execution difficulty against {facts.opponent_name}, "
                f"this clinical finish generated {xt_str} and shifted match momentum into overdrive."
            )
        elif facts.event_type.lower() == "shot":
            if (facts.outcome and "save" in facts.outcome) or (facts.sub_type and "save" in facts.sub_type):
                story = (
                    f"In minute {facts.match_minute}, {facts.receiver_name} produced a crucial save to deny {facts.passer_name}, "
                    f"stopping a ferocious {dist_str} strike traveling at {speed_str}. Facing an exacting {pdr_str} shot difficulty "
                    f"under high threat ({xt_str}), the save preserved the defensive line for {facts.opponent_name}."
                )
            else:
                story = (
                    f"In minute {facts.match_minute}, {facts.passer_name} unleashed a dangerous {dist_str} shot towards {facts.receiver_name} "
                    f"clocked at {speed_str}. Navigating a {pdr_str} shot difficulty against {facts.defenders_in_corridor} defenders, "
                    f"the attempt registered {xt_str} and pressured the {facts.opponent_name} backline."
                )
        elif facts.event_type.lower() == "tackle":
            story = (
                f"In minute {facts.match_minute}, {facts.passer_name} executed a decisive tackle on {facts.receiver_name} "
                f"over a {dist_str} engagement distance at {speed_str}. Recording a {pdr_str} tackle difficulty rating, "
                f"the intervention neutralized {xt_str} opponent threat and restored possession for {facts.team_name}."
            )
        elif facts.event_type.lower() in ("turnover", "interception"):
            story = (
                f"In minute {facts.match_minute}, {facts.passer_name} forced a critical turnover against {facts.receiver_name} "
                f"across a {dist_str} recovery zone at {speed_str}. Overcoming a {pdr_str} challenge difficulty, "
                f"the takeaway generated {xt_str} in transition momentum for {facts.team_name}."
            )
        elif facts.event_type.lower() == "foul":
            story = (
                f"In minute {facts.match_minute}, {facts.passer_name} committed a tactical foul on {facts.receiver_name} "
                f"over a {dist_str} contest zone at {speed_str}. Under a {pdr_str} intensity rating, "
                f"the stoppage contained {xt_str} progression and broke up the {facts.opponent_name} counter-attack."
            )
        elif facts.event_type.lower() == "substitution":
            story = (
                f"In minute {facts.match_minute}, {facts.team_name} make a change as {facts.passer_name} replaces "
                f"{facts.receiver_name}, giving the side fresh legs and a different shape against {facts.opponent_name}."
            )
        elif facts.event_type.lower() == "card":
            kind = (facts.sub_type or "yellow_card").lower()
            if kind == "yellow_card":
                story = (
                    f"In minute {facts.match_minute}, {facts.passer_name} is shown a yellow card for a foul on "
                    f"{facts.receiver_name}, a booking that forces {facts.team_name} to defend more carefully against {facts.opponent_name}."
                )
            else:
                how = "a second yellow card" if kind == "second_yellow" else "a straight red card"
                story = (
                    f"In minute {facts.match_minute}, {facts.passer_name} is shown {how} for a foul on "
                    f"{facts.receiver_name} and is sent off, leaving {facts.team_name} a player short against {facts.opponent_name}."
                )
        elif facts.event_type.lower() == "pressure":
            story = (
                f"At {facts.match_minute}, {facts.passer_name} pressed {facts.receiver_name} during {facts.opponent_name}'s build-up. "
                f"The pressure context records {dist_str} between the event coordinates, {speed_str} ball speed, "
                f"a {pdr_str} pressure difficulty and {xt_str} threat change; {facts.tactical_context} explains how the action "
                f"could disrupt the next phase of possession."
            )
        elif facts.xt_gained >= 0.15:
            story = (
                f"In minute {facts.match_minute}, {facts.passer_name} executed an incisive {dist_str} pass "
                f"to {facts.receiver_name} travelling at {speed_str}. Navigating a {pdr_str} pass difficulty "
                f"rating against {facts.defenders_in_corridor} corridor defenders, this move surged Expected Threat "
                f"by {xt_str}, slicing open the {facts.opponent_name} defensive block."
            )
        elif facts.pass_difficulty >= 70.0:
            story = (
                f"Under intense defensive containment at {facts.match_minute}, {facts.passer_name} threaded "
                f"a high-difficulty {dist_str} pass to {facts.receiver_name} clocked at {speed_str}. Overcoming an "
                f"exacting {pdr_str} difficulty rating and bypassing {facts.defenders_in_corridor} covering defenders, "
                f"the action generated {xt_str} and relieved tactical pressure."
            )
        elif facts.chaos_index >= 60.0:
            story = (
                f"Amid high transition volatility (Chaos Index: {facts.chaos_index:.1f}%) at {facts.match_minute}, "
                f"{facts.passer_name} brought composure by delivering a {dist_str} pass to {facts.receiver_name} "
                f"at {speed_str}. With a {pdr_str} difficulty rating and {xt_str} progression, it neutralized turnover "
                f"momentum and established forward structure."
            )
        else:
            story = (
                f"During structured build-up at {facts.match_minute}, {facts.passer_name} linked with "
                f"{facts.receiver_name} over a measured {dist_str} distance at {speed_str}. Recording a {pdr_str} "
                f"difficulty rating and yielding {xt_str}, the sequence maintained control and unlocked tactical territory."
            )

        # Include milestone callout if present
        if facts.milestone:
            story = f"{story} [Milestone: {facts.milestone}]"
        elif "[Milestone:" in facts.tactical_context and "[Milestone:" not in story:
            m_part = facts.tactical_context.split("[Milestone:")[1].split("]")[0].strip()
            story = f"{story} [Milestone: {m_part}]"

        # If revision on critique
        if critique:
            corrections = []
            if facts.passer_name.lower() not in story.lower():
                corrections.append(f"Passer: {facts.passer_name}")
            if facts.receiver_name.lower() not in story.lower():
                corrections.append(f"Receiver: {facts.receiver_name}")
            if pdr_str not in story:
                corrections.append(f"Pass Difficulty: {pdr_str}")
            if dist_str not in story:
                corrections.append(f"Pass Distance: {dist_str}")
            if speed_str not in story:
                corrections.append(f"Ball Speed: {speed_str}")
            if corrections:
                story = f"{story} [Corrections Applied: {', '.join(corrections)}]"

        return DraftNarrative(
            event_id=facts.event_id,
            narrative=story,
            generation_attempt=attempt,
            model_used=self.model_name,
            critique_addressed=critique,
        )

    def _model_narrative(
        self,
        facts: FactPack,
        critique: Optional[str],
        attempt: int,
        allow_live: bool,
    ) -> Optional[DraftNarrative]:
        """Returns a Foundry-written draft from cache or a live call, or None to use the local template.

        Cached answers are returned instantly. On a miss the live stream never
        waits for the model: it uses the local template now and warms the cache
        in the background. Blocking callers (ingest, jump) may call live.
        """
        service = self.narrative_service
        if service is None or not service.enabled:
            return None
        model = f"azure-foundry-{service.adapter.deployment}"
        if attempt == 0:
            cached = service.lookup(facts)
            if cached:
                return DraftNarrative(
                    event_id=facts.event_id, narrative=cached, generation_attempt=attempt,
                    model_used=model, critique_addressed=critique, from_cache=True,
                )
        if not allow_live:
            if attempt == 0:
                service.warm_in_background(facts, _VERIFIER)
            return None
        text = service.generate_live(facts, critique)
        if not text:
            return None
        return DraftNarrative(
            event_id=facts.event_id, narrative=text, generation_attempt=attempt,
            model_used=model, critique_addressed=critique, from_cache=False,
        )


from backend.agents.verifier_agent import VerifierAgent  # noqa: E402

_VERIFIER = VerifierAgent()

