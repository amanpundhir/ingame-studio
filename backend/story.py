"""InGame Studio - Model-written match stories and tactical explanations.

Both the match story (per persona and language) and the tactical explanation of
a moment are written by the Foundry model from a short fact sheet, checked so
that every number in the text comes from that fact sheet, and cached. If the
model is unavailable or its text fails the check, a factual local template is
returned instead and nothing is cached.
"""

import hashlib
import re
import threading
from typing import Any, Dict, List, Optional

PROMPT_VERSION = "story-v2"

LANGUAGE_NAMES = {
    "en": "English", "es": "Spanish",
}

PERSONA_BRIEF = {
    "tactical": "a tactical analyst: precise, data-led, mention expected goals, control and pressure",
    "casual": "an excited broadcaster for casual fans: simple words, energy, no jargon",
    "club": "a passionate supporter of {club}: partisan and emotional, always from {club}'s point of view",
    "fantasy": "a fantasy football scout: focus on who produced points, bonus points and what it means for managers",
}

_ARABIC_DIGITS = str.maketrans("٠١٢٣٤٥٦٧٨٩", "0123456789")
_NUMBER = re.compile(r"\d+(?:[.,]\d+)?")


def _numbers(text: str) -> List[float]:
    values = []
    for token in _NUMBER.findall(text.translate(_ARABIC_DIGITS)):
        try:
            values.append(float(token.replace(",", ".")))
        except ValueError:
            continue
    return values


def ungrounded_numbers(text: str, facts_text: str) -> List[float]:
    """Numbers in text that do not appear in the fact sheet (tiny whole counts are allowed)."""
    allowed = _numbers(facts_text)
    bad: List[float] = []
    for value in _numbers(text):
        if value <= 11 and float(value).is_integer():
            continue
        if not any(abs(value - known) <= 0.51 for known in allowed):
            bad.append(value)
    return bad


def numbers_are_grounded(text: str, facts_text: str) -> bool:
    """True when every number in text appears in the fact sheet (or is a tiny count)."""
    return not ungrounded_numbers(text, facts_text)


# A rejected text goes back to the model once or twice with a critique, exactly like the
# per-event narratives in the Pundit/Verifier loop.
MAX_STORY_RETRIES = 2


_key_locks: Dict[str, threading.Lock] = {}
_key_locks_guard = threading.Lock()


def _lock_for(key: str) -> threading.Lock:
    with _key_locks_guard:
        return _key_locks.setdefault(key, threading.Lock())


def _cache_key(*parts: str) -> str:
    return hashlib.sha256("|".join((PROMPT_VERSION,) + parts).encode("utf-8")).hexdigest()[:32]


def _complete_cached(service: Any, key: str, system: str, user: str, facts_text: str, max_tokens: int) -> Optional[Dict[str, str]]:
    """Cache first, then one live (single-flight) model call. Returns text and source or None."""
    if service is None or not service.enabled:
        return None
    cached = service.cache.get(key)
    if cached:
        return {"text": cached, "source": "azure_foundry_cache"}
    with _lock_for(key):  # single flight: simultaneous viewers share one model call
        cached = service.cache.get(key)
        if cached:
            return {"text": cached, "source": "azure_foundry_cache"}
        text = None
        critique = ""
        for _attempt in range(MAX_STORY_RETRIES + 1):
            try:
                text = service.adapter.complete(system, user + critique, max_tokens=max_tokens)
            except Exception:
                text = None
            service.live_calls += 1
            if not text:  # model error or token budget full: do not keep asking
                break
            bad = ungrounded_numbers(text, facts_text)
            if not bad:
                service.cache.put(key, text, f"azure-foundry-{service.adapter.deployment}")
                return {"text": text, "source": "azure_foundry_live"}
            shown = ", ".join(f"{value:g}" for value in bad[:6])
            critique = (
                f"\n\nREVIEWER CRITIQUE: your previous text used numbers that are not in the facts ({shown}). "
                "Rewrite it using only numbers that appear in the facts above."
            )
            text = None
        service.live_failures += 1
        return None


def story_fact_sheet(recap: Dict[str, Any]) -> str:
    score = recap.get("final_score", {})
    xg = recap.get("xg_balance", {})
    totals = recap.get("team_totals", {})
    motm = recap.get("man_of_the_match", {})
    lines = [
        f"Fixture: {score.get('home_team')} {score.get('home')}-{score.get('away')} {score.get('away_team')}",
        f"Status: {recap.get('status')} at {recap.get('clock')}",
        f"Expected goals: {score.get('home_team')} {float(xg.get('home_xg', 0)):.2f}, {score.get('away_team')} {float(xg.get('away_xg', 0)):.2f}",
        f"Shots: {xg.get('home_shots', 0)} vs {xg.get('away_shots', 0)}; on target {totals.get('shots_on_target', {}).get('home', 0)} vs {totals.get('shots_on_target', {}).get('away', 0)}",
        f"Possession %: {totals.get('possession_pct', {}).get('home', 0)} vs {totals.get('possession_pct', {}).get('away', 0)}",
        f"Pass accuracy %: {totals.get('pass_accuracy_pct', {}).get('home', 0)} vs {totals.get('pass_accuracy_pct', {}).get('away', 0)}",
        f"Fouls: {totals.get('fouls', {}).get('home', 0)} vs {totals.get('fouls', {}).get('away', 0)}; "
        f"yellow cards {totals.get('yellow_cards', {}).get('home', 0)} vs {totals.get('yellow_cards', {}).get('away', 0)}; "
        f"red cards {totals.get('red_cards', {}).get('home', 0)} vs {totals.get('red_cards', {}).get('away', 0)}; "
        f"substitutions {totals.get('substitutions', {}).get('home', 0)} vs {totals.get('substitutions', {}).get('away', 0)}",
        f"Control-versus-chaos index (average): {recap.get('tactical_entropy', {}).get('average_cci', 0)}",
    ]
    for point in recap.get("turning_points", [])[:6]:
        lines.append(f"Moment at {point.get('minute')}: {point.get('title')} ({point.get('team')}), score after {point.get('score_after')}")
    if motm.get("name"):
        lines.append(
            f"Player of the match: {motm['name']} ({motm.get('team')}), rating {motm.get('rating')}, "
            f"{motm.get('goals', 0)} goals, {motm.get('fantasy_bonus_points', 0)} bonus points"
        )
    return "\n".join(lines)


def template_story(recap: Dict[str, Any], language: str) -> str:
    summaries = recap.get("localized_summaries", {})
    base = summaries.get(language) or recap.get("match_story", "")
    return base


def generate_story(recap: Dict[str, Any], persona: str, language: str, club: str, service: Any) -> Dict[str, str]:
    facts = story_fact_sheet(recap)
    language = language if language in LANGUAGE_NAMES else "en"
    brief = PERSONA_BRIEF.get(persona, PERSONA_BRIEF["tactical"]).format(club=club)
    system = (
        f"You are {brief}. Write a match story of 80 to 120 words in {LANGUAGE_NAMES[language]}. "
        "Use ONLY the facts provided. Do not invent players, scores, cards, injuries, quotes, venues or managers. "
        "Every number you write must appear in the facts. Plain prose, no markdown, no emojis."
    )
    club_key = club if persona == "club" else ""
    result = _complete_cached(
        service, _cache_key("story", persona, language, club_key, facts), system, facts, facts, max_tokens=420,
    )
    if result:
        return {"text": result["text"], "source": result["source"], "persona": persona, "language": language}
    return {"text": template_story(recap, language), "source": "local_template", "persona": persona, "language": language}


def moment_fact_sheet(moment: Dict[str, Any], event: Dict[str, Any]) -> str:
    metrics = event.get("tactical_metrics") or {}
    return "\n".join([
        f"Moment type: {moment.get('turning_point')}",
        f"Clock: {moment.get('clock')}",
        f"Team in possession: {event.get('team')}; player: {event.get('player_name')}; other player: {event.get('secondary_player_name')}",
        f"Event: {event.get('event_type')} ({event.get('outcome')}) - {event.get('context')}",
        f"Ball speed: {metrics.get('ball_speed_kmh')} km/h; difficulty rating: {metrics.get('pass_difficulty')}%; expected threat change: {metrics.get('xt_gained')}",
        f"Defending team: {moment.get('defending_team')}",
        f"Defensive line depth from own goal: {moment.get('defensive_line_depth_m')} m",
        f"Offside line at x = {moment.get('offside_line_x')} m",
        f"Defenders pressing the ball within 18 m: {moment.get('pressing_players')}",
        f"Open passing options: {len(moment.get('passing_lanes', []))}; riskiest lane risk: "
        f"{max([lane['risk'] for lane in moment.get('passing_lanes', [])] or [0])}%",
    ])


def template_explanation(moment: Dict[str, Any], event: Dict[str, Any]) -> str:
    return (
        f"{event.get('context') or moment.get('description')} "
        f"{moment.get('defending_team')} held a defensive line {moment.get('defensive_line_depth_m')} m from their own goal "
        f"with the offside line at x = {moment.get('offside_line_x')} m, and {moment.get('pressing_players')} defenders were "
        f"within 18 m of the ball."
    )


PERSONA_KEYS = ("tactical", "casual", "club", "fantasy")


def _persona_note_fallback(persona: str, moment: Dict[str, Any], event: Dict[str, Any]) -> str:
    who = event.get("player_name") or "The player"
    team = event.get("team")
    metrics = event.get("tactical_metrics") or {}
    if persona == "tactical":
        return (
            f"{moment.get('turning_point')} at {moment.get('clock')}: {moment.get('defending_team')} had a line "
            f"{moment.get('defensive_line_depth_m')} m from goal over {moment.get('compactness_m2'):.0f} m2."
        )
    if persona == "casual":
        return f"{who} makes the difference for {team} at {moment.get('clock')} and the defence is stretched."
    if persona == "club":
        return f"{who} and {team} take control here at {moment.get('clock')}."
    return f"{who} ({team}): expected threat change {metrics.get('xt_gained')} at {moment.get('clock')}."


def analyse_moment(moment: Dict[str, Any], event: Dict[str, Any], service: Any, language: str = "en") -> Dict[str, Any]:
    """Takeaway, structural reading and four persona notes for one tactical moment."""
    from concurrent.futures import ThreadPoolExecutor

    facts = moment_fact_sheet(moment, event)
    language = language if language in LANGUAGE_NAMES else "en"
    lang_name = LANGUAGE_NAMES[language]
    metrics = event.get("tactical_metrics") or {}
    team = event.get("team")

    takeaway_system = (
        f"You are a football tactical analyst writing in {lang_name}. In 2 to 3 sentences explain why this moment "
        "matters: team shape, defensive line height, pressing and the passing options. Use ONLY the facts provided and "
        "quote the key numbers with their units. Do not invent players, scores or events. Plain prose, no markdown."
    )

    def note(persona: str) -> Dict[str, str]:
        brief = PERSONA_BRIEF[persona].format(club=team or "the team")
        system = (
            f"You are {brief}. Write {lang_name}, 1 to 2 sentences about this moment. Use ONLY the facts provided; "
            "every number must appear in them. Do not invent players, scores or events. Plain prose."
        )
        result = _complete_cached(service, _cache_key("moment-note", persona, language, facts), system, facts, facts, 140)
        if result:
            return {"text": result["text"], "source": result["source"]}
        return {"text": _persona_note_fallback(persona, moment, event), "source": "local_template"}

    with ThreadPoolExecutor(max_workers=5) as pool:
        takeaway_future = pool.submit(
            _complete_cached, service, _cache_key("moment", language, facts), takeaway_system, facts, facts, 220
        )
        note_futures = {persona: pool.submit(note, persona) for persona in PERSONA_KEYS}
        takeaway = takeaway_future.result()
        notes = {persona: future.result() for persona, future in note_futures.items()}

    takeaway_text = takeaway["text"] if takeaway else template_explanation(moment, event)
    sources = {n["source"] for n in notes.values()} | {takeaway["source"] if takeaway else "local_template"}
    model_written = any(src.startswith("azure_foundry") for src in sources)
    defending = moment.get("defending_team")
    breakdown = {
        "structural_weaknesses": (
            f"{defending} defended with a back line {moment.get('defensive_line_depth_m')} m from their "
            f"own goal and the offside line at x = {moment.get('offside_line_x')} m. The widest gap between two back-line "
            f"players was {moment.get('line_gap_m')} m, and {moment.get('pressing_players')} defenders were within 18 m of the ball."
        ),
        "player_decisions": (
            f"{event.get('player_name')} ({team}) acted on {event.get('secondary_player_name') or 'the opponent'}: "
            f"{event.get('context') or event.get('event_type')} Ball speed {metrics.get('ball_speed_kmh')} km/h, "
            f"difficulty rating {metrics.get('pass_difficulty')}%, expected threat change {metrics.get('xt_gained')}."
        ),
        "team_shape": (
            f"{defending} outfield block covered {moment.get('compactness_m2'):.0f} m2 "
            f"with the line {moment.get('defensive_line_depth_m')} m from goal."
        ),
        "key_takeaway": takeaway_text,
        "grounding_score": 100,
        "pdr": float(metrics.get("pass_difficulty") or 0.0),
        "depth_m": float(moment.get("defensive_line_depth_m") or 0.0),
        "compactness_m2": float(moment.get("compactness_m2") or 0.0),
        "press_pct": round(min(1.0, int(moment.get("pressing_players") or 0) / 5.0) * 100),
        "persona_notes": {persona: notes[persona]["text"] for persona in PERSONA_KEYS},
        "source": "azure_foundry" if model_written else "local_template",
    }
    return {"analysis": takeaway_text, "breakdown": breakdown}
