"""InGame Studio - Agent 4: The Studio Director (Host & Personalizer).

Transforms verified tactical insights into 4 customized broadcast personas:
1. Casual Fan (high-energy, plain-English, emojis)
2. Tactical Purist (Expected Threat xT, compact lines, numerical depth)
3. Club Loyalist (passionate, partisan heroism, club pride)
4. Player-Lock Fantasy (sprint speed, off-ball runs, bonus points projection)

Formats uppercase lower-third ticker straps, generates spatial
telestrator vector payloads, and produces English and Spanish localizations.
"""

from typing import Any, Dict, Optional
from backend.agents.models import (
    FactPack,
    PersonaOutputs,
    TelestratorVectors,
    VerifiedInsight,
)


class StudioDirectorAgent:
    """Agent 4: The Studio Director.

    Broadcast showrunner adapting factual tactical intelligence for diverse
    audiences, international syndication, and visual telestration overlays.
    """

    FRAME_RATE = 25
    # Seconds an overlay stays on screen, by event type.
    OVERLAY_SECONDS = {"goal": 12.0, "card": 9.0, "substitution": 9.0, "shot": 8.0, "default": 6.0}

    def __init__(self, channel_branding: str = "InGame Studio"):
        self.channel_branding = channel_branding

    def adapt_personas(self, facts: FactPack, verified_narrative: str) -> PersonaOutputs:
        """Adapts verified intelligence into 4 distinct viewer personas and ticker.

        Args:
            facts: Authoritative FactPack.
            verified_narrative: Verified causal story approved by Agent 3 or fallback.

        Returns:
            PersonaOutputs with 4 narratives and formatted broadcast ticker.
        """
        dist_str = f"{facts.pass_distance_m:.1f}m"
        pdr_str = f"{facts.pass_difficulty:.1f}%"
        speed_str = f"{facts.ball_speed_kmh:.1f} km/h"
        xt_sign = "+" if facts.xt_gained >= 0 else ""
        xt_str = f"{xt_sign}{facts.xt_gained:.2f} xT"
        evt_type = facts.event_type.lower()
        milestone_callout = f" [Milestone: {facts.milestone}]" if facts.milestone else ""

        if evt_type == "goal":
            casual_story = (
                f"⚽ GOAL! SENSATIONAL FINISH! At {facts.match_minute}, {facts.passer_name} scores an absolute screamer "
                f"for {facts.team_name}, beating {facts.receiver_name} with a {dist_str} rocket clocked at {speed_str}! "
                f"Matchday magic at its finest! 🔥🎯{milestone_callout}"
            )
            tactical_analysis = (
                f"Tactical Breakdown [{facts.match_minute}]: {facts.passer_name} converts clinical goal opportunity "
                f"for {facts.team_name} from {dist_str} at {speed_str}. Beating {facts.receiver_name} under a {pdr_str} "
                f"execution difficulty rating, the strike yields {xt_str} and alters match state.{milestone_callout}"
            )
            club_loyalist_story = (
                f"PURE JUBILATION FOR {facts.team_name.upper()}! In minute {facts.match_minute}, {facts.passer_name} "
                f"delivers pure ecstasy, blasting a {dist_str} missile past {facts.receiver_name} at {speed_str}! "
                f"That is what {facts.team_name} courage is all about! Unbelievable pride! Come on {facts.team_name}!{milestone_callout}"
            )
            player_lock_story = (
                f"Fantasy Matchday Scout [{facts.match_minute}]: GOAL! {facts.passer_name} scores from {dist_str} at {speed_str} "
                f"({pdr_str} difficulty). Generates {xt_str} and secures +6 Fantasy points with provisional +3 BPS bonus points!"
            )
        elif evt_type == "shot":
            if (facts.outcome and "save" in facts.outcome) or (facts.sub_type and "save" in facts.sub_type):
                casual_story = (
                    f"🧤 WHAT A SAVE! At {facts.match_minute}, {facts.receiver_name} pulls off a heroic save to deny "
                    f"{facts.passer_name}'s {dist_str} bullet clocked at {speed_str}! Incredible reflexes between the sticks! 🚀🔥{milestone_callout}"
                )
                tactical_analysis = (
                    f"Tactical Breakdown [{facts.match_minute}]: Goalkeeper save by {facts.receiver_name} negating "
                    f"{facts.passer_name}'s {dist_str} strike at {speed_str}. Facing {pdr_str} shot difficulty and {xt_str} threat, "
                    f"the intervention preserves defensive equity.{milestone_callout}"
                )
                club_loyalist_story = (
                    f"Heroic goalkeeping! In minute {facts.match_minute}, {facts.receiver_name} stands tall under fire, "
                    f"parrying away {facts.passer_name}'s {dist_str} effort at {speed_str}! Outstanding defensive resilience!{milestone_callout}"
                )
                player_lock_story = (
                    f"Fantasy Matchday Scout [{facts.match_minute}]: Shot on target by {facts.passer_name} saved by {facts.receiver_name} "
                    f"({speed_str}, {pdr_str} difficulty). GK earns +1 save point, denying {xt_str} threat."
                )
            else:
                casual_story = (
                    f"🚀 HUGE EFFORT! At {facts.match_minute}, {facts.passer_name} pulls the trigger from {dist_str} at {speed_str} "
                    f"against {facts.receiver_name}! Heart in mouths! 🔥{milestone_callout}"
                )
                tactical_analysis = (
                    f"Tactical Breakdown [{facts.match_minute}]: Shot attempt by {facts.passer_name} from {dist_str} clocked "
                    f"at {speed_str} ({pdr_str} difficulty). Created {xt_str} penetrating {facts.opponent_name} penalty box.{milestone_callout}"
                )
                club_loyalist_story = (
                    f"Attacking courage from {facts.team_name}! In minute {facts.match_minute}, {facts.passer_name} takes responsibility, "
                    f"testing {facts.receiver_name} with a {dist_str} drive at {speed_str}! Relentless ambition!{milestone_callout}"
                )
                player_lock_story = (
                    f"Fantasy Matchday Scout [{facts.match_minute}]: {facts.passer_name} unleashes {dist_str} shot at {speed_str} "
                    f"({pdr_str} difficulty). Generates {xt_str} attacking threat, hunting bonus points."
                )
        elif evt_type == "tackle":
            casual_story = (
                f"💥 CRUNCHING CHALLENGE! At {facts.match_minute}, {facts.passer_name} stops {facts.receiver_name} in their tracks "
                f"with a thunderous tackle clocked at {speed_str}! Defensive perfection! 🛡️⚡{milestone_callout}"
            )
            tactical_analysis = (
                f"Tactical Breakdown [{facts.match_minute}]: High-leverage tackle won by {facts.passer_name} against {facts.receiver_name} "
                f"over {dist_str} at {speed_str}. Navigating {pdr_str} tackle difficulty, it recovers possession ({xt_str}).{milestone_callout}"
            )
            club_loyalist_story = (
                f"Warrior spirit from {facts.team_name}! In minute {facts.match_minute}, {facts.passer_name} puts their body on the line "
                f"against {facts.receiver_name} with an emphatic {dist_str} tackle at {speed_str}! That's our pride and passion!{milestone_callout}"
            )
            player_lock_story = (
                f"Fantasy Matchday Scout [{facts.match_minute}]: {facts.passer_name} wins crucial tackle against {facts.receiver_name} "
                f"({pdr_str} difficulty, {speed_str}). Adds defensive intervention credits and BPS bonus equity."
            )
        elif evt_type in ("turnover", "interception"):
            casual_story = (
                f"⚡ TURNOVER ALERT! At {facts.match_minute}, {facts.passer_name} intercepts the ball from {facts.receiver_name} "
                f"at {speed_str}! Fast break opportunity! 🔥🏃{milestone_callout}"
            )
            tactical_analysis = (
                f"Tactical Breakdown [{facts.match_minute}]: Possession regained by {facts.passer_name} dispossessing {facts.receiver_name} "
                f"over {dist_str} at {speed_str}. {pdr_str} difficulty, flipping Expected Threat by {xt_str}.{milestone_callout}"
            )
            club_loyalist_story = (
                f"Sharp reading of the game from {facts.team_name}! In minute {facts.match_minute}, {facts.passer_name} steps in "
                f"ahead of {facts.receiver_name} at {speed_str}! Relentless pressing!{milestone_callout}"
            )
            player_lock_story = (
                f"Fantasy Matchday Scout [{facts.match_minute}]: {facts.passer_name} forces turnover from {facts.receiver_name} "
                f"({speed_str}, {pdr_str} difficulty, {xt_str}). Boosts baseline recovery BPS."
            )
        elif evt_type == "foul":
            casual_story = (
                f"🛑 WHISTLE BLOWN! At {facts.match_minute}, {facts.passer_name} halts {facts.receiver_name} with a tactical foul "
                f"at {speed_str}! High stakes on the pitch! ⚠️{milestone_callout}"
            )
            tactical_analysis = (
                f"Tactical Breakdown [{facts.match_minute}]: Tactical foul by {facts.passer_name} on {facts.receiver_name} "
                f"over {dist_str} at {speed_str} ({pdr_str} difficulty). Stops {xt_str} transition progression.{milestone_callout}"
            )
            club_loyalist_story = (
                f"Total commitment from {facts.team_name}! In minute {facts.match_minute}, {facts.passer_name} breaks up "
                f"{facts.receiver_name}'s counter at {speed_str}! Defending the badge with heart and courage!{milestone_callout}"
            )
            player_lock_story = (
                f"Fantasy Matchday Scout [{facts.match_minute}]: Foul conceded by {facts.passer_name} on {facts.receiver_name} "
                f"({speed_str}, {pdr_str} difficulty). -1 foul penalty on disciplinary ledger."
            )
        elif evt_type == "substitution":
            casual_story = (
                f"🔄 FRESH LEGS! At {facts.match_minute}, {facts.team_name} make a change: {facts.passer_name} comes on "
                f"for {facts.receiver_name}!{milestone_callout}"
            )
            tactical_analysis = (
                f"Tactical Breakdown [{facts.match_minute}]: {facts.team_name} substitution. {facts.passer_name} replaces "
                f"{facts.receiver_name}, changing the shape of the side against {facts.opponent_name}.{milestone_callout}"
            )
            club_loyalist_story = (
                f"Decision time for {facts.team_name}! In minute {facts.match_minute}, {facts.passer_name} is sent on to "
                f"replace {facts.receiver_name}. Come on {facts.team_name}!{milestone_callout}"
            )
            player_lock_story = (
                f"Fantasy Matchday Scout [{facts.match_minute}]: {facts.passer_name} is on for {facts.receiver_name}. "
                f"{facts.receiver_name}'s minutes stop here, so check bonus potential before banking points.{milestone_callout}"
            )
        elif evt_type == "card":
            kind = (facts.sub_type or "yellow_card").lower()
            if kind == "yellow_card":
                casual_story = (
                    f"🟨 BOOKED! At {facts.match_minute}, {facts.passer_name} goes into the referee's book for a foul on "
                    f"{facts.receiver_name}.{milestone_callout}"
                )
                tactical_analysis = (
                    f"Tactical Breakdown [{facts.match_minute}]: {facts.passer_name} ({facts.team_name}) is cautioned for a foul on "
                    f"{facts.receiver_name} and must now tackle with care.{milestone_callout}"
                )
                club_loyalist_story = (
                    f"The referee shows {facts.passer_name} a yellow card at {facts.match_minute}. {facts.team_name} must stay "
                    f"disciplined!{milestone_callout}"
                )
                player_lock_story = (
                    f"Fantasy Matchday Scout [{facts.match_minute}]: yellow card for {facts.passer_name} (-1 point).{milestone_callout}"
                )
            else:
                casual_story = (
                    f"🟥 SENT OFF! At {facts.match_minute}, {facts.passer_name} sees red for a foul on "
                    f"{facts.receiver_name}, and {facts.team_name} are down to ten!{milestone_callout}"
                )
                tactical_analysis = (
                    f"Tactical Breakdown [{facts.match_minute}]: {facts.passer_name} is dismissed after a foul on "
                    f"{facts.receiver_name}. {facts.team_name} lose a player and must reorganise their shape.{milestone_callout}"
                )
                club_loyalist_story = (
                    f"A heavy blow for {facts.team_name}: {facts.passer_name} is sent off at {facts.match_minute}. "
                    f"The team now has to dig deep!{milestone_callout}"
                )
                player_lock_story = (
                    f"Fantasy Matchday Scout [{facts.match_minute}]: red card for {facts.passer_name} (-3 points). "
                    f"Minutes stop here.{milestone_callout}"
                )
        elif evt_type == "pressure":
            pressure_context = facts.tactical_context or f"{facts.passer_name} closes down {facts.receiver_name}"
            pressure_result = (facts.outcome or "applied").replace("_", " ")
            casual_story = (
                f"⏱️ THE PRESS IS ON! At {facts.match_minute}, {facts.passer_name} closes down {facts.receiver_name} "
                f"for {facts.team_name}, forcing the opposition to react. {pressure_context}.{milestone_callout}"
            )
            tactical_analysis = (
                f"Tactical Breakdown [{facts.match_minute}]: {facts.team_name} applies {facts.sub_type or 'open-play'} pressure "
                f"through {facts.passer_name} against {facts.receiver_name}. The pressure was {pressure_result}; "
                f"{facts.defenders_in_corridor} nearby defenders and a CCI of {facts.chaos_index:.1f} describe the local context. "
                f"{pressure_context}.{milestone_callout}"
            )
            club_loyalist_story = (
                f"Relentless work from {facts.team_name}! {facts.passer_name} leads the press on {facts.receiver_name}, "
                f"making every touch uncomfortable. {pressure_context}.{milestone_callout}"
            )
            player_lock_story = (
                f"Fantasy Matchday Scout [{facts.match_minute}]: {facts.passer_name} contributes to {facts.team_name}'s "
                f"press against {facts.receiver_name}. Pressure outcome: {pressure_result}; match context CCI {facts.chaos_index:.1f}."
            )
        else:
            # Standard pass events
            casual_story = (
                f"⚡ WHAT A MOMENT! At {facts.match_minute}, {facts.passer_name} uncorks an electric {dist_str} pass "
                f"straight to {facts.receiver_name} clocked at {speed_str}! Breaking through {facts.defenders_in_corridor} "
                f"opponents with ice in their veins, that is Matchday magic! 🔥🎯{milestone_callout}"
            )
            tactical_analysis = (
                f"Tactical Breakdown [{facts.match_minute}]: {facts.passer_name} identifies an inverted passing channel, "
                f"progressing possession {dist_str} to {facts.receiver_name} at {speed_str}. Navigating an exacting {pdr_str} "
                f"Pass Difficulty Rating and {facts.defenders_in_corridor} corridor defenders, the action yields {xt_str} and "
                f"decompresses the {facts.opponent_name} mid-block structure.{milestone_callout}"
            )
            club_loyalist_story = (
                f"Pure heart and quality from {facts.team_name}! In minute {facts.match_minute}, {facts.passer_name} "
                f"shows supreme courage under fire, piercing the {facts.opponent_name} lines with a laser-focused {dist_str} "
                f"ball to {facts.receiver_name} at {speed_str}! That's the passion and fight we stand for! Come on {facts.team_name}!{milestone_callout}"
            )
            player_lock_story = (
                f"Fantasy Matchday Scout [{facts.match_minute}]: {facts.passer_name} registers a prime key progression to "
                f"{facts.receiver_name} ({dist_str} pass, {pdr_str} difficulty, {speed_str}). Producing {xt_str}, this high-threat "
                f"sequence adds +3 BPS baseline points. Essential differential asset in current game-week form!"
            )

        # Broadcast lower-third ticker strap
        lower_third_ticker = self.generate_ticker(facts, verification_status="VERIFIED")

        return PersonaOutputs(
            casual_story=casual_story,
            tactical_analysis=tactical_analysis,
            club_loyalist_story=club_loyalist_story,
            player_lock_story=player_lock_story,
            lower_third_ticker=lower_third_ticker,
        )

    def generate_ticker(self, facts: FactPack, verification_status: str = "VERIFIED") -> str:
        """Formats an uppercase live broadcast ticker strap."""
        xt_sign = "+" if facts.xt_gained >= 0 else ""
        evt_type = facts.event_type.lower()
        milestone_strap = f" | MILESTONE: {facts.milestone.upper()}" if facts.milestone else ""

        if evt_type == "goal":
            ticker = (
                f"INGAME LIVE | {facts.match_minute} | "
                f"GOAL! {facts.passer_name.upper()} ({facts.team_name.upper()}) | "
                f"{facts.ball_speed_kmh:.1f} KM/H FROM {facts.pass_distance_m:.1f}M | "
                f"DIFFICULTY: {facts.pass_difficulty:.1f}% | "
                f"XT GAINED: {xt_sign}{facts.xt_gained:.2f} | "
                f"STATUS: {verification_status.upper()}{milestone_strap}"
            )
        elif evt_type == "shot":
            sub = "SHOT SAVED" if (facts.outcome and "save" in facts.outcome) or (facts.sub_type and "save" in facts.sub_type) else "SHOT"
            ticker = (
                f"INGAME LIVE | {facts.match_minute} | "
                f"{sub}: {facts.passer_name.upper()} ({facts.ball_speed_kmh:.1f} KM/H FROM {facts.pass_distance_m:.1f}M) | "
                f"DIFFICULTY: {facts.pass_difficulty:.1f}% | "
                f"STATUS: {verification_status.upper()}{milestone_strap}"
            )
        elif evt_type == "tackle":
            ticker = (
                f"INGAME LIVE | {facts.match_minute} | "
                f"TACKLE WON: {facts.passer_name.upper()} ON {facts.receiver_name.upper()} | "
                f"DIFFICULTY: {facts.pass_difficulty:.1f}% | "
                f"STATUS: {verification_status.upper()}{milestone_strap}"
            )
        elif evt_type in ("turnover", "interception"):
            ticker = (
                f"INGAME LIVE | {facts.match_minute} | "
                f"TURNOVER: {facts.passer_name.upper()} RECOVERS FROM {facts.receiver_name.upper()} | "
                f"DIFFICULTY: {facts.pass_difficulty:.1f}% | "
                f"STATUS: {verification_status.upper()}{milestone_strap}"
            )
        elif evt_type == "foul":
            ticker = (
                f"INGAME LIVE | {facts.match_minute} | "
                f"FOUL: {facts.passer_name.upper()} ON {facts.receiver_name.upper()} | "
                f"STATUS: {verification_status.upper()}{milestone_strap}"
            )
        elif evt_type == "substitution":
            ticker = (
                f"INGAME LIVE | {facts.match_minute} | SUBSTITUTION ({facts.team_name.upper()}): "
                f"{facts.passer_name.upper()} ON, {facts.receiver_name.upper()} OFF | "
                f"STATUS: {verification_status.upper()}{milestone_strap}"
            )
        elif evt_type == "card":
            card_label = {"yellow_card": "YELLOW CARD", "second_yellow": "SECOND YELLOW, SENT OFF", "red_card": "RED CARD"}.get(
                (facts.sub_type or "").lower(), "CARD"
            )
            ticker = (
                f"INGAME LIVE | {facts.match_minute} | {card_label}: {facts.passer_name.upper()} "
                f"({facts.team_name.upper()}) | STATUS: {verification_status.upper()}{milestone_strap}"
            )
        elif evt_type == "pressure":
            ticker = (
                f"INGAME LIVE | {facts.match_minute} | PRESSURE: {facts.passer_name.upper()} "
                f"CLOSES DOWN {facts.receiver_name.upper()} | {facts.sub_type or 'OPEN PLAY'} | "
                f"OUTCOME: {facts.outcome or 'APPLIED'} | CCI: {facts.chaos_index:.1f} | "
                f"STATUS: {verification_status.upper()}{milestone_strap}"
            )
        else:
            ticker = (
                f"INGAME LIVE | {facts.match_minute} | "
                f"{facts.passer_name.upper()} -> {facts.receiver_name.upper()} "
                f"({facts.pass_distance_m:.1f}M @ {facts.ball_speed_kmh:.1f} KM/H) | "
                f"PASS DIFFICULTY: {facts.pass_difficulty:.1f}% | "
                f"XT GAINED: {xt_sign}{facts.xt_gained:.2f} | "
                f"STATUS: {verification_status.upper()}{milestone_strap}"
            )
        return ticker.upper()

    def generate_telestrator(self, facts: FactPack) -> Dict[str, Any]:
        """Generates telestrator graphic vectors and pressure polygon annotations."""
        dx = facts.end_x - facts.start_x
        dy = facts.end_y - facts.start_y
        dist = facts.pass_distance_m

        # Perpendicular normal vector for corridor polygon
        if dist > 1e-4:
            nx = -dy / dist * 2.0
            ny = dx / dist * 2.0
        else:
            nx, ny = 0.0, 2.0

        corridor_polygon = [
            {"x": round(max(0.0, min(105.0, facts.start_x + nx)), 2), "y": round(max(0.0, min(68.0, facts.start_y + ny)), 2)},
            {"x": round(max(0.0, min(105.0, facts.end_x + nx)), 2), "y": round(max(0.0, min(68.0, facts.end_y + ny)), 2)},
            {"x": round(max(0.0, min(105.0, facts.end_x - nx)), 2), "y": round(max(0.0, min(68.0, facts.end_y - ny)), 2)},
            {"x": round(max(0.0, min(105.0, facts.start_x - nx)), 2), "y": round(max(0.0, min(68.0, facts.start_y - ny)), 2)},
        ]

        vectors = TelestratorVectors(
            start_x=round(facts.start_x, 2),
            start_y=round(facts.start_y, 2),
            end_x=round(facts.end_x, 2),
            end_y=round(facts.end_y, 2),
            distance_m=facts.pass_distance_m,
            corridor_width_m=4.0,
            cone_angle_deg=20.0,
            target_ring_radius_m=2.5,
            color_hex="#00ff87",  # vibrant green
            line_style="solid",
            pressure_polygon=corridor_polygon,
        )
        return vectors.model_dump()

    def generate_translations(self, facts: FactPack) -> Dict[str, Dict[str, str]]:
        """Generates the English and Spanish localization dictionary.

        Covers all 4 personas (casual, tactical, club/loyalist, player/fantasy) and the broadcast ticker.
        """
        xt_sign = "+" if facts.xt_gained >= 0 else ""
        dist = f"{facts.pass_distance_m:.1f}"
        speed = f"{facts.ball_speed_kmh:.1f}"
        pdr = f"{facts.pass_difficulty:.1f}"
        xt = f"{xt_sign}{facts.xt_gained:.2f}"
        evt_type = facts.event_type.lower()

        if evt_type == "goal":
            translations = {
                "en": {
                    "casual": f"⚽ GOAL! {facts.passer_name} scores an absolute stunner past {facts.receiver_name} at {speed} km/h from {dist}m! 🔥",
                    "tactical": f"Tactical Breakdown [{facts.match_minute}]: Goal converted by {facts.passer_name} ({speed} km/h, {dist}m). PDR: {pdr}%, Delta xT: {xt}.",
                    "club": f"Pure glory for {facts.team_name}! {facts.passer_name} scores an unbelievable goal!",
                    "player": f"Fantasy Scout: GOAL for {facts.passer_name}! +6 pts and bonus trajectory.",
                    "ticker": self.generate_ticker(facts, "VERIFIED"),
                },
                "es": {
                    "casual": f"⚽ ¡GOLAZO! ¡Al minuto {facts.match_minute}, {facts.passer_name} anota un gol espectacular superando a {facts.receiver_name} a {speed} km/h! 🔥",
                    "tactical": f"Análisis Táctico [{facts.match_minute}]: Gol de {facts.passer_name} ({speed} km/h, {dist}m). Dificultad: {pdr}%, xT: {xt}.",
                    "club": f"¡Orgullo total para {facts.team_name}! {facts.passer_name} anota un golazo inolvidable.",
                    "player": f"Fantasy Scout: ¡GOL de {facts.passer_name}! +6 puntos y puntos de bonificación.",
                    "ticker": f"INGAME EN VIVO | {facts.match_minute} | ¡GOL! {facts.passer_name.upper()} ({dist}M @ {speed} KM/H)",
                },
            }
        elif evt_type == "shot":
            translations = {
                "en": {
                    "casual": f"🚀 HUGE EFFORT! At {facts.match_minute}, {facts.passer_name} strikes from {dist}m at {speed} km/h! 🔥",
                    "tactical": f"Tactical Breakdown [{facts.match_minute}]: Shot attempt by {facts.passer_name} ({dist}m @ {speed} km/h). PDR: {pdr}%, threat xT: {xt}.",
                    "club": f"Attacking courage from {facts.team_name}! {facts.passer_name} fires a venomous drive.",
                    "player": f"Fantasy Scout: {facts.passer_name} registers shot on goal ({speed} km/h). Threat index {xt}.",
                    "ticker": self.generate_ticker(facts, "VERIFIED"),
                },
                "es": {
                    "casual": f"🚀 ¡DISPARO POTENTE! Al minuto {facts.match_minute}, {facts.passer_name} saca un cañonazo de {dist}m a {speed} km/h! 🔥",
                    "tactical": f"Análisis Táctico [{facts.match_minute}]: Remate de {facts.passer_name} ({dist}m a {speed} km/h). Dificultad: {pdr}%, xT: {xt}.",
                    "club": f"¡Ambición ofensiva de {facts.team_name}! Gran intento de {facts.passer_name}.",
                    "player": f"Fantasy Scout: Disparo a puerta de {facts.passer_name} ({speed} km/h). Genera {xt} xT.",
                    "ticker": f"INGAME EN VIVO | {facts.match_minute} | DISPARO: {facts.passer_name.upper()} ({dist}M @ {speed} KM/H)",
                },
            }
        elif evt_type == "tackle":
            translations = {
                "en": {
                    "casual": f"💥 CRUNCHING CHALLENGE! At {facts.match_minute}, {facts.passer_name} stops {facts.receiver_name} with an emphatic tackle! 🛡️⚡",
                    "tactical": f"Tactical Breakdown [{facts.match_minute}]: High-leverage tackle won by {facts.passer_name} against {facts.receiver_name}. PDR: {pdr}%, xT: {xt}.",
                    "club": f"Warrior spirit from {facts.team_name}! {facts.passer_name} puts in a heroic tackle on {facts.receiver_name}!",
                    "player": f"Fantasy Scout: {facts.passer_name} wins crucial tackle against {facts.receiver_name}. Defensive intervention credits.",
                    "ticker": self.generate_ticker(facts, "VERIFIED"),
                },
                "es": {
                    "casual": f"💥 ¡ENTRADA CONTUNDENTE! Al minuto {facts.match_minute}, {facts.passer_name} frena a {facts.receiver_name} con una gran entrada defensiva! 🛡️⚡",
                    "tactical": f"Análisis Táctico [{facts.match_minute}]: Entrada ganada por {facts.passer_name} ante {facts.receiver_name}. Dificultad: {pdr}%, xT: {xt}.",
                    "club": f"¡Espíritu guerrero de {facts.team_name}! {facts.passer_name} se deja la piel con una entrada decisiva.",
                    "player": f"Fantasy Scout: Entrada exitosa de {facts.passer_name} sobre {facts.receiver_name}. Puntos defensivos BPS.",
                    "ticker": f"INGAME EN VIVO | {facts.match_minute} | ENTRADA RECUPERADA: {facts.passer_name.upper()} SOBRE {facts.receiver_name.upper()}",
                },
            }
        elif evt_type in ("turnover", "interception"):
            translations = {
                "en": {
                    "casual": f"⚡ TURNOVER ALERT! At {facts.match_minute}, {facts.passer_name} intercepts the ball from {facts.receiver_name}! Fast break! 🔥🏃",
                    "tactical": f"Tactical Breakdown [{facts.match_minute}]: Possession regained by {facts.passer_name} dispossessing {facts.receiver_name}. PDR: {pdr}%, xT: {xt}.",
                    "club": f"Sharp reading of the game from {facts.team_name}! {facts.passer_name} steps in ahead of {facts.receiver_name}!",
                    "player": f"Fantasy Scout: {facts.passer_name} forces turnover from {facts.receiver_name}. Boosts baseline recovery BPS.",
                    "ticker": self.generate_ticker(facts, "VERIFIED"),
                },
                "es": {
                    "casual": f"⚡ ¡RECUPERACIÓN CLAVE! Al minuto {facts.match_minute}, {facts.passer_name} intercepta el balón ante {facts.receiver_name}! ¡Contraataque! 🔥🏃",
                    "tactical": f"Análisis Táctico [{facts.match_minute}]: Balón recuperado por {facts.passer_name} superando a {facts.receiver_name}. Dificultad: {pdr}%, xT: {xt}.",
                    "club": f"¡Presión asfixiante de {facts.team_name}! Gran anticipación de {facts.passer_name}.",
                    "player": f"Fantasy Scout: Recuperación de balón por {facts.passer_name} sobre {facts.receiver_name}. Puntos BPS.",
                    "ticker": f"INGAME EN VIVO | {facts.match_minute} | RECUPERACIÓN: {facts.passer_name.upper()} ANTE {facts.receiver_name.upper()}",
                },
            }
        elif evt_type == "foul":
            translations = {
                "en": {
                    "casual": f"🛑 WHISTLE BLOWN! At {facts.match_minute}, {facts.passer_name} halts {facts.receiver_name} with a tactical foul! ⚠️",
                    "tactical": f"Tactical Breakdown [{facts.match_minute}]: Tactical foul by {facts.passer_name} on {facts.receiver_name}. PDR: {pdr}%, stops transition {xt}.",
                    "club": f"Total commitment from {facts.team_name}! {facts.passer_name} breaks up the counter attack!",
                    "player": f"Fantasy Scout: Foul conceded by {facts.passer_name} on {facts.receiver_name}. Disciplinary ledger adjustment.",
                    "ticker": self.generate_ticker(facts, "VERIFIED"),
                },
                "es": {
                    "casual": f"🛑 ¡FALTA TÁCTICA! Al minuto {facts.match_minute}, {facts.passer_name} detiene la contra de {facts.receiver_name} con infracción táctica! ⚠️",
                    "tactical": f"Análisis Táctico [{facts.match_minute}]: Infracción táctica cometida por {facts.passer_name} sobre {facts.receiver_name}. Frena progresión {xt}.",
                    "club": f"¡Compromiso y entrega de {facts.team_name}! {facts.passer_name} frena el contraataque.",
                    "player": f"Fantasy Scout: Falta cometida por {facts.passer_name} sobre {facts.receiver_name}.",
                    "ticker": f"INGAME EN VIVO | {facts.match_minute} | FALTA: {facts.passer_name.upper()} SOBRE {facts.receiver_name.upper()}",
                },
            }
        elif evt_type == "substitution":
            translations = {
                "en": {
                    "casual": f"🔄 FRESH LEGS! At {facts.match_minute}, {facts.passer_name} comes on for {facts.receiver_name} at {facts.team_name}!",
                    "tactical": f"Tactical Breakdown [{facts.match_minute}]: {facts.team_name} replace {facts.receiver_name} with {facts.passer_name}.",
                    "club": f"A change for {facts.team_name}! {facts.passer_name} is on for {facts.receiver_name}.",
                    "player": f"Fantasy Scout: {facts.passer_name} is on for {facts.receiver_name}; minutes stop for the player coming off.",
                    "ticker": self.generate_ticker(facts, "VERIFIED"),
                },
                "es": {
                    "casual": f"🔄 ¡PIERNAS FRESCAS! Al minuto {facts.match_minute}, {facts.passer_name} entra por {facts.receiver_name} en {facts.team_name}!",
                    "tactical": f"Análisis Táctico [{facts.match_minute}]: {facts.team_name} sustituye a {facts.receiver_name} por {facts.passer_name}.",
                    "club": f"¡Cambio en {facts.team_name}! Entra {facts.passer_name} por {facts.receiver_name}.",
                    "player": f"Fantasy Scout: {facts.passer_name} entra por {facts.receiver_name}; el jugador sustituido ya no sumará minutos.",
                    "ticker": f"INGAME EN VIVO | {facts.match_minute} | CAMBIO ({facts.team_name.upper()}): ENTRA {facts.passer_name.upper()}, SALE {facts.receiver_name.upper()}",
                },
            }
        elif evt_type == "card":
            card_kind = (facts.sub_type or "yellow_card").lower()
            sent_off = card_kind != "yellow_card"
            translations = {
                "en": {
                    "casual": (
                        f"🟥 SENT OFF! At {facts.match_minute}, {facts.passer_name} sees red for a foul on {facts.receiver_name}!"
                        if sent_off else
                        f"🟨 BOOKED! At {facts.match_minute}, {facts.passer_name} is cautioned for a foul on {facts.receiver_name}."
                    ),
                    "tactical": (
                        f"Tactical Breakdown [{facts.match_minute}]: {facts.passer_name} is dismissed; {facts.team_name} are down to ten."
                        if sent_off else
                        f"Tactical Breakdown [{facts.match_minute}]: {facts.passer_name} ({facts.team_name}) is booked for a foul on {facts.receiver_name}."
                    ),
                    "club": (
                        f"A heavy blow for {facts.team_name}: {facts.passer_name} is sent off."
                        if sent_off else
                        f"{facts.passer_name} is booked. {facts.team_name} must stay disciplined!"
                    ),
                    "player": (
                        f"Fantasy Scout: red card for {facts.passer_name} (-3 points)."
                        if sent_off else
                        f"Fantasy Scout: yellow card for {facts.passer_name} (-1 point)."
                    ),
                    "ticker": self.generate_ticker(facts, "VERIFIED"),
                },
                "es": {
                    "casual": (
                        f"🟥 ¡EXPULSADO! Al minuto {facts.match_minute}, {facts.passer_name} ve la roja por una falta sobre {facts.receiver_name}."
                        if sent_off else
                        f"🟨 ¡AMARILLA! Al minuto {facts.match_minute}, {facts.passer_name} ve la tarjeta por una falta sobre {facts.receiver_name}."
                    ),
                    "tactical": (
                        f"Análisis Táctico [{facts.match_minute}]: {facts.passer_name} es expulsado; {facts.team_name} se queda con diez."
                        if sent_off else
                        f"Análisis Táctico [{facts.match_minute}]: {facts.passer_name} ({facts.team_name}) es amonestado por una falta sobre {facts.receiver_name}."
                    ),
                    "club": (
                        f"Golpe duro para {facts.team_name}: {facts.passer_name} es expulsado."
                        if sent_off else
                        f"{facts.passer_name} es amonestado. ¡{facts.team_name} debe mantener la disciplina!"
                    ),
                    "player": (
                        f"Fantasy Scout: tarjeta roja para {facts.passer_name} (-3 puntos)."
                        if sent_off else
                        f"Fantasy Scout: tarjeta amarilla para {facts.passer_name} (-1 punto)."
                    ),
                    "ticker": f"INGAME EN VIVO | {facts.match_minute} | {'EXPULSIÓN' if sent_off else 'TARJETA AMARILLA'}: {facts.passer_name.upper()} ({facts.team_name.upper()})",
                },
            }
        elif evt_type == "pressure":
            subtype = (facts.sub_type or "open-play pressure").replace("_", " ")
            outcome = (facts.outcome or "applied").replace("_", " ")
            translations = {
                "en": {
                    "casual": f"⏱️ THE PRESS IS ON! At {facts.match_minute}, {facts.passer_name} closes down {facts.receiver_name} for {facts.team_name}, forcing a quick decision!",
                    "tactical": f"Pressing phase [{facts.match_minute}]: {facts.passer_name} applies {subtype} pressure to {facts.receiver_name}; outcome: {outcome}. CCI: {facts.chaos_index:.1f}.",
                    "club": f"Relentless effort from {facts.team_name}! {facts.passer_name} leads the press and makes life difficult for {facts.receiver_name}.",
                    "player": f"Fantasy Scout: {facts.passer_name} contributes to the press on {facts.receiver_name}. Pressure outcome: {outcome}; CCI: {facts.chaos_index:.1f}.",
                    "ticker": self.generate_ticker(facts, "VERIFIED"),
                },
                "es": {
                    "casual": f"⏱️ ¡PRESIÓN INTENSA! En el minuto {facts.match_minute}, {facts.passer_name} encimó a {facts.receiver_name} para {facts.team_name} y le obligó a decidir rápido.",
                    "tactical": f"Fase de presión [{facts.match_minute}]: {facts.passer_name} aplica presión de tipo {subtype} sobre {facts.receiver_name}; resultado: {outcome}. CCI: {facts.chaos_index:.1f}.",
                    "club": f"¡Esfuerzo incansable de {facts.team_name}! {facts.passer_name} lidera la presión sobre {facts.receiver_name}.",
                    "player": f"Fantasy Scout: {facts.passer_name} participa en la presión sobre {facts.receiver_name}. Resultado: {outcome}; CCI: {facts.chaos_index:.1f}.",
                    "ticker": f"PRESIÓN | {facts.match_minute} | {facts.passer_name.upper()} ENCIERRA A {facts.receiver_name.upper()} | {subtype.upper()} | RESULTADO: {outcome.upper()} | CCI: {facts.chaos_index:.1f}",
                },
            }
        else:
            # Default / Pass localization
            translations = {
                "en": {
                    "casual": f"⚡ WHAT A MOMENT! {facts.passer_name} lasers a {dist}m pass to {facts.receiver_name} at {speed} km/h! 🔥",
                    "tactical": f"Tactical Breakdown [{facts.match_minute}]: {facts.passer_name} progresses {dist}m to {facts.receiver_name}. PDR: {pdr}%, Delta xT: {xt}.",
                    "club": f"Pure heart and pride from {facts.team_name}! {facts.passer_name} threads an exceptional pass.",
                    "player": f"Fantasy Scout: {facts.passer_name} generates {xt} xT with a key progression.",
                    "ticker": self.generate_ticker(facts, "VERIFIED"),
                },
                "es": {
                    "casual": f"⚡ ¡QUÉ JUGADA! Al minuto {facts.match_minute}, {facts.passer_name} conecta un pase espectacular de {dist}m con {facts.receiver_name} a {speed} km/h! 🔥",
                    "tactical": f"Análisis Táctico [{facts.match_minute}]: {facts.passer_name} progresa con un pase vertical de {dist}m hacia {facts.receiver_name}. Dificultad: {pdr}%, xT: {xt}.",
                    "club": f"¡Puro corazón y orgullo de {facts.team_name}! Gran jugada de {facts.passer_name}.",
                    "player": f"Fantasy Scout: {facts.passer_name} progresa y genera {xt} xT.",
                    "ticker": f"INGAME EN VIVO | {facts.match_minute} | {facts.passer_name.upper()} -> {facts.receiver_name.upper()} ({dist}M @ {speed} KM/H) | DIFICULTAD: {pdr}%",
                },
            }

        # Populate synonyms so any persona key lookup succeeds without undefined errors
        for lang, ldict in translations.items():
            if "club" in ldict and "loyalist" not in ldict:
                ldict["loyalist"] = ldict["club"]
            elif "loyalist" in ldict and "club" not in ldict:
                ldict["club"] = ldict["loyalist"]
            if "player" in ldict:
                ldict["fantasy"] = ldict["player"]
                ldict["player_lock"] = ldict["player"]
            elif "player_lock" in ldict:
                ldict["player"] = ldict["player_lock"]
                ldict["fantasy"] = ldict["player_lock"]

        return translations

    def create_verified_insight(
        self,
        facts: FactPack,
        verified_narrative: str,
        grounding_score: float,
        verification_status: str = "VERIFIED",
        retries_attempted: int = 0,
    ) -> VerifiedInsight:
        """Assembles the complete final VerifiedInsight broadcast artifact conforming to schema.json."""
        personas = self.adapt_personas(facts, verified_narrative)
        telestrator = self.generate_telestrator(facts)
        translations = self.generate_translations(facts)

        metrics = {
            "pass_distance_m": facts.pass_distance_m,
            "pass_difficulty": facts.pass_difficulty,
            "ball_speed_kmh": facts.ball_speed_kmh,
            "chaos_index": facts.chaos_index,
            "xt_gained": facts.xt_gained,
            "defenders_in_corridor": float(facts.defenders_in_corridor),
            "defenders_in_cone": float(facts.defenders_in_cone),
        }

        # Override ticker status if needed
        ticker = self.generate_ticker(facts, verification_status=verification_status)

        # Timing for a synchronised overlay: when the moment happened and how long to show it.
        duration_sec = self.OVERLAY_SECONDS.get(facts.event_type, self.OVERLAY_SECONDS["default"])
        start_frame = facts.frame_index
        end_frame = start_frame + int(round(duration_sec * self.FRAME_RATE)) if start_frame is not None else None

        return VerifiedInsight(
            event_id=facts.event_id,
            frame_index=start_frame,
            match_clock=facts.match_minute,
            period=facts.period,
            display_from_frame=start_frame,
            display_until_frame=end_frame,
            display_duration_sec=duration_sec,
            grounding_score=round(max(0.0, min(1.0, float(grounding_score))), 2),
            verification_status=verification_status,
            retries_attempted=int(retries_attempted),
            casual_story=personas.casual_story,
            tactical_analysis=personas.tactical_analysis,
            club_loyalist_story=personas.club_loyalist_story,
            player_lock_story=personas.player_lock_story,
            lower_third_ticker=ticker,
            metrics=metrics,
            telestrator_vectors=telestrator,
            translations=translations,
        )
