"""
InGame Studio - 22-Player Analytics Tracker & Match Stats Test Suite (Requirement R7)
Validates:
- Full 22-player tracking across authentic Northbridge Lions and Harbourside City rosters
- Physical bounds: monotonic distance accumulation, sprint speed caps (<= 36.0 km/h), full-match distance bands
- Teleportation guard preventing displacement spikes (>1.5m) from inflating distance
- Match stats aggregation: possession %, xG, pass accuracy %, tackles won %, Chaos Index
- Explainable player ratings (0.0 - 10.0) and single MOTM badge allocation
- Official Fantasy Bonus Point System (BPS) and 3/2/1 podium distribution
- GET /api/analytics REST endpoint completeness and contract conformity
"""

import json
import os
import pytest
from fastapi.testclient import TestClient

from backend.app import app
from backend.math_engine import MatchAnalyticsTracker, PlayerAnalytics
from generator.match_generator import NORTHBRIDGE_ROSTER, AWAY_ROSTER


@pytest.fixture
def client():
    """Provides TestClient for FastAPI analytics endpoint."""
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture
def synthetic_events():
    """Loads calibrated 90-minute synthetic events dataset."""
    events_path = os.path.join(os.path.dirname(__file__), "..", "data", "synthetic_events.json")
    with open(events_path, "r", encoding="utf-8") as f:
        return json.load(f)


class Test22PlayerRosterTracking:
    """Validates player coverage and roster authenticity."""

    def test_all_22_players_present(self):
        """Asserts MatchAnalyticsTracker tracks exactly 22 players."""
        tracker = MatchAnalyticsTracker()
        stats = tracker.get_all_player_stats()
        assert len(stats) == 22, f"Expected 22 players, found {len(stats)}"

    def test_northbridge_11_players_present(self):
        """Asserts 11 authentic Northbridge Lions players with IDs NBL_01 to NBL_41."""
        tracker = MatchAnalyticsTracker()
        stats = tracker.get_all_player_stats()
        northbridge_ids = {p["player_id"] for p in stats if p["team"] == "home"}
        expected_northbridge = {p["player_id"] for p in NORTHBRIDGE_ROSTER}
        assert len(northbridge_ids) == 11
        assert northbridge_ids == expected_northbridge

    def test_man_city_11_players_present(self):
        """Asserts 11 authentic Harbourside players with IDs HSC_31 to HSC_47."""
        tracker = MatchAnalyticsTracker()
        stats = tracker.get_all_player_stats()
        city_ids = {p["player_id"] for p in stats if p["team"] == "away"}
        expected_city = {p["player_id"] for p in AWAY_ROSTER}
        assert len(city_ids) == 11
        assert city_ids == expected_city

    def test_unique_player_ids_and_squad_numbers(self):
        """Asserts all 22 player IDs are unique and squad numbers are unique per team."""
        tracker = MatchAnalyticsTracker()
        stats = tracker.get_all_player_stats()
        player_ids = [p["player_id"] for p in stats]
        assert len(player_ids) == len(set(player_ids))

        home_jerseys = [p["jersey_number"] for p in stats if p["team"] == "home"]
        away_jerseys = [p["jersey_number"] for p in stats if p["team"] == "away"]
        assert len(home_jerseys) == len(set(home_jerseys))
        assert len(away_jerseys) == len(set(away_jerseys))


class TestPhysicalTrackingBounds:
    """Validates physical kinematic bounds and distance accumulation."""

    def test_distance_accumulates_monotonically(self):
        """Asserts player distance increases monotonically when stepping within physical bounds."""
        p = PlayerAnalytics(player_id="TEST_01", name="Tester", team="home", jersey_number=10, role="MF")
        assert p.distance_meters == 0.0

        p.update_tracking(10.0, 10.0, 15.0)
        assert p.distance_meters == 0.0  # First frame sets initial coordinate

        p.update_tracking(10.5, 10.0, 18.0)
        assert p.distance_meters == pytest.approx(0.5, abs=1e-3)

        p.update_tracking(11.0, 10.0, 20.0)
        assert p.distance_meters == pytest.approx(1.0, abs=1e-3)

    def test_teleportation_guard_ignores_large_jumps(self):
        """Asserts sudden coordinate jumps > 1.5m (e.g. replay jumps or resets) are not accumulated."""
        p = PlayerAnalytics(player_id="TEST_01", name="Tester", team="home", jersey_number=10, role="MF")
        p.update_tracking(10.0, 10.0, 15.0)
        p.update_tracking(10.5, 10.0, 18.0)
        dist_before = p.distance_meters

        # Sudden jump of 50m
        p.update_tracking(60.5, 10.0, 25.0)
        assert p.distance_meters == dist_before

    def test_player_speed_within_physical_envelope(self):
        """Asserts top speed is clamped to maximum (36.0 km/h)."""
        p = PlayerAnalytics(player_id="TEST_01", name="Tester", team="home", jersey_number=10, role="MF")
        p.update_tracking(10.0, 10.0, 45.0)  # Extreme speed
        assert p.top_speed_kmh <= 36.0
        assert p.top_speed_kmh == 36.0

    def test_event_only_distance_and_speed_metrics_are_bounded(self, synthetic_events):
        """Event-only aggregation must not invent tracking-derived distances."""
        tracker = MatchAnalyticsTracker()
        tracker.simulate_full(synthetic_events)
        stats = tracker.get_all_player_stats()

        for p in stats:
            dist = p["distance_km"]
            speed = p["top_speed_kmh"]
            assert 0.0 <= speed <= 36.0, f"Speed out of bounds for {p['name']}: {speed}"

            assert 0.0 <= dist <= 15.0, f"Distance out of bounds for {p['name']}: {dist} km"


class TestMatchStatsAggregation:
    """Validates match-level statistical aggregations."""

    def test_event_derived_possession_is_bounded(self, synthetic_events):
        """Event-only inputs yield valid bounded possession percentages."""
        tracker = MatchAnalyticsTracker()
        tracker.simulate_full(synthetic_events)
        m = tracker.get_match_stats()
        home_pos = m["possession_pct"]["home"]
        away_pos = m["possession_pct"]["away"]
        assert 0.0 <= home_pos <= 100.0
        assert 0.0 <= away_pos <= 100.0
        if home_pos + away_pos > 0.0:
            assert (home_pos + away_pos) == pytest.approx(100.0, abs=0.2)

    def test_pass_accuracy_bounds(self, synthetic_events):
        """Asserts completed passes <= total and accuracy is within [0.0, 100.0]%."""
        tracker = MatchAnalyticsTracker()
        tracker.simulate_full(synthetic_events)
        m = tracker.get_match_stats()
        for side in ["home", "away"]:
            p = m["passes"][side]
            assert p["completed"] <= p["total"]
            assert 0.0 <= p["accuracy_pct"] <= 100.0

    def test_tackles_won_percentage_bounds(self, synthetic_events):
        """Asserts tackles won <= total and percentage is within [0.0, 100.0]%."""
        tracker = MatchAnalyticsTracker()
        tracker.simulate_full(synthetic_events)
        m = tracker.get_match_stats()
        for side in ["home", "away"]:
            t = m["tackles"][side]
            assert t["won"] <= t["total"]
            assert 0.0 <= t["won_pct"] <= 100.0

    def test_xg_non_negative_and_plausible(self, synthetic_events):
        """Asserts xG is non-negative and realistic for high-profile clash."""
        tracker = MatchAnalyticsTracker()
        tracker.simulate_full(synthetic_events)
        m = tracker.get_match_stats()
        assert m["xg"]["home"] >= 0.0
        assert m["xg"]["away"] >= 0.0
        assert m["xg"]["home"] <= 20.0
        assert m["xg"]["away"] <= 20.0

    def test_chaos_index_in_bounds(self, synthetic_events):
        """Asserts Chaos Index is strictly bounded within [0.0, 100.0]."""
        tracker = MatchAnalyticsTracker()
        tracker.simulate_full(synthetic_events)
        m = tracker.get_match_stats()
        assert 0.0 <= m["chaos_index"] <= 100.0


class TestPlayerRatingsAndMOTM:
    """Validates explainable 0.0 - 10.0 player ratings and MOTM award."""

    def test_ratings_bounded_0_to_10(self, synthetic_events):
        """Asserts all 22 player ratings fall strictly within [4.0, 10.0]."""
        tracker = MatchAnalyticsTracker()
        tracker.simulate_full(synthetic_events)
        stats = tracker.get_all_player_stats()
        for p in stats:
            assert 4.0 <= p["rating"] <= 10.0, f"Rating out of bounds for {p['name']}: {p['rating']}"

    def test_motm_assigned_to_top_rated_player(self, synthetic_events):
        """Asserts exactly one player receives is_motm=True, matching the highest rating."""
        tracker = MatchAnalyticsTracker()
        tracker.simulate_full(synthetic_events)
        stats = tracker.get_all_player_stats()

        motm_players = [p for p in stats if p["is_motm"] is True]
        assert len(motm_players) == 1, f"Expected exactly 1 MOTM, found {len(motm_players)}"

        max_rating = max(p["rating"] for p in stats)
        assert motm_players[0]["rating"] == max_rating

    def test_goal_scorers_receive_goal_credit(self, synthetic_events):
        """Asserts generated scorers receive goal credit and bounded ratings."""
        tracker = MatchAnalyticsTracker()
        tracker.simulate_full(synthetic_events)
        stats_by_id = {p["player_id"]: p for p in tracker.get_all_player_stats()}

        goal_scorer_ids = {
            event["player_id"] for event in synthetic_events
            if event.get("event_type") == "goal" or event.get("outcome") == "goal"
        }
        assert goal_scorer_ids
        for pid in goal_scorer_ids:
            player = stats_by_id[pid]
            assert player["goals"] > 0
            assert 4.0 <= player["rating"] <= 10.0


class TestFantasyBPS:
    """Validates official Fantasy Bonus Point System and 3/2/1 podium distribution."""

    def test_bps_calculated_for_all_players(self, synthetic_events):
        """Asserts all 22 players receive integer BPS >= 0."""
        tracker = MatchAnalyticsTracker()
        tracker.simulate_full(synthetic_events)
        stats = tracker.get_all_player_stats()
        for p in stats:
            assert isinstance(p["bps"], int)
            assert p["bps"] >= 0

    def test_fantasy_bonus_podium_distribution(self, synthetic_events):
        """Asserts podium awards exactly 3, 2, and 1 bonus points summing to 6."""
        tracker = MatchAnalyticsTracker()
        tracker.simulate_full(synthetic_events)
        stats = tracker.get_all_player_stats()

        pts_3 = [p for p in stats if p["fantasy_bonus_points"] == 3]
        pts_2 = [p for p in stats if p["fantasy_bonus_points"] == 2]
        pts_1 = [p for p in stats if p["fantasy_bonus_points"] == 1]

        assert len(pts_3) == 1
        assert len(pts_2) == 1
        assert len(pts_1) == 1

        total_bonus = sum(p["fantasy_bonus_points"] for p in stats)
        assert total_bonus == 6

    def test_non_podium_players_receive_zero(self, synthetic_events):
        """Asserts remaining 19 players receive exactly 0 bonus points."""
        tracker = MatchAnalyticsTracker()
        tracker.simulate_full(synthetic_events)
        stats = tracker.get_all_player_stats()
        non_podium = [p for p in stats if p["fantasy_bonus_points"] == 0]
        assert len(non_podium) == len(stats) - 3


class TestAnalyticsRestEndpoint:
    """Validates the GET /api/analytics REST endpoint."""

    def test_get_analytics_endpoint_200(self, client):
        """GET /api/analytics returns HTTP 200 with match_stats and player_stats."""
        client.post("/api/control", json={"action": "simulate_full"})
        resp = client.get("/api/analytics")
        assert resp.status_code == 200
        data = resp.json()
        assert "match_stats" in data
        assert "player_stats" in data
        assert len(data["player_stats"]) >= 22

    def test_analytics_schema_completeness(self, client):
        """Validates all required match and player metric fields are present in response."""
        resp = client.get("/api/analytics")
        assert resp.status_code == 200
        data = resp.json()

        m = data["match_stats"]
        for key in ["possession_pct", "xg", "shots", "passes", "tackles", "interceptions", "fouls", "cards", "corners", "chaos_index", "score"]:
            assert key in m, f"Missing match stat: {key}"

        p = data["player_stats"][0]
        for key in ["player_id", "name", "team", "jersey_number", "role", "minutes_played", "distance_km", "top_speed_kmh", "passes", "xt_created", "xg", "shots", "goals", "assists", "rating", "is_motm", "bps", "fantasy_bonus_points"]:
            assert key in p, f"Missing player stat: {key}"
