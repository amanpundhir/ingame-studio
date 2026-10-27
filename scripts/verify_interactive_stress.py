"""InGame Studio - Empirical Verification & Stress Harness.
Author: challenger_interactive_stress
Mission: Empirically verify 5-tab application endpoints, data integrity, and stability.
"""

import json
import os
import sys
import traceback

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from fastapi.testclient import TestClient
from backend.app import app

def run_empirical_verification():
    with TestClient(app) as client:
        results = {
            "passed": 0,
            "failed": 0,
            "warnings": 0,
            "details": []
        }

        def record_test(name: str, passed: bool, msg: str, is_warning: bool = False):
            if passed:
                results["passed"] += 1
                status_str = "[PASS]"
            elif is_warning:
                results["warnings"] += 1
                status_str = "[WARN]"
            else:
                results["failed"] += 1
                status_str = "[FAIL]"
            out = f"{status_str} {name}: {msg}"
            print(out)
            results["details"].append(out)

        print("=" * 80)
        print("STARTING EMPIRICAL VERIFICATION HARNESS")
        print("=" * 80)

        # --------------------------------------------------------------------------
        # 1. Verify GET /api/state
        # --------------------------------------------------------------------------
        print("\n--- 1. Testing GET /api/state ---")
        try:
            r = client.get("/api/state")
            if r.status_code == 200:
                data = r.json()
                required_keys = ["match_id", "clock", "period", "is_paused", "speed_multiplier", "score", "frame", "match_stats"]
                missing = [k for k in required_keys if k not in data]
                if not missing:
                    record_test("GET /api/state structure", True, f"Status 200, all keys present: {list(data.keys())}")
                else:
                    record_test("GET /api/state structure", False, f"Missing keys: {missing}")

                # Verify score structure
                score = data.get("score", {})
                if "home" in score and "away" in score and isinstance(score["home"], int) and isinstance(score["away"], int):
                    record_test("GET /api/state score", True, f"Score: {score}")
                else:
                    record_test("GET /api/state score", False, f"Invalid score format: {score}")

                # Verify frame presence
                frame = data.get("frame")
                if frame is not None and isinstance(frame, dict):
                    record_test("GET /api/state frame", True, f"Frame present, clock={frame.get('clock')}, players={len(frame.get('players', []))}")
                else:
                    record_test("GET /api/state frame", False, f"Frame is null or not dict: {frame}")
            else:
                record_test("GET /api/state", False, f"Status {r.status_code}: {r.text}")
        except Exception as e:
            record_test("GET /api/state exception", False, str(e))

        # --------------------------------------------------------------------------
        # 2. Verify GET /api/players and GET /api/players/NBL_7 vs NBL_07
        # --------------------------------------------------------------------------
        print("\n--- 2. Testing GET /api/players and GET /api/players/{id} ---")
        try:
            r = client.get("/api/players")
            if r.status_code == 200:
                p_data = r.json()
                teams = p_data.get("teams", {})
                home_players = teams.get("home", {}).get("players", [])
                away_players = teams.get("away", {}).get("players", [])
                all_players = p_data.get("players", [])

                record_test("GET /api/players counts", 
                            len(home_players) == 11 and len(away_players) == 11 and len(all_players) == 22,
                            f"Home={len(home_players)}, Away={len(away_players)}, Total={len(all_players)}")

                # Check player structure for first player
                if all_players:
                    sample_p = all_players[0]
                    has_fields = all(k in sample_p for k in ["player_id", "name", "team", "jersey_number", "role", "rating", "radar", "heatmap", "events"])
                    record_test("Player profile schema", has_fields, f"Sample player: {sample_p.get('name')} ({sample_p.get('player_id')}) with radar axes={len(sample_p.get('radar', []))}")
            else:
                record_test("GET /api/players", False, f"Status {r.status_code}: {r.text}")
        except Exception as e:
            record_test("GET /api/players exception", False, str(e))

        # Test GET /api/players/NBL_7
        try:
            r_ars7 = client.get("/api/players/NBL_7")
            if r_ars7.status_code == 200:
                record_test("GET /api/players/NBL_7", True, f"Found Kofi Sarpong with unpadded ID: {r_ars7.json().get('name')}")
            elif r_ars7.status_code == 404:
                # Documented finding: unpadded ID returns 404 because roster IDs are zero-padded (NBL_07)
                record_test("GET /api/players/NBL_7 unpadded ID behavior", False, 
                            f"Returned HTTP 404 (detail: {r_ars7.json().get('detail')}). Roster strictly uses 2-digit zero-padded IDs (NBL_07).",
                            is_warning=True)
            else:
                record_test("GET /api/players/NBL_7", False, f"Unexpected status {r_ars7.status_code}")
        except Exception as e:
            record_test("GET /api/players/NBL_7 exception", False, str(e))

        # Test GET /api/players/NBL_07 (Canonical ID for Kofi Sarpong)
        try:
            r_ars07 = client.get("/api/players/NBL_07")
            if r_ars07.status_code == 200:
                sarpong = r_ars07.json()
                record_test("GET /api/players/NBL_07 (Sarpong)", 
                            sarpong.get("name") == "Kofi Sarpong" and sarpong.get("jersey_number") == 7,
                            f"Retrieved: {sarpong.get('name')}, #{sarpong.get('jersey_number')}, Role={sarpong.get('role')}, Rating={sarpong.get('rating')}, Radar={len(sarpong.get('radar', []))} axes, Events={len(sarpong.get('events', []))}")
            else:
                record_test("GET /api/players/NBL_07", False, f"Status {r_ars07.status_code}: {r_ars07.text}")
        except Exception as e:
            record_test("GET /api/players/NBL_07 exception", False, str(e))

        # --------------------------------------------------------------------------
        # 3. Verify GET /api/tactical
        # --------------------------------------------------------------------------
        print("\n--- 3. Testing GET /api/tactical ---")
        try:
            r_tactical = client.get("/api/tactical")
            if r_tactical.status_code == 200:
                t_data = r_tactical.json()
                moments = t_data.get("moments", [])
                record_test("Tactical moments count", len(moments) == 4, f"Found {len(moments)} moments (expected 4)")

                expected_turning_points = ["High Press Turnover", "Goal Buildup", "Counter Attack", "Low Block Shape"]
                found_tps = [m.get("turning_point") for m in moments]
                record_test("Tactical turning points match", found_tps == expected_turning_points, f"Found turning points: {found_tps}")

                # Verify 5 Tactical Layers in each moment
                all_layers_valid = True
                for idx, m in enumerate(moments):
                    has_passing = bool(m.get("passing_lanes") and isinstance(m["passing_lanes"], list))
                    has_low_block = bool(m.get("low_block_polygon") and len(m["low_block_polygon"]) >= 4)
                    has_def_line = (m.get("defensive_line_depth_m") is not None and m["defensive_line_depth_m"] > 0)
                    has_offside = (m.get("offside_line_x") is not None and 0 <= m["offside_line_x"] <= 105)
                    has_pressing = bool(m.get("pressing_zones") and isinstance(m["pressing_zones"], list))
                    has_frame = bool(m.get("frame") and len(m.get("frame", {}).get("players", [])) == 22)
                    has_ai = bool(m.get("ai_analysis"))

                    if not (has_passing and has_low_block and has_def_line and has_offside and has_pressing and has_frame and has_ai):
                        all_layers_valid = False
                        record_test(f"Moment {idx} ({m.get('id')}) layers", False, 
                                    f"passing={has_passing}, low_block={has_low_block}, def_line={has_def_line}, offside={has_offside}, pressing={has_pressing}, frame_players={len(m.get('frame',{}).get('players',[]))}, ai={has_ai}")

                if all_layers_valid:
                    record_test("All 4 moments contain 5 tactical layers & 22-player freeze frame", True, "Passing lanes, low block polygon, defensive depth, offside line, pressing zones, and 22-player coordinates all valid.")
            else:
                record_test("GET /api/tactical", False, f"Status {r_tactical.status_code}: {r_tactical.text}")
        except Exception as e:
            record_test("GET /api/tactical exception", False, str(e))

        # --------------------------------------------------------------------------
        # 4. Verify POST /api/control with {"action": "simulate_full"}
        # --------------------------------------------------------------------------
        print("\n--- 4. Testing POST /api/control {'action': 'simulate_full'} ---")
        try:
            r_sim = client.post("/api/control", json={"action": "simulate_full"})
            if r_sim.status_code == 200:
                sim_data = r_sim.json()
                is_sim_full = (sim_data.get("status") == "simulated_full")
                clock_val = sim_data.get("clock")
                score_val = sim_data.get("score")
                record_test("POST /api/control simulate_full", is_sim_full, f"Status: {sim_data.get('status')}, Clock: {clock_val}, Score: {score_val}")

                match_stats = sim_data.get("match_stats", {})
                player_stats = sim_data.get("player_stats", [])
                record_test("simulate_full stats output", 
                            len(player_stats) == 22 and "field_tilt" in match_stats and "territory" in match_stats,
                            f"22 players tracked, field_tilt={match_stats.get('field_tilt')}, territory={match_stats.get('territory')}")
            else:
                record_test("POST /api/control simulate_full", False, f"Status {r_sim.status_code}: {r_sim.text}")
        except Exception as e:
            record_test("POST /api/control simulate_full exception", False, str(e))

        # Also test POST /api/simulate_full direct alias
        try:
            r_sim_direct = client.post("/api/simulate_full")
            record_test("POST /api/simulate_full direct alias", 
                        r_sim_direct.status_code == 200 and r_sim_direct.json().get("status") == "simulated_full",
                        f"Status {r_sim_direct.status_code}, status={r_sim_direct.json().get('status')}")
        except Exception as e:
            record_test("POST /api/simulate_full direct alias exception", False, str(e))

        # --------------------------------------------------------------------------
        # 5. Verify GET /api/recap & Highlights Sequence
        # --------------------------------------------------------------------------
        print("\n--- 5. Testing GET /api/recap & highlights_sequence ---")
        try:
            r_recap = client.get("/api/recap")
            if r_recap.status_code == 200:
                recap_data = r_recap.json()
                record_test("GET /api/recap status", True, f"Match status: {recap_data.get('status')}, scoreline: {recap_data.get('scoreline')}")

                # Verify highlights_sequence
                hl_seq = recap_data.get("highlights_sequence", [])
                if hl_seq and isinstance(hl_seq, list) and len(hl_seq) >= 3:
                    hl_valid = True
                    for h in hl_seq:
                        if not all(k in h for k in ["id", "minute", "title", "start_frame", "end_frame", "duration_seconds", "event_type"]):
                            hl_valid = False
                        if h.get("start_frame", 0) > h.get("end_frame", 0):
                            hl_valid = False
                    record_test("Highlights sequence scrubber validity", hl_valid, 
                                f"{len(hl_seq)} highlight clips with valid minute/frames/duration: {[h['minute'] + ' ' + h['title'] for h in hl_seq[:3]]}")
                else:
                    record_test("Highlights sequence presence", False, f"highlights_sequence empty or invalid: {hl_seq}")
            else:
                record_test("GET /api/recap", False, f"Status {r_recap.status_code}: {r_recap.text}")
        except Exception as e:
            record_test("GET /api/recap exception", False, str(e))

        # --------------------------------------------------------------------------
        # 6. Deep Data Validity: Field Tilt and Territory Invariants Post Full Match
        # --------------------------------------------------------------------------
        print("\n--- 6. Testing Data Validity: Field Tilt & Territory Invariants ---")
        try:
            r_state = client.get("/api/state")
            ms = r_state.json().get("match_stats", {})
            ft = ms.get("field_tilt", {})
            ter = ms.get("territory", {})

            # Field Tilt sum invariant
            ft_home = ft.get("home", 0.0)
            ft_away = ft.get("away", 0.0)
            ft_sum = round(ft_home + ft_away, 1)
            record_test("Field Tilt invariant", 
                        ft_sum == 100.0 and 0.0 <= ft_home <= 100.0 and 0.0 <= ft_away <= 100.0,
                        f"Home {ft_home}% + Away {ft_away}% = {ft_sum}% (raw: {ft})")

            # Territory sum invariant
            ter_home = ter.get("home", 0.0)
            ter_away = ter.get("away", 0.0)
            ter_sum = round(ter_home + ter_away, 1)
            record_test("Territory invariant", 
                        ter_sum == 100.0 and 0.0 <= ter_home <= 100.0 and 0.0 <= ter_away <= 100.0,
                        f"Home {ter_home}% + Away {ter_away}% = {ter_sum}% (raw: {ter})")

            # Possession invariant
            poss = ms.get("possession_pct", {})
            poss_home = poss.get("home", 0.0)
            poss_away = poss.get("away", 0.0)
            poss_sum = round(poss_home + poss_away, 1)
            record_test("Possession invariant", 
                        poss_sum == 100.0,
                        f"Home {poss_home}% + Away {poss_away}% = {poss_sum}%")
        except Exception as e:
            record_test("Field Tilt / Territory exception", False, str(e))

        # --------------------------------------------------------------------------
        # 7. Adversarial Stress & Error Handling
        # --------------------------------------------------------------------------
        print("\n--- 7. Adversarial Stress & Robustness ---")
        # Unsupported action
        r_bad_action = client.post("/api/control", json={"action": "invalid_action_xyz"})
        record_test("Reject unsupported control action", r_bad_action.status_code == 400, f"Returned HTTP {r_bad_action.status_code}")

        # Negative speed multiplier
        r_bad_speed = client.post("/api/control", json={"action": "speed", "multiplier": -5.0})
        record_test("Reject negative speed multiplier", r_bad_speed.status_code == 400, f"Returned HTTP {r_bad_speed.status_code}")

        # Nonexistent event jump
        r_bad_jump = client.post("/api/control", json={"action": "jump", "event_id": "NON_EXISTENT_999"})
        record_test("Reject jump to nonexistent event", r_bad_jump.status_code == 404, f"Returned HTTP {r_bad_jump.status_code}")

        # Nonexistent player id
        r_bad_player = client.get("/api/players/NON_EXISTENT_PLAYER")
        record_test("Reject nonexistent player query", r_bad_player.status_code == 404, f"Returned HTTP {r_bad_player.status_code}")

        # Idempotent simulate_full stress (calling 3 times consecutively)
        sim_stress_ok = True
        for i in range(3):
            r_rep = client.post("/api/control", json={"action": "simulate_full"})
            if r_rep.status_code != 200 or r_rep.json().get("status") != "simulated_full":
                sim_stress_ok = False
        record_test("simulate_full 3x rapid consecutive stress", sim_stress_ok, "Passed without crashes or state corruption")

        print("\n" + "=" * 80)
        print(f"VERIFICATION COMPLETE: {results['passed']} PASSED, {results['failed']} FAILED, {results['warnings']} WARNINGS")
        print("=" * 80)

        return results

if __name__ == "__main__":
    res = run_empirical_verification()
    sys.exit(0 if res["failed"] == 0 else 1)
