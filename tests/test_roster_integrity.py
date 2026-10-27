"""
Test Suite: Roster & Formation Integrity (Requirements R1 & R2)
Validates authentic squad rosters for Northbridge Lions and Harbourside City,
tactical 4-3-3 role distributions, kickoff pitch half containment (X <= 52.5 vs X >= 52.5),
goalkeeper 6-yard box placement, center-spot striker positioning, and simulation consistency.
"""

import math
import pytest
from generator.match_generator import MatchGenerator, NORTHBRIDGE_ROSTER, AWAY_ROSTER


class TestRosterComposition:
    """Validates squad rosters, player counts, names, numbers, and roles."""

    def test_home_roster_count(self):
        """Asserts Northbridge Lions squad sheet contains exactly 11 active starting players."""
        assert len(NORTHBRIDGE_ROSTER) == 11, f"Expected 11 Northbridge Lions players, found {len(NORTHBRIDGE_ROSTER)}"

    def test_away_roster_count(self):
        """Asserts Harbourside City squad sheet contains exactly 11 active starting players."""
        assert len(AWAY_ROSTER) == 11, f"Expected 11 Harbourside players, found {len(AWAY_ROSTER)}"

    def test_total_player_count_in_generator(self):
        """Asserts MatchGenerator instantiates exactly 22 players (11 home, 11 away)."""
        gen = MatchGenerator(match_id="IGS_TEST_ROSTER", frame_rate=25)
        assert len(gen.players) == 22
        home_players = [p for p in gen.players.values() if p.team == "home"]
        away_players = [p for p in gen.players.values() if p.team == "away"]
        assert len(home_players) == 11
        assert len(away_players) == 11

    def test_northbridge_player_names_and_numbers(self):
        """Asserts all 11 Northbridge Lions players match authentic 2024/25 starters and squad numbers."""
        expected_northbridge = {
            "NBL_01": ("Daniel Roark", 1, "GK"),
            "NBL_04": ("Ben Whitlock", 4, "DF"),
            "NBL_02": ("Wilfred Sandoval", 2, "DF"),
            "NBL_06": ("Gabriel Marchetti", 6, "DF"),
            "NBL_12": ("Joris Tamblyn", 12, "DF"),
            "NBL_05": ("Tomas Pardoe", 5, "MF"),
            "NBL_41": ("Declan Rowe", 41, "MF"),
            "NBL_08": ("Martin Olsvik", 8, "MF"),
            "NBL_07": ("Kofi Sarpong", 7, "FW"),
            "NBL_29": ("Kai Halvorsen", 29, "FW"),
            "NBL_11": ("Mateus Montoya", 11, "FW"),
        }

        actual_northbridge = {p["player_id"]: (p["name"], p["jersey_number"], p["role"]) for p in NORTHBRIDGE_ROSTER}
        assert actual_northbridge == expected_northbridge

    def test_man_city_player_names_and_numbers(self):
        """Asserts all 11 Harbourside City players match authentic 2024/25 starters and squad numbers."""
        expected_city = {
            "HSC_31": ("Enzo Barreto", 31, "GK"),
            "HSC_02": ("Kyle Walden", 2, "DF"),
            "HSC_25": ("Manuel Adeyemi", 25, "DF"),
            "HSC_03": ("Ruben Duarte", 3, "DF"),
            "HSC_24": ("Josip Grbic", 24, "DF"),
            "HSC_16": ("Rodrigo Vale", 16, "MF"),
            "HSC_17": ("Karel Devos", 17, "MF"),
            "HSC_20": ("Bernardo Santoro", 20, "MF"),
            "HSC_47": ("Phil Fenton", 47, "FW"),
            "HSC_09": ("Anders Hagen", 9, "FW"),
            "HSC_11": ("Jeremy Dukes", 11, "FW"),
        }

        actual_city = {p["player_id"]: (p["name"], p["jersey_number"], p["role"]) for p in AWAY_ROSTER}
        assert actual_city == expected_city

    def test_unique_player_ids_and_jerseys(self):
        """Asserts all player IDs are globally unique and jersey numbers are unique per team."""
        all_ids = [p["player_id"] for p in NORTHBRIDGE_ROSTER] + [p["player_id"] for p in AWAY_ROSTER]
        assert len(all_ids) == len(set(all_ids)), "Duplicate player_id found across rosters"

        ars_jerseys = [p["jersey_number"] for p in NORTHBRIDGE_ROSTER]
        assert len(ars_jerseys) == len(set(ars_jerseys)), "Duplicate jersey number in Northbridge Lions roster"

        mci_jerseys = [p["jersey_number"] for p in AWAY_ROSTER]
        assert len(mci_jerseys) == len(set(mci_jerseys)), "Duplicate jersey number in Harbourside roster"

    def test_tactical_roles_distribution(self):
        """Asserts both teams adhere to a 4-3-3 formation (1 GK, 4 DF, 3 MF, 3 FW)."""
        def count_roles(roster):
            counts = {"GK": 0, "DF": 0, "MF": 0, "FW": 0}
            for p in roster:
                counts[p["role"]] += 1
            return counts

        ars_roles = count_roles(NORTHBRIDGE_ROSTER)
        mci_roles = count_roles(AWAY_ROSTER)

        expected_433 = {"GK": 1, "DF": 4, "MF": 3, "FW": 3}
        assert ars_roles == expected_433, f"Northbridge Lions formation mismatch: {ars_roles}"
        assert mci_roles == expected_433, f"Harbourside formation mismatch: {mci_roles}"


class TestKickoffSpatialBoundaries:
    """Validates strict pitch half containment at kickoff (X <= 52.5 for Northbridge Lions, X >= 52.5 for Harbourside)."""

    def test_roster_base_x_half_confinement(self):
        """Asserts every player's defined base_x is strictly inside their respective half."""
        for p in NORTHBRIDGE_ROSTER:
            assert p["base_x"] <= 52.5, f"Northbridge Lions player {p['name']} has base_x > 52.5: {p['base_x']}"
            assert 0.0 <= p["base_x"], f"Northbridge Lions player {p['name']} has negative base_x: {p['base_x']}"
            assert 0.0 <= p["base_y"] <= 68.0, f"Northbridge Lions player {p['name']} has base_y out of bounds: {p['base_y']}"

        for p in AWAY_ROSTER:
            assert p["base_x"] >= 52.5, f"Harbourside player {p['name']} has base_x < 52.5: {p['base_x']}"
            assert p["base_x"] <= 105.0, f"Harbourside player {p['name']} has base_x > 105.0: {p['base_x']}"
            assert 0.0 <= p["base_y"] <= 68.0, f"Harbourside player {p['name']} has base_y out of bounds: {p['base_y']}"

    def test_frame_1_kickoff_half_confinement(self):
        """Asserts opening frame 1 players are strictly bounded within their respective halves."""
        gen = MatchGenerator(match_id="IGS_TEST_KICKOFF", frame_rate=25)
        frame = gen.step()
        assert frame["frame_id"] == 1
        assert frame["clock"] == "00:00"

        for p in frame["players"]:
            if p["team"] == "home":
                assert p["x"] <= 52.5, f"Northbridge Lions player {p['name']} crossed into away half on frame 1: {p['x']}"
            elif p["team"] == "away":
                assert p["x"] >= 52.5, f"Harbourside player {p['name']} crossed into home half on frame 1: {p['x']}"

    def test_clock_00_00_multi_step_half_confinement(self):
        """Asserts players remain strictly confined to their halves throughout clock 00:00."""
        gen = MatchGenerator(match_id="IGS_TEST_MULTI_STEP", frame_rate=25)
        # Advance through all 24 frames comprising clock 00:00 (0.04s to 0.96s at 25Hz)
        for _ in range(24):
            frame = gen.step()
            assert frame["clock"] == "00:00"
            for p in frame["players"]:
                if p["team"] == "home":
                    assert p["x"] <= 52.5, f"Northbridge Lions player {p['name']} crossed half during 00:00: {p['x']}"
                elif p["team"] == "away":
                    assert p["x"] >= 52.5, f"Harbourside player {p['name']} crossed half during 00:00: {p['x']}"

        # Continue stepping through kickoff phase (50 frames total) verifying half containment
        for _ in range(26):
            frame = gen.step()
            for p in frame["players"]:
                if p["team"] == "home":
                    assert p["x"] <= 52.5, f"Northbridge Lions player {p['name']} crossed half during kickoff: {p['x']}"
                elif p["team"] == "away":
                    assert p["x"] >= 52.5, f"Harbourside player {p['name']} crossed half during kickoff: {p['x']}"

    def test_canonical_kickoff_frame_method(self):
        """Asserts get_kickoff_frame() returns a valid frame at clock 00:00 with 22 half-bounded players."""
        gen = MatchGenerator(match_id="IGS_TEST_CANONICAL", frame_rate=25)
        kf = gen.get_kickoff_frame()

        assert kf["clock"] == "00:00"
        assert kf["period"] == 1
        assert len(kf["players"]) == 22
        assert kf["ball"]["x"] == 52.5
        assert kf["ball"]["y"] == 34.0
        assert kf["ball"]["z"] == 0.0

        for p in kf["players"]:
            if p["team"] == "home":
                assert p["x"] <= 52.5
            elif p["team"] == "away":
                assert p["x"] >= 52.5


class TestGoalkeeperBoxContainment:
    """Validates goalkeeper positioning inside the standard 6-yard box (goal area)."""

    def test_northbridge_gk_base_position(self):
        """Asserts Daniel Roark is positioned inside Northbridge Lions 6-yard box (X in [0.0, 5.5], Y in [24.84, 43.16])."""
        roark = next(p for p in NORTHBRIDGE_ROSTER if p["player_id"] == "NBL_01")
        assert 0.0 <= roark["base_x"] <= 5.5, f"Roark base_x {roark['base_x']} not inside 6-yard box [0.0, 5.5]"
        assert 24.84 <= roark["base_y"] <= 43.16, f"Roark base_y {roark['base_y']} not inside 6-yard box Y span"
        assert roark["base_x"] == 4.0
        assert roark["base_y"] == 34.0

    def test_man_city_gk_base_position(self):
        """Asserts Enzo Barreto is positioned inside Harbourside 6-yard box (X in [99.5, 105.0], Y in [24.84, 43.16])."""
        barreto = next(p for p in AWAY_ROSTER if p["player_id"] == "HSC_31")
        assert 99.5 <= barreto["base_x"] <= 105.0, f"Enzo Barreto base_x {barreto['base_x']} not inside 6-yard box [99.5, 105.0]"
        assert 24.84 <= barreto["base_y"] <= 43.16, f"Enzo Barreto base_y {barreto['base_y']} not inside 6-yard box Y span"
        assert barreto["base_x"] == 101.0
        assert barreto["base_y"] == 34.0

    def test_goalkeepers_remain_in_6yard_boxes_during_kickoff(self):
        """Asserts both goalkeepers remain strictly inside their 6-yard boxes during kickoff frames."""
        gen = MatchGenerator(match_id="IGS_TEST_GK", frame_rate=25)
        for _ in range(50):
            frame = gen.step()
            players_by_id = {p["player_id"]: p for p in frame["players"]}

            roark = players_by_id["NBL_01"]
            barreto = players_by_id["HSC_31"]

            assert 0.0 <= roark["x"] <= 5.5, f"Roark strayed outside 6-yard box: x={roark['x']}"
            assert 99.5 <= barreto["x"] <= 105.0, f"Enzo Barreto strayed outside 6-yard box: x={barreto['x']}"


class TestCenterSpotStrikers:
    """Validates center forward positioning at the center spot for the opening whistle."""

    def test_halvorsen_kickoff_center_spot(self):
        """Asserts Kai Halvorsen is stationed at (52.2, 34.0) on the Northbridge Lions side of center spot."""
        halvorsen = next(p for p in NORTHBRIDGE_ROSTER if p["player_id"] == "NBL_29")
        assert halvorsen["base_x"] == 52.2
        assert halvorsen["base_y"] == 34.0
        assert halvorsen["base_x"] <= 52.5, "Halvorsen crossed halfway line"
        dist_to_center = math.hypot(halvorsen["base_x"] - 52.5, halvorsen["base_y"] - 34.0)
        assert dist_to_center <= 0.5, f"Halvorsen is too far from center spot: {dist_to_center}m"

    def test_hagen_kickoff_center_spot(self):
        """Asserts Anders Hagen is stationed at (52.8, 34.0) on the Harbourside side of center spot."""
        hagen = next(p for p in AWAY_ROSTER if p["player_id"] == "HSC_09")
        assert hagen["base_x"] == 52.8
        assert hagen["base_y"] == 34.0
        assert hagen["base_x"] >= 52.5, "Hagen crossed halfway line"
        dist_to_center = math.hypot(hagen["base_x"] - 52.5, hagen["base_y"] - 34.0)
        assert dist_to_center <= 0.5, f"Hagen is too far from center spot: {dist_to_center}m"

    def test_striker_separation_and_non_collision(self):
        """Asserts both strikers are separated across the halfway line without coordinate collision."""
        halvorsen = next(p for p in NORTHBRIDGE_ROSTER if p["player_id"] == "NBL_29")
        hagen = next(p for p in AWAY_ROSTER if p["player_id"] == "HSC_09")

        sep = math.hypot(halvorsen["base_x"] - hagen["base_x"], halvorsen["base_y"] - hagen["base_y"])
        assert sep == pytest.approx(0.6, abs=1e-3)
        assert halvorsen["base_x"] < 52.5 < hagen["base_x"]

    def test_kickoff_ball_placement_and_possession(self):
        """Asserts the ball starts at (52.5, 34.0) possessed by Northbridge Lions striker Kai Halvorsen (NBL_29)."""
        gen = MatchGenerator(match_id="IGS_TEST_BALL", frame_rate=25)
        frame = gen.step()
        ball = frame["ball"]

        assert ball["x"] == 52.5
        assert ball["y"] == 34.0
        assert ball["z"] == 0.0
        assert ball["speed_kmh"] == 0.0
        assert ball["possession_team"] == "home"
        assert ball["possessed_by_player_id"] == "NBL_29"
        assert ball["status"] == "in_play"


class TestGeneratorReset:
    """Validates generator reset restores authentic kickoff state."""

    def test_generator_reset_restores_kickoff_state(self):
        """Asserts calling reset() resets frame index, elapsed time, and repositions players at kickoff."""
        gen = MatchGenerator(match_id="IGS_TEST_RESET", frame_rate=25)
        # Run 100 frames
        for _ in range(100):
            gen.step()

        assert gen.frame_index == 100
        assert gen.elapsed_sec > 0.0

        # Reset generator
        gen.reset()

        assert gen.frame_index == 0
        assert gen.elapsed_sec == 0.0
        assert gen.get_clock_string() == "00:00"

        # Step frame 1 after reset
        f1 = gen.step()
        assert f1["frame_id"] == 1
        assert f1["clock"] == "00:00"

        players_by_id = {p["player_id"]: p for p in f1["players"]}
        assert players_by_id["NBL_01"]["x"] == 4.0
        assert players_by_id["HSC_31"]["x"] == 101.0
        assert players_by_id["NBL_29"]["x"] == 52.2
        assert players_by_id["HSC_09"]["x"] == 52.8
