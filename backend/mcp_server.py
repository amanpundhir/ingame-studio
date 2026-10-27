"""InGame Studio - Azure Model Context Protocol (MCP) Server.

Exposes InGame Studio tactical telemetry, physical kinematics, causal reasoning,
and post-match analytics tools to AI agents, Microsoft Copilot Studio, and Azure AI Foundry
via standard Model Context Protocol (JSON-RPC 2.0) over stdio and programmatic Python APIs.

Exposed Tools (7):
1. get_live_telemetry: Ingests/retrieves 25Hz spatial tracking frames for 22 players and ball.
2. calculate_pass_difficulty: Computes Pass Difficulty Rating (PDR in [0, 100]).
3. calculate_chaos_control_index: Evaluates match rhythm volatility (CCI in [0, 100]).
4. get_player_metrics: Retrieves real-time cumulative physical & tactical stats for a player.
5. get_match_analytics_overview: Returns team-level possession, xG, shots, passes, and tackles.
6. get_match_recap: Synthesizes automated full-match post-game studio report.
7. verify_narrative_grounding: Audits draft causal narratives against telemetry FactPack within 1% tolerance.
"""

import json
import logging
import os
import sys
from typing import Any, Callable, Dict, List, Optional, Union

from backend.math_engine import TacticalMathEngine, MatchAnalyticsTracker
from backend.agents.models import FactPack, DraftNarrative
from backend.agents.verifier_agent import VerifierAgent
from backend.match_recap import generate_match_recap
from generator.match_generator import MatchGenerator

logger = logging.getLogger("ingame.mcp")


class InGameMCPServer:
    """InGame Studio Model Context Protocol (MCP) Server.

    Implements JSON-RPC 2.0 protocol specifications for AI tool execution.
    """

    PROTOCOL_VERSION = "2024-11-05"
    SERVER_NAME = "ingame-azure-mcp-server"
    SERVER_VERSION = "1.0.0"

    def __init__(self, live_source: Optional[Callable[[], Dict[str, Any]]] = None):
        """``live_source`` returns ``{"tracker", "events", "clock", "status"}`` for the match that is
        being played right now. With it the analytics tools describe the match as it stands at
        the current clock; without it the server pre-loads the whole bundled match."""
        self.live_source = live_source
        self.generator = MatchGenerator()
        self.analytics_tracker = MatchAnalyticsTracker()
        self.verifier = VerifierAgent(tolerance_pct=0.01)
        if live_source is not None:
            return

        # Pre-seed tracker with synthetic events for rich metrics
        events_path = os.path.join(os.path.dirname(__file__), "..", "data", "synthetic_events.json")
        if os.path.exists(events_path):
            try:
                with open(events_path, "r", encoding="utf-8") as f:
                    events = json.load(f)
                    self.analytics_tracker.simulate_full(events)
            except Exception as e:
                logger.warning(f"Could not pre-simulate events in MCP server: {e}")

    def list_tools(self) -> List[Dict[str, Any]]:
        """Returns metadata and JSON Schema definitions for all 7 registered MCP tools."""
        return [
            {
                "name": "get_live_telemetry",
                "description": "Retrieves 25Hz spatial coordinate tracking for all 22 players and the ball on a 105m x 68m pitch.",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "frame_index": {
                            "type": "integer",
                            "description": "Optional zero-based frame index to retrieve.",
                        }
                    },
                },
            },
            {
                "name": "calculate_pass_difficulty",
                "description": "Calculates Pass Difficulty Rating (PDR in [0.0, 100.0]) based on distance, intercept angle cones, corridor density, and ball speed.",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "distance_m": {
                            "type": "number",
                            "description": "Pass distance in meters (0 to 105m).",
                        },
                        "defenders_in_cone": {
                            "type": "integer",
                            "description": "Defenders located within +-20 degree angular intercept cone.",
                            "default": 0,
                        },
                        "defenders_in_corridor": {
                            "type": "integer",
                            "description": "Defenders within 4m of direct passing lane corridor.",
                            "default": 0,
                        },
                        "ball_speed_kmh": {
                            "type": "number",
                            "description": "Ball travel speed in km/h.",
                            "default": 0.0,
                        },
                    },
                    "required": ["distance_m"],
                },
            },
            {
                "name": "calculate_chaos_control_index",
                "description": "Calculates Chaos vs. Control Rhythm Index (CCI in [0.0, 100.0]) measuring match tempo volatility, turnover rate, and line displacement.",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "recent_turnovers": {
                            "type": "integer",
                            "description": "Number of possession turnovers in rolling window.",
                            "default": 0,
                        },
                        "ball_speed_variance": {
                            "type": "number",
                            "description": "Variance of instantaneous ball velocity.",
                            "default": 0.0,
                        },
                        "defensive_line_displacement_m": {
                            "type": "number",
                            "description": "Longitudinal displacement range of defensive line in meters.",
                            "default": 0.0,
                        },
                    },
                },
            },
            {
                "name": "get_player_metrics",
                "description": "Retrieves real-time physical, tactical, and broadcast performance statistics for an authentic player (e.g. NBL_07, HSC_09).",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "player_id": {
                            "type": "string",
                            "description": "Unique player ID (e.g. 'NBL_07' for Sarpong, 'HSC_09' for Hagen).",
                        }
                    },
                    "required": ["player_id"],
                },
            },
            {
                "name": "get_match_analytics_overview",
                "description": "Returns current match statistics overview including score, possession percentage, xG, shots, passes, and tackles.",
                "inputSchema": {
                    "type": "object",
                    "properties": {},
                },
            },
            {
                "name": "get_match_recap",
                "description": "Generates a full-match post-game studio report including editorial story, xG balance, turning points, Man of the Match, entropy shifts, and English and Spanish summaries.",
                "inputSchema": {
                    "type": "object",
                    "properties": {},
                },
            },
            {
                "name": "verify_narrative_grounding",
                "description": "Audits a broadcast causal narrative against telemetry facts within 1% relative error tolerance to eliminate AI hallucinations.",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "fact_pack": {
                            "type": "object",
                            "description": "Authoritative FactPack dictionary with telemetry facts.",
                        },
                        "draft_narrative": {
                            "type": "string",
                            "description": "The broadcast narrative text to audit.",
                        },
                    },
                    "required": ["fact_pack", "draft_narrative"],
                },
            },
        ]

    # --------------------------------------------------------------------------
    # Tool Implementations
    # --------------------------------------------------------------------------

    def get_live_telemetry(self, frame_index: Optional[int] = None) -> Dict[str, Any]:
        """Retrieves a 25Hz tracking telemetry frame."""
        if frame_index is not None and frame_index > 0:
            for _ in range(min(frame_index, 50)):
                self.generator.step()
        frame = self.generator.step()
        return frame

    def calculate_pass_difficulty(
        self,
        distance_m: float,
        defenders_in_cone: int = 0,
        defenders_in_corridor: int = 0,
        ball_speed_kmh: float = 0.0,
    ) -> Dict[str, Any]:
        """Calculates Pass Difficulty Rating (PDR) bounded in [0.0, 100.0]."""
        pdr = TacticalMathEngine.calculate_pass_difficulty(
            distance_m=float(distance_m),
            defenders_in_cone=int(defenders_in_cone),
            defenders_radius_4m=int(defenders_in_corridor),
            ball_speed_kmh=float(ball_speed_kmh),
        )
        return {
            "pass_difficulty_rating": pdr,
            "distance_m": round(float(distance_m), 1),
            "defenders_in_cone": int(defenders_in_cone),
            "defenders_in_corridor": int(defenders_in_corridor),
            "ball_speed_kmh": round(float(ball_speed_kmh), 1),
            "unit": "percent",
        }

    def calculate_chaos_control_index(
        self,
        recent_turnovers: int = 0,
        ball_speed_variance: float = 0.0,
        defensive_line_displacement_m: float = 0.0,
    ) -> Dict[str, Any]:
        """Calculates Chaos vs. Control Rhythm Index (CCI) bounded in [0.0, 100.0]."""
        cci = TacticalMathEngine.calculate_chaos_index(
            recent_turnovers_count=int(recent_turnovers),
            ball_speed_variance=float(ball_speed_variance),
            defensive_line_displacement_m=float(defensive_line_displacement_m),
        )
        if cci < 35.0:
            zone = "High Control"
        elif cci <= 65.0:
            zone = "Balanced Contest"
        else:
            zone = "Chaos / High Transition"

        return {
            "chaos_control_index": cci,
            "tactical_zone": zone,
            "recent_turnovers": int(recent_turnovers),
            "ball_speed_variance": round(float(ball_speed_variance), 2),
            "defensive_line_displacement_m": round(float(defensive_line_displacement_m), 2),
        }

    def get_player_metrics(self, player_id: str) -> Dict[str, Any]:
        """Retrieves individual player metrics."""
        if not player_id or not isinstance(player_id, str):
            raise ValueError("player_id must be a non-empty string.")

        pid_upper = player_id.upper().strip()
        tracker = self._live().get("tracker") or self.analytics_tracker
        player = tracker.players.get(pid_upper)
        if not player:
            # Fallback search by surname or jersey
            for p in list(tracker.players.values()):
                if pid_upper in p.name.upper() or pid_upper == str(p.jersey_number):
                    player = p
                    break

        if not player:
            valid_ids = list(tracker.players.keys())
            raise ValueError(f"Player '{player_id}' not found. Valid IDs: {valid_ids[:6]}...")

        data = player.to_dict()
        live = self._live()
        if live:
            data["as_of_clock"] = live.get("clock")
        return data

    def _live(self) -> Dict[str, Any]:
        """The live match (tracker, events so far, clock, status), or {} when the bundled match is used."""
        return dict(self.live_source()) if self.live_source is not None else {}

    def get_match_analytics_overview(self) -> Dict[str, Any]:
        """Returns team-level match statistics (as the match stands at the current clock when live)."""
        live = self._live()
        tracker = live.get("tracker") or self.analytics_tracker
        stats = dict(tracker.get_match_stats())
        if "possession_pct" in stats and "possession" not in stats:
            stats["possession"] = stats["possession_pct"]
        if live:
            stats["match_clock"] = live.get("clock")
            stats["match_status"] = live.get("status")
        return stats

    def get_match_recap(self) -> Dict[str, Any]:
        """Match report: everything up to the current clock when live, the whole match otherwise."""
        live = self._live()
        if live:
            recap = generate_match_recap(live.get("tracker"), events=live.get("events") or [], clock=live.get("clock"))
            recap["match_status"] = live.get("status")
            return recap
        return generate_match_recap(self.analytics_tracker)

    def verify_narrative_grounding(
        self,
        fact_pack: Union[Dict[str, Any], FactPack],
        draft_narrative: str,
    ) -> Dict[str, Any]:
        """Verifies narrative against FactPack."""
        if isinstance(fact_pack, dict):
            # Parse into FactPack model if needed
            fp = FactPack(**fact_pack)
        else:
            fp = fact_pack

        res = self.verifier.verify(fp, draft_narrative)
        return {
            "is_valid": res.is_valid,
            "grounding_score": res.grounding_score,
            "critique": res.critique,
            "discrepancies": res.discrepancies,
            "checked_citations": res.checked_citations,
        }

    # --------------------------------------------------------------------------
    # Tool Dispatcher
    # --------------------------------------------------------------------------

    def call_tool(self, name: str, arguments: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Dispatches and executes an MCP tool by name."""
        args = arguments or {}

        if name == "get_live_telemetry":
            return self.get_live_telemetry(frame_index=args.get("frame_index"))

        elif name == "calculate_pass_difficulty":
            if "distance_m" not in args:
                raise ValueError("calculate_pass_difficulty requires 'distance_m'.")
            return self.calculate_pass_difficulty(
                distance_m=float(args["distance_m"]),
                defenders_in_cone=int(args.get("defenders_in_cone", 0)),
                defenders_in_corridor=int(args.get("defenders_in_corridor", 0)),
                ball_speed_kmh=float(args.get("ball_speed_kmh", 0.0)),
            )

        elif name == "calculate_chaos_control_index":
            return self.calculate_chaos_control_index(
                recent_turnovers=int(args.get("recent_turnovers", 0)),
                ball_speed_variance=float(args.get("ball_speed_variance", 0.0)),
                defensive_line_displacement_m=float(args.get("defensive_line_displacement_m", 0.0)),
            )

        elif name == "get_player_metrics":
            if "player_id" not in args:
                raise ValueError("get_player_metrics requires 'player_id'.")
            return self.get_player_metrics(player_id=args["player_id"])

        elif name == "get_match_analytics_overview":
            return self.get_match_analytics_overview()

        elif name == "get_match_recap":
            return self.get_match_recap()

        elif name == "verify_narrative_grounding":
            if "fact_pack" not in args or "draft_narrative" not in args:
                raise ValueError("verify_narrative_grounding requires 'fact_pack' and 'draft_narrative'.")
            return self.verify_narrative_grounding(
                fact_pack=args["fact_pack"],
                draft_narrative=str(args["draft_narrative"]),
            )

        else:
            raise KeyError(f"Tool '{name}' not found.")

    # --------------------------------------------------------------------------
    # JSON-RPC 2.0 Request Handling
    # --------------------------------------------------------------------------

    def handle_request(self, req: Dict[str, Any]) -> Dict[str, Any]:
        """Processes a single JSON-RPC 2.0 request and produces conforming response."""
        if not isinstance(req, dict):
            return {
                "jsonrpc": "2.0",
                "id": None,
                "error": {"code": -32600, "message": "Invalid Request: Body must be a JSON object."},
            }

        req_id = req.get("id")
        method = req.get("method")
        params = req.get("params", {})

        if req.get("jsonrpc") != "2.0" or not method or not isinstance(method, str):
            return {
                "jsonrpc": "2.0",
                "id": req_id,
                "error": {"code": -32600, "message": "Invalid Request: Missing 'jsonrpc: 2.0' or 'method'."},
            }

        # Protocol Handshakes
        if method == "initialize":
            return {
                "jsonrpc": "2.0",
                "id": req_id,
                "result": {
                    "protocolVersion": self.PROTOCOL_VERSION,
                    "capabilities": {"tools": {}},
                    "serverInfo": {
                        "name": self.SERVER_NAME,
                        "version": self.SERVER_VERSION,
                    },
                },
            }

        elif method in ("notifications/initialized", "initialized"):
            return {"jsonrpc": "2.0", "id": req_id, "result": {}}

        elif method == "ping":
            return {"jsonrpc": "2.0", "id": req_id, "result": {}}

        # Tools Operations
        elif method == "tools/list":
            return {
                "jsonrpc": "2.0",
                "id": req_id,
                "result": {"tools": self.list_tools()},
            }

        elif method == "tools/call":
            tool_name = params.get("name")
            tool_args = params.get("arguments", {})

            if not tool_name:
                return {
                    "jsonrpc": "2.0",
                    "id": req_id,
                    "error": {"code": -32602, "message": "Missing 'name' in tools/call parameters."},
                }

            try:
                output = self.call_tool(tool_name, tool_args)
                return {
                    "jsonrpc": "2.0",
                    "id": req_id,
                    "result": {
                        "content": [
                            {
                                "type": "text",
                                "text": json.dumps(output, indent=2),
                            }
                        ],
                        "structured": output,
                        "isError": False,
                    },
                }
            except KeyError as e:
                return {
                    "jsonrpc": "2.0",
                    "id": req_id,
                    "error": {"code": -32601, "message": str(e)},
                }
            except ValueError as e:
                return {
                    "jsonrpc": "2.0",
                    "id": req_id,
                    "error": {"code": -32602, "message": f"Invalid params: {e}"},
                }
            except Exception as e:
                logger.exception("Error executing tool")
                return {
                    "jsonrpc": "2.0",
                    "id": req_id,
                    "error": {"code": -32603, "message": f"Internal error: {e}"},
                }

        else:
            return {
                "jsonrpc": "2.0",
                "id": req_id,
                "error": {"code": -32601, "message": f"Method '{method}' not found."},
            }

    def run_stdio(self) -> None:
        """Executes persistent JSON-RPC 2.0 loop reading from stdin and writing to stdout."""
        logger.info(f"{self.SERVER_NAME} v{self.SERVER_VERSION} started on stdio.")
        for line in sys.stdin:
            line_str = line.strip()
            if not line_str:
                continue
            try:
                req = json.loads(line_str)
                resp = self.handle_request(req)
            except json.JSONDecodeError as e:
                resp = {
                    "jsonrpc": "2.0",
                    "id": None,
                    "error": {"code": -32700, "message": f"Parse error: {e}"},
                }
            sys.stdout.write(json.dumps(resp) + "\n")
            sys.stdout.flush()


# Module-level server singleton
server = InGameMCPServer()

if __name__ == "__main__":
    server.run_stdio()
