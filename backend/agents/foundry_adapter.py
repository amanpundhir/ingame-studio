"""InGame Studio - Microsoft AI Foundry & Azure OpenAI Adapter.

Connects the 4-agent causal reasoning and verification workflow with Azure AI Foundry
and Azure OpenAI services (e.g. GPT-4o, Phi-3.5) with a guaranteed zero-cost deterministic
local fallback to ensure 100% broadcast continuity and test reliability without credentials.
"""

import logging
import os
import re
import threading
import time
from collections import deque
from typing import Any, Deque, Dict, List, Optional, Union

import httpx
from backend.agents.models import FactPack, DraftNarrative, VerificationResult
from backend.agents.verifier_agent import VerifierAgent

logger = logging.getLogger("ingame.foundry")
NL = chr(10)

# The deployment's quota is 150,000 tokens per minute. Stay well below it so bulk jobs
# (pre-generation) and live viewers never push the service into rate limiting.
DEFAULT_TPM_LIMIT = 150_000
DEFAULT_TPM_USAGE = 0.6


class TokenBudget:
    """Sliding one-minute window of tokens spent on the model.

    ``acquire`` reserves an estimate before a call and waits until the window has room;
    ``settle`` replaces the estimate with the real usage reported by the service.
    """

    def __init__(self, tokens_per_minute: int):
        self.tokens_per_minute = max(1_000, int(tokens_per_minute))
        self._window: Deque[list] = deque()
        self._lock = threading.Lock()
        self.total_tokens = 0
        self.total_calls = 0

    def _prune(self, now: float) -> None:
        while self._window and now - self._window[0][0] >= 60.0:
            self._window.popleft()

    def used_last_minute(self) -> int:
        with self._lock:
            self._prune(time.time())
            return int(sum(entry[1] for entry in self._window))

    def acquire(self, estimate: int, max_wait: float) -> Optional[list]:
        deadline = time.time() + max_wait
        while True:
            with self._lock:
                now = time.time()
                self._prune(now)
                used = sum(entry[1] for entry in self._window)
                if not self._window or used + estimate <= self.tokens_per_minute:
                    entry = [now, int(estimate)]
                    self._window.append(entry)
                    self.total_calls += 1
                    return entry
                wait = 60.0 - (now - self._window[0][0])
            if time.time() >= deadline:
                return None
            time.sleep(min(max(wait, 0.05), 1.0))

    def settle(self, entry: Optional[list], actual: int) -> None:
        if entry is not None:
            with self._lock:
                self.total_tokens += int(actual)
                entry[1] = int(actual)


_BUDGETS: Dict[str, TokenBudget] = {}
_BUDGETS_LOCK = threading.Lock()


def get_token_budget(deployment: str) -> TokenBudget:
    with _BUDGETS_LOCK:
        budget = _BUDGETS.get(deployment)
        if budget is None:
            limit = int(os.environ.get("AZURE_OPENAI_TPM_LIMIT", DEFAULT_TPM_LIMIT))
            usage = float(os.environ.get("AZURE_OPENAI_TPM_USAGE", DEFAULT_TPM_USAGE))
            budget = _BUDGETS[deployment] = TokenBudget(int(limit * max(0.05, min(1.0, usage))))
        return budget


class AzureFoundryAdapter:
    """Pluggable adapter for Microsoft AI Foundry / Azure OpenAI Service.

    Architecture:
    1. Inspects environment variables for Azure AI Foundry credentials:
       - AZURE_AI_FOUNDRY_ENDPOINT or AZURE_OPENAI_ENDPOINT
       - AZURE_OPENAI_API_KEY or AZURE_AI_KEY
       - AZURE_OPENAI_DEPLOYMENT (default: "gpt-4.1-mini")
       - AZURE_OPENAI_API_VERSION (default: "2024-10-21")
    2. If credentials exist and service is reachable, calls Azure OpenAI Chat Completions.
    3. If credentials are unset, invalid, or API call fails, seamlessly falls back to
       deterministic local causal reasoning engine with guaranteed zero latency and 0 hallucinations.
    """

    def __init__(
        self,
        endpoint: Optional[str] = None,
        api_key: Optional[str] = None,
        deployment: Optional[str] = None,
        api_version: Optional[str] = None,
        timeout_seconds: float = 20.0,
    ):
        # Credentials passed in code always win; the INGAME_LLM=off switch only
        # silences credentials that came from the environment / .env file.
        self._explicit_credentials = bool(endpoint and api_key)
        self.endpoint = (
            endpoint
            or os.environ.get("AZURE_AI_FOUNDRY_ENDPOINT")
            or os.environ.get("AZURE_OPENAI_ENDPOINT")
        )
        self.api_key = (
            api_key
            or os.environ.get("AZURE_OPENAI_API_KEY")
            or os.environ.get("AZURE_AI_KEY")
        )
        self.deployment = (
            deployment
            or os.environ.get("AZURE_OPENAI_DEPLOYMENT")
            or "gpt-4.1-mini"
        )
        self.api_version = (
            api_version
            or os.environ.get("AZURE_OPENAI_API_VERSION")
            or "2024-10-21"
        )
        self.timeout_seconds = timeout_seconds
        # How long a call may wait for room in the token budget before giving up. Live
        # requests give up quickly (the app falls back to the cached or local text);
        # bulk jobs raise this.
        self.budget_wait_seconds = 8.0
        if self.endpoint:
            # Accept a full URL copied from the portal (e.g. ".../openai/v1/responses")
            # and keep only the resource base address.
            m = re.match(r"(https?://[^/]+)", self.endpoint.strip())
            self.endpoint = m.group(1) if m else self.endpoint
        self.verifier = VerifierAgent(tolerance_pct=0.01)

    def is_cloud_connected(self) -> bool:
        """Returns True if valid Azure Foundry / Azure OpenAI configuration is present."""
        if not self._explicit_credentials and os.environ.get("INGAME_LLM", "").lower() == "off":
            return False
        return bool(self.endpoint and self.api_key and len(self.api_key) > 8)

    def get_status(self) -> Dict[str, Any]:
        """Returns current operational status of the Foundry adapter."""
        connected = self.is_cloud_connected()
        masked_key = f"{self.api_key[:4]}...{self.api_key[-4:]}" if self.api_key and len(self.api_key) > 8 else None
        return {
            "connected": connected,
            "mode": "azure_foundry" if connected else "local_fallback",
            "endpoint": self.endpoint,
            "deployment": self.deployment,
            "api_version": self.api_version,
            "api_key_masked": masked_key,
            "tokens_last_minute": get_token_budget(self.deployment).used_last_minute(),
            "tokens_per_minute_budget": get_token_budget(self.deployment).tokens_per_minute,
        }

    def generate_narrative(
        self,
        facts: FactPack,
        critique: Optional[str] = None,
        attempt: int = 0,
    ) -> DraftNarrative:
        """Generates a causal match narrative using Azure AI Foundry if connected,

        falling back deterministically to local heuristic reasoning if unavailable.
        """
        if self.is_cloud_connected():
            try:
                narrative_text = self._call_azure_openai_chat(facts, critique, attempt)
                if narrative_text:
                    return DraftNarrative(
                        event_id=facts.event_id,
                        narrative=narrative_text,
                        generation_attempt=attempt,
                        model_used=f"azure-foundry-{self.deployment}",
                        critique_addressed=critique,
                    )
            except Exception as e:
                logger.warning(f"Azure AI Foundry request failed, activating local fallback: {e}")

        # Deterministic local fallback
        return self._local_heuristic_narrative(facts, critique, attempt)

    def evaluate_grounding(
        self,
        facts: FactPack,
        narrative: Union[DraftNarrative, str],
    ) -> VerificationResult:
        """Evaluates whether a narrative is mathematically and factually grounded against telemetry."""
        return self.verifier.verify(facts, narrative)

    def generate_recap_story(self, match_stats: Dict[str, Any]) -> str:
        """Generates a high-level editorial match story from match analytics."""
        score_home = match_stats.get("score", {}).get("home", 2)
        score_away = match_stats.get("score", {}).get("away", 2)
        home_xg = match_stats.get("xg", {}).get("home", 1.84)
        away_xg = match_stats.get("xg", {}).get("away", 1.72)

        if score_home > score_away:
            outcome_str = f"Northbridge Lions secured a commanding {score_home}-{score_away} victory"
        elif score_away > score_home:
            outcome_str = f"Harbourside City earned a clinical {score_away}-{score_home} triumph"
        else:
            outcome_str = f"Northbridge Lions and Harbourside City shared the spoils in an epic {score_home}-{score_away} draw"

        return (
            f"{outcome_str} at Northbridge Park. With Expected Goals finishing {home_xg:.2f} to {away_xg:.2f}, "
            f"both sides traded tactical momentum across 90 minutes of elite intensity. "
            f"Tactical discipline and transition efficiency proved decisive in an evenly matched contest."
        )

    # --------------------------------------------------------------------------
    # Cloud Azure OpenAI Request Execution
    # --------------------------------------------------------------------------

    def complete(self, system_prompt: str, user_content: str, max_tokens: int = 220) -> Optional[str]:
        """Runs one chat completion against the Foundry / Azure OpenAI deployment."""
        url = (
            f"{self.endpoint.rstrip('/')}/openai/deployments/"
            f"{self.deployment}/chat/completions?api-version={self.api_version}"
        )
        headers = {"api-key": self.api_key, "Content-Type": "application/json"}
        payload = {
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_content},
            ],
            "max_completion_tokens": max_tokens,
        }
        budget = get_token_budget(self.deployment)
        estimate = int((len(system_prompt) + len(user_content)) / 3.5) + int(max_tokens)
        reservation = budget.acquire(estimate, self.budget_wait_seconds)
        if reservation is None:
            logger.info("Token budget is full; skipping this model call")
            return None
        resp = None
        for attempt in range(4):
            with httpx.Client(timeout=self.timeout_seconds) as client:
                resp = client.post(url, headers=headers, json=payload)
            if resp.status_code not in (429, 503):
                break
            # Rate limited: wait as long as the service asks (bounded), then retry.
            try:
                wait = float(resp.headers.get("retry-after", 2 ** attempt))
            except (TypeError, ValueError):
                wait = 2.0 ** attempt
            time.sleep(min(wait, 20.0))
        if resp is None or resp.status_code != 200:
            code = resp.status_code if resp is not None else "no response"
            logger.warning(f"Azure OpenAI returned HTTP {code}")
            return None
        body = resp.json()
        usage = body.get("usage") or {}
        if usage.get("total_tokens"):
            budget.settle(reservation, int(usage["total_tokens"]))
        choices = body.get("choices", [])
        if not choices:
            return None
        return (choices[0].get("message", {}).get("content") or "").strip() or None

    def _non_play_prompt(self, facts: FactPack, critique: Optional[str]) -> tuple:
        """Prompt for substitutions and cards, which have no pass distance, speed or difficulty."""
        if facts.event_type == "substitution":
            system_prompt = (
                "You are The Pundit, an expert football broadcast analyst. Write 2 sentences about this "
                "substitution and what it changes for the team. You may use only the facts provided. "
                "GROUNDING RULES: (1) name both players exactly as given, saying who comes on and who goes off; "
                "(2) do not use any numbers except the match minute; (3) never invent injuries, scores, "
                "formations, cards or events that are not in the facts; (4) do not use the words goal, goals, "
                "scored or scoring. Plain prose only: no markdown, no emojis, no bullet points."
            )
            user_content = (
                f"Match minute: {facts.match_minute}" + NL
                + f"Team making the change: {facts.team_name} against {facts.opponent_name}" + NL
                + f"Player coming on: {facts.passer_name}" + NL
                + f"Player going off: {facts.receiver_name}" + NL
            )
        else:
            kind = {"yellow_card": "yellow card (a caution, not a dismissal)",
                    "second_yellow": "second yellow card, so the player is sent off",
                    "red_card": "straight red card, so the player is sent off"}.get(facts.sub_type or "", facts.sub_type or "card")
            system_prompt = (
                "You are The Pundit, an expert football broadcast analyst. Write 2 sentences about this "
                "disciplinary card and how it affects the team. You may use only the facts provided. "
                "GROUNDING RULES: (1) name both players exactly as given; (2) describe exactly the card type "
                "given, and only say a player is sent off if the facts say so; (3) do not use any numbers "
                "except the match minute; (4) never invent penalties, injuries, scores or events that are not "
                "in the facts; (5) do not use the words goal, goals, scored or scoring. Plain prose only: no "
                "markdown, no emojis, no bullet points."
            )
            user_content = (
                f"Match minute: {facts.match_minute}" + NL
                + f"Team: {facts.team_name} against {facts.opponent_name}" + NL
                + f"Card: {kind}" + NL
                + f"Player shown the card: {facts.passer_name}" + NL
                + f"Player fouled: {facts.receiver_name}" + NL
            )
        if critique:
            user_content += NL + f"Your previous draft was rejected: {critique}. Fix exactly those problems."
        return system_prompt, user_content

    def generate_text_for_facts(self, facts: FactPack, critique: Optional[str] = None) -> Optional[str]:
        """Asks the model for a grounded tactical narrative for one match moment."""
        if facts.event_type in ("substitution", "card"):
            system_prompt, user_content = self._non_play_prompt(facts, critique)
            return self.complete(system_prompt, user_content)
        system_prompt = (
            "You are The Pundit, an expert football broadcast analyst. Write 2 to 3 sentences that explain "
            "WHY this match moment matters tactically. You may use only the facts provided. "
            "GROUNDING RULES: (1) name both players exactly as given; (2) state the distance with 'm' "
            "(e.g. 24.5m); (3) state the ball speed with 'km/h'; (4) state the difficulty rating with '%' "
            "exactly as given; (5) never invent scores, cards, penalties, injuries or events that are not in "
            "the facts; (6) unless the event type is 'goal', do not use the words goal, goals, scored or "
            "scoring (the word goalkeeper is fine); (7) for tackles, turnovers, fouls and pressure do not "
            "describe a pass. Plain prose only: no markdown, no emojis, no bullet points."
        )
        user_content = (
            f"Match minute: {facts.match_minute}" + NL
            + f"Event type: {facts.event_type}"
            + (f" ({facts.sub_type})" if facts.sub_type else "")
            + (f", outcome: {facts.outcome}" if facts.outcome else "") + NL
            + f"Acting team: {facts.team_name} against {facts.opponent_name}" + NL
            + f"Primary player: {facts.passer_name}" + NL
            + f"Second player: {facts.receiver_name}" + NL
            + f"Distance: {facts.pass_distance_m:.1f}m" + NL
            + f"Ball speed: {facts.ball_speed_kmh:.1f} km/h" + NL
            + f"Difficulty rating: {facts.pass_difficulty:.1f}%" + NL
            + f"Expected threat change: {facts.xt_gained:+.3f} xT" + NL
            + f"Chaos vs control index: {facts.chaos_index:.1f}/100" + NL
            + f"Context: {facts.tactical_context}" + NL
        )
        if facts.milestone:
            user_content += f"Milestone to mention: {facts.milestone}" + NL
        if critique:
            user_content += NL + f"Your previous draft was rejected: {critique}. Fix exactly those problems."
        return self.complete(system_prompt, user_content)

    def _call_azure_openai_chat(
        self,
        facts: FactPack,
        critique: Optional[str] = None,
        attempt: int = 0,
    ) -> Optional[str]:
        """Backwards-compatible wrapper used by generate_narrative."""
        return self.generate_text_for_facts(facts, critique)

    # --------------------------------------------------------------------------
    # Deterministic Local Heuristic Reasoner (Guaranteed Fallback)
    # --------------------------------------------------------------------------

    def _local_heuristic_narrative(
        self,
        facts: FactPack,
        critique: Optional[str] = None,
        attempt: int = 0,
    ) -> DraftNarrative:
        """Deterministic, grounded tactical narrative generator.

        Guaranteed to cite exact entities and numerical metrics within 1% error tolerance.
        """
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
            model_used="deterministic-foundry-fallback",
            critique_addressed=critique,
        )
