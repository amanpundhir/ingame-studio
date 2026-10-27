"""The Match Analyst only knows the match up to the current clock, and answers in the viewer's persona."""

import json
import os

from backend.agents.analyst_agent import INSTRUCTIONS, PERSONA_VOICE, MatchAnalystAgent
from backend.math_engine import MatchAnalyticsTracker
from backend.mcp_server import InGameMCPServer

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _events():
    with open(os.path.join(ROOT, "data", "synthetic_events.json"), encoding="utf-8") as handle:
        return json.load(handle)


def _live_source_at(clock_limit_sec):
    """A live match that has played only up to ``clock_limit_sec`` (first-half clock, mm:ss)."""
    played = [
        e for e in _events()
        if e["period"] == 1 and int(e["clock"].split(":")[0]) * 60 + int(e["clock"].split(":")[1]) <= clock_limit_sec
    ]
    tracker = MatchAnalyticsTracker()
    for event in played:
        tracker.record_event(event)
    clock = f"{clock_limit_sec // 60:02d}:{clock_limit_sec % 60:02d}"
    return lambda: {"tracker": tracker, "events": played, "clock": clock, "status": "LIVE",
                    "score": tracker.get_match_stats().get("score", {"home": 0, "away": 0})}


def test_mcp_tools_describe_the_match_so_far_not_the_whole_match():
    early = InGameMCPServer(live_source=_live_source_at(10 * 60))
    late = InGameMCPServer(live_source=_live_source_at(44 * 60))

    early_overview = early.get_match_analytics_overview()
    late_overview = late.get_match_analytics_overview()

    assert early_overview["match_clock"] == "10:00" and early_overview["match_status"] == "LIVE"
    # Fewer passes had been played at minute 10 than at minute 44.
    assert early_overview["passes"]["home"]["total"] < late_overview["passes"]["home"]["total"]

    early_recap = early.get_match_recap()
    assert early_recap["final_score"]["home"] == 0 and early_recap["final_score"]["away"] == 0
    assert early_recap["match_status"] == "LIVE"


def test_analyst_moment_sentence_carries_clock_and_score():
    analyst = MatchAnalystAgent(
        mcp_server=InGameMCPServer(live_source=_live_source_at(600)),
        live_context=lambda: {"clock": "34:10", "status": "LIVE", "score": {"home": 1, "away": 0}, "events": []},
    )
    moment = analyst._moment()
    assert "34:10" in moment["sentence"] and moment["score"] == "1-0"

    not_started = MatchAnalystAgent(mcp_server=None, live_context=lambda: {"clock": "00:00", "status": "NOT_STARTED", "score": {}})
    assert "not kicked off" in not_started._moment()["sentence"]

    over = MatchAnalystAgent(mcp_server=None, live_context=lambda: {"clock": "94:30", "status": "FT", "score": {"home": 3, "away": 1}})
    assert "full time" in over._moment()["sentence"].lower()


def test_club_persona_is_told_which_side_it_supports():
    away = MatchAnalystAgent._sides_sentence("club", "Harbourside City")
    home = MatchAnalystAgent._sides_sentence("club", "Northbridge Lions")
    assert "'away' is Harbourside City" in away and "supports Harbourside City, which is the 'away' side" in away
    assert "supports Northbridge Lions, which is the 'home' side" in home
    # Other personas get the team mapping but no allegiance.
    assert "supports" not in MatchAnalystAgent._sides_sentence("tactical", "Harbourside City")


def test_each_persona_has_its_own_voice_and_the_club_one_names_the_club():
    assert set(PERSONA_VOICE) == {"tactical", "casual", "club", "fantasy"}
    assert len(set(PERSONA_VOICE.values())) == 4
    assert "{club}" in PERSONA_VOICE["club"]
    assert "never mention" in INSTRUCTIONS.lower() or "Never mention" in INSTRUCTIONS


def test_recent_events_tool_only_returns_events_played_so_far():
    played = [e for e in _events() if e["period"] == 1][:60]
    analyst = MatchAnalystAgent(
        mcp_server=None, live_context=lambda: {"clock": "10:00", "status": "LIVE", "score": {}, "events": played}
    )
    calls = []
    tools = {fn.__name__: fn for fn in analyst._tools(calls)}
    rows = json.loads(tools["get_recent_events"](limit=50))
    assert rows and all(row["clock"] <= max(e["clock"] for e in played) for row in rows)
    assert calls and calls[0]["tool"] == "get_recent_events"
