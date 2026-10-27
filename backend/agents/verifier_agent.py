"""InGame Studio - Agent 3: The Ref (Grounding & Verification).

Evaluates draft narratives produced by Agent 2 against the authoritative FactPack.
Emulates Microsoft Foundry Grounding Evaluation principles:
- Rejects hallucinations and altered statistics.
- Validates numerical consistency within strictly 1% relative tolerance.
- Verifies entity naming (passer, receiver).
- Detects ungrounded match events (e.g. claiming a goal when event was a pass).
- Emits actionable critiques to guide bounded retries and triggers fallback when needed.
"""

import re
from typing import Dict, List, Tuple, Union
from backend.agents.models import FactPack, DraftNarrative, VerificationResult


NON_PLAY_EVENTS = ("substitution", "card")


class VerifierAgent:
    """Agent 3: The Ref.

    Independent verification agent ensuring broadcast narrative integrity.
    Programmatically audits text against telemetry fact packs.
    """

    def __init__(self, tolerance_pct: float = 0.01):
        """Initializes Verifier with relative error tolerance (default 0.01 = 1%)."""
        self.tolerance_pct = tolerance_pct

    def verify(self, facts: FactPack, draft: Union[DraftNarrative, str]) -> VerificationResult:
        """Audits a draft narrative against the ground-truth FactPack.

        Args:
            facts: Authoritative FactPack.
            draft: DraftNarrative or string narrative.

        Returns:
            VerificationResult detailing pass/fail status, grounding score, and critique.
        """
        text = draft.narrative if isinstance(draft, DraftNarrative) else str(draft)
        discrepancies: List[str] = []
        checked_citations: Dict[str, bool] = {}

        # 1. Entity verification: Passer Name
        has_passer = facts.passer_name.lower() in text.lower()
        checked_citations["passer_name"] = has_passer
        if not has_passer:
            discrepancies.append(f"Missing or incorrect passer name: '{facts.passer_name}'")

        # 2. Entity verification: Receiver Name
        has_receiver = facts.receiver_name.lower() in text.lower()
        checked_citations["receiver_name"] = has_receiver
        if not has_receiver:
            discrepancies.append(f"Missing or incorrect receiver name: '{facts.receiver_name}'")

        # Substitutions and cards are not ball actions, so they carry no pass distance,
        # speed or difficulty to cite; their names and the type of card are checked instead.
        if facts.event_type.lower() not in NON_PLAY_EVENTS:
            # 3. Numerical verification: Pass Difficulty Rating (%)
            pdr_valid, pdr_reason = self._verify_percentage(
                text=text,
                target_value=facts.pass_difficulty,
                name="pass difficulty",
            )
            checked_citations["pass_difficulty"] = pdr_valid
            if not pdr_valid:
                discrepancies.append(pdr_reason)

            # 4. Numerical verification: Pass Distance (meters)
            dist_valid, dist_reason = self._verify_metric_unit(
                text=text,
                target_value=facts.pass_distance_m,
                unit_pattern=r"(?:m\b|meters?\b|metres?\b)",
                name="pass distance",
            )
            checked_citations["pass_distance"] = dist_valid
            if not dist_valid:
                discrepancies.append(dist_reason)

            # 5. Numerical verification: Ball Speed (km/h)
            speed_valid, speed_reason = self._verify_metric_unit(
                text=text,
                target_value=facts.ball_speed_kmh,
                unit_pattern=r"(?:km/h\b|kmh\b|kph\b)",
                name="ball speed",
            )
            checked_citations["ball_speed"] = speed_valid
            if not speed_valid:
                discrepancies.append(speed_reason)

        # 6. Hallucination guard: Contradictory outcome or event claims
        hallucination_found, hall_reason = self._check_hallucinated_outcomes(text, facts)
        checked_citations["outcome_consistency"] = not hallucination_found
        if hallucination_found:
            discrepancies.append(hall_reason)

        # Calculate grounding score
        total_checks = len(checked_citations)
        passed_checks = sum(1 for v in checked_citations.values() if v)
        grounding_score = round(passed_checks / max(1, total_checks), 2)

        # Must pass all checks (grounding_score >= 0.95) and zero discrepancies
        is_valid = (len(discrepancies) == 0) and (grounding_score >= 0.95)

        if is_valid:
            critique = "VERIFIED: Narrative is factually grounded against telemetry."
        else:
            critique = "REJECTED: " + "; ".join(discrepancies)

        return VerificationResult(
            is_valid=is_valid,
            grounding_score=grounding_score,
            critique=critique,
            discrepancies=discrepancies,
            checked_citations=checked_citations,
        )

    def _verify_percentage(self, text: str, target_value: float, name: str) -> Tuple[bool, str]:
        """Verifies if percentage mentioned in text matches target within 1% relative tolerance."""
        # Find all percentages in text like 80.0%, 80%, etc.
        matches = re.findall(r"(\d+(?:\.\d+)?)\s*%", text)
        if not matches:
            return False, f"Missing {name} percentage citation (expected {target_value:.1f}%)"

        # Check if any percentage matches target within relative tolerance
        for m in matches:
            val = float(m)
            if self._is_within_tolerance(val, target_value):
                return True, "Valid"

        found_str = ", ".join(f"{m}%" for m in matches)
        return False, f"Contradictory {name} cited: found {found_str}, expected {target_value:.1f}% (exceeds {self.tolerance_pct*100:.0f}% tolerance)"

    def _verify_metric_unit(
        self,
        text: str,
        target_value: float,
        unit_pattern: str,
        name: str,
    ) -> Tuple[bool, str]:
        """Verifies if metric with unit in text matches target within 1% relative tolerance."""
        pattern = rf"(\d+(?:\.\d+)?)\s*{unit_pattern}"
        matches = re.findall(pattern, text, flags=re.IGNORECASE)
        if not matches:
            return False, f"Missing {name} citation (expected {target_value:.1f})"

        for m in matches:
            val = float(m)
            if self._is_within_tolerance(val, target_value):
                return True, "Valid"

        found_str = ", ".join(matches)
        return False, f"Contradictory {name} cited: found {found_str}, expected {target_value:.1f} (exceeds {self.tolerance_pct*100:.0f}% tolerance)"

    def _is_within_tolerance(self, claimed: float, actual: float) -> bool:
        """Calculates relative error: |claimed - actual| / max(actual, 1e-4) <= tolerance_pct."""
        if actual == 0.0:
            return abs(claimed) <= 1e-3
        rel_error = abs(claimed - actual) / abs(actual)
        return rel_error <= self.tolerance_pct

    def _check_hallucinated_outcomes(self, text: str, facts: FactPack) -> Tuple[bool, str]:
        """Detects exaggerated, contradicted, or misclassified match events."""
        lower = text.lower()
        evt_type = facts.event_type.lower()

        # Reject goal claims if event is not a goal
        if evt_type != "goal":
            # Strip benign spatial / target compounds (e.g. "towards goal", "goal kick", "goalkeeper")
            cleaned = re.sub(r"\b(?:towards|on|facing|at)\s+goal\b", "", lower)
            cleaned = re.sub(r"\bgoal\s*(?:kick|line|mouth|post|area|keeper)\b", "", cleaned)

            # 1. Scoring verbs asserting a goal was scored
            if re.search(r"\b(scored|scores|scoring|netted|netting)\b", cleaned):
                return True, f"Hallucinated event: Narrative claimed a goal occurred on a '{evt_type}' event."

            # 2. Goal nouns, screamer assertions, or goal net/corner finish claims
            if (
                re.search(r"\b(goals?|screamer)\b", cleaned)
                or "⚽" in lower
                or "back of the net" in lower
                or "into the bottom corner" in lower
                or "into the top corner" in lower
                or "opened the scoring" in lower
                or "opens the scoring" in lower
            ):
                return True, f"Hallucinated event: Narrative claimed a goal occurred on a '{evt_type}' event."

        # If event is a goal, reject pass misclassification and require goal identification
        if evt_type == "goal":
            pass_phrases = ["pass straight to", "executed an incisive", "pass to", "completed a", "threaded a"]
            if any(p in lower for p in pass_phrases) and "scored" not in lower and "goal" not in lower:
                return True, "Hallucinated event: Goal event misclassified as a pass."
            goal_identifiers = ["goal", "scored", "screamer", "strike", "finish", "netted"]
            if not any(term in lower for term in goal_identifiers):
                return True, "Missing event grounding: Goal event was not recognized as a goal."

        # Reject pass misclassification on tackles, turnovers, interceptions, fouls
        if evt_type in ("tackle", "turnover", "interception", "foul"):
            pass_indicators = [
                r"\bpass\s+straight\s+to\b",
                r"\bcompleted\s+a\s+(?:\w+\s+)?pass\b",
                r"\bexecuted\s+an?\s+(?:\w+\s+)?pass\b",
                r"\bthreaded\s+a\s+(?:\w+\s+)?pass\b",
                r"\bdelivering\s+a\s+(?:\w+\s+)?pass\b",
                r"\bpass(?:ed|ing)?\s+to\b",
                r"\blinked\s+with\b",
            ]
            if any(re.search(pat, lower) for pat in pass_indicators):
                return True, f"Hallucinated event: {evt_type.capitalize()} event misclassified as a pass."

        # A card event must describe the card that was actually shown
        if evt_type == "card":
            kind = (facts.sub_type or "").lower()
            sent_off = re.search(r"\b(sent\s+off|red\s+card|dismiss(?:ed|al)|straight\s+red)\b", lower)
            if kind == "yellow_card" and sent_off:
                return True, "Hallucinated event: a yellow card was described as a dismissal."
            if kind in ("red_card", "second_yellow") and not sent_off:
                return True, "Missing event grounding: the dismissal was not described."

        # Reject disciplinary card claims if not a card event
        if evt_type not in ("card", "red_card", "yellow_card"):
            card_patterns = [
                r"\b(?:red|yellow)\s+card\b",
                r"\bsent\s+off\b",
                r"\bdismissed\s+by\s+(?:the\s+)?referee\b",
                r"\b(?:shown|issued|received|given)\s+a\s+(?:red|yellow)\s+card\b",
                r"\bstraight\s+red\b",
                r"\bbooked\s+by\s+(?:the\s+)?referee\b",
                r"\bmarching\s+orders\b",
            ]
            if any(re.search(pat, lower) for pat in card_patterns):
                return True, f"Hallucinated event: Disciplinary card sanction claimed on '{evt_type}' event without card sanction."

        # Reject penalty claims if not a penalty event
        if evt_type not in ("penalty", "foul"):
            penalty_patterns = [
                r"\b(?:awarded|conceded|won|earned)\s+(?:a\s+)?penalty\b",
                r"\bpenalty\s+(?:kick\s+)?awarded\b",
                r"\bpoints?\s+to\s+the\s+(?:penalty\s+)?spot\b",
                r"\bspot[\s-]kick\s+awarded\b",
            ]
            if any(re.search(pat, lower) for pat in penalty_patterns):
                return True, f"Hallucinated event: Penalty award claimed on '{evt_type}' event."

        # Reject save claims on non-shot/non-goal events
        if evt_type not in ("shot", "goal"):
            save_patterns = [
                r"\b(?:crucial|heroic|superb|fingertip|miraculous|stunning)?\s*save\s+to\s+deny\b",
                r"\bgoalkeeper\s+save\b",
                r"\bpulled\s+off\s+a\s+(?:\w+\s+)?save\b",
            ]
            if any(re.search(pat, lower) for pat in save_patterns):
                return True, f"Hallucinated event: Goalkeeper save claimed on '{evt_type}' event."

        return False, ""
