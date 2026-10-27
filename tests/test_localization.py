"""InGame Studio - Localization Verification Test Suite (English and Spanish).

Validates:
1. Complete translation dictionary across English (en) and Spanish (es).
2. Coverage of all 4 audience personas (casual, tactical, club/loyalist, player/fantasy) and broadcast ticker.
3. Absence of null, undefined, empty, or uninitialized string fields.
4. Authentic domain vocabulary across event types (goal, shot, tackle, turnover, foul, pass, substitution, card).
5. Seamless integration with StudioDirectorAgent and VerifiedInsight broadcast payloads.
"""

import pytest
from backend.agents.director_agent import StudioDirectorAgent
from backend.agents.models import FactPack, VerifiedInsight
from backend.agents.orchestrator import MatchIntelligenceOrchestrator


def make_fact_pack(
    event_type: str = "pass",
    passer: str = "Declan Rowe",
    receiver: str = "Kofi Sarpong",
    team: str = "Northbridge Lions",
    dist: float = 28.5,
    speed: float = 72.0,
    pdr: float = 80.0,
    xt: float = 0.18,
    outcome: str = "completed",
    sub_type: str = None,
) -> FactPack:
    """Helper to instantiate calibrated FactPack for testing."""
    return FactPack(
        event_id=f"EVT_TEST_{event_type.upper()}",
        match_minute="42:18",
        period=1,
        event_type=event_type,
        passer_name=passer,
        receiver_name=receiver,
        team_name=team,
        opponent_name="Harbourside City",
        start_x=50.0,
        start_y=30.0,
        end_x=75.0,
        end_y=30.0,
        pass_distance_m=dist,
        pass_difficulty=pdr,
        ball_speed_kmh=speed,
        chaos_index=65.0,
        xt_gained=xt,
        defenders_in_corridor=2,
        defenders_in_cone=1,
        tactical_context=f"Tactical {event_type} phase",
        outcome=outcome,
        sub_type=sub_type,
    )


class TestLocalizationDictionaryCompleteness:
    """Validates structural completeness of the localization dictionaries."""

    @pytest.mark.parametrize("event_type", ["goal", "shot", "tackle", "turnover", "foul", "pass", "substitution", "card"])
    def test_both_languages_present_for_all_event_types(self, event_type):
        """Asserts EN and ES are always present and nothing else is generated."""
        director = StudioDirectorAgent()
        facts = make_fact_pack(event_type=event_type)
        translations = director.generate_translations(facts)

        expected_languages = ["en", "es"]
        assert set(translations) == set(expected_languages)
        for lang in expected_languages:
            assert lang in translations, f"Missing language code '{lang}' for event_type '{event_type}'"

    @pytest.mark.parametrize("event_type", ["goal", "shot", "tackle", "turnover", "foul", "pass", "substitution", "card"])
    def test_all_personas_and_ticker_present_per_language(self, event_type):
        """Asserts casual, tactical, club, loyalist, player, fantasy, player_lock, and ticker exist for all languages."""
        director = StudioDirectorAgent()
        facts = make_fact_pack(event_type=event_type)
        translations = director.generate_translations(facts)

        required_persona_keys = [
            "casual",
            "tactical",
            "club",
            "loyalist",
            "player",
            "fantasy",
            "player_lock",
            "ticker",
        ]

        for lang in ["en", "es"]:
            lang_dict = translations[lang]
            for key in required_persona_keys:
                assert key in lang_dict, (
                    f"Language '{lang}' missing persona key '{key}' for event_type '{event_type}'"
                )

    def test_no_undefined_or_null_or_empty_values(self):
        """Asserts no field contains null, undefined, empty, or uninitialized values."""
        director = StudioDirectorAgent()
        for evt_type in ["goal", "shot", "tackle", "turnover", "foul", "pass", "substitution", "card"]:
            facts = make_fact_pack(event_type=evt_type)
            translations = director.generate_translations(facts)
            for lang, ldict in translations.items():
                for k, v in ldict.items():
                    assert v is not None, f"Found None for {lang}.{k} in event {evt_type}"
                    assert isinstance(v, str), f"Expected str for {lang}.{k}, got {type(v)}"
                    clean_v = v.strip()
                    assert len(clean_v) > 10, f"Value too short for {lang}.{k}: '{clean_v}'"
                    assert "undefined" not in clean_v.lower(), f"'undefined' found in {lang}.{k}: {clean_v}"
                    assert "null" not in clean_v.lower(), f"'null' found in {lang}.{k}: {clean_v}"


class TestAuthenticVocabulary:
    """Validates that authentic football vocabulary is used in each language."""

    def test_spanish_authentic_terms(self):
        """Asserts Spanish translations include accurate tactical terms."""
        director = StudioDirectorAgent()

        # Goal
        facts_goal = make_fact_pack(event_type="goal", passer="Kofi Sarpong", receiver="Enzo Barreto")
        es_goal = director.generate_translations(facts_goal)["es"]
        assert "GOL" in es_goal["casual"] or "GOLAZO" in es_goal["casual"]
        assert "Análisis Táctico" in es_goal["tactical"]
        assert "INGAME EN VIVO" in es_goal["ticker"]

        # Tackle
        facts_tackle = make_fact_pack(event_type="tackle")
        es_tackle = director.generate_translations(facts_tackle)["es"]
        assert "ENTRADA" in es_tackle["casual"].upper() or "ENTRADA" in es_tackle["tactical"].upper()

    def test_english_authentic_terms(self):
        """Asserts English translations contain broadcast terminology."""
        director = StudioDirectorAgent()
        facts_goal = make_fact_pack(event_type="goal", passer="Kofi Sarpong")
        en_goal = director.generate_translations(facts_goal)["en"]
        assert "GOAL" in en_goal["casual"]
        assert "Tactical Breakdown" in en_goal["tactical"]
        assert "INGAME LIVE" in en_goal["ticker"]


class TestVerifiedInsightIntegration:
    """Validates multi-language integration with VerifiedInsight and Orchestrator."""

    def test_director_create_verified_insight_contains_valid_translations(self):
        """Asserts VerifiedInsight created by StudioDirectorAgent contains complete translations."""
        director = StudioDirectorAgent()
        facts = make_fact_pack(event_type="goal", passer="Kofi Sarpong", receiver="Enzo Barreto")
        insight = director.create_verified_insight(
            facts=facts,
            verified_narrative="Verified goal narrative.",
            grounding_score=0.98,
        )

        assert isinstance(insight, VerifiedInsight)
        assert insight.translations is not None
        assert len(insight.translations) == 2

        # Check frontend persona indexing compatibility
        for lang in ["en", "es"]:
            # Frontend uses insight.translations[language][activePersona] with activePersona in ['casual', 'tactical', 'club', 'fantasy']
            assert "casual" in insight.translations[lang]
            assert "tactical" in insight.translations[lang]
            assert "club" in insight.translations[lang]
            assert "fantasy" in insight.translations[lang]

    def test_orchestrator_emits_localized_insight(self):
        """Asserts MatchIntelligenceOrchestrator emits English and Spanish insights."""
        orchestrator = MatchIntelligenceOrchestrator()
        sample_event = {
            "event_id": "EVT_TEST_ORCH_5L",
            "match_id": "IGS_2026_NBL_HSC",
            "event_type": "goal",
            "period": 1,
            "clock": "28:15",
            "frame_index": 700,
            "team": "Northbridge Lions",
            "player_id": "NBL_07",
            "player_name": "Kofi Sarpong",
            "secondary_player_id": "HSC_31",
            "secondary_player_name": "Enzo Barreto",
            "location_x": 92.5,
            "location_y": 32.0,
            "outcome": "goal",
        }

        insight = orchestrator.process_event(sample_event)
        assert insight.verification_status in ("VERIFIED", "FALLBACK_APPLIED")
        assert insight.translations is not None
        assert set(insight.translations.keys()) == {"en", "es"}


class TestSubstitutionAndCardLocalization:
    """Substitutions and cards read correctly in both languages."""

    def test_substitution_names_both_players(self):
        director = StudioDirectorAgent()
        facts = make_fact_pack(event_type="substitution", passer="Lars Tordal", receiver="Mateus Montoya", sub_type="tactical_change")
        translations = director.generate_translations(facts)
        for lang in ("en", "es"):
            assert "Lars Tordal" in translations[lang]["casual"]
            assert "Mateus Montoya" in translations[lang]["tactical"]
        assert "SUBSTITUTION" in translations["en"]["ticker"]
        assert "CAMBIO" in translations["es"]["ticker"]

    def test_yellow_and_red_cards_are_told_apart(self):
        director = StudioDirectorAgent()
        yellow = director.generate_translations(make_fact_pack(event_type="card", sub_type="yellow_card", outcome="yellow"))
        red = director.generate_translations(make_fact_pack(event_type="card", sub_type="red_card", outcome="red"))
        assert "BOOKED" in yellow["en"]["casual"] and "SENT OFF" in red["en"]["casual"]
        assert "AMARILLA" in yellow["es"]["casual"] and "EXPULSADO" in red["es"]["casual"]
