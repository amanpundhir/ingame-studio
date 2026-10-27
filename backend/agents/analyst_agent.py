"""InGame Studio - the Match Analyst: an Agent Framework agent that uses MCP tools.

The four pipeline agents explain moments as they happen. The Match Analyst answers a
viewer's own question about the match ("who ran the most?", "how did the red card change
the game?"). It is a Microsoft Agent Framework ``Agent`` running on the Foundry model, and
it gets its facts only by calling tools: the InGame MCP server's analytics tools (match
overview, player metrics, match recap, control-vs-chaos index) plus a roster lookup.

Its answer is then checked the same way every other text is: every number must come from
a tool result. A rejected answer is retried once with a critique; if it still fails, the
viewer gets a plain statement that the answer could not be verified, never an unverified one.
"""

import json
import logging
import re
import time
from typing import Any, Callable, Dict, List, Optional

from backend.agents.af_workflow import _run_blocking
from backend.agents.foundry_adapter import AzureFoundryAdapter, get_token_budget
from backend.moments import AWAY_NAME, HOME_NAME
from backend.story import numbers_are_grounded, LANGUAGE_NAMES

logger = logging.getLogger("ingame.analyst")

INSTRUCTIONS = (
    "You are the InGame Studio Match Analyst, talking to a viewer WHILE THE MATCH IS BEING PLAYED. "
    "{moment} Answer in {language}, in at most 90 words, in this voice: {voice}. "
    "You know NOTHING about the match except what the tools return, and the tools only describe the match up "
    "to the current clock. Call the tools you need before answering. Use only names and numbers that a tool "
    "returned. Never mention, predict or hint at anything after the current clock. If the tools do not contain "
    "the answer yet, say so. Plain prose, no markdown, no emojis."
)

# How the viewer's chosen persona shapes the answer. The club persona is told which club the
# viewer supports, so the answer takes that side (while staying factual).
PERSONA_VOICE = {
    "tactical": (
        "a tactical analyst. Be precise and data-led: lean on expected threat, field tilt, pressing, the "
        "control-versus-chaos index and shape, and explain why things are happening."
    ),
    "casual": (
        "an excited broadcaster talking to a casual fan. Use simple words and energy, no jargon, "
        "and focus on the big moments and who is shining."
    ),
    "club": (
        "a passionate supporter of {club}. Speak as one of the {club} fans: call {club} 'we' and 'us' and "
        "the opponent 'they'. Be emotional and partisan in tone, celebrate {club}'s good moments and "
        "feel their setbacks, but never bend or invent a fact in their favour."
    ),
    "fantasy": (
        "a fantasy football scout. Focus on who is producing points, bonus points, key passes, ratings and "
        "cards, and say what it means for a manager's picks."
    ),
}


class MatchAnalystAgent:
    """Answers viewer questions with an Agent Framework agent that calls MCP tools."""

    def __init__(
        self,
        mcp_server: Any,
        adapter: Optional[AzureFoundryAdapter] = None,
        rosters: Optional[List[Dict[str, Any]]] = None,
        live_context: Optional[Callable[[], Dict[str, Any]]] = None,
    ):
        """``live_context`` returns ``{"clock", "status", "score", "events"}`` for the match right now."""
        self.mcp = mcp_server
        self.adapter = adapter or AzureFoundryAdapter()
        self.rosters = rosters or []
        self.live_context = live_context

    # ------------------------------------------------------------------
    @property
    def available(self) -> bool:
        try:
            import agent_framework  # noqa: F401
            import agent_framework_openai  # noqa: F401
        except ImportError:
            return False
        return self.adapter.is_cloud_connected()

    def _tools(self, calls: List[Dict[str, Any]]) -> List[Callable[..., Any]]:
        """The tools the agent may call. Each call and its result are recorded in ``calls``."""

        def record(name: str, args: Dict[str, Any], result: Any) -> str:
            text = json.dumps(result, ensure_ascii=False, default=str)
            calls.append({"tool": name, "arguments": args, "result": text})
            return text[:6000]

        def get_match_analytics_overview() -> str:
            """Team-level match statistics: score, possession, expected goals, shots, passes, tackles."""
            return record("get_match_analytics_overview", {}, self.mcp.call_tool("get_match_analytics_overview", {}))

        def get_match_recap() -> str:
            """Full-match report: final score, turning points, man of the match, expected-goals balance."""
            return record("get_match_recap", {}, self.mcp.call_tool("get_match_recap", {}))

        def get_player_metrics(player_id: str) -> str:
            """Physical and tactical statistics for one player. player_id looks like NBL_07 or HSC_09."""
            return record(
                "get_player_metrics", {"player_id": player_id},
                self.mcp.call_tool("get_player_metrics", {"player_id": player_id}),
            )

        def find_player(name: str) -> str:
            """Find a player id from (part of) a name. Use it before get_player_metrics."""
            needle = name.strip().lower()
            found = [
                {"player_id": p["player_id"], "name": p["name"], "team": p.get("team"), "role": p.get("role")}
                for p in self.rosters if needle and needle in str(p.get("name", "")).lower()
            ][:5]
            return record("find_player", {"name": name}, found)

        def get_recent_events(limit: int = 8) -> str:
            """The most recent match events so far (goals, cards, substitutions, shots, tackles), newest last."""
            events = list((self.live_context() or {}).get("events") or []) if self.live_context else []
            keep = [e for e in events if e.get("event_type") in ("goal", "shot", "card", "substitution", "tackle", "foul")]
            rows = [
                {"clock": e.get("clock"), "type": e.get("event_type"), "sub_type": e.get("sub_type"),
                 "team": e.get("team"), "player": e.get("player_name"), "outcome": e.get("outcome")}
                for e in keep[-max(1, min(int(limit), 20)):]
            ]
            return record("get_recent_events", {"limit": limit}, rows)

        return [get_match_analytics_overview, get_match_recap, get_player_metrics, find_player, get_recent_events]

    @staticmethod
    def _sides_sentence(persona: str, club: str) -> str:
        """Tells the agent which team the tools call 'home' and 'away', and whom the viewer supports."""
        text = (
            f"In the tool data, 'home' is {HOME_NAME} and 'away' is {AWAY_NAME}; always attribute a statistic "
            "to the right team."
        )
        if persona == "club" and club:
            side = "home" if club == HOME_NAME else "away" if club == AWAY_NAME else ""
            if side:
                text += (
                    f" The viewer supports {club}, which is the '{side}' side, so 'we' and 'us' mean the "
                    f"'{side}' numbers and 'they' means the other side."
                )
        return text

    def _moment(self) -> Dict[str, Any]:
        """Clock, status and score of the match right now."""
        ctx = (self.live_context() or {}) if self.live_context else {}
        score = ctx.get("score") or {}
        clock = ctx.get("clock") or "00:00"
        status = ctx.get("status") or "LIVE"
        text = f"{score.get('home', 0)}-{score.get('away', 0)}"
        if status == "NOT_STARTED":
            sentence = "The match has not kicked off yet (00:00); nothing has happened."
        elif status == "FT":
            sentence = f"The match is over: full time at {clock}, final score {text}."
        else:
            sentence = f"The match clock is {clock} and the score is {text}."
        return {"clock": clock, "status": status, "score": text, "sentence": sentence}

    async def _run_agent(self, question: str, language: str, persona: str, calls: List[Dict[str, Any]], extra: str = "", club: str = "", moment: str = "") -> str:
        from agent_framework import Agent
        from agent_framework_openai import OpenAIChatCompletionClient

        client = OpenAIChatCompletionClient(
            model=self.adapter.deployment,
            api_key=self.adapter.api_key,
            azure_endpoint=self.adapter.endpoint,
            api_version=self.adapter.api_version,
        )
        agent = Agent(
            client,
            INSTRUCTIONS.format(
                moment=moment, language=LANGUAGE_NAMES.get(language, "English"),
                voice=PERSONA_VOICE.get(persona, PERSONA_VOICE["tactical"]).format(club=club or "the home side"),
            ),
            name="match-analyst",
            tools=self._tools(calls),
        )
        response = await agent.run(question + extra)
        return (response.text or "").strip()

    # ------------------------------------------------------------------
    def ask(self, question: str, language: str = "en", persona: str = "tactical", club: str = "") -> Dict[str, Any]:
        """Answers one question about the match as it stands now.

        Returns the answer, the tools used, whether it was verified, and the clock and score it is based on.
        """
        question = (question or "").strip()[:400]
        language = language if language in LANGUAGE_NAMES else "en"
        moment = self._moment()
        base = {
            "question": question, "language": language, "persona": persona, "club": club if persona == "club" else "",
            "tools_used": [], "verified": False, "as_of_clock": moment["clock"], "as_of_score": moment["score"],
            "match_status": moment["status"],
        }
        if not question:
            return {**base, "answer": "", "source": "empty_question"}
        if not self.available:
            return {**base, "answer": "The Match Analyst needs the Azure AI Foundry connection, which is not configured.",
                    "source": "unavailable"}

        budget = get_token_budget(self.adapter.deployment)
        reservation = budget.acquire(6000, 8.0)
        if reservation is None:
            return {**base, "answer": "The analyst is busy right now. Please try again in a moment.", "source": "busy"}

        calls: List[Dict[str, Any]] = []
        started = time.time()
        critique = ""
        answer = ""
        try:
            for attempt in range(2):  # one answer, and one retry with a critique
                answer = _run_blocking(
                    lambda: self._run_agent(
                        question, language, persona, calls, critique, club,
                        moment["sentence"] + " " + self._sides_sentence(persona, club),
                    )
                )
                # The clock and score given to the agent are facts too.
                facts_text = moment["sentence"] + " " + " ".join(call["result"] for call in calls)
                if answer and calls and numbers_are_grounded(answer, facts_text):
                    return {
                        **base, "answer": answer, "verified": True, "source": "agent_framework+mcp",
                        "tools_used": [{"tool": c["tool"], "arguments": c["arguments"]} for c in calls],
                        "attempts": attempt + 1, "seconds": round(time.time() - started, 1),
                    }
                critique = (
                    "\n\nYour previous answer used numbers that no tool returned, or you answered without calling "
                    "a tool. Call the tools, then answer using only the numbers they return."
                )
        except Exception as exc:  # noqa: BLE001 - never raise into the API
            logger.warning("Match Analyst failed: %s", exc)
            return {**base, "answer": "The analyst could not answer right now.", "source": "error"}

        return {
            **base,
            "answer": "I could not verify an answer to that against the match data, so I am not giving one.",
            "source": "unverified",
            "tools_used": [{"tool": c["tool"], "arguments": c["arguments"]} for c in calls],
            "attempts": 2,
        }
