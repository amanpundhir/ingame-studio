"""Test Suite for InGame Studio Viewer Personas & Broadcast Overlays.

Validates:
1. Generation of 4 distinct, verified persona narratives:
   - Casual Fan (high-energy, emojis, accessible thrill)
   - Tactical Purist (Expected Threat xT, spatial geometry, numerical depth)
   - Club Loyalist (passionate club pride, heroism, devotion)
   - Player-Lock Fantasy Scout (fantasy metrics, BPS points projection)
2. Uppercase live broadcast lower-third ticker formatting.
3. Multi-language localization in English and Spanish.
4. Telestrator vector generation (passing line, target ring, corridor polygon).
5. Verification of personalized outputs across calibrated match moments.
"""

import json
import os
import pytest
from backend.agents.models import FactPack, PersonaOutputs, VerifiedInsight
from backend.agents.director_agent import StudioDirectorAgent
from backend.agents.orchestrator import MatchIntelligenceOrchestrator


@pytest.fixture(scope="module")
def synthetic_events():
    """Loads calibrated events from data/synthetic_events.json."""
    current_dir = os.path.dirname(os.path.abspath(__file__))
    repo_root = os.path.dirname(current_dir)
    events_path = os.path.join(repo_root, "data", "synthetic_events.json")
    with open(events_path, "r", encoding="utf-8") as f:
        return json.load(f)


@pytest.fixture
def calibrated_fact_pack():
    """Authoritative FactPack for Declan Rowe -> Kofi Sarpong line-breaking pass."""
    return FactPack(
        event_id="EVT_1009",
        match_minute="42:18",
        period=1,
        event_type="pass",
        passer_name="Declan Rowe",
        receiver_name="Kofi Sarpong",
        team_name="Northbridge Lions",
        opponent_name="Harbourside City",
        start_x=48.5,
        start_y=28.0,
        end_x=77.0,
        end_y=28.0,
        pass_distance_m=28.5,
        pass_difficulty=80.0,
        ball_speed_kmh=72.0,
        chaos_index=68.0,
        xt_gained=0.18,
        defenders_in_corridor=2,
        defenders_in_cone=1,
        tactical_context="High-pressure vertical progression breaking opposition mid-block",
    )


class TestViewerPersonas:
    """Tests 4 distinct broadcast personas produced by Agent 4 (The Studio Director)."""

    def test_four_personas_are_distinct_and_non_empty(self, calibrated_fact_pack):
        """Asserts all 4 personas generate non-empty, unique narratives."""
        director = StudioDirectorAgent()
        personas = director.adapt_personas(calibrated_fact_pack, "Verified causal narrative.")

        stories = [
            personas.casual_story,
            personas.tactical_analysis,
            personas.club_loyalist_story,
            personas.player_lock_story,
        ]

        # All narratives must be non-empty strings
        for s in stories:
            assert isinstance(s, str)
            assert len(s.strip()) > 30

        # All 4 personas must be distinct from each other
        assert len(set(stories)) == 4

    def test_casual_fan_persona_characteristics(self, calibrated_fact_pack):
        """Asserts Casual Fan persona has high energy, emojis, and plain language."""
        director = StudioDirectorAgent()
        personas = director.adapt_personas(calibrated_fact_pack, "Verified baseline.")

        story = personas.casual_story
        # Emojis indicating excitement
        assert any(e in story for e in ["⚡", "🔥", "🎯", "🚀", "⚽"])
        # Mentions players
        assert "Declan Rowe" in story
        assert "Kofi Sarpong" in story
        assert "72.0 km/h" in story

    def test_tactical_purist_persona_characteristics(self, calibrated_fact_pack):
        """Asserts Tactical Purist persona includes xT, geometry, and numerical depth."""
        director = StudioDirectorAgent()
        personas = director.adapt_personas(calibrated_fact_pack, "Verified baseline.")

        story = personas.tactical_analysis
        assert "Tactical Breakdown" in story
        assert "Expected Threat" in story or "xT" in story
        assert "+0.18" in story
        assert "80.0%" in story
        assert "28.5m" in story
        assert "corridor defenders" in story

    def test_club_loyalist_persona_characteristics(self, calibrated_fact_pack):
        """Asserts Club Loyalist persona expresses partisan pride and heroism."""
        director = StudioDirectorAgent()
        personas = director.adapt_personas(calibrated_fact_pack, "Verified baseline.")

        story = personas.club_loyalist_story
        assert "Northbridge Lions" in story
        assert "Harbourside City" in story
        assert any(term in story.lower() for term in ["heart", "courage", "passion", "pride"])

    def test_player_lock_fantasy_persona_characteristics(self, calibrated_fact_pack):
        """Asserts Player-Lock Fantasy persona tracks fantasy metrics and bonus points."""
        director = StudioDirectorAgent()
        personas = director.adapt_personas(calibrated_fact_pack, "Verified baseline.")

        story = personas.player_lock_story
        assert "Fantasy" in story
        assert "BPS" in story
        assert "Declan Rowe" in story
        assert "Kofi Sarpong" in story


class TestBroadcastLowerThirdTicker:
    """Tests formatting of live broadcast lower-third ticker straps."""

    def test_ticker_is_uppercase_and_well_formatted(self, calibrated_fact_pack):
        """Asserts ticker conforms to uppercase broadcast strap style."""
        director = StudioDirectorAgent()
        ticker = director.generate_ticker(calibrated_fact_pack, verification_status="VERIFIED")

        # Must be uppercase
        assert ticker == ticker.upper()
        # Must include required broadcast tags
        assert "INGAME LIVE" in ticker
        assert "42:18" in ticker
        assert "DECLAN ROWE" in ticker
        assert "KOFI SARPONG" in ticker
        assert "28.5M" in ticker
        assert "72.0 KM/H" in ticker
        assert "PASS DIFFICULTY: 80.0%" in ticker
        assert "XT GAINED: +0.18" in ticker
        assert "STATUS: VERIFIED" in ticker

    def test_ticker_reflects_fallback_status(self, calibrated_fact_pack):
        """Asserts ticker updates status correctly when fallback is applied."""
        director = StudioDirectorAgent()
        ticker = director.generate_ticker(calibrated_fact_pack, verification_status="FALLBACK_APPLIED")

        assert "STATUS: FALLBACK_APPLIED" in ticker


class TestMultiLanguageLocalization:
    """Tests translation dictionary generation in English and Spanish."""

    def test_all_languages_present(self, calibrated_fact_pack):
        """Asserts localization dict contains EN and ES only."""
        director = StudioDirectorAgent()
        translations = director.generate_translations(calibrated_fact_pack)

        expected_languages = ["en", "es"]
        assert set(translations) == set(expected_languages)
        for lang in expected_languages:
            assert lang in translations
            lang_dict = translations[lang]
            assert "casual" in lang_dict
            assert "tactical" in lang_dict
            assert "ticker" in lang_dict
            assert len(lang_dict["casual"]) > 0
            assert len(lang_dict["tactical"]) > 0
            assert len(lang_dict["ticker"]) > 0

    def test_language_specific_phrasing(self, calibrated_fact_pack):
        """Asserts genuine translated terms are present in localized versions."""
        director = StudioDirectorAgent()
        translations = director.generate_translations(calibrated_fact_pack)

        # Spanish
        assert "¡QUÉ JUGADA!" in translations["es"]["casual"]
        assert "Análisis Táctico" in translations["es"]["tactical"]


class TestTelestratorVectors:
    """Tests spatial telestrator vector annotations for UI rendering."""

    def test_telestrator_vectors_structure(self, calibrated_fact_pack):
        """Asserts telestrator contains valid coordinates, line style, and pressure polygon."""
        director = StudioDirectorAgent()
        vectors = director.generate_telestrator(calibrated_fact_pack)

        assert vectors["start_x"] == 48.5
        assert vectors["start_y"] == 28.0
        assert vectors["end_x"] == 77.0
        assert vectors["end_y"] == 28.0
        assert vectors["distance_m"] == 28.5
        assert vectors["corridor_width_m"] == 4.0
        assert vectors["cone_angle_deg"] == 20.0
        assert vectors["color_hex"] == "#00ff87"

        # Check pressure corridor polygon
        polygon = vectors["pressure_polygon"]
        assert isinstance(polygon, list)
        assert len(polygon) == 4
        for pt in polygon:
            assert "x" in pt and "y" in pt
            assert 0.0 <= pt["x"] <= 105.0
            assert 0.0 <= pt["y"] <= 68.0


class TestDatasetMomentsPersonalization:
    """Tests end-to-end multi-agent orchestration on calibrated events."""

    def test_orchestrator_on_synthetic_events_dataset(self, synthetic_events):
        """Processes pass events from synthetic_events.json and verifies insight integrity."""
        orchestrator = MatchIntelligenceOrchestrator()

        # Filter for pass events in the dataset
        pass_events = [e for e in synthetic_events if e.get("event_type") == "pass"]
        assert len(pass_events) >= 5

        # Test first 10 pass events
        for event in pass_events[:10]:
            insight = orchestrator.process_event(event)

            assert isinstance(insight, VerifiedInsight)
            assert insight.event_id == event["event_id"]
            assert insight.verification_status in ("VERIFIED", "FALLBACK_APPLIED")
            assert 0.0 <= insight.grounding_score <= 1.0

            # 4 distinct personas present
            stories = [
                insight.casual_story,
                insight.tactical_analysis,
                insight.club_loyalist_story,
                insight.player_lock_story,
            ]
            assert len(set(stories)) == 4

            # Ticker is uppercase
            assert insight.lower_third_ticker == insight.lower_third_ticker.upper()
            assert "INGAME LIVE" in insight.lower_third_ticker

            # Telestrator vectors present
            assert "start_x" in insight.telestrator_vectors
            assert "end_x" in insight.telestrator_vectors
            assert len(insight.telestrator_vectors["pressure_polygon"]) == 4

            # Translations present
            assert insight.translations is not None
            assert set(insight.translations.keys()) == {"en", "es"}
